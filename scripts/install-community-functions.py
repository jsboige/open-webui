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
FUNCTIONS = [
    ('markdown_normalizer.py', 'markdown_normalizer', 'Markdown Normalizer', 'filter'),
    ('async_context_compression.py', 'async_context_compression', 'Async Context Compression', 'filter'),
    ('flash_card.py', 'flash_card', 'Flash Card', 'action'),
    ('smart_mind_map.py', 'smart_mind_map', 'Smart Mind Map', 'action'),
]

FUNCTIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'community-functions')


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


def create_function(base_url, token, func_id, name, content, meta=None):
    """Create a new function via the API."""
    payload = {
        'id': func_id,
        'name': name,
        'content': content,
        'meta': meta or {}
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f'{base_url}/api/v1/functions/create',
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    )
    resp = urllib.request.urlopen(req)
    return json.load(resp)


def update_function(base_url, token, func_id, name, content, meta=None):
    """Update an existing function via the API."""
    payload = {
        'name': name,
        'content': content,
        'meta': meta or {}
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f'{base_url}/api/v1/functions/id/{func_id}/update',
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


def main():
    parser = argparse.ArgumentParser(description='Install community functions into Open WebUI')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without executing')
    parser.add_argument('--global', dest='make_global', action='store_true',
                        help='Enable functions globally after installation')
    parser.add_argument('--functions', nargs='+',
                        help='Only install these functions (by ID)')
    args = parser.parse_args()

    # Load credentials
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_env(env_path)

    base_url = os.environ.get('MYIA_URL', 'https://open-webui.myia.io')
    email = os.environ.get('MYIA_EMAIL')
    password = os.environ.get('MYIA_PASSWORD')

    if not email or not password:
        print("ERROR: MYIA_EMAIL and MYIA_PASSWORD must be set in .env")
        sys.exit(1)

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

    # Authenticate
    print(f"\n=== Authenticating to {base_url} ===")
    token = authenticate(base_url, email, password)
    print("  OK")

    # Get existing functions
    print("\n=== Checking existing functions ===")
    existing = get_existing_functions(base_url, token)
    print(f"  {len(existing)} functions exist")

    # Install
    print("\n=== Installing functions ===")
    results = {}

    for func_id, func_name, func_type, source, meta in functions_to_install:
        try:
            if func_id in existing:
                print(f"\n  [{func_type}] {func_name}: Updating (already exists)...", end=" ", flush=True)
                result = update_function(base_url, token, func_id, func_name, source, meta)
                print("OK (updated)")
                results[func_id] = 'updated'
            else:
                print(f"\n  [{func_type}] {func_name}: Creating...", end=" ", flush=True)
                result = create_function(base_url, token, func_id, func_name, source, meta)
                print("OK (created)")
                results[func_id] = 'created'

            # Toggle global if requested
            if args.make_global:
                print(f"    Enabling globally...", end=" ", flush=True)
                toggle_function_global(base_url, token, func_id)
                print("OK")

        except urllib.error.HTTPError as e:
            error_body = e.read().decode()[:300]
            print(f"ERROR HTTP {e.code}: {error_body}")
            results[func_id] = f'error: {e.code}'
        except Exception as e:
            print(f"ERROR: {e}")
            results[func_id] = f'error: {e}'

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for func_id, status in results.items():
        func_name = next(n for i, n, _, _, _ in functions_to_install if i == func_id)
        print(f"  {func_name}: {status}")
    print("=" * 60)


if __name__ == '__main__':
    main()
