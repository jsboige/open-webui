#!/usr/bin/env python3
"""Preflight check for Qwen3.5 -> Qwen3.6 + zwz -> omnicoder migration.

Verifies across all 7 tenants:
- Auth works
- Local.qwen3.6-35b-a3b exposed by /openai/models (medium connector)
- Local.omnicoder-9b exposed (mini connector, needed for vision-expert)
- Current state of each wrapper that deploy_model_order.sh touches
"""
import json
import ssl
import sys
import urllib.request
from pathlib import Path

TENANTS = ["MYIA", "EPF", "EPF_GENAI", "ECE", "ESG", "EPITA", "PAUWELS"]

REQUIRED_CONNECTOR_MODELS = [
    "Local.qwen3.6-35b-a3b",
    "Local.omnicoder-9b",
]

WRAPPERS_TO_CREATE_OR_UPDATE = [
    "Local.qwen3.6-35b-a3b",
    "Local.qwen3.6-35b-a3b-fast",
    "expert-analyste",
    "redacteur-technique",
    "vision-expert",
    "Qwen_think",
    "Qwen_think-code",
    "Qwen_think-reason",
    "Qwen_instruct",
]

WRAPPERS_TO_DELETE = [
    "Local.qwen3.5-35b-a3b-fast",
    "Local.qwen3.5-35b-a3b",
]


def load_env(p):
    env = {}
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip("'\"")
    return env


def http(url, method="GET", token=None, body=None, timeout=15):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as e:
        return 0, {"error": str(e)[:200]}


def main():
    env = load_env(".env")
    report = []
    for t in TENANTS:
        url = env.get(f"{t}_URL")
        email = env.get(f"{t}_EMAIL")
        password = env.get(f"{t}_PASSWORD")
        if not url or not email or not password:
            report.append({"tenant": t, "error": "missing creds in .env"})
            continue

        # Auth
        st, body = http(
            f"{url}/api/v1/auths/signin",
            method="POST",
            body={"email": email, "password": password},
        )
        token = body.get("token") if isinstance(body, dict) else None
        if not token:
            report.append({"tenant": t, "error": f"auth failed (HTTP {st}): {body}"})
            continue

        # Connector models
        st, body = http(f"{url}/openai/models", token=token)
        conn_ids = set()
        if st == 200 and isinstance(body, dict):
            conn_ids = {m.get("id") for m in body.get("data", []) if m.get("id")}
        missing_conn = [m for m in REQUIRED_CONNECTOR_MODELS if m not in conn_ids]

        # Wrapper status
        wrapper_state = {}
        for wid in WRAPPERS_TO_CREATE_OR_UPDATE + WRAPPERS_TO_DELETE:
            st, _ = http(f"{url}/api/v1/models/model?id={wid}", token=token)
            wrapper_state[wid] = st

        report.append({
            "tenant": t,
            "url": url,
            "auth": "OK",
            "missing_connector_models": missing_conn,
            "wrappers": wrapper_state,
        })

    print(json.dumps(report, indent=2))

    # Summary
    print("\n=== SUMMARY ===", file=sys.stderr)
    blockers = 0
    for r in report:
        t = r["tenant"]
        if r.get("error"):
            print(f"[X] {t}: {r['error']}", file=sys.stderr)
            blockers += 1
            continue
        miss = r["missing_connector_models"]
        if miss:
            print(f"[X] {t}: connector models MISSING -> {miss}", file=sys.stderr)
            blockers += 1
        else:
            ws = r["wrappers"]
            existing_new = sum(1 for w in WRAPPERS_TO_CREATE_OR_UPDATE if ws.get(w) == 200)
            missing_new = sum(1 for w in WRAPPERS_TO_CREATE_OR_UPDATE if ws.get(w) != 200)
            to_delete = sum(1 for w in WRAPPERS_TO_DELETE if ws.get(w) == 200)
            print(
                f"[OK] {t}: connectors OK, wrappers to update={existing_new}, "
                f"to create={missing_new}, to delete={to_delete}",
                file=sys.stderr,
            )

    print(f"\nBlockers: {blockers}", file=sys.stderr)
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
