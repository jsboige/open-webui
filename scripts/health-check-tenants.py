#!/usr/bin/env python3
"""
Health check across all Open WebUI tenants.

Verifies for each tenant:
  - Login works
  - Number of models exposed via /api/models
  - Connector status (enabled/disabled) via /openai/config
  - End-to-end chat completion on representative models
  - Personas with broken base_model_id (target missing from /api/models)

Usage:
  python scripts/health-check-tenants.py
  python scripts/health-check-tenants.py --tenants MYIA EPITA
  python scripts/health-check-tenants.py --skip-completions   # faster

Reads credentials from .env at repo root: {TENANT}_URL, {TENANT}_EMAIL, {TENANT}_PASSWORD.
Uses urllib (no third-party dependencies).
"""

import argparse
import json
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

DEFAULT_TENANTS = ["MYIA", "EPF", "EPF_GENAI", "ECE", "ESG", "EPITA", "PAUWELS"]
DEFAULT_PROBE_MODELS = [
    "MistralAI.mistral-medium-latest",
    "DeepSeek.deepseek-v4-flash",
    "OpenRouter.anthropic/claude-haiku-4.5",
    "Local.qwen3.6-35b-a3b",
    "OpenAI.gpt-5",
]


def load_env(env_path: Path) -> dict:
    env = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip("'\"")
    return env


def http(url, method="GET", token=None, body=None, timeout=30):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)[:200]}


def signin(base, email, password):
    code, data = http(f"{base}/api/v1/auths/signin", "POST", body={"email": email, "password": password})
    return data.get("token") if code == 200 else None


def check_tenant(name, base, email, password, probe_models, skip_completions):
    print(f"\n=== {name} ({base}) ===")
    token = signin(base, email, password)
    if not token:
        print("  LOGIN FAILED")
        return {"login": False}

    code, data = http(f"{base}/api/models", token=token)
    if code != 200:
        print(f"  /api/models -> {code}")
        return {"login": True, "models_status": code}

    models = data.get("data", [])
    model_ids = {m.get("id") for m in models}
    by_owner = defaultdict(int)
    for m in models:
        by_owner[m.get("owned_by") or "?"] += 1

    code, conf = http(f"{base}/openai/config", token=token)
    connectors = []
    if code == 200:
        urls = conf.get("OPENAI_API_BASE_URLS", [])
        configs = conf.get("OPENAI_API_CONFIGS", {})
        for i, u in enumerate(urls):
            c = configs.get(str(i), {})
            connectors.append({
                "idx": i,
                "url": u,
                "prefix": c.get("prefix_id", ""),
                "enabled": c.get("enable", True),
            })

    enabled = sum(1 for c in connectors if c["enabled"])
    print(f"  Models: {len(models)} ({', '.join(f'{k}={v}' for k, v in sorted(by_owner.items()))})")
    print(f"  Connectors: {enabled}/{len(connectors)} enabled")

    broken_personas = []
    for m in models:
        mid = m.get("id")
        if mid in model_ids and m.get("info"):
            base_id = m["info"].get("base_model_id")
            if base_id and base_id not in model_ids:
                broken_personas.append((mid, m.get("name"), base_id))
    if broken_personas:
        print(f"  BROKEN personas (base_model_id missing): {len(broken_personas)}")
        for mid, mname, bid in broken_personas:
            print(f"    {mid:35} | {mname:30} | base={bid}")
    else:
        print("  Personas: all base_model_id valid")

    completion_results = {}
    if not skip_completions:
        for model in probe_models:
            if model not in model_ids:
                completion_results[model] = "MISSING"
                print(f"  COMPLETION  {model:50} MISSING from /api/models")
                continue
            body = {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "stream": False,
            }
            code, data = http(f"{base}/api/chat/completions", "POST", token=token, body=body, timeout=45)
            if code == 200:
                try:
                    txt = data["choices"][0]["message"]["content"][:50].replace("\n", " ")
                    completion_results[model] = "OK"
                    print(f"  COMPLETION  {model:50} OK -> {txt}")
                except Exception:
                    completion_results[model] = f"BAD_RESPONSE"
                    print(f"  COMPLETION  {model:50} bad response shape")
            else:
                err = (data.get("detail") or data.get("error") or str(data))[:100]
                completion_results[model] = f"FAIL[{code}]"
                print(f"  COMPLETION  {model:50} FAIL [{code}] {err}")

    return {
        "login": True,
        "models_total": len(models),
        "by_owner": dict(by_owner),
        "connectors_enabled": enabled,
        "connectors_total": len(connectors),
        "broken_personas": broken_personas,
        "completions": completion_results,
    }


