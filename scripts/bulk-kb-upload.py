#!/usr/bin/env python3
"""
Bulk upload PDFs to an Open WebUI Knowledge Base.

Designed to run on the HOST machine (not inside container) since it needs
access to Google Drive files. Uses the Open WebUI HTTP API.

Usage:
  python3 scripts/bulk-kb-upload.py --kb-id <kb_id> --dir <pdf_directory>

Environment variables (from .env):
  MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD
"""

import os
import sys
import json
import time
import glob
import argparse
import urllib.request
import urllib.error
import mimetypes
import uuid

# Load .env file manually (no dotenv dependency)
def load_env(env_path):
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


def authenticate(base_url, email, password):
    """Sign in and return JWT token."""
    data = json.dumps({'email': email, 'password': password}).encode()
    req = urllib.request.Request(
        f'{base_url}/api/v1/auths/signin',
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req)
    return json.load(resp)['token']


def multipart_encode(fields, files):
    """Build multipart/form-data body."""
    boundary = uuid.uuid4().hex
    lines = []
    for key, value in fields.items():
        lines.append(f'--{boundary}'.encode())
        lines.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        lines.append(b'')
        lines.append(value.encode() if isinstance(value, str) else value)
    for key, (filename, content, content_type) in files.items():
        lines.append(f'--{boundary}'.encode())
        lines.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'.encode())
        lines.append(f'Content-Type: {content_type}'.encode())
        lines.append(b'')
        lines.append(content)
    lines.append(f'--{boundary}--'.encode())
    lines.append(b'')
    body = b'\r\n'.join(lines)
    content_type = f'multipart/form-data; boundary={boundary}'
    return body, content_type


def upload_file(base_url, token, file_path):
    """Upload a file to Open WebUI and return file_id."""
    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or 'application/pdf'

    with open(file_path, 'rb') as f:
        file_data = f.read()

    body, ct = multipart_encode({}, {'file': (filename, file_data, content_type)})

    req = urllib.request.Request(
        f'{base_url}/api/v1/files/',
        data=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': ct
        }
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.load(resp)
    return result['id'], result.get('filename', filename)


