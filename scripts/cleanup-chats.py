#!/usr/bin/env python3
"""
Cleanup test/loose conversations on Open WebUI tenant instances.

Lists and optionally deletes chats that are NOT in folders (i.e., loose/test chats).
Chats organized in folders are considered intentional and are always kept.

Usage:
  # Dry-run on myia (default)
  python scripts/cleanup-chats.py --tenant myia --dry-run

  # Dry-run on all tenants
  python scripts/cleanup-chats.py --tenant all --dry-run

  # Actually delete loose chats older than 7 days on myia
  python scripts/cleanup-chats.py --tenant myia --delete --keep-recent 7

  # Delete only chats matching a pattern
  python scripts/cleanup-chats.py --tenant myia --delete --pattern "^New Chat$|^test"

Environment variables (from .env):
  {TENANT}_URL, {TENANT}_EMAIL, {TENANT}_PASSWORD
"""

import os
import re
import sys
import time
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)


# Tenant definitions: name -> (env_prefix, description)
TENANTS = {
    "myia":     ("MYIA",      "MyIA (reference)"),
    "epf":      ("EPF",       "EPF"),
    "epf-genai":("EPF_GENAI", "EPF GenAI"),
    "ece":      ("ECE",       "ECE"),
    "esg":      ("ESG",       "ESG"),
    "epita":    ("EPITA",     "EPITA"),
    "pauwels":  ("PAUWELS",   "Pauwels / Formation Pro"),
}


def load_env_file(env_path):
    """Load a .env file into a dict (simple key=value parser)."""
    env = {}
    if not os.path.isfile(env_path):
        print(f"ERROR: .env file not found: {env_path}")
        sys.exit(1)
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def get_tenant_creds(tenant_name, env):
    """Get (url, email, password) for a tenant from env dict."""
    prefix = TENANTS[tenant_name][0]
    url = env.get(f"{prefix}_URL")
    email = env.get(f"{prefix}_EMAIL")
    password = env.get(f"{prefix}_PASSWORD")
    if not all([url, email, password]):
        missing = []
        if not url: missing.append(f"{prefix}_URL")
        if not email: missing.append(f"{prefix}_EMAIL")
        if not password: missing.append(f"{prefix}_PASSWORD")
        print(f"  WARNING: Missing env vars for {tenant_name}: {', '.join(missing)}")
        return None
    return url.rstrip("/"), email, password