def check_pins(tenant_prefixes, expected_tag):
    """Verify each tenant's RUNNING OWUI container is on the pinned image tag.

    Catches silent drift where a container was recreated (e.g. a compose
    `up -d --force-recreate` during maintenance) and, if a floating tag like
    `cuda` slipped into the env, pulled a NEWER image than the fleet pin — so
    the fleet splits across builds with no API-visible signal. Read-only
    (docker inspect); degrades to UNKNOWN if docker is unreachable.
    """
    expected_ref = f"ghcr.io/open-webui/open-webui:{expected_tag}"
    print(f"\n=== IMAGE PIN CHECK (expect {expected_ref}) ===")
    refs = {}
    for prefix in tenant_prefixes:
        container = f"{prefix.lower().replace('_', '-')}-open-webui-open-webui-1"
        try:
            actual = subprocess.run(
                ["docker", "inspect", "--format", "{{.Config.Image}}", container],
                capture_output=True, timeout=10,
            ).stdout.decode().strip()
        except Exception as e:
            actual = ""
            refs[prefix] = f"UNKNOWN ({str(e)[:40]})"
            print(f"  {prefix:12} UNKNOWN  (docker inspect failed: {str(e)[:50]})")
            continue
        if not actual:
            refs[prefix] = "UNKNOWN (container not found)"
            print(f"  {prefix:12} UNKNOWN  (container {container} not found)")
        else:
            verdict = "MATCH" if actual == expected_ref else "DRIFT"
            refs[prefix] = actual
            mark = "OK" if verdict == "MATCH" else "!!"
            print(f"  {prefix:12} {verdict:6} {mark}  {actual}")

    unique = {r for r in refs.values() if not r.startswith("UNKNOWN")}
    if len(unique) == 1:
        print(f"  -> UNIFORM: all tenants on {next(iter(unique))}")
    elif len(unique) > 1:
        print(f"  -> DRIFT: {len(unique)} distinct images across the fleet:")
        for r in sorted(unique):
            on = [p for p, v in refs.items() if v == r]
            print(f"       {r}  <- {', '.join(on)}")
    unknown = [p for p, v in refs.items() if v.startswith("UNKNOWN")]
    if unknown:
        print(f"  -> UNKNOWN for: {', '.join(unknown)} (docker not reachable?)")
    return refs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenants", nargs="+", default=DEFAULT_TENANTS, help="Tenant names (env prefix)")
    parser.add_argument("--probe-models", nargs="+", default=DEFAULT_PROBE_MODELS, help="Models to test via chat completion")
    parser.add_argument("--skip-completions", action="store_true", help="Skip chat completion tests (faster)")
    parser.add_argument(
        "--check-pin",
        metavar="EXPECTED_TAG",
        default=None,
        help="Also verify each tenant's RUNNING container image is pinned to this tag "
        "(e.g. v0.10.2-cuda) via docker inspect. Catches silent drift after a recreate. "
        "Needs docker access to the host running the fleet.",
    )
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    args = parser.parse_args()

    env = load_env(Path(args.env_file))
    if not env:
        print(f"ERROR: cannot read {args.env_file}", file=sys.stderr)
        sys.exit(2)

    summary = {}
    for t in args.tenants:
        base = env.get(f"{t}_URL")
        email = env.get(f"{t}_EMAIL")
        password = env.get(f"{t}_PASSWORD")
        if not (base and email and password):
            print(f"\n{t}: missing credentials in {args.env_file} (need {t}_URL/_EMAIL/_PASSWORD)")
            continue
        summary[t] = check_tenant(t, base, email, password, args.probe_models, args.skip_completions)

    if args.check_pin:
        check_pins(args.tenants, args.check_pin)

    print("\n\n=== SUMMARY ===")
    for t, r in summary.items():
        if not r.get("login"):
            print(f"  {t:12} LOGIN FAILED")
            continue
        line = f"  {t:12} models={r['models_total']:3} connectors={r['connectors_enabled']}/{r['connectors_total']}"
        if r.get("broken_personas"):
            line += f" BROKEN_PERSONAS={len(r['broken_personas'])}"
        if r.get("completions"):
            ok = sum(1 for v in r["completions"].values() if v == "OK")
            line += f" completions={ok}/{len(r['completions'])}"
        print(line)


if __name__ == "__main__":
    main()
