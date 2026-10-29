#!/usr/bin/env python3
"""
Audit all workspace items (prompts, tools, functions) on an Open WebUI tenant
and generate a Markdown report to stdout.

Usage:
  python scripts/audit-workspace.py
  python scripts/audit-workspace.py --url https://open-webui.myia.io --email admin@example.com --password secret

Environment variables (defaults for --url, --email, --password):
  MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD
"""

import os
import sys
import argparse
import json
from datetime import datetime, timezone

import requests


def login(base_url: str, email: str, password: str) -> str:
    """Authenticate and return JWT token."""
    resp = requests.post(
        f"{base_url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token")
    if not token:
        print(f"ERROR: No token in signin response: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    return token


def fetch_items(base_url: str, token: str, endpoint: str) -> list:
    """Fetch a list of items from an API endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Some endpoints return a list directly, others wrap in a dict
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Try common wrapper keys
        for key in ("items", "data", "prompts", "tools", "functions"):
            if key in data:
                return data[key]
        return [data]
    return data


def truncate(text: str, max_len: int = 100) -> str:
    """Truncate text to max_len characters, adding ellipsis if needed."""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def escape_md(text: str) -> str:
    """Escape pipe characters for Markdown table cells."""
    if not text:
        return ""
    return text.replace("|", "\\|")


def format_timestamp(ts) -> str:
    """Format a Unix timestamp (int or float) to a readable date string."""
    if not ts:
        return ""
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            return str(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return str(ts)


def generate_report(base_url: str, prompts: list, tools: list, functions: list) -> str:
    """Generate Markdown report from fetched workspace items."""
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.append(f"# Workspace Audit Report")
    lines.append("")
    lines.append(f"**Tenant URL**: {base_url}")
    lines.append(f"**Generated**: {now}")
    lines.append("")

    # --- Summary ---
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Item Type | Count |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| Prompts   | {len(prompts)} |")
    lines.append(f"| Tools     | {len(tools)} |")
    lines.append(f"| Functions | {len(functions)} |")
    lines.append(f"| **Total** | **{len(prompts) + len(tools) + len(functions)}** |")
    lines.append("")

    # --- Prompts ---
    lines.append("## Prompts")
    lines.append("")
    if not prompts:
        lines.append("_No prompts found._")
    else:
        lines.append("| # | Command | Name | Content (excerpt) | Tags |")
        lines.append("|---|---------|------|--------------------|------|")
        for i, p in enumerate(prompts, 1):
            cmd = escape_md(p.get("command", p.get("id", "")))
            name = escape_md(p.get("name", p.get("title", "")))
            content = escape_md(truncate(p.get("content", ""), 100))
            # Tags can be a list of strings or list of dicts
            raw_tags = p.get("tags", []) or []
            if raw_tags and isinstance(raw_tags[0], dict):
                tags = ", ".join(t.get("name", t.get("tag_name", str(t))) for t in raw_tags)
            else:
                tags = ", ".join(str(t) for t in raw_tags)
            tags = escape_md(tags)
            lines.append(f"| {i} | `/{cmd}` | {name} | {content} | {tags} |")
    lines.append("")

    # --- Tools ---
    lines.append("## Tools")
    lines.append("")
    if not tools:
        lines.append("_No tools found._")
    else:
        lines.append("| # | ID | Name | Description | Author | Version | Active |")
        lines.append("|---|----|------|-------------|--------|---------|--------|")
        for i, t in enumerate(tools, 1):
            tid = escape_md(t.get("id", ""))
            name = escape_md(t.get("name", ""))
            meta = t.get("meta", {}) or {}
            # Description can be at meta.description or meta.manifest.description
            desc = meta.get("description", "")
            if not desc:
                manifest = meta.get("manifest", {}) or {}
                desc = manifest.get("description", "")
            desc = escape_md(truncate(desc, 80))
            manifest = meta.get("manifest", {}) or {}
            author = escape_md(manifest.get("author", meta.get("author", "")))
            version = manifest.get("version", meta.get("version", ""))
            version = escape_md(str(version)) if version else ""
            is_active = "Yes" if t.get("is_active", True) else "No"
            lines.append(f"| {i} | `{tid}` | {name} | {desc} | {author} | {version} | {is_active} |")
    lines.append("")

    # --- Functions ---
    lines.append("## Functions")
    lines.append("")
    if not functions:
        lines.append("_No functions found._")
    else:
        lines.append("| # | ID | Name | Type | Description | Active | Global |")
        lines.append("|---|----|------|------|-------------|--------|--------|")
        for i, fn in enumerate(functions, 1):
            fid = escape_md(fn.get("id", ""))
            name = escape_md(fn.get("name", ""))
            ftype = escape_md(fn.get("type", ""))
            meta = fn.get("meta", {}) or {}
            # Description can be at meta.description or meta.manifest.description
            desc = meta.get("description", "")
            if not desc:
                manifest = meta.get("manifest", {}) or {}
                desc = manifest.get("description", "")
            desc = escape_md(truncate(desc, 80))
            is_active = "Yes" if fn.get("is_active", True) else "No"
            is_global = "Yes" if fn.get("is_global", False) else "No"
            lines.append(f"| {i} | `{fid}` | {name} | {ftype} | {desc} | {is_active} | {is_global} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Audit workspace items (prompts, tools, functions) on an Open WebUI tenant."
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("MYIA_URL", "https://open-webui.myia.io"),
        help="Base URL of the Open WebUI instance (default: MYIA_URL env or https://open-webui.myia.io)",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("MYIA_EMAIL", ""),
        help="Admin email (default: MYIA_EMAIL env)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("MYIA_PASSWORD", ""),
        help="Admin password (default: MYIA_PASSWORD env)",
    )
    args = parser.parse_args()

    if not args.email or not args.password:
        print("ERROR: --email and --password (or MYIA_EMAIL/MYIA_PASSWORD env vars) are required.", file=sys.stderr)
        sys.exit(1)

    base_url = args.url.rstrip("/")

    # 1. Login
    print(f"Logging in to {base_url} ...", file=sys.stderr)
    token = login(base_url, args.email, args.password)
    print("Login successful.", file=sys.stderr)

    # 2. Fetch workspace items
    print("Fetching prompts...", file=sys.stderr)
    prompts = fetch_items(base_url, token, "/api/v1/prompts/")
    print(f"  Found {len(prompts)} prompts.", file=sys.stderr)

    print("Fetching tools...", file=sys.stderr)
    tools = fetch_items(base_url, token, "/api/v1/tools/")
    print(f"  Found {len(tools)} tools.", file=sys.stderr)

    print("Fetching functions...", file=sys.stderr)
    functions = fetch_items(base_url, token, "/api/v1/functions/")
    print(f"  Found {len(functions)} functions.", file=sys.stderr)

    # 3. Generate and output report
    report = generate_report(base_url, prompts, tools, functions)
    print(report)

    print("\nAudit complete.", file=sys.stderr)


if __name__ == "__main__":
    main()