def login(url, email, password):
    """Authenticate and return JWT token."""
    resp = requests.post(
        f"{url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"  ERROR: Login failed (HTTP {resp.status_code}): {resp.text[:200]}")
        return None
    data = resp.json()
    return data.get("token")


def get_headers(token):
    """Return auth headers."""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def fetch_all_chats(url, headers):
    """
    Fetch all chats using /list endpoint with include_folders=true.
    Paginates through all pages (60 per page).
    Returns list of chat dicts with: id, title, updated_at, created_at.
    Note: /list endpoint does NOT return folder_id.
    """
    all_chats = []
    page = 1
    while True:
        resp = requests.get(
            f"{url}/api/v1/chats/list",
            params={"page": page, "include_folders": "true"},
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  ERROR: Failed to fetch chat list page {page} (HTTP {resp.status_code})")
            break
        chats = resp.json()
        if not chats:
            break
        all_chats.extend(chats)
        if len(chats) < 60:
            break
        page += 1
    return all_chats


def fetch_loose_chats(url, headers):
    """
    Fetch only loose chats (not in any folder) using /list with include_folders=false.
    Paginates through all pages (60 per page).
    """
    loose_chats = []
    page = 1
    while True:
        resp = requests.get(
            f"{url}/api/v1/chats/list",
            params={"page": page, "include_folders": "false"},
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  ERROR: Failed to fetch loose chat list page {page} (HTTP {resp.status_code})")
            break
        chats = resp.json()
        if not chats:
            break
        loose_chats.extend(chats)
        if len(chats) < 60:
            break
        page += 1
    return loose_chats


def fetch_folders(url, headers):
    """Fetch all folders."""
    resp = requests.get(f"{url}/api/v1/folders/", headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"  WARNING: Failed to fetch folders (HTTP {resp.status_code})")
        return []
    return resp.json()


def delete_chat(url, headers, chat_id):
    """Delete a single chat. Returns True on success."""
    resp = requests.delete(
        f"{url}/api/v1/chats/{chat_id}",
        headers=headers,
        timeout=30,
    )
    return resp.status_code == 200


def format_timestamp(ts):
    """Convert epoch timestamp to readable datetime string."""
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError, OSError):
        return f"(invalid: {ts})"


def process_tenant(tenant_name, env, args):
    """Process a single tenant: list and optionally delete loose chats."""
    desc = TENANTS[tenant_name][1]
    print(f"\n{'='*70}")
    print(f"  TENANT: {tenant_name} ({desc})")
    print(f"{'='*70}")

    creds = get_tenant_creds(tenant_name, env)
    if not creds:
        return

    url, email, password = creds
    print(f"  URL: {url}")
    print(f"  User: {email}")

    # Login
    token = login(url, email, password)
    if not token:
        return

    print(f"  Login: OK")

    # Fetch folders
    folders = fetch_folders(url, get_headers(token))
    folder_names = {f.get("id"): f.get("name", "(unnamed)") for f in folders}
    print(f"  Folders: {len(folders)}")
    for fid, fname in folder_names.items():
        print(f"    - {fname} ({fid})")

    # Fetch all chats and loose chats
    all_chats = fetch_all_chats(url, get_headers(token))
    loose_chats = fetch_loose_chats(url, get_headers(token))

    # Build sets for counting
    all_ids = {c["id"] for c in all_chats}
    loose_ids = {c["id"] for c in loose_chats}
    in_folder_count = len(all_ids) - len(loose_ids)

    print(f"\n  SUMMARY:")
    print(f"    Total chats:      {len(all_chats)}")
    print(f"    In folders (keep): {in_folder_count}")
    print(f"    Loose (candidates): {len(loose_chats)}")

    if not loose_chats:
        print(f"\n  No loose chats to clean up.")
        return

    # Apply filters
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=args.keep_recent)
    cutoff_ts = cutoff.timestamp()

    # Filter by age
    candidates = []
    kept_recent = 0
    for chat in loose_chats:
        updated_at = chat.get("updated_at", 0)
        if updated_at > cutoff_ts:
            kept_recent += 1
            continue
        candidates.append(chat)

    # Filter by pattern
    if args.pattern:
        pattern = re.compile(args.pattern, re.IGNORECASE)
        before_pattern = len(candidates)
        candidates = [c for c in candidates if pattern.search(c.get("title", ""))]
        filtered_out = before_pattern - len(candidates)
        if filtered_out > 0:
            print(f"    Pattern filter:   {filtered_out} excluded (don't match '{args.pattern}')")

    if kept_recent > 0:
        print(f"    Kept (recent {args.keep_recent}d): {kept_recent}")

    print(f"    To delete:        {len(candidates)}")

    # List loose chats
    print(f"\n  LOOSE CHATS (not in folders):")
    print(f"  {'Status':<10} {'Updated':<20} {'Title'}")
    print(f"  {'-'*10} {'-'*20} {'-'*40}")

    # Sort by updated_at descending
    loose_sorted = sorted(loose_chats, key=lambda c: c.get("updated_at", 0), reverse=True)
    candidate_ids = {c["id"] for c in candidates}

    for chat in loose_sorted:
        chat_id = chat["id"]
        title = chat.get("title", "(untitled)")
        updated = format_timestamp(chat.get("updated_at", 0))
        if chat_id in candidate_ids:
            status = "DELETE"
        else:
            # Kept by recent filter or pattern filter
            status = "KEEP"
        print(f"  {status:<10} {updated:<20} {title[:60]}")

    # Delete if --delete
    if args.delete and candidates:
        print(f"\n  DELETING {len(candidates)} chats...")
        deleted = 0
        failed = 0
        for i, chat in enumerate(candidates, 1):
            chat_id = chat["id"]
            title = chat.get("title", "(untitled)")
            ok = delete_chat(url, get_headers(token), chat_id)
            if ok:
                deleted += 1
                print(f"    [{i}/{len(candidates)}] Deleted: {title[:50]}")
            else:
                failed += 1
                print(f"    [{i}/{len(candidates)}] FAILED:  {title[:50]}")
            # Small delay to avoid rate limiting
            if i % 10 == 0:
                time.sleep(0.5)
        print(f"\n  Result: {deleted} deleted, {failed} failed")
    elif not args.delete:
        print(f"\n  DRY RUN: No chats deleted. Use --delete to actually delete.")


def main():
    parser = argparse.ArgumentParser(
        description="List and optionally delete loose/test conversations on Open WebUI tenants.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --tenant myia --dry-run          # List loose chats on myia
  %(prog)s --tenant all --dry-run           # List loose chats on all tenants
  %(prog)s --tenant myia --delete           # Delete loose chats older than 7 days
  %(prog)s --tenant myia --delete --keep-recent 0  # Delete ALL loose chats
  %(prog)s --tenant myia --dry-run --pattern "^New Chat$"  # Only target default-named chats
""",
    )
    parser.add_argument(
        "--tenant",
        default="myia",
        help="Tenant name (myia, epf, ece, ...) or 'all' (default: myia)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="List chats without deleting (default behavior)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        default=False,
        help="Actually delete loose chats",
    )
    parser.add_argument(
        "--keep-recent",
        type=int,
        default=7,
        metavar="N",
        help="Keep chats from the last N days even if loose (default: 7)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default=None,
        metavar="REGEX",
        help="Only delete chats whose title matches this regex pattern",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Path to .env file (default: .env in script's parent directory)",
    )

    args = parser.parse_args()

    # Resolve env file path
    if args.env_file:
        env_path = args.env_file
    else:
        # Look for .env in the parent of the scripts/ directory
        script_dir = Path(__file__).resolve().parent
        env_path = str(script_dir.parent / ".env")
        # Fallback: also check /app/.env (Docker mount)
        if not os.path.isfile(env_path):
            env_path = "/app/.env"

    print(f"Loading credentials from: {env_path}")
    env = load_env_file(env_path)

    # Determine tenants to process
    tenant_arg = args.tenant.lower()
    if tenant_arg == "all":
        tenant_list = list(TENANTS.keys())
    elif tenant_arg in TENANTS:
        tenant_list = [tenant_arg]
    else:
        print(f"ERROR: Unknown tenant '{tenant_arg}'. Available: {', '.join(TENANTS.keys())}, all")
        sys.exit(1)

    mode = "DELETE" if args.delete else "DRY RUN"
    print(f"Mode: {mode}")
    print(f"Keep recent: {args.keep_recent} days")
    if args.pattern:
        print(f"Pattern filter: {args.pattern}")
    print(f"Tenants: {', '.join(tenant_list)}")

    for tenant in tenant_list:
        process_tenant(tenant, env, args)

    print(f"\n{'='*70}")
    print("Done.")


if __name__ == "__main__":
    main()
