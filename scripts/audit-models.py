#!/usr/bin/env python3
"""
Audit all models on an Open WebUI tenant and generate a Markdown report.

Inventories all custom/overlay models, checks avatar status, documents
parameters, and identifies models missing avatars.

Usage:
  python scripts/audit-models.py
  python scripts/audit-models.py --url https://open-webui.myia.io --email admin@example.com --password secret

Environment variables (from .env or shell):
  MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD
"""

import os
import sys
import json
import argparse
import textwrap
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env(env_path):
    """Load .env file into os.environ (setdefault — won't overwrite existing)."""
    if not os.path.exists(env_path):
        return
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def authenticate(base_url, email, password):
    """Sign in and return JWT token."""
    resp = requests.post(
        f"{base_url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"ERROR: Authentication failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    return data.get("token")


def fetch_all_custom_models(base_url, token):
    """Fetch all custom/overlay models via paginated /api/v1/models/list endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    all_models = []
    page = 1
    while True:
        resp = requests.get(
            f"{base_url}/api/v1/models/list",
            headers=headers,
            params={"page": page},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"ERROR: Failed to fetch models page {page} ({resp.status_code}): {resp.text}", file=sys.stderr)
            break
        data = resp.json()
        items = data.get("items", [])
        total = data.get("total", 0)
        all_models.extend(items)
        if len(all_models) >= total or not items:
            break
        page += 1
    return all_models


def fetch_base_models(base_url, token):
    """Fetch provider base models via /api/v1/models/base (admin only)."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{base_url}/api/v1/models/base",
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"WARNING: Failed to fetch base models ({resp.status_code}): {resp.text}", file=sys.stderr)
        return []
    return resp.json()


# ---------------------------------------------------------------------------
# Model analysis helpers
# ---------------------------------------------------------------------------

def classify_avatar(meta):
    """Classify the avatar status of a model."""
    url = meta.get("profile_image_url", "") or ""
    if not url or url == "/static/favicon.png":
        return "No Avatar"
    if url.startswith("data:image/"):
        # Estimate size of base64 data
        size_bytes = len(url) * 3 // 4
        size_kb = size_bytes / 1024
        return f"Custom Avatar (~{size_kb:.0f} KB)"
    return f"URL Avatar"


def truncate(text, maxlen):
    """Truncate text to maxlen, adding ellipsis if needed."""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", "").strip()
    if len(text) <= maxlen:
        return text
    return text[: maxlen - 3] + "..."


def escape_md(text):
    """Escape pipe characters for Markdown tables."""
    if not text:
        return ""
    return text.replace("|", "\\|")


