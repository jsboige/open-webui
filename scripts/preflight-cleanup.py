#!/usr/bin/env python3
"""
Pre-flight cleanup for Open WebUI tenant instances before Phase 3 deployment.

Actions:
  - Delete broken functions (autotoolv2, artifacts_v2, better_r1, moea, mixture_of_agents)
  - Delete unused tools (home_assistant_tool)
  - Clean model filterIds referencing deleted functions
  - Purge spam accounts (@qq.com, admin1-7@gmail.com, defaultuser, etc.)
  - Delete existing KBs (replaced by myia shallow copies)
  - Downgrade excess admins on epf-genai

Usage:
  python scripts/preflight-cleanup.py [--dry-run] [--tenants ece epf ...]

Environment variables (from .env):
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
    'pauwels':   ('PAUWELS',   'Pauwels / Formation Pro'),
}

# Functions to delete (crash /api/models on v0.8.x)
FUNCTIONS_TO_DELETE = ['autotoolv2', 'artifacts_v2', 'better_r1', 'moea', 'mixture_of_agents']

# Tools to delete
TOOLS_TO_DELETE = ['home_assistant_tool']

# Spam patterns for account purging
SPAM_PATTERNS = [
    '@qq.com',
    'defaultuser@defaultuser.com',
    'roots@gmail.com',
]
SPAM_EXACT_EMAILS = [
    f'admin{i}@gmail.com' for i in range(1, 10)
]

# Admin emails to keep (all others on epf-genai get downgraded)
ADMIN_EMAILS_KEEP = [
    'jsboige@hotmail.com',
    'jsboige@omnesintervenant.com',
    'jsboige@myia.org',
    'j.boige@intervenant-ggeedu.fr',
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


def delete_functions(base_url, token, dry_run):
    """Delete broken functions."""
    status, functions = api_request(f'{base_url}/api/v1/functions/', token)
    if status != 200:
        print(f"    WARNING: Could not list functions ({status})")
        return 0
    existing_ids = {f['id'] for f in functions}
    deleted = 0
    for func_id in FUNCTIONS_TO_DELETE:
        if func_id in existing_ids:
            if dry_run:
                print(f"    [DRY RUN] Would delete function: {func_id}")
            else:
                s, _ = api_request(f'{base_url}/api/v1/functions/id/{func_id}/delete', token, method='DELETE')
                print(f"    Deleted function {func_id}: {s}")
            deleted += 1
        else:
            print(f"    Function {func_id}: not found (skip)")
    return deleted


def delete_tools(base_url, token, dry_run):
    """Delete unused tools."""
    status, tools = api_request(f'{base_url}/api/v1/tools/', token)
    if status != 200:
        print(f"    WARNING: Could not list tools ({status})")
        return 0
    existing_ids = {t['id'] for t in tools}
    deleted = 0
    for tool_id in TOOLS_TO_DELETE:
        if tool_id in existing_ids:
            if dry_run:
                print(f"    [DRY RUN] Would delete tool: {tool_id}")
            else:
                s, _ = api_request(f'{base_url}/api/v1/tools/id/{tool_id}/delete', token, method='DELETE')
                print(f"    Deleted tool {tool_id}: {s}")
            deleted += 1
        else:
            print(f"    Tool {tool_id}: not found (skip)")
    return deleted


def clean_model_filter_ids(base_url, token, dry_run):
    """Remove references to deleted functions from model filterIds."""
    status, body = api_request(f'{base_url}/api/models', token)
    if status != 200:
        print(f"    WARNING: Could not list models ({status})")
        return 0
    models = body if isinstance(body, list) else body.get('data', body.get('models', []))
    cleaned = 0
    for model in models:
        meta = model.get('meta') or model.get('info', {}).get('meta', {})
        if not meta:
            continue
        filter_ids = meta.get('filterIds', [])
        if not filter_ids:
            continue
        bad_ids = [fid for fid in filter_ids if fid in FUNCTIONS_TO_DELETE]
        if bad_ids:
            new_filter_ids = [fid for fid in filter_ids if fid not in FUNCTIONS_TO_DELETE]
            model_id = model.get('id', '')
            if dry_run:
                print(f"    [DRY RUN] Would clean filterIds on model {model_id}: remove {bad_ids}")
            else:
                meta['filterIds'] = new_filter_ids
                s, _ = api_request(
                    f'{base_url}/api/v1/models/id/{model_id}/update',
                    token, method='POST',
                    data={'meta': meta, 'name': model.get('name', model_id)}
                )
                print(f"    Cleaned filterIds on model {model_id}: {s} (removed {bad_ids})")
            cleaned += 1
    return cleaned


def purge_spam_accounts(base_url, token, dry_run):
    """Delete spam accounts based on email patterns."""
    status, body = api_request(f'{base_url}/api/v1/users/', token)
    if status != 200:
        print(f"    WARNING: Could not list users ({status})")
        return 0
    users = body if isinstance(body, list) else body.get('users', body.get('data', []))
    purged = 0
    for user in users:
        email = user.get('email', '')
        is_spam = any(pattern in email for pattern in SPAM_PATTERNS)
        is_spam = is_spam or email in SPAM_EXACT_EMAILS
        if is_spam:
            if dry_run:
                print(f"    [DRY RUN] Would purge spam: {email} ({user.get('name', '?')})")
            else:
                s, _ = api_request(f'{base_url}/api/v1/users/{user["id"]}', token, method='DELETE')
                print(f"    Purged spam: {email} ({s})")
            purged += 1
    return purged


def delete_knowledge_bases(base_url, token, dry_run):
    """Delete all existing KBs (will be replaced by shallow copies)."""
    status, body = api_request(f'{base_url}/api/v1/knowledge/', token)
    if status != 200:
        print(f"    WARNING: Could not list KBs ({status})")
        return 0
    kbs = body if isinstance(body, list) else body.get('items', body.get('data', []))
    deleted = 0
    for kb in kbs:
        kb_id = kb.get('id', '')
        kb_name = kb.get('name', '?')
        if dry_run:
            print(f"    [DRY RUN] Would delete KB: {kb_name} ({kb_id})")
        else:
            s, _ = api_request(f'{base_url}/api/v1/knowledge/{kb_id}/delete', token, method='DELETE')
            print(f"    Deleted KB: {kb_name} ({s})")
        deleted += 1
    return deleted


def downgrade_excess_admins(base_url, token, dry_run):
    """Downgrade non-essential admin accounts to user role."""
    status, body = api_request(f'{base_url}/api/v1/users/', token)
    if status != 200:
        print(f"    WARNING: Could not list users ({status})")
        return 0
    users = body if isinstance(body, list) else body.get('users', body.get('data', []))
    downgraded = 0
    for user in users:
        if user.get('role') == 'admin' and user.get('email') not in ADMIN_EMAILS_KEEP:
            if dry_run:
                print(f"    [DRY RUN] Would downgrade admin: {user['email']} -> user")
            else:
                s, _ = api_request(
                    f'{base_url}/api/v1/users/{user["id"]}/update',
                    token, method='POST',
                    data={'role': 'user'}
                )
                print(f"    Downgraded admin: {user['email']} -> user ({s})")
            downgraded += 1
    return downgraded


def process_tenant(tenant_key, env_prefix, description, args):
    """Run all cleanup tasks for a single tenant."""
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

    print(f"\n  --- Deleting broken functions ---")
    delete_functions(url, token, args.dry_run)

    print(f"\n  --- Deleting unused tools ---")
    delete_tools(url, token, args.dry_run)

    print(f"\n  --- Cleaning model filterIds ---")
    clean_model_filter_ids(url, token, args.dry_run)

    print(f"\n  --- Purging spam accounts ---")
    purge_spam_accounts(url, token, args.dry_run)

    print(f"\n  --- Deleting existing KBs ---")
    delete_knowledge_bases(url, token, args.dry_run)

    if tenant_key == 'epf-genai':
        print(f"\n  --- Downgrading excess admins (epf-genai specific) ---")
        downgrade_excess_admins(url, token, args.dry_run)


def main():
    parser = argparse.ArgumentParser(description='Pre-flight cleanup for tenant deployment')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without executing')
    parser.add_argument('--tenants', nargs='+', choices=list(TENANTS.keys()),
                        help='Only process these tenants')
    args = parser.parse_args()

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_env(env_path)

    if args.dry_run:
        print("=== DRY RUN MODE ===\n")

    tenants_to_process = args.tenants or list(TENANTS.keys())

    for tenant_key in tenants_to_process:
        env_prefix, description = TENANTS[tenant_key]
        process_tenant(tenant_key, env_prefix, description, args)

    print(f"\n{'='*60}")
    print("Done.")
    if args.dry_run:
        print("(No changes made — re-run without --dry-run to execute)")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
