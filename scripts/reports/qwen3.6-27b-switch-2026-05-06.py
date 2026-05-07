#!/usr/bin/env python3
"""Switch 9 OWUI custom models from Qwen3.6-35B-A3B (MoE) -> Qwen3.6-27B (Dense) base.

Mirrors the cutover on vLLM medium (ai-01, port 5002) where the served model name
becomes 'qwen3.6-27b'. The OWUI 'Local' connector (idx=3) prefixes upstream model
names with 'Local.', so all wrappers' base_model_id flips:
    Local.qwen3.6-35b-a3b  ->  Local.qwen3.6-27b

9 wrappers x 7 tenants = 63 update operations.

Description sweeps:
  '35B-A3B' -> '27B'
  'MoE'     -> 'Dense'   (case-insensitive only when adjacent to '35B' marker context)

Wrapper IDs and human-facing names are NOT renamed (cosmetic-only follow-up
deferred to avoid extra surface during the cutover window).

Usage:
  set KOKORO=...   (no secrets needed; uses .env tenant credentials)
  python scripts/reports/qwen3.6-27b-switch-2026-05-06.py [--dry-run]
"""
import os, sys, json, argparse, urllib.request, urllib.error
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
TARGET_IDS = [
    'Local.qwen3.6-35b-a3b',
    'Local.qwen3.6-35b-a3b-fast',
    'expert-analyste',
    'redacteur-technique',
    'Qwen_think',
    'Qwen_think-code',
    'Qwen_think-reason',
    'Qwen_instruct',
    'vision-expert',
]
OLD_BASE = 'Local.qwen3.6-35b-a3b'
NEW_BASE = 'Local.qwen3.6-27b'

def load_env(p):
    if not Path(p).exists(): return
    for line in open(p, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,_,v=line.partition('=')
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

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

def update_description(desc):
    if not desc: return desc, False
    new = desc
    new = new.replace('Qwen3.6-35B-A3B', 'Qwen3.6-27B')
    new = new.replace('Qwen3.6 35B-A3B', 'Qwen3.6 27B')
    new = new.replace('35B-A3B', '27B')
    return new, (new != desc)

def switch_one(base, tok, mid, dry):
    s, b = api(f'{base}/api/v1/models/model?id={mid}', tok)
    if s != 200 or not isinstance(b, dict) or not b.get('id'):
        return {'step':'fetch','ok':False,'status':s}
    cur_base = b.get('base_model_id')
    if cur_base != OLD_BASE:
        return {'step':'noop','ok':True,'note':f'base={cur_base}, expected {OLD_BASE}'}
    payload = {
        'id': b['id'],
        'base_model_id': NEW_BASE,
        'name': b.get('name'),
        'meta': b.get('meta', {}) or {},
        'params': b.get('params', {}) or {},
        'access_control': b.get('access_control'),
        'is_active': b.get('is_active', True),
    }
    desc = (payload['meta'] or {}).get('description', '')
    new_desc, changed = update_description(desc)
    if changed:
        payload['meta']['description'] = new_desc
    if dry:
        return {'step':'update','ok':True,'dry_run':True,
                'old_base':cur_base,'new_base':NEW_BASE,
                'desc_changed':changed}
    s, b = api(f'{base}/api/v1/models/model/update?id={mid}', tok, method='POST', data=payload)
    return {'step':'update','ok':(s==200),'status':s,
            'desc_changed':changed,
            'body': 'OK' if s==200 else b}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args=ap.parse_args()
    load_env(Path(__file__).parent.parent.parent / '.env')
    out = {'generated_at': datetime.now(timezone.utc).isoformat(),
           'dry_run': args.dry_run, 'tenants': []}
    total_ok = total_fail = total_noop = 0
    for tid, prefix in TENANTS:
        base  = os.environ.get(f'{prefix}_URL','').rstrip('/')
        email = os.environ.get(f'{prefix}_EMAIL','')
        pwd   = os.environ.get(f'{prefix}_PASSWORD','')
        rec = {'tenant': tid, 'ops': {}}
        sys.stderr.write(f'[{tid}] '); sys.stderr.flush()
        try:
            tok = signin(base, email, pwd)
            for mid in TARGET_IDS:
                r = switch_one(base, tok, mid, args.dry_run)
                rec['ops'][mid] = r
                if r['step'] == 'noop':
                    total_noop += 1; sys.stderr.write('-')
                elif r['ok']:
                    total_ok += 1; sys.stderr.write('+')
                else:
                    total_fail += 1; sys.stderr.write('X')
            sys.stderr.write(' ')
        except Exception as e:
            sys.stderr.write(f'ERROR {e}')
            rec['error'] = str(e)
        sys.stderr.write('\n')
        out['tenants'].append(rec)
    sys.stderr.write(f'\n=== TOTAL ok={total_ok} noop={total_noop} fail={total_fail} (expected: 63 ops) ===\n')
    out['totals'] = {'ok': total_ok, 'noop': total_noop, 'fail': total_fail}
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
