#!/usr/bin/env python3
"""Audit Qwen3.6 wrappers across 7 OWUI tenants prior to vLLM cutover 35B-A3B -> 27B Dense.

Targets the 9 OWUI custom models expected to reference the vLLM model:
  - Local.qwen3.6-35b-a3b, Local.qwen3.6-35b-a3b-fast
  - expert-analyste, redacteur-technique
  - Qwen_think, Qwen_think-code, Qwen_think-reason, Qwen_instruct
  - vision-expert  (was repointed to Local.qwen3.6-35b-a3b on 2026-05-01)

For each, fetches /api/v1/models/model?id=X to get the real base_model_id.
Outputs a JSON inventory consumed by the switch script.
"""
import os, sys, json, urllib.request, urllib.error
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

def main():
    load_env(Path(__file__).parent.parent.parent / '.env')
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'tenants': []}
    for tid, prefix in TENANTS:
        base  = os.environ.get(f'{prefix}_URL','').rstrip('/')
        email = os.environ.get(f'{prefix}_EMAIL','')
        pwd   = os.environ.get(f'{prefix}_PASSWORD','')
        rec = {'tenant': tid, 'models': {}}
        sys.stderr.write(f'[{tid}] '); sys.stderr.flush()
        try:
            tok = signin(base, email, pwd)
            for mid in TARGET_IDS:
                s, b = api(f'{base}/api/v1/models/model?id={mid}', tok)
                if s == 200 and isinstance(b, dict) and b.get('id'):
                    desc = ((b.get('meta') or {}).get('description') or '')
                    rec['models'][mid] = {
                        'present': True,
                        'base_model_id': b.get('base_model_id'),
                        'is_active': b.get('is_active', True),
                        'description': desc[:200],
                    }
                    sys.stderr.write('.')
                else:
                    rec['models'][mid] = {'present': False, 'status': s}
                    sys.stderr.write('x')
            sys.stderr.write(' ')
        except Exception as e:
            sys.stderr.write(f'ERROR {e}')
            rec['error'] = str(e)
        sys.stderr.write('\n')
        out['tenants'].append(rec)
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