def check_file_ready(base_url, token, file_id):
    """Check if file has been processed (content extracted).

    v0.8.2 doesn't use meta.status. Instead, we check if the file
    has a collection_name in meta (fully processed) or if data.content
    exists (text extracted, ready to add to KB).
    """
    req = urllib.request.Request(
        f'{base_url}/api/v1/files/{file_id}',
        headers={'Authorization': f'Bearer {token}'}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.load(resp)
        meta = result.get('meta', {}) or {}
        # Check if collection already assigned (fully embedded)
        if meta.get('collection_name'):
            return 'ready', len(meta.get('collection_name', ''))
        # Check if content has been extracted
        data = result.get('data', {})
        if isinstance(data, dict):
            content = data.get('content', '')
            if content and len(content) > 0:
                return 'ready', len(content)
        # Check for error in meta
        if meta.get('error'):
            return 'error', meta['error']
        return 'pending', 0
    except Exception as e:
        return 'error', str(e)


def wait_for_processing(base_url, token, file_id, max_wait=300):
    """Wait for file text extraction to complete."""
    start = time.time()
    while time.time() - start < max_wait:
        status, detail = check_file_ready(base_url, token, file_id)
        if status == 'ready':
            return True, f'{detail} chars' if isinstance(detail, int) else ''
        if status == 'error':
            return False, str(detail)
        time.sleep(3)
    return False, 'timeout'


def add_file_to_kb(base_url, token, kb_id, file_id):
    """Add a processed file to a knowledge base."""
    data = json.dumps({'file_id': file_id}).encode()
    req = urllib.request.Request(
        f'{base_url}/api/v1/knowledge/{kb_id}/file/add',
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    )
    resp = urllib.request.urlopen(req, timeout=600)
    return json.load(resp)


def main():
    parser = argparse.ArgumentParser(description='Bulk upload PDFs to Open WebUI KB')
    parser.add_argument('--kb-id', required=True, help='Knowledge Base ID')
    parser.add_argument('--dir', required=True, help='Directory containing PDFs')
    parser.add_argument('--recursive', action='store_true', help='Search subdirectories')
    parser.add_argument('--max-size-mb', type=float, default=50, help='Max file size in MB (default: 50)')
    parser.add_argument('--delay', type=float, default=2, help='Delay between uploads in seconds')
    parser.add_argument('--dry-run', action='store_true', help='List files without uploading')
    parser.add_argument('--skip-existing', action='store_true', default=True, help='Skip files already in KB')
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

    # Find PDFs
    if args.recursive:
        pattern = os.path.join(args.dir, '**', '*.pdf')
        pdf_files = glob.glob(pattern, recursive=True)
    else:
        pattern = os.path.join(args.dir, '*.pdf')
        pdf_files = glob.glob(pattern)

    # Filter by size
    max_bytes = args.max_size_mb * 1024 * 1024
    filtered = []
    skipped_size = 0
    for f in sorted(pdf_files):
        size = os.path.getsize(f)
        if size > max_bytes:
            skipped_size += 1
            print(f"  SKIP (too large: {size/1024/1024:.1f} MB): {os.path.basename(f)}")
        else:
            filtered.append(f)

    print(f"\nFound {len(filtered)} PDFs to upload ({skipped_size} skipped for size > {args.max_size_mb} MB)")
    total_size = sum(os.path.getsize(f) for f in filtered)
    print(f"Total size: {total_size/1024/1024:.1f} MB")

    if args.dry_run:
        for f in filtered:
            size = os.path.getsize(f) / 1024 / 1024
            print(f"  {size:6.1f} MB  {os.path.basename(f)}")
        print(f"\nDry run complete. Use without --dry-run to upload.")
        return

    # Authenticate
    print(f"\nAuthenticating to {base_url}...")
    token = authenticate(base_url, email, password)
    print("OK")

    # Get existing file names for skip-existing logic
    existing_files = {}
    if args.skip_existing:
        print("Fetching existing files...")
        req = urllib.request.Request(
            f'{base_url}/api/v1/files/',
            headers={'Authorization': f'Bearer {token}'}
        )
        resp = urllib.request.urlopen(req, timeout=60)
        file_data = json.load(resp)
        file_list = file_data if isinstance(file_data, list) else file_data.get('files', file_data.get('data', []))
        for f in file_list:
            meta = f.get('meta', {}) or {}
            name = meta.get('name', f.get('filename', ''))
            if name:
                existing_files[name] = f['id']
        print(f"  {len(existing_files)} existing files found")

    # Upload each file
    succeeded = 0
    failed = 0
    skipped = 0
    results = []

    for i, pdf_path in enumerate(filtered, 1):
        filename = os.path.basename(pdf_path)
        size_mb = os.path.getsize(pdf_path) / 1024 / 1024
        print(f"\n[{i}/{len(filtered)}] {filename} ({size_mb:.1f} MB)")

        # Skip if already uploaded
        if args.skip_existing and filename in existing_files:
            existing_id = existing_files[filename]
            print(f"  Already uploaded (id={existing_id[:8]}...), adding to KB...")
            try:
                add_file_to_kb(base_url, token, args.kb_id, existing_id)
                print("  OK (reused)")
                succeeded += 1
                skipped += 1
                results.append({'file': filename, 'status': 'reused', 'file_id': existing_id})
            except urllib.error.HTTPError as e:
                error_body = e.read().decode()[:200]
                if '409' in str(e.code) or 'already exists' in error_body.lower():
                    print(f"  Already in KB, skipping")
                    succeeded += 1
                    skipped += 1
                else:
                    print(f"  HTTP {e.code}: {error_body}")
                    failed += 1
            except Exception as e:
                print(f"  ERROR adding existing: {e}")
                failed += 1
            continue

        try:
            # Upload
            print(f"  Uploading...", end=" ", flush=True)
            file_id, stored_name = upload_file(base_url, token, pdf_path)
            print(f"OK (id={file_id[:8]}...)")

            # Wait for processing
            print(f"  Processing...", end=" ", flush=True)
            ok, detail = wait_for_processing(base_url, token, file_id)
            if not ok:
                print(f"FAILED: {detail}")
                failed += 1
                results.append({'file': filename, 'status': 'process_failed', 'error': detail})
                continue
            print(f"OK ({detail})")

            # Add to KB
            print(f"  Adding to KB...", end=" ", flush=True)
            add_file_to_kb(base_url, token, args.kb_id, file_id)
            print("OK")

            succeeded += 1
            results.append({'file': filename, 'status': 'ok', 'file_id': file_id})

        except urllib.error.HTTPError as e:
            error_body = e.read().decode()[:200]
            print(f"  HTTP {e.code}: {error_body}")
            failed += 1
            results.append({'file': filename, 'status': 'http_error', 'error': f'{e.code}: {error_body}'})
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
            results.append({'file': filename, 'status': 'error', 'error': str(e)})

        # Delay between uploads
        if i < len(filtered):
            time.sleep(args.delay)

    # Summary
    print("\n" + "=" * 60)
    print(f"Upload complete: {succeeded} succeeded ({skipped} reused), {failed} failed, {len(filtered)} total")
    print("=" * 60)

    if failed > 0:
        print("\nFailed files:")
        for r in results:
            if r['status'] != 'ok':
                print(f"  - {r['file']}: {r.get('error', 'unknown')}")


if __name__ == '__main__':
    main()
