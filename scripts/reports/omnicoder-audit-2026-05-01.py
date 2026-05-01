#!/usr/bin/env python3
"""One-shot audit: OmniCoder references + Kokoro TTS endpoint snapshot on 7 OWUI tenants.
Output: reports/omnicoder-audit-2026-05-01.json + stdout summary.
"""
import os, sys, json, urllib.request, urllib.error
from datetime import datetime, timezone

TENANTS = [
    ('myia',      'MYIA',      'Reference (myia)'),
    ('epf',       'EPF',       'EPF'),
    ('epf-genai', 'EPF_GENAI', 'EPF GenAI'),
    ('ece',       'ECE',       'ECE'),
    ('esg',       'ESG',       'ESG'),
    ('epita',     'EPITA',     'EPITA'),
    ('pauwels',   'PAUWELS',   'Formation Pro'),
]

OMNICODER_NEEDLES = ['omnicoder', 'qwen3.5-mini', 'mini.text-generation', '5001', 'Local.qwen3.5-35b-a3b-fast']

def load_env(p):
    if not os.path.exists(p): return
    for line in open(p):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

def api(url, token=None, method='GET', data=None, timeout=30):
    h = {'Content-Type': 'application/json'}
    if token: h['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=h, method=method)
    if data is not None: req.data = json.dumps(data).encode()
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: body = json.loads(e.read().decode())
        except Exception: body = {'detail': str(e)}
        return e.code, body
    except Exception as e:
        return 0, {'error': str(e)}

def signin(base, email, password):
    s, b = api(f'{base}/api/v1/auths/signin', method='POST', data={'email': email, 'password': password})
    if s != 200: raise RuntimeError(f'auth failed {s}: {b}')
    return b['token']

def has_needle(blob):
    s = json.dumps(blob, ensure_ascii=False).lower()
    return [n for n in OMNICODER_NEEDLES if n.lower() in s]

def audit_tenant(tenant_id, prefix, label):
    base  = os.environ.get(f'{prefix}_URL', '').rstrip('/')
    email = os.environ.get(f'{prefix}_EMAIL', '')
    pwd   = os.environ.get(f'{prefix}_PASSWORD', '')
    if not (base and email and pwd):
        return {'tenant': tenant_id, 'error': 'missing creds'}
    out = {'tenant': tenant_id, 'label': label, 'url': base}
    try:
        tok = signin(base, email, pwd)
    except Exception as e:
        out['error'] = str(e); return out
    out['auth'] = 'OK'

    # OpenAI connectors
    s, b = api(f'{base}/openai/config', tok)
    if s == 200:
        urls    = b.get('OPENAI_API_BASE_URLS') or []
        keys    = b.get('OPENAI_API_KEYS') or []
        configs = b.get('OPENAI_API_CONFIGS') or {}
        flagged = []
        for i, u in enumerate(urls):
            cfg = configs.get(str(i), {})
            prefix_id = cfg.get('prefix_id') or cfg.get('name') or ''
            enabled = cfg.get('enable', True)
            if any(n.lower() in (u or '').lower() for n in OMNICODER_NEEDLES) or \
               any(n.lower() in str(prefix_id).lower() for n in OMNICODER_NEEDLES):
                flagged.append({'idx': i, 'url': u, 'prefix_id': prefix_id, 'enabled': enabled})
        out['openai_connectors_total'] = len(urls)
        out['openai_omnicoder_flagged'] = flagged
    else:
        out['openai_error'] = f'{s}: {b}'

    # Custom models (paginated)
    flagged_models = []
    page = 1
    total_models = 0
    while True:
        s, b = api(f'{base}/api/v1/models/list?page={page}', tok)
        if s != 200:
            out['models_error'] = f'{s}: {b}'; break
        items = b.get('items', [])
        total = b.get('total', len(items))
        for m in items:
            blob = json.dumps(m, ensure_ascii=False).lower()
            hits = [n for n in OMNICODER_NEEDLES if n.lower() in blob]
            if hits:
                flagged_models.append({
                    'id': m.get('id'),
                    'name': m.get('name'),
                    'base_model_id': m.get('base_model_id'),
                    'is_active': m.get('is_active'),
                    'hits': hits,
                })
        total_models += len(items)
        if total_models >= total or not items: break
        page += 1
    out['models_total_listed'] = total_models
    out['models_omnicoder_flagged'] = flagged_models

    # Audio config snapshot (TTS endpoint)
    s, b = api(f'{base}/api/v1/audio/config', tok)
    if s == 200:
        tts = b.get('tts', {}) or {}
        stt = b.get('stt', {}) or {}
        out['audio_tts'] = {
            'ENGINE':    tts.get('ENGINE'),
            'API_KEY':   '***' if tts.get('API_KEY') else '',
            'OPENAI_API_BASE_URL': tts.get('OPENAI_API_BASE_URL'),
            'OPENAI_API_KEY_set': bool(tts.get('OPENAI_API_KEY')),
            'MODEL':     tts.get('MODEL'),
            'VOICE':     tts.get('VOICE'),
            'SPLIT_ON':  tts.get('SPLIT_ON'),
        }
        out['audio_stt_engine'] = stt.get('ENGINE')
    else:
        out['audio_error'] = f'{s}: {b}'

    return out

def main():
    load_env(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    results = []
    for t, p, lbl in TENANTS:
        sys.stderr.write(f'\n[{t}] auditing... ')
        sys.stderr.flush()
        r = audit_tenant(t, p, lbl)
        sys.stderr.write('done\n')
        results.append(r)
    out = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'needles': OMNICODER_NEEDLES,
        'tenants': results,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
