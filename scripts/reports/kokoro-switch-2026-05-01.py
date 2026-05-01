#!/usr/bin/env python3
"""Switch OWUI Audio TTS endpoint from internal kokoro-tts:8880 to tts.myia.io/kokoro/v1.

Reads token from env var KOKORO_TOKEN (never logs it). For each tenant:
  GET  /api/v1/audio/config                -> snapshot
  POST /api/v1/audio/config/update         -> rewrite tts.OPENAI_API_BASE_URL + tts.OPENAI_API_KEY

Usage:
  KOKORO_TOKEN='...' python scripts/reports/kokoro-switch-2026-05-01.py [--dry-run]
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
NEW_URL = 'https://tts.myia.io/kokoro/v1'
OLD_URL_FRAGMENT = 'kokoro-tts:8880'

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

def switch_tenant(base, tok, kokoro_token, dry):
    s,b = api(f'{base}/api/v1/audio/config', tok)
    if s != 200:
        return {'step':'fetch','ok':False,'status':s}
    # Detect current state
    cur_url = (b.get('tts',{}) or {}).get('OPENAI_API_BASE_URL','')
    if NEW_URL.rstrip('/') == cur_url.rstrip('/') and (b.get('tts',{}) or {}).get('OPENAI_API_KEY'):
        return {'step':'noop','ok':True,'note':'already on new endpoint with key'}
    if OLD_URL_FRAGMENT not in cur_url and 'tts.myia.io' not in cur_url:
        return {'step':'skip','ok':False,'note':f'unexpected URL: {cur_url}'}
    # Build update payload (matching the GET shape)
    payload = {
        'tts': {**(b.get('tts',{}) or {})},
        'stt': {**(b.get('stt',{}) or {})},
    }
    payload['tts']['OPENAI_API_BASE_URL'] = NEW_URL
    payload['tts']['OPENAI_API_KEY']      = kokoro_token
    # Ensure rest of fields preserved
    payload['tts'].setdefault('ENGINE', 'openai')
    payload['tts'].setdefault('MODEL', 'kokoro')
    payload['tts'].setdefault('VOICE', 'ff_siwis')
    if dry:
        # Mask token in dry-run output
        out = {'step':'update','ok':True,'dry_run':True,
               'old_url': cur_url, 'new_url': NEW_URL,
               'token_set_len': len(kokoro_token)}
        return out
    s,b = api(f'{base}/api/v1/audio/config/update', tok, method='POST', data=payload)
    return {'step':'update','ok':(s==200),'status':s,'old_url':cur_url,'new_url':NEW_URL,
            'body':'OK' if s==200 else b}

def synth_test(base, tok):
    """Synthesis smoke test via OWUI proxy."""
    s,b = api(f'{base}/api/v1/audio/speech', tok, method='POST',
              data={'input':'Test rapide.', 'model':'kokoro', 'voice':'ff_siwis'},
              timeout=30)
    # OWUI returns audio bytes, but our api() expects JSON. Use raw urllib here.
    h={'Content-Type':'application/json','Authorization':f'Bearer {tok}'}
    req=urllib.request.Request(f'{base}/api/v1/audio/speech', headers=h, method='POST',
                               data=json.dumps({'input':'Test.', 'model':'kokoro', 'voice':'ff_siwis'}).encode())
    try:
        r=urllib.request.urlopen(req, timeout=30)
        body=r.read()
        return {'ok':True,'status':r.status,'bytes':len(body),
                'is_audio': body[:3]==b'ID3' or body[:2]==b'\xff\xfb'}
    except urllib.error.HTTPError as e:
        try: msg=json.loads(e.read().decode())
        except Exception: msg=str(e)
        return {'ok':False,'status':e.code,'detail':msg}
    except Exception as e:
        return {'ok':False,'error':str(e)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-test', action='store_true')
    args=ap.parse_args()
    tok_env = os.environ.get('KOKORO_TOKEN','').strip()
    if not tok_env:
        sys.stderr.write('ERROR: KOKORO_TOKEN env var not set\n'); sys.exit(2)
    load_env(Path(__file__).parent.parent.parent / '.env')
    out = {'generated_at': datetime.now(timezone.utc).isoformat(),
           'dry_run': args.dry_run, 'tenants': []}
    for tid, prefix in TENANTS:
        base  = os.environ.get(f'{prefix}_URL','').rstrip('/')
        email = os.environ.get(f'{prefix}_EMAIL','')
        pwd   = os.environ.get(f'{prefix}_PASSWORD','')
        rec = {'tenant': tid}
        sys.stderr.write(f'\n[{tid}] '); sys.stderr.flush()
        try:
            stok = signin(base, email, pwd)
            sys.stderr.write('auth ')
            r = switch_tenant(base, stok, tok_env, args.dry_run)
            sys.stderr.write(f'switch:{r["step"]}/{r["ok"]} ')
            rec['switch'] = r
            if not args.dry_run and not args.no_test and r['ok']:
                t = synth_test(base, stok)
                sys.stderr.write(f'synth:{t.get("status")} bytes={t.get("bytes",0)}')
                rec['synth_test'] = t
        except Exception as e:
            sys.stderr.write(f'ERROR {e}')
            rec['error'] = str(e)
        out['tenants'].append(rec)
    sys.stderr.write('\n')
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
