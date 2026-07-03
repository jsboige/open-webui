#!/usr/bin/env python3
"""Resync OWUI tts.OPENAI_API_KEY with the Kokoro container API_KEY.

Context: post-v0.9.5 smoke (2026-05-16) showed HTTP 401 from Kokoro backend.
IISManagement diagnosed that the container's API_KEY had drifted from the OWUI bearer.

Reads new token from KOKORO_TOKEN env var (never persisted/logged). Output JSON
reports token LENGTH + a short non-reversible sha256 prefix ONLY (never any
characters of the token) for audit. Public repo: no secret material in output.

Smoke verification is done by the dedicated `post-v0.9.5-smoke-2026-05-16.py`
after running this script — keeping responsibilities separate.

Usage:
  KOKORO_TOKEN='...' python scripts/reports/kokoro-token-resync-2026-05-16.py [--dry-run]
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

def resync(base, tok, new_token, dry):
    s,b = api(f'{base}/api/v1/audio/config', tok)
    if s != 200:
        return {'step':'fetch','ok':False,'status':s}
    tts = b.get('tts') or {}
    old_key = tts.get('OPENAI_API_KEY') or ''
    if old_key == new_token:
        return {'step':'noop','ok':True,'note':'already in sync',
                'old_masked':mask(old_key), 'new_masked':mask(new_token)}
    tts['OPENAI_API_KEY'] = new_token
    b['tts'] = tts
    if dry:
        return {'step':'update','ok':True,'dry_run':True,
                'old_masked':mask(old_key), 'new_masked':mask(new_token)}
    s2,b2 = api(f'{base}/api/v1/audio/config/update', tok, method='POST', data=b)
    return {'step':'update','ok':(s2==200),'status':s2,
            'old_masked':mask(old_key), 'new_masked':mask(new_token),
            'body':'OK' if s2==200 else str(b2)[:200]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args=ap.parse_args()
    new_tok = os.environ.get('KOKORO_TOKEN','').strip()
    if not new_tok:
        sys.stderr.write('ERROR: KOKORO_TOKEN env var not set\n'); sys.exit(2)
    if len(new_tok) < 32:
        sys.stderr.write(f'ERROR: KOKORO_TOKEN too short (len={len(new_tok)})\n'); sys.exit(2)
    load_env(Path(__file__).parent.parent.parent / '.env')
    out = {'generated_at': datetime.now(timezone.utc).isoformat(),
           'dry_run': args.dry_run,
           'new_token_masked': mask(new_tok),
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
            r = resync(base, stok, new_tok, args.dry_run)
            sys.stderr.write(f'resync:{r.get("step")}/{r.get("ok")}')
            rec['resync'] = r
        except Exception as e:
            sys.stderr.write(f'ERROR {e}')
            rec['error'] = str(e)
        out['tenants'].append(rec)
    sys.stderr.write('\n')
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