def format_timestamp(ts):
    """Convert epoch timestamp to readable date."""
    if not ts:
        return ""
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return ""


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(custom_models, base_models, base_url):
    """Generate Markdown audit report."""
    lines = []

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Model Audit Report")
    lines.append(f"")
    lines.append(f"**Tenant:** {base_url}")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Tool:** `scripts/audit-models.py`")
    lines.append(f"")

    # Build base model lookup
    base_model_ids = set()
    for bm in base_models:
        bm_id = bm.get("id", "")
        base_model_ids.add(bm_id)

    # Analyze custom models
    models_with_custom_avatar = []
    models_with_url_avatar = []
    models_without_avatar = []
    all_analyzed = []

    for m in sorted(custom_models, key=lambda x: (x.get("name") or x.get("id", "")).lower()):
        model_id = m.get("id", "")
        name = m.get("name", model_id)
        base_model_id = m.get("base_model_id") or ""
        meta = m.get("meta", {}) or {}
        params = m.get("params", {}) or {}
        is_active = m.get("is_active", True)
        updated_at = m.get("updated_at", 0)
        created_at = m.get("created_at", 0)

        avatar_status = classify_avatar(meta)
        description = truncate(meta.get("description", ""), 80)
        system_prompt = truncate(params.get("system", ""), 100)

        temperature = params.get("temperature", "")
        top_p = params.get("top_p", "")
        custom_params = params.get("custom_params", None)
        function_calling = params.get("function_calling", "")

        entry = {
            "id": model_id,
            "name": name,
            "base_model_id": base_model_id,
            "avatar_status": avatar_status,
            "description": description,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "top_p": top_p,
            "custom_params": custom_params,
            "function_calling": function_calling,
            "is_active": is_active,
            "updated_at": format_timestamp(updated_at),
            "created_at": format_timestamp(created_at),
        }
        all_analyzed.append(entry)

        if "Custom Avatar" in avatar_status:
            models_with_custom_avatar.append(entry)
        elif "URL Avatar" in avatar_status:
            models_with_url_avatar.append(entry)
        else:
            models_without_avatar.append(entry)

    # ---- Section 1: Summary ----
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Custom/overlay models (DB) | {len(custom_models)} |")
    lines.append(f"| Base models (providers) | {len(base_models)} |")
    lines.append(f"| Models with custom avatar | {len(models_with_custom_avatar)} |")
    lines.append(f"| Models with URL avatar | {len(models_with_url_avatar)} |")
    lines.append(f"| Models without avatar | {len(models_without_avatar)} |")
    active_count = sum(1 for e in all_analyzed if e["is_active"])
    inactive_count = len(all_analyzed) - active_count
    lines.append(f"| Active models | {active_count} |")
    lines.append(f"| Inactive models | {inactive_count} |")
    lines.append("")

    # Count models with various params set
    with_system = sum(1 for e in all_analyzed if e["system_prompt"])
    with_description = sum(1 for e in all_analyzed if e["description"])
    with_base = sum(1 for e in all_analyzed if e["base_model_id"])
    with_custom_params = sum(1 for e in all_analyzed if e["custom_params"])
    with_func_calling = sum(1 for e in all_analyzed if e["function_calling"])

    lines.append("### Configuration Coverage")
    lines.append("")
    lines.append(f"| Setting | Models with it set |")
    lines.append(f"|---------|-------------------|")
    lines.append(f"| `base_model_id` | {with_base} / {len(all_analyzed)} |")
    lines.append(f"| `meta.description` | {with_description} / {len(all_analyzed)} |")
    lines.append(f"| `params.system` (system prompt) | {with_system} / {len(all_analyzed)} |")
    lines.append(f"| `params.custom_params` | {with_custom_params} / {len(all_analyzed)} |")
    lines.append(f"| `params.function_calling` | {with_func_calling} / {len(all_analyzed)} |")
    lines.append("")

    # ---- Section 2: Detailed table ----
    lines.append("## Detailed Model Inventory")
    lines.append("")
    lines.append("| # | Name | ID | Base Model | Avatar | Active | Description |")
    lines.append("|---|------|----|------------|--------|--------|-------------|")

    for i, entry in enumerate(all_analyzed, 1):
        name = escape_md(entry["name"])
        model_id = escape_md(entry["id"])
        base = escape_md(entry["base_model_id"]) if entry["base_model_id"] else "-"
        avatar = entry["avatar_status"]
        active = "Yes" if entry["is_active"] else "**No**"
        desc = escape_md(entry["description"]) if entry["description"] else "-"
        lines.append(f"| {i} | {name} | `{model_id}` | `{base}` | {avatar} | {active} | {desc} |")

    lines.append("")

    # ---- Section 3: Parameters detail ----
    lines.append("## Model Parameters")
    lines.append("")
    lines.append("| Name | System Prompt (first 100 chars) | Temp | Top-P | Function Calling | Custom Params |")
    lines.append("|------|--------------------------------|------|-------|------------------|---------------|")

    for entry in all_analyzed:
        name = escape_md(entry["name"])
        system = escape_md(entry["system_prompt"]) if entry["system_prompt"] else "-"
        temp = entry["temperature"] if entry["temperature"] != "" else "-"
        top_p = entry["top_p"] if entry["top_p"] != "" else "-"
        fc = entry["function_calling"] if entry["function_calling"] else "-"
        cp = "-"
        if entry["custom_params"]:
            cp = escape_md(truncate(json.dumps(entry["custom_params"]), 60))
        lines.append(f"| {name} | {system} | {temp} | {top_p} | {fc} | {cp} |")

    lines.append("")

    # ---- Section 4: Models missing avatars ----
    if models_without_avatar:
        lines.append("## Models Missing Avatars")
        lines.append("")
        lines.append("These models have no custom avatar (using default favicon or empty):")
        lines.append("")
        for entry in models_without_avatar:
            base_info = f" (base: `{entry['base_model_id']}`)" if entry["base_model_id"] else ""
            lines.append(f"- **{entry['name']}** — `{entry['id']}`{base_info}")
        lines.append("")

    # ---- Section 5: Models with custom avatars ----
    if models_with_custom_avatar:
        lines.append("## Models With Custom Avatars")
        lines.append("")
        for entry in models_with_custom_avatar:
            lines.append(f"- **{entry['name']}** — `{entry['id']}` — {entry['avatar_status']}")
        lines.append("")

    # ---- Section 6: Base models from providers ----
    if base_models:
        lines.append("## Base Models (Providers)")
        lines.append("")
        lines.append(f"Total base models available from configured providers: **{len(base_models)}**")
        lines.append("")

        # Group by provider prefix
        providers = {}
        for bm in base_models:
            bm_id = bm.get("id", "")
            # Provider is the part before the first dot or slash
            if "." in bm_id:
                provider = bm_id.split(".")[0]
            elif "/" in bm_id:
                provider = bm_id.split("/")[0]
            else:
                provider = "other"
            providers.setdefault(provider, []).append(bm_id)

        lines.append("| Provider | Count | Example Models |")
        lines.append("|----------|-------|----------------|")
        for provider in sorted(providers.keys()):
            ids = sorted(providers[provider])
            examples = ", ".join(f"`{m}`" for m in ids[:3])
            if len(ids) > 3:
                examples += f", ... (+{len(ids) - 3} more)"
            lines.append(f"| {provider} | {len(ids)} | {examples} |")
        lines.append("")

    # ---- Section 7: Warnings / Issues ----
    issues = []
    for entry in all_analyzed:
        if not entry["base_model_id"]:
            # Model without base_model_id: could be an override or broken
            issues.append(f"- `{entry['id']}` (**{entry['name']}**): no `base_model_id` set — may be invisible to non-admin users")
        if not entry["is_active"]:
            issues.append(f"- `{entry['id']}` (**{entry['name']}**): model is **inactive**")

    if issues:
        lines.append("## Potential Issues")
        lines.append("")
        for issue in issues:
            lines.append(issue)
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Audit all models on an Open WebUI tenant"
    )
    parser.add_argument("--url", default=None, help="Open WebUI base URL (default: MYIA_URL env)")
    parser.add_argument("--email", default=None, help="Admin email (default: MYIA_EMAIL env)")
    parser.add_argument("--password", default=None, help="Admin password (default: MYIA_PASSWORD env)")
    parser.add_argument("--output", "-o", default=None, help="Write report to file (default: stdout only)")
    args = parser.parse_args()

    # Load .env from repo root (same pattern as other scripts)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    load_env(os.path.join(repo_root, ".env"))
    load_env(os.path.join(repo_root, "myia.env"))

    base_url = (args.url or os.environ.get("MYIA_URL", "")).rstrip("/")
    email = args.email or os.environ.get("MYIA_EMAIL", "")
    password = args.password or os.environ.get("MYIA_PASSWORD", "")

    if not base_url or not email or not password:
        print("ERROR: --url, --email, --password (or MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD env vars) are required.", file=sys.stderr)
        sys.exit(1)

    # Step 1: Authenticate
    print(f"Authenticating to {base_url}...", file=sys.stderr)
    token = authenticate(base_url, email, password)
    print(f"Authenticated successfully.", file=sys.stderr)

    # Step 2: Fetch models
    print("Fetching custom/overlay models...", file=sys.stderr)
    custom_models = fetch_all_custom_models(base_url, token)
    print(f"  Found {len(custom_models)} custom/overlay models.", file=sys.stderr)

    print("Fetching base models (providers)...", file=sys.stderr)
    base_models = fetch_base_models(base_url, token)
    print(f"  Found {len(base_models)} base models.", file=sys.stderr)

    # Step 3: Generate report
    report = generate_report(custom_models, base_models, base_url)

    # Output
    print(report)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
