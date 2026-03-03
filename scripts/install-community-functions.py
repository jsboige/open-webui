#!/usr/bin/env python3
"""
Install community functions into Open WebUI via the API.

Reads Python source files from scripts/community-functions/ and installs
them as functions using POST /api/v1/functions/create.

Usage:
  python scripts/install-community-functions.py [--dry-run]

Environment variables (from .env):
  MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD
"""

import os
import sys
import json
import re
import argparse
import urllib.request
import urllib.error


# Function definitions: (file_basename, function_id, function_name, function_type)
# Types: 'filter', 'action' use /api/v1/functions/ endpoint
#         'tool' uses /api/v1/tools/ endpoint
FUNCTIONS = [
    # Priority 1 (already installed)
    ('markdown_normalizer.py', 'markdown_normalizer', 'Markdown Normalizer', 'filter'),
    ('async_context_compression.py', 'async_context_compression', 'Async Context Compression', 'filter'),
    ('flash_card.py', 'flash_card', 'Flash Card', 'action'),
    ('smart_mind_map.py', 'smart_mind_map', 'Smart Mind Map', 'action'),
    # Priority 2
    ('export_to_word.py', 'export_to_word', 'Export to Word Enhanced', 'action'),
    ('sub_agent.py', 'sub_agent', 'Sub Agent', 'tool'),
    ('youtube_transcript.py', 'youtube_transcript', 'YouTube Transcript Provider', 'tool'),
    ('visuals_toolkit.py', 'visuals_toolkit', 'Visuals Toolkit', 'tool'),
    # Priority 3 (added 2026-03-03)
    ('smart_infographic.py', 'smart_infographic', 'Smart Infographic', 'action'),
    ('llm_council.py', 'llm_council', 'LLM Council', 'tool'),
]

FUNCTIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'community-functions')

# Tenants for multi-tenant deployment
TENANTS = {
    "myia": ("MYIA_URL", "MYIA_EMAIL", "MYIA_PASSWORD"),
    "epf": ("EPF_URL", "EPF_EMAIL", "EPF_PASSWORD"),
    "epf-genai": ("EPF_GENAI_URL", "EPF_GENAI_EMAIL", "EPF_GENAI_PASSWORD"),
    "ece": ("ECE_URL", "ECE_EMAIL", "ECE_PASSWORD"),
    "esg": ("ESG_URL", "ESG_EMAIL", "ESG_PASSWORD"),
    "epita": ("EPITA_URL", "EPITA_EMAIL", "EPITA_PASSWORD"),
    "pauwels": ("PAUWELS_URL", "PAUWELS_EMAIL", "PAUWELS_PASSWORD"),
}


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


def authenticate(base_url, email, password):
    data = json.dumps({'email': email, 'password': password}).encode()
    req = urllib.request.Request(
        f'{base_url}/api/v1/auths/signin',
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req)
    return json.load(resp)['token']


