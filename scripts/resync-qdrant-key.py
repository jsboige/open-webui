#!/usr/bin/env python3
"""Resync the fleet-wide QDRANT_API_KEY after a Qdrant server-side key rotation.

Context (found 2026-07-10, wakeup BH): the Qdrant server rotated its API key in
the window 07-05 -> 07-09. Neither po-2026 (roo-state-manager embeddings) nor the
7 OWUI tenants were resynced, so every tenant's held key now returns
401 "Invalid API key or JWT" against qdrant.myia.io. Qdrant itself is UP
(healthz 200) — only auth fails. Effect on OWUI: RAG is broken fleet-wide (the
13 shared KBs / ~362K vectors are unreachable) the moment any KB-grounded query
runs. It was latent because RAG only touches Qdrant on an actual query.

QDRANT_API_KEY is a docker ENV var, injected by each docker-compose-<tenant>.yaml
via `QDRANT_API_KEY=${QDRANT_API_KEY}` and interpolated from the per-tenant
`<tenant>.env` (and the repo-root `.env`). All 8 files currently hold the SAME
value. So the fix is: rewrite that one line in the 8 env files, recreate the 7
containers, verify auth returns 200.

GOTCHA (found 2026-07-11): docker compose gives an inherited shell / Windows-
registry `QDRANT_API_KEY` PRECEDENCE over `--env-file` when interpolating
`${QDRANT_API_KEY}`. On ai-01 a stale User-scoped `QDRANT_API_KEY` was silently
shadowing the env files, so rewriting them had NO effect and a plain `up -d` left
the container on the old key. This script therefore (a) passes the new key
explicitly in the recreate subprocess env, (b) `--force-recreate`s the open-webui
service, and (c) on Windows makes the durable var right via `setx` (User scope).

SECRETS: the new key is read ONLY from the env var QDRANT_API_KEY_NEW (never a
positional arg — those leak into shell history — and never via RooSync: a Qdrant
key's SOURCE is the infra/master.env side, so distributing it over RooSync is a
bypass; jsboige sets it out-of-band with `setx QDRANT_API_KEY_NEW ...`). Output
is a masked JSON audit: token LENGTH + short non-reversible sha256 prefix ONLY,
never any character of the key. Safe for a public repo.

Usage:
  # 1. jsboige sets the rotated key out-of-band (User scope), reopens the shell:
  setx QDRANT_API_KEY_NEW "<new-qdrant-key>"
  # 2. plan only (no writes, no restarts) — always run this first:
  python scripts/resync-qdrant-key.py
  # 3. write the 8 env files:
  python scripts/resync-qdrant-key.py --apply
  # 4. write + recreate the 7 containers + verify auth == 200:
  python scripts/resync-qdrant-key.py --recreate --verify

Exit codes: 0 = plan/apply/verify all clean; 1 = one or more steps failed;
2 = QDRANT_API_KEY_NEW unset/too short (nothing done).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

KEY = "QDRANT_API_KEY"
NEW_KEY_ENV = "QDRANT_API_KEY_NEW"
REPO = Path(__file__).resolve().parent.parent

# (tenant id, env file, compose file, compose project). Container name is
# "<project>-open-webui-1" (e.g. myia-open-webui-open-webui-1).
TENANTS = [
    ("myia",      "myia.env",      "docker-compose-myia.yaml",      "myia-open-webui"),
    ("epf",       "epf.env",       "docker-compose-epf.yaml",       "epf-open-webui"),
    ("esg",       "esg.env",       "docker-compose-esg.yaml",       "esg-open-webui"),
    ("ece",       "ece.env",       "docker-compose-ece.yaml",       "ece-open-webui"),
    ("epf-genai", "epf-genai.env", "docker-compose-epf-genai.yaml", "epf-genai-open-webui"),
    ("epita",     "epita.env",     "docker-compose-epita.yaml",     "epita-open-webui"),
    ("pauwels",   "pauwels.env",   "docker-compose-pauwels.yaml",   "pauwels-open-webui"),
]
# The repo-root .env holds the same shared value; keep it in sync too.
EXTRA_ENV_FILES = [".env"]

QDRANT_HEALTH_URL = "https://qdrant.myia.io/healthz"
QDRANT_AUTH_URL = "https://qdrant.myia.io/collections"


def mask(s: str | None) -> str | None:
    """Secret-safe fingerprint: LENGTH + short non-reversible sha256 prefix ONLY
    (machine rule secret-mask-hygiene). Never any character of the key."""
    if not s or not isinstance(s, str):
        return None
    return f"len={len(s)} sha256:{hashlib.sha256(s.encode()).hexdigest()[:8]}"


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def read_key(env_path: Path) -> tuple[str | None, int]:
    """Return (current value of QDRANT_API_KEY, line index) or (None, -1)."""
    if not env_path.exists():
        return None, -1
    lines = env_path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{KEY}="):
            return line[len(KEY) + 1:].strip().strip("'\""), i
    return None, -1


def rewrite_key(env_path: Path, new_val: str, apply: bool) -> dict:
    """Replace exactly the QDRANT_API_KEY= line, preserving everything else and
    per-line endings. Atomic write, UTF-8 no-BOM. Validates the result before
    committing it (line count unchanged, exactly one KEY line, new value present)."""
    raw = env_path.read_text(encoding="utf-8")
    # keepends preserves each line's own CRLF/LF so we don't rewrite endings.
    lines = raw.splitlines(keepends=True)
    matches = [i for i, l in enumerate(lines) if l.startswith(f"{KEY}=")]
    if len(matches) != 1:
        return {"ok": False, "reason": f"expected 1 {KEY} line, found {len(matches)}"}
    i = matches[0]
    original = lines[i]
    # Preserve the original line ending.
    ending = ""
    for suffix in ("\r\n", "\n", "\r"):
        if original.endswith(suffix):
            ending = suffix
            break
    old_val = original[len(KEY) + 1:].rstrip("\r\n").strip().strip("'\"")
    if old_val == new_val:
        return {"ok": True, "changed": False, "note": "already in sync",
                "old": mask(old_val), "new": mask(new_val)}
    new_lines = list(lines)
    new_lines[i] = f"{KEY}={new_val}{ending}"
    new_content = "".join(new_lines)
    # Post-image validation before we touch disk.
    check = new_content.splitlines()
    n_key = sum(1 for l in check if l.startswith(f"{KEY}="))
    if len(check) != len(raw.splitlines()) or n_key != 1 \
            or f"{KEY}={new_val}" not in check:
        return {"ok": False, "reason": "post-image validation failed (aborted, no write)"}
    if apply:
        # Atomic replace: temp in same dir -> os.replace. UTF-8, no BOM.
        fd, tmp = tempfile.mkstemp(dir=str(env_path.parent), prefix=".qresync-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(new_content)
            os.replace(tmp, env_path)
        except Exception as e:  # noqa: BLE001
            if os.path.exists(tmp):
                os.remove(tmp)
            return {"ok": False, "reason": f"write failed: {e}"}
    return {"ok": True, "changed": True, "applied": apply,
            "old": mask(old_val), "new": mask(new_val)}


def sync_shell_var(new_val: str, apply: bool) -> dict:
    """docker compose gives an inherited shell / Windows-registry QDRANT_API_KEY
    PRECEDENCE over --env-file for `${VAR}` interpolation. If such a var is set and
    stale, rewriting the env files has NO effect. Detect it, and on Windows make it
    durable via `setx` (User scope) so future `docker compose up` runs interpolate
    the correct key. Never prints the value (masked fingerprints only)."""
    inherited = os.environ.get(KEY)
    shadowing = bool(inherited) and inherited != new_val
    rec = {"inherited": mask(inherited), "shadowing": shadowing, "ok": True}
    if not shadowing:
        rec["action"] = "none (no stale shadow)"
        return rec
    if not apply:
        rec["action"] = "plan: would update durable QDRANT_API_KEY (setx User / export)"
        return rec
    # Fix this process so the recreate step interpolates correctly regardless.
    os.environ[KEY] = new_val
    if os.name == "nt":
        # setx persists to the User registry; the value is a subprocess arg
        # (host-local, like a manual setx), never echoed to stdout.
        cp = _run(["setx", KEY, new_val], timeout=30)
        rec["ok"] = cp.returncode == 0
        rec["rc"] = cp.returncode
        rec["action"] = "setx User QDRANT_API_KEY (durable)"
    else:
        # The recreate env override fixes THIS run; durability needs a manual export.
        rec["durable"] = False
        rec["action"] = f"WARN: export {KEY} in the shell/service env for durability"
    return rec


def recreate(compose_file: str, env_file: str, project: str, new_val: str) -> dict:
    # Pass QDRANT_API_KEY explicitly in the subprocess env: compose gives an
    # inherited shell/registry var precedence over --env-file, so a stale value
    # would otherwise shadow the rewritten env file. --force-recreate on just the
    # open-webui service guarantees the container is rebuilt with the new key
    # (plain `up -d` sees "no config change" and leaves it on the old one) without
    # churning the tenant's other services (bots, terminal, whisper adapter).
    env = {**os.environ, KEY: new_val}
    cmd = ["docker", "compose", "-p", project, "-f", str(REPO / compose_file),
           "--env-file", str(REPO / env_file), "up", "-d", "--force-recreate",
           "open-webui"]
    cp = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    return {"ok": cp.returncode == 0, "rc": cp.returncode,
            "err": (cp.stderr or cp.stdout or "").strip()[-300:] if cp.returncode else ""}


def verify(project: str) -> dict:
    """From inside the container, auth against Qdrant with its own (now-updated)
    key. 200 = fixed. Never prints the key."""
    container = f"{project}-open-webui-1"
    cp = _run(["docker", "exec", container, "sh", "-c",
               'curl -sk -o /dev/null -w "%{http_code}" -H "api-key: $QDRANT_API_KEY" '
               + QDRANT_AUTH_URL], timeout=60)
    code = (cp.stdout or "").strip()
    return {"container": container, "auth_http": code, "ok": code == "200"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Resync fleet QDRANT_API_KEY after a rotation.")
    ap.add_argument("--apply", action="store_true", help="Write the env files (default: plan only).")
    ap.add_argument("--recreate", action="store_true",
                    help="Implies --apply; also `docker compose up -d` each tenant.")
    ap.add_argument("--verify", action="store_true",
                    help="After recreate, assert Qdrant auth returns 200 per tenant.")
    args = ap.parse_args()
    apply = args.apply or args.recreate

    new_key = os.environ.get(NEW_KEY_ENV, "").strip()
    if not new_key:
        sys.stderr.write(f"ERROR: {NEW_KEY_ENV} env var not set. "
                         f"jsboige: setx {NEW_KEY_ENV} \"<new-key>\" (out-of-band, never via RooSync).\n")
        return 2
    if len(new_key) < 16:
        sys.stderr.write(f"ERROR: {NEW_KEY_ENV} too short (len={len(new_key)}); refusing.\n")
        return 2

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "recreate+verify" if args.recreate else ("apply" if apply else "plan"),
        "new_key_masked": mask(new_key),
        "env_files": [],
        "shell_var": {},
        "recreate": [],
        "verify": [],
    }
    ok = True

    all_env = EXTRA_ENV_FILES + [ef for _, ef, _, _ in TENANTS]
    for ef in all_env:
        p = REPO / ef
        cur, _ = read_key(p)
        rec = {"file": ef, "current": mask(cur)}
        r = rewrite_key(p, new_key, apply) if cur is not None else {"ok": False, "reason": "no key line / missing"}
        rec.update(r)
        ok = ok and r.get("ok", False)
        out["env_files"].append(rec)
        sys.stderr.write(f"[env] {ef:<16} {'OK' if r.get('ok') else 'FAIL'} "
                         f"{'changed' if r.get('changed') else r.get('note') or r.get('reason','')}\n")

    # A stale inherited QDRANT_API_KEY shadows the env files in compose interpolation.
    shell = sync_shell_var(new_key, apply)
    out["shell_var"] = shell
    ok = ok and shell.get("ok", False)
    sys.stderr.write(f"[shell] {'OK' if shell.get('ok') else 'FAIL'} {shell['action']}"
                     f"{' (stale shadow detected)' if shell.get('shadowing') else ''}\n")

    if args.recreate and ok:
        for tid, ef, cf, proj in TENANTS:
            r = recreate(cf, ef, proj, new_key)
            r["tenant"] = tid
            ok = ok and r["ok"]
            out["recreate"].append(r)
            sys.stderr.write(f"[recreate] {tid:<10} {'OK' if r['ok'] else 'FAIL rc=' + str(r['rc'])}\n")

    if args.verify and args.recreate:
        for tid, ef, cf, proj in TENANTS:
            r = verify(proj)
            r["tenant"] = tid
            ok = ok and r["ok"]
            out["verify"].append(r)
            sys.stderr.write(f"[verify] {tid:<10} auth={r['auth_http']} {'OK' if r['ok'] else 'FAIL'}\n")

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
