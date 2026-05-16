#!/usr/bin/env python3
"""Post v0.9.5 upgrade smoke tests on 7 OWUI tenants.

For each tenant:
  - Auth (login)
  - Chat completion via Mistral connector (cheap, no local GPU)
  - TTS synthesis via Kokoro
  - Tool Servers config has new MCP_AUTH token + 12 OpenAI connectors
  - GET /api/v1/models count
  - Recent ERROR/CRITICAL count in container logs

Usage: python scripts/reports/post-v0.9.5-smoke-2026-05-16.py
"""
import os, sys, json, urllib.request, urllib.error, subprocess
from datetime import datetime, timezone
from pathlib import Path

TENANTS = [
    ('myia',      'MYIA',      'myia-open-webui-open-webui-1'),
    ('epf',       'EPF',       'epf-open-webui-open-webui-1'),
    ('epf-genai', 'EPF_GENAI', 'epf-genai-open-webui-open-webui-1'),
    ('ece',       'ECE',       'ece-open-webui-open-webui-1'),
    ('esg',       'ESG',       'esg-open-webui-open-webui-1'),
    ('epita',     'EPITA',     'epita-open-webui-open-webui-1'),
    ('pauwels',   'PAUWELS',   'pauwels-open-webui-open-webui-1'),
]

NEW_TOKEN_PREFIX = 'ad28ecc7'

def load_env(p):
    if not Path(p).exists(): return
    for line in open(p):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,_,v=line.partition('=')
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

def api_json(url, tok=None, method='GET', data=None, timeout=30):
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
    except Exception as e:
        return 0, {'error': str(e)}

def api_raw(url, tok=None, method='POST', data=None, timeout=30):
    h={'Content-Type':'application/json'}
    if tok: h['Authorization']=f'Bearer {tok}'
    req=urllib.request.Request(url, headers=h, method=method,
                               data=json.dumps(data).encode() if data else None)
    try:
        r=urllib.request.urlopen(req, timeout=timeout)
        body=r.read()
        return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()

def signin(base, email, pwd):
    s, b = api_json(f'{base}/api/v1/auths/signin', method='POST',
                    data={'email': email, 'password': pwd})
    if s != 200: raise RuntimeError(f'auth {s}')
    return b['token']

def smoke_tenant(base, tok, container):
    out = {}
    # 1. Version
    s,b = api_json(f'{base}/api/v1/configs', tok)
    # 2. Models count
    s,b = api_json(f'{base}/api/v1/models', tok, timeout=15)
    out['models_count'] = (b.get('count') if isinstance(b, dict) else None) or (
                          len(b.get('data', [])) if isinstance(b, dict) else (
                          len(b) if isinstance(b, list) else 0))
    # 3. OpenAI connectors
    s,b = api_json(f'{base}/openai/config', tok)
    if s == 200:
        urls = b.get('OPENAI_API_BASE_URLS', [])
        ena  = b.get('OPENAI_API_CONFIGS', {})
        out['openai_connectors_total'] = len(urls)
        out['openai_connectors_enabled'] = sum(1 for k,v in ena.items() if v.get('enable', True))
    # 4. Tool Servers
    s,b = api_json(f'{base}/api/v1/configs/tool_servers', tok)
    if s == 200:
        conns = b.get('TOOL_SERVER_CONNECTIONS', [])
        out['tool_servers_count'] = len(conns)
        out['tool_servers_on_new_token'] = sum(1 for c in conns
                                                if (c.get('key') or '').startswith(NEW_TOKEN_PREFIX))
    # 5. Chat completion (Mistral - cheap). v0.9.5 needs chat_id + id.
    s,b = api_json(f'{base}/api/chat/completions', tok, method='POST', data={
        'model': 'MistralAI.mistral-medium-latest',
        'messages': [{'role':'user','content':'Reply with just OK.'}],
        'stream': False,
        'max_tokens': 10,
        'chat_id': 'local:smoke-2026-05-16',
        'id': 'smoke-msg-1',
    }, timeout=45)
    out['chat_status'] = s
    if s == 200:
        try:
            out['chat_content'] = b['choices'][0]['message']['content'][:50]
        except Exception:
            out['chat_content'] = 'parse-error'
    else:
        out['chat_error'] = str(b)[:100]
    # 6. TTS Kokoro
    s,b = api_raw(f'{base}/api/v1/audio/speech', tok, method='POST',
                  data={'input':'Test.','model':'kokoro','voice':'ff_siwis'}, timeout=20)
    out['tts_status'] = s
    if s == 200:
        out['tts_bytes'] = len(b)
        out['tts_is_audio'] = (b[:3] == b'ID3' or b[:2] == b'\xff\xfb')
    # 7. Container errors (last 10min)
    try:
        logs = subprocess.run(['docker','logs',container,'--since','10m'],
                              capture_output=True, timeout=10).stderr.decode('utf-8','replace')
        errs = sum(1 for l in logs.splitlines()
                   if any(p in l for p in ('ERROR','CRITICAL','Traceback')))
        out['log_errors_10m'] = errs
    except Exception as e:
        out['log_errors_10m'] = f'err: {e}'
    return out

def main():
    load_env(Path(__file__).parent.parent.parent / '.env')
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'tenants': {}}
    for tid, prefix, container in TENANTS:
        base  = os.environ.get(f'{prefix}_URL','').rstrip('/')
        email = os.environ.get(f'{prefix}_EMAIL','')
        pwd   = os.environ.get(f'{prefix}_PASSWORD','')
        sys.stderr.write(f'\n[{tid}] '); sys.stderr.flush()
        rec = {}
        try:
            tok = signin(base, email, pwd)
            sys.stderr.write('auth ')
            rec = smoke_tenant(base, tok, container)
            sys.stderr.write(
                f'models={rec.get("models_count")} '
                f'conn={rec.get("openai_connectors_enabled")}/{rec.get("openai_connectors_total")} '
                f'tools={rec.get("tool_servers_on_new_token")}/{rec.get("tool_servers_count")} '
                f'chat={rec.get("chat_status")} '
                f'tts={rec.get("tts_status")} '
                f'errs={rec.get("log_errors_10m")}'
            )
        except Exception as e:
            sys.stderr.write(f'ERROR {e}')
            rec['error'] = str(e)
        out['tenants'][tid] = rec
    sys.stderr.write('\n')
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
