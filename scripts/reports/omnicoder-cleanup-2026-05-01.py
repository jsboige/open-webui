#!/usr/bin/env python3
"""Cleanup OmniCoder references on 7 OWUI tenants (post-deprecation 2026-04-30).

Two actions:
1. Repoint custom model `vision-expert` from base=Local.omnicoder-9b → Local.qwen3.6-35b-a3b
   (and refresh description to drop "OmniCoder-9B" mention).
2. Disable OpenAI connector pointing to api.mini.text-generation-webui.myia.io (idx=2,
   prefix=Local) — server returns 502 since 2026-04-30.

Usage:
  python scripts/reports/omnicoder-cleanup-2026-05-01.py [--dry-run]
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
NEW_BASE = 'Local.qwen3.6-35b-a3b'
OLD_BASE = 'Local.omnicoder-9b'
DEAD_URL_FRAGMENT = 'mini.text-generation-webui.myia.io'

def load_env(p):
    if not Path(p).exists(): return
    for line in open(p):
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

def fix_vision_expert(base, tok, dry):
    s,b = api(f'{base}/api/v1/models/model?id=vision-expert', tok)
    if s != 200:
        return {'step':'fetch','ok':False,'status':s,'body':b}
    if b.get('base_model_id') != OLD_BASE:
        return {'step':'noop','ok':True,'note':f'already on {b.get("base_model_id")}'}
    payload = {
        'id': b['id'],
        'base_model_id': NEW_BASE,
        'name': b.get('name'),
        'meta': b.get('meta', {}),
        'params': b.get('params', {}),
        'access_control': b.get('access_control'),
        'is_active': b.get('is_active', True),
    }
    # refresh description
    desc = (payload['meta'] or {}).get('description', '')
    if 'OmniCoder' in desc:
        payload['meta']['description'] = desc.replace(
            'Basé sur OmniCoder-9B (local, gratuit)',
            'Basé sur Qwen3.6-35B-A3B (local, gratuit, multimodal)'
        )
    if dry:
        return {'step':'update','ok':True,'dry_run':True,'new_base':NEW_BASE}
    s,b = api(f'{base}/api/v1/models/model/update?id=vision-expert', tok, method='POST', data=payload)
    return {'step':'update','ok':(s==200),'status':s,'body':b if s!=200 else 'OK'}

def disable_dead_connector(base, tok, dry):
    s,b = api(f'{base}/openai/config', tok)
    if s != 200:
        return {'step':'fetch_openai','ok':False,'status':s}
    urls = b.get('OPENAI_API_BASE_URLS') or []
    cfgs = b.get('OPENAI_API_CONFIGS') or {}
    target_idx = None
    for i,u in enumerate(urls):
        if u and DEAD_URL_FRAGMENT in u:
            target_idx = i; break
    if target_idx is None:
        return {'step':'noop','ok':True,'note':'no dead connector found'}
    cfg = cfgs.get(str(target_idx), {}) or {}
    if cfg.get('enable') is False:
        return {'step':'noop','ok':True,'note':f'idx={target_idx} already disabled'}
    cfg['enable'] = False
    cfgs[str(target_idx)] = cfg
    payload = {
        'ENABLE_OPENAI_API':   b.get('ENABLE_OPENAI_API', True),
        'OPENAI_API_BASE_URLS': urls,
        'OPENAI_API_KEYS':     b.get('OPENAI_API_KEYS') or [],
        'OPENAI_API_CONFIGS':  cfgs,
    }
    if dry:
        return {'step':'disable','ok':True,'dry_run':True,'idx':target_idx,'url':urls[target_idx]}
    s,b = api(f'{base}/openai/config/update', tok, method='POST', data=payload)
    return {'step':'disable','ok':(s==200),'status':s,'body':b if s!=200 else 'OK','idx':target_idx}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args=ap.parse_args()
    load_env(Path(__file__).parent.parent.parent / '.env')
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'dry_run': args.dry_run, 'tenants': []}
    for tid, prefix in TENANTS:
        base  = os.environ.get(f'{prefix}_URL','').rstrip('/')
        email = os.environ.get(f'{prefix}_EMAIL','')
        pwd   = os.environ.get(f'{prefix}_PASSWORD','')
        rec = {'tenant': tid}
        sys.stderr.write(f'\n[{tid}] '); sys.stderr.flush()
        try:
            tok = signin(base, email, pwd)
            sys.stderr.write('auth OK ')
            r1 = fix_vision_expert(base, tok, args.dry_run)
            sys.stderr.write(f'vexp:{r1["step"]}/{r1["ok"]} ')
            r2 = disable_dead_connector(base, tok, args.dry_run)
            sys.stderr.write(f'conn:{r2["step"]}/{r2["ok"]}')
            rec['vision_expert'] = r1; rec['connector_disable'] = r2
        except Exception as e:
            sys.stderr.write(f'ERROR {e}')
            rec['error'] = str(e)
        out['tenants'].append(rec)
    sys.stderr.write('\n')
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
