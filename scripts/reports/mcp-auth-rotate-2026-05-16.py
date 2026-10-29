#!/usr/bin/env python3
"""Rotate MCP_AUTH bearer token in OWUI tool_servers config across 7 tenants.

Context: an sk-agent proxy bearer token leaked on a PUBLIC repo (2026-05-16) and
was rotated fleet-wide by this one-shot. Old token: read from env var
MCP_AUTH_OLD (never hardcoded here — public repo; the leaked value is dead +
already public). New token: read from env var MCP_AUTH_NEW (never persisted/logged).

For each tenant:
  GET  /api/v1/configs/tool_servers              -> snapshot
  POST /api/v1/configs/tool_servers              -> rewrite key on entries matching old
  GET  /api/v1/configs/tool_servers              -> verify

Usage:
  MCP_AUTH_NEW='...' python scripts/reports/mcp-auth-rotate-2026-05-16.py [--dry-run] [--no-verify]
Output is JSON on stdout with secret-safe token fingerprints (length + a short
non-reversible sha256 prefix, never any characters of the token).
"""
import os, sys, json, argparse, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

TENANTS = [
    ('myia',      'MYIA'),
    ('epf',       'EPF'),
    ('epf-genai', 'EPF_GENAI'),
    ('ece',       'ECE'),
    ('esg',       'ESG'),
    ('epita',     'EPITA'),
    ('pauwels',   'PAUWELS'),
]
OLD_TOKEN = os.environ.get('MCP_AUTH_OLD', '').strip()  # never hardcoded (public repo); the dead+already-public pre-rotation token to match

def load_env(p):
    if not Path(p).exists(): return
    for line in open(p):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,_,v=line.partition('=')
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

def mask(s):
    """Secret-safe fingerprint: token LENGTH + a short non-reversible sha256
    prefix ONLY — never any character of the token (machine rule: report length
    only). Supersedes the old first8...last4 mask, which disclosed 12 chars of a
    live secret into this JSON audit output (public repo)."""
    if not s or not isinstance(s, str): return None
    return f'len={len(s)} sha256:{hashlib.sha256(s.encode()).hexdigest()[:8]}'

def api(url, tok=None, method='GET', data=None, timeout=30):
    h={'Content-Type':'application/json'}
    if tok: h['Authorization']=f'Bearer {tok}'
    req=urllib.request.Request(url, headers=h, method=method)
    if data is not None: req.data=json.dumps(data).encode()
    try:
        r=urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: b=json.loads(e.read().decode())
        except Exception: b={'detail':str(e)}
        return e.code, b

def signin(base,email,pwd):
    s,b=api(f'{base}/api/v1/auths/signin', method='POST', data={'email':email,'password':pwd})
    if s != 200: raise RuntimeError(f'auth {s}: {b}')
    return b['token']

def rotate_tenant(base, tok, new_token, dry):
    s,b = api(f'{base}/api/v1/configs/tool_servers', tok)
    if s != 200:
        return {'step':'fetch','ok':False,'status':s,'body':b}
    conns = b.get('TOOL_SERVER_CONNECTIONS') or []
    rotated = 0
    for c in conns:
        if c.get('key') == OLD_TOKEN:
            c['key'] = new_token
            rotated += 1
    if rotated == 0:
        # Idempotency: check if already on new token
        already_new = sum(1 for c in conns if c.get('key') == new_token)
        return {'step':'noop','ok':True,'count':len(conns),
                'already_new':already_new,'note':'no old token present'}
    if dry:
        return {'step':'rotate','ok':True,'dry_run':True,'rotated':rotated,
                'total_connections':len(conns)}
    s2,b2 = api(f'{base}/api/v1/configs/tool_servers', tok, method='POST', data=b)
    return {'step':'rotate','ok':(s2==200),'status':s2,'rotated':rotated,
            'total_connections':len(conns),
            'body':'OK' if s2==200 else b2}

def verify_tenant(base, tok, new_token):
    s,b = api(f'{base}/api/v1/configs/tool_servers', tok)
    if s != 200:
        return {'ok':False,'status':s}
    conns = b.get('TOOL_SERVER_CONNECTIONS') or []
    keys = [c.get('key') for c in conns]
    return {'ok':True,
            'count':len(conns),
            'on_new': sum(1 for k in keys if k == new_token),
            'on_old': sum(1 for k in keys if k == OLD_TOKEN),
            'other':  sum(1 for k in keys if k not in (new_token, OLD_TOKEN))}

def proxy_smoke_test(base, tok, new_token):
    """Optional: call MCP proxy from outside the container to confirm new token works.
       We don't go through OWUI's /openai/chat — instead, hit the same URL OWUI uses
       (but resolved as host alias) from where this script runs. Skipped if internal
       url is myia-mcp-proxy (Docker-only)."""
    # Cheaper check: GET tool_servers/verify endpoint if it exists; otherwise skip
    s,b = api(f'{base}/api/v1/configs/tool_servers/verify', tok, method='POST',
              data={'url':'http://myia-mcp-proxy:9090/sk-agent/mcp','key':new_token,
                    'auth_type':'bearer','path':'','type':'mcp'}, timeout=15)
    return {'status':s,'ok': s == 200}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-verify', action='store_true')
    args=ap.parse_args()
    tok_env = os.environ.get('MCP_AUTH_NEW','').strip()
    if not tok_env:
        sys.stderr.write('ERROR: MCP_AUTH_NEW env var not set\n'); sys.exit(2)
    if len(tok_env) < 32:
        sys.stderr.write(f'ERROR: MCP_AUTH_NEW looks too short (len={len(tok_env)})\n'); sys.exit(2)
    if not OLD_TOKEN:
        sys.stderr.write('ERROR: MCP_AUTH_OLD env var not set (the dead pre-rotation token to match)\n'); sys.exit(2)
    if tok_env == OLD_TOKEN:
        sys.stderr.write('ERROR: MCP_AUTH_NEW == OLD_TOKEN, refusing\n'); sys.exit(2)
    load_env(Path(__file__).parent.parent.parent / '.env')
    out = {'generated_at': datetime.now(timezone.utc).isoformat(),
           'dry_run': args.dry_run,
           'old_token_masked': mask(OLD_TOKEN),
           'new_token_masked': mask(tok_env),
           'tenants': []}
    for tid, prefix in TENANTS:
        base  = os.environ.get(f'{prefix}_URL','').rstrip('/')
        email = os.environ.get(f'{prefix}_EMAIL','')
        pwd   = os.environ.get(f'{prefix}_PASSWORD','')
        rec = {'tenant': tid, 'base': base}
        sys.stderr.write(f'\n[{tid}] '); sys.stderr.flush()
        try:
            stok = signin(base, email, pwd)
            sys.stderr.write('auth ')
            r = rotate_tenant(base, stok, tok_env, args.dry_run)
            sys.stderr.write(f'rotate:{r.get("step")}/{r.get("ok")} ')
            rec['rotate'] = r
            if not args.dry_run and not args.no_verify and r.get('ok'):
                v = verify_tenant(base, stok, tok_env)
                sys.stderr.write(f'verify:new={v.get("on_new")} old={v.get("on_old")}')
                rec['verify'] = v
        except Exception as e:
            sys.stderr.write(f'ERROR {e}')
            rec['error'] = str(e)
        out['tenants'].append(rec)
    sys.stderr.write('\n')
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
