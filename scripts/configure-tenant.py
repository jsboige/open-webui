#!/usr/bin/env python3
"""
Configure tenant instances by cloning settings from the myia reference instance.

Clones: OpenAI connections, embedding, audio (TTS+STT), image gen, RAG & web search,
        tool servers (MCP), terminal servers (Open Terminal).

Usage:
  python scripts/configure-tenant.py [--dry-run] [--tenants ece epf ...]
  python scripts/configure-tenant.py --sections "OpenAI Connections" "Audio"

Environment variables (from .env):
  MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD
  {TENANT}_URL, {TENANT}_EMAIL, {TENANT}_PASSWORD
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error

# Tenant definitions: (env_prefix, description)
TENANTS = {
    'ece':       ('ECE',       'ECE'),
    'epf':       ('EPF',       'EPF'),
    'epf-genai': ('EPF_GENAI', 'EPF GenAI'),
    'epita':     ('EPITA',     'EPITA'),
    'esg':       ('ESG',       'ESG'),
    'pauwels':   ('PAUWELS',   'Formation Pro'),
}

# Config sections to clone: (name, GET path, POST path)
# NOTE: Terminal Servers excluded from default — each tenant has its own container URL.
# Use --sections "Terminal Servers" to explicitly clone (will overwrite per-tenant URLs!).
CONFIG_SECTIONS = [
    ('OpenAI Connections', '/openai/config',                '/openai/config/update'),
    ('Embedding',          '/api/v1/retrieval/embedding',   '/api/v1/retrieval/embedding/update'),
    ('Audio',              '/api/v1/audio/config',          '/api/v1/audio/config/update'),
    ('Image Generation',   '/api/v1/images/config',         '/api/v1/images/config/update'),
    ('RAG & Web Search',   '/api/v1/retrieval/config',      '/api/v1/retrieval/config/update'),
    ('Tool Servers',       '/api/v1/configs/tool_servers',     '/api/v1/configs/tool_servers'),
]

# Sections not cloned by default (per-tenant config)
EXTRA_SECTIONS = [
    ('Terminal Servers',   '/api/v1/configs/terminal_servers', '/api/v1/configs/terminal_servers'),
]


def load_env(env_path):
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def api_request(url, token=None, method='GET', data=None):
    """Make an API request, return (status_code, response_body)."""
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers, method=method)
    if data is not None:
        req.data = json.dumps(data).encode()
    try:
        resp = urllib.request.urlopen(req)
        body = json.load(resp)
        return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {'detail': str(e)}
        return e.code, body


def authenticate(base_url, email, password):
    status, body = api_request(
        f'{base_url}/api/v1/auths/signin',
        data={'email': email, 'password': password},
        method='POST'
    )
    if status != 200:
        raise RuntimeError(f"Auth failed ({status}): {body}")
    return body['token']


def fetch_reference_configs(base_url, token, section_filter=None):
    """Fetch all config sections from the reference instance (myia)."""
    configs = {}
    all_sections = CONFIG_SECTIONS + EXTRA_SECTIONS
    for name, get_path, _ in all_sections:
        if section_filter and name not in section_filter:
            continue
        print(f"  Fetching {name}...", end=" ", flush=True)
        status, body = api_request(f'{base_url}{get_path}', token)
        if status == 200:
            # Remove status field if present (not part of update payload)
            body.pop('status', None)
            configs[name] = body
            size = len(json.dumps(body))
            print(f"OK ({size} bytes)")
        else:
            detail = body.get('detail', '?') if isinstance(body, dict) else str(body)
            print(f"FAILED ({status}): {str(detail)[:100]}")
            configs[name] = None
    return configs


def push_config(base_url, token, name, post_path, config_data, dry_run):
    """Push a config section to a tenant."""
    if config_data is None:
        print(f"    {name}: SKIP (no reference data)")
        return False
    if dry_run:
        keys = list(config_data.keys())[:5]
        print(f"    [DRY RUN] Would push {name} ({len(json.dumps(config_data))} bytes, keys: {keys}...)")
        return True

    status, body = api_request(f'{base_url}{post_path}', token, method='POST', data=config_data)
    if status == 200:
        print(f"    {name}: OK")
        return True
    else:
        detail = json.dumps(body)[:200] if isinstance(body, dict) else str(body)[:200]
        print(f"    {name}: FAILED ({status}): {detail}")
        return False


def process_tenant(tenant_key, env_prefix, description, configs, args):
    """Push all configs to a tenant."""
    url = os.environ.get(f'{env_prefix}_URL')
    email = os.environ.get(f'{env_prefix}_EMAIL')
    password = os.environ.get(f'{env_prefix}_PASSWORD')

    if not url or not email or not password:
        print(f"\n  SKIP {description}: Missing credentials ({env_prefix}_URL/EMAIL/PASSWORD)")
        return

    print(f"\n{'='*60}")
    print(f"  {description} ({url})")
    print(f"{'='*60}")

    try:
        token = authenticate(url, email, password)
        print(f"  Authenticated as {email}")
    except Exception as e:
        print(f"  ERROR: Authentication failed: {e}")
        return

    success = 0
    total = 0
    all_sections = CONFIG_SECTIONS + EXTRA_SECTIONS
    for name, _, post_path in all_sections:
        if name not in configs:
            continue
        total += 1
        if push_config(url, token, name, post_path, configs.get(name), args.dry_run):
            success += 1

    print(f"\n  Result: {success}/{total} sections configured")


def main():
    parser = argparse.ArgumentParser(description='Configure tenants from myia reference')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without executing')
    parser.add_argument('--tenants', nargs='+', choices=list(TENANTS.keys()),
                        help='Only process these tenants')
    parser.add_argument('--sections', nargs='+',
                        help='Only clone these config sections (by name)')
    args = parser.parse_args()

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_env(env_path)

    # Fetch reference config from myia
    myia_url = os.environ.get('MYIA_URL', 'https://open-webui.myia.io')
    myia_email = os.environ.get('MYIA_EMAIL')
    myia_password = os.environ.get('MYIA_PASSWORD')

    if not myia_email or not myia_password:
        print("ERROR: MYIA_EMAIL and MYIA_PASSWORD must be set in .env")
        sys.exit(1)

    print(f"=== Fetching reference config from {myia_url} ===")
    try:
        myia_token = authenticate(myia_url, myia_email, myia_password)
    except Exception as e:
        print(f"ERROR: Cannot authenticate to myia: {e}")
        sys.exit(1)
    print(f"  Authenticated as {myia_email}")

    configs = fetch_reference_configs(myia_url, myia_token, args.sections)

    fetched = sum(1 for v in configs.values() if v is not None)
    print(f"\n  Fetched {fetched}/{len(configs)} config sections")

    if args.dry_run:
        print("\n=== DRY RUN MODE ===")

    # Push to each tenant
    tenants_to_process = args.tenants or list(TENANTS.keys())

    for tenant_key in tenants_to_process:
        env_prefix, description = TENANTS[tenant_key]
        process_tenant(tenant_key, env_prefix, description, configs, args)

    print(f"\n{'='*60}")
    print("Done.")
    if args.dry_run:
        print("(No changes made — re-run without --dry-run to execute)")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
