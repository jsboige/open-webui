"""Restore meta.terminalId on TP tutor models (v0.10.2 regression fix).

v0.10 UI only sends terminal_id when model.info.meta.terminalId is set
(Chat.svelte setDefaults -> selectedTerminalId). Tutor models lost/never had
it -> get_terminal_tools never resolves -> run_command unavailable in UI.

Usage: python fix-tutor-terminal-id.py [tenant ...]   (default: myia)
"""
import json
import sys
import urllib.request

ENV_PATH = r"d:\Open-WebUI\myia-open-webui\.env"
PORTS = {"myia": 2090, "epf": 3010, "esg": 3011, "ece": 3012,
         "epf-genai": 3013, "epita": 3014, "pauwels": 3016}
# Only the 4 terminal-enabled tutors; tp-prompt-engineering is conversational-only
TUTORS = ["tp-linux-debutant", "tp-git-workflow", "tp-python-data", "tp-data-analyst-agent"]
# All 5 tutors must be public (wildcard read grant) — they currently have 0
# grants in access_grant, which v0.10 treats as private/owner-only
ALL_TUTORS = TUTORS + ["tp-prompt-engineering"]
TERMINAL_ID = "open-terminal"
PUBLIC_GRANT = {"principal_type": "user", "principal_id": "*", "permission": "read"}


def load_env():
    env = {}
    for line in open(ENV_PATH, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'").strip('"')
    return env


def api(base, method, path, token=None, body=None):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 **({"Authorization": "Bearer " + token} if token else {})},
        method=method)
    return json.load(urllib.request.urlopen(req, timeout=60))


def fix_tenant(tenant, env):
    base = f"http://localhost:{PORTS[tenant]}"
    prefix = tenant.replace("-", "_").upper()
    creds = {"email": env[f"{prefix}_EMAIL"], "password": env[f"{prefix}_PASSWORD"]}
    token = api(base, "POST", "/api/v1/auths/signin", body=creds)["token"]

    # sanity: terminal connection id must exist on this tenant
    cfg = api(base, "GET", "/api/v1/configs/terminal_servers", token)
    tids = [c.get("id") for c in cfg.get("TERMINAL_SERVER_CONNECTIONS", [])]
    if TERMINAL_ID not in tids:
        print(f"[{tenant}] SKIP — terminal connection ids = {tids} (expected '{TERMINAL_ID}')")
        return

    for mid in ALL_TUTORS:
        try:
            m = api(base, "GET", f"/api/v1/models/model?id={mid}", token)
        except Exception as e:
            print(f"[{tenant}] {mid}: GET failed ({e})")
            continue
        meta = m.get("meta") or {}
        grants = m.get("access_grants") or []
        needs_terminal = mid in TUTORS and meta.get("terminalId") != TERMINAL_ID
        has_public = any(g.get("principal_id") == "*" and g.get("permission") == "read"
                         for g in grants)
        if not needs_terminal and has_public:
            print(f"[{tenant}] {mid}: already OK")
            continue
        if mid in TUTORS:
            meta["terminalId"] = TERMINAL_ID
        if not has_public:
            grants = grants + [PUBLIC_GRANT]
        form = {
            "id": m["id"],
            "base_model_id": m.get("base_model_id"),
            "name": m["name"],
            "meta": meta,
            "params": m.get("params") or {},
            # ModelForm rejects access_grants=None (list_type) — always a list
            "access_grants": grants,
            "is_active": m.get("is_active", True),
        }
        api(base, "POST", f"/api/v1/models/model/update?id={mid}", token, form)
        # verify
        m2 = api(base, "GET", f"/api/v1/models/model?id={mid}", token)
        t_ok = mid not in TUTORS or (m2.get("meta") or {}).get("terminalId") == TERMINAL_ID
        g_ok = any(g.get("principal_id") == "*" for g in (m2.get("access_grants") or []))
        print(f"[{tenant}] {mid}: terminalId={'OK' if t_ok else 'FAILED'} publicGrant={'OK' if g_ok else 'FAILED'}")


if __name__ == "__main__":
    tenants = sys.argv[1:] or ["myia"]
    env = load_env()
    for t in tenants:
        fix_tenant(t, env)