def get_existing_functions(base_url, token):
    """Fetch list of existing function IDs."""
    req = urllib.request.Request(
        f'{base_url}/api/v1/functions/',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp = urllib.request.urlopen(req)
    functions = json.load(resp)
    return {f['id']: f['name'] for f in functions}


def get_existing_tools(base_url, token):
    """Fetch list of existing tool IDs."""
    req = urllib.request.Request(
        f'{base_url}/api/v1/tools/',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp = urllib.request.urlopen(req)
    tools = json.load(resp)
    return {t['id']: t['name'] for t in tools}


def extract_metadata(source_code):
    """Extract metadata from the docstring at the top of the file."""
    meta = {}
    # Look for title, description, version in the docstring
    match = re.search(r'(?:title|name)\s*:\s*(.+)', source_code[:2000])
    if match:
        meta['name'] = match.group(1).strip()
    match = re.search(r'description\s*:\s*(.+)', source_code[:2000])
    if match:
        meta['description'] = match.group(1).strip()
    match = re.search(r'version\s*:\s*(.+)', source_code[:2000])
    if match:
        meta['version'] = match.group(1).strip()
    return meta


def _api_endpoint(base_url, func_type, suffix):
    """Return the correct API endpoint based on function type."""
    if func_type == 'tool':
        return f'{base_url}/api/v1/tools/{suffix}'
    return f'{base_url}/api/v1/functions/{suffix}'


def create_function(base_url, token, func_id, name, content, meta=None, func_type='filter'):
    """Create a new function or tool via the API."""
    payload = {
        'id': func_id,
        'name': name,
        'content': content,
        'meta': meta or {}
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        _api_endpoint(base_url, func_type, 'create'),
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    )
    resp = urllib.request.urlopen(req)
    return json.load(resp)


def update_function(base_url, token, func_id, name, content, meta=None, func_type='filter'):
    """Update an existing function or tool via the API."""
    payload = {
        'id': func_id,
        'name': name,
        'content': content,
        'meta': meta or {}
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        _api_endpoint(base_url, func_type, f'id/{func_id}/update'),
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    )
    resp = urllib.request.urlopen(req)
    return json.load(resp)


def toggle_function_global(base_url, token, func_id):
    """Toggle a function to be globally active."""
    req = urllib.request.Request(
        f'{base_url}/api/v1/functions/id/{func_id}/toggle/global',
        data=b'',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    return json.load(resp)


def install_on_tenant(base_url, email, password, functions_to_install, make_global=False):
    """Install functions on a single tenant. Returns dict of results."""
    token = authenticate(base_url, email, password)
    existing_functions = get_existing_functions(base_url, token)
    existing_tools = get_existing_tools(base_url, token)
    results = {}

    for func_id, func_name, func_type, source, meta in functions_to_install:
        existing = existing_tools if func_type == 'tool' else existing_functions
        try:
            if func_id in existing:
                print(f"    [{func_type}] {func_name}: Updating...", end=" ", flush=True)
                update_function(base_url, token, func_id, func_name, source, meta, func_type)
                print("OK")
                results[func_id] = 'updated'
            else:
                print(f"    [{func_type}] {func_name}: Creating...", end=" ", flush=True)
                create_function(base_url, token, func_id, func_name, source, meta, func_type)
                print("OK")
                results[func_id] = 'created'

            if make_global and func_type != 'tool':
                toggle_function_global(base_url, token, func_id)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode()[:300]
            print(f"ERROR HTTP {e.code}: {error_body}")
            results[func_id] = f'error: {e.code}'
        except Exception as e:
            print(f"ERROR: {e}")
            results[func_id] = f'error: {e}'

    return results


def main():
    parser = argparse.ArgumentParser(description='Install community functions into Open WebUI')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without executing')
    parser.add_argument('--global', dest='make_global', action='store_true',
                        help='Enable functions globally after installation')
    parser.add_argument('--functions', nargs='+',
                        help='Only install these functions (by ID)')
    parser.add_argument('--tenant', default='myia',
                        help='Tenant to install on (default: myia, use "all" for all tenants)')
    args = parser.parse_args()

    # Load credentials
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    for env_file in ['.env', 'myia.env']:
        load_env(os.path.join(repo_dir, env_file))

    # Check which functions to install
    functions_to_install = []
    for filename, func_id, func_name, func_type in FUNCTIONS:
        if args.functions and func_id not in args.functions:
            continue
        filepath = os.path.join(FUNCTIONS_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  WARNING: File not found: {filepath}")
            continue
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        meta = extract_metadata(source)
        meta.setdefault('description', f'{func_name} ({func_type})')
        functions_to_install.append((func_id, func_name, func_type, source, meta))

    print(f"=== Functions to install: {len(functions_to_install)} ===")
    for func_id, func_name, func_type, _, meta in functions_to_install:
        print(f"  [{func_type}] {func_name} (id={func_id}) — {meta.get('description', '')[:80]}")

    if args.dry_run:
        print("\n=== DRY RUN: No changes made ===")
        return

    # Determine tenants
    if args.tenant == 'all':
        tenants_to_process = list(TENANTS.items())
    else:
        if args.tenant in TENANTS:
            tenants_to_process = [(args.tenant, TENANTS[args.tenant])]
        else:
            # Legacy single-tenant mode
            base_url = os.environ.get('MYIA_URL', 'https://open-webui.myia.io')
            email = os.environ.get('MYIA_EMAIL')
            password = os.environ.get('MYIA_PASSWORD')
            if not email or not password:
                print("ERROR: credentials not found")
                sys.exit(1)
            tenants_to_process = [('myia', ('MYIA_URL', 'MYIA_EMAIL', 'MYIA_PASSWORD'))]

    all_results = {}
    for tenant_name, (url_key, email_key, pwd_key) in tenants_to_process:
        url = os.environ.get(url_key, '')
        email = os.environ.get(email_key, '')
        pwd = os.environ.get(pwd_key, '')

        if not url or not email or not pwd:
            print(f"\n  {tenant_name}: SKIP (missing credentials)")
            continue

        print(f"\n=== {tenant_name}: {url} ===")
        try:
            results = install_on_tenant(url, email, pwd, functions_to_install, args.make_global)
            all_results[tenant_name] = results
        except Exception as e:
            print(f"  FAILED: {e}")
            all_results[tenant_name] = {'_error': str(e)}

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for tenant_name, results in all_results.items():
        print(f"\n  {tenant_name}:")
        for func_id, status in results.items():
            print(f"    {func_id}: {status}")
    print("=" * 60)


if __name__ == '__main__':
    main()
