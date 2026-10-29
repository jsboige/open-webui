#!/usr/bin/env python3
"""
Shallow-copy knowledge bases from myia_db to other tenant databases.

Copies knowledge, file, and knowledge_file rows via direct PostgreSQL connections.
Uses the SAME KB UUIDs so tenants share Qdrant vectors without re-embedding.

The physical PDF files must be accessible from tenant containers. This script
handles only the database side. For file access, either:
  - Mount myia's uploads dir in tenant containers, OR
  - Create symlinks in each tenant's WSL data directory

Usage:
  python scripts/shallow-copy-kbs.py [--dry-run] [--tenants ece epf ...]

Prerequisites:
  - pip install psycopg2-binary (host) or run inside a container with psycopg2
  - PostgreSQL server accessible (PG_HOST, PG_PORT, PG_USER, PG_PASS in .env)
  - Target databases exist with schema (start OWUI once)
  - Target databases must have at least one admin user (log in once)
"""

import os
import sys
import json
import argparse

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not found. Install with: pip install psycopg2-binary")
    print("Or run this script inside the Open WebUI container.")
    sys.exit(1)

# Tenant definitions: (env_prefix, pg_database, admin_email)
TENANTS = {
    'ece':       ('ECE',       'ece_db',       'jsboige@omnesintervenant.com'),
    'epf':       ('EPF',       'epf_db',       'jsboige@hotmail.com'),
    'epf-genai': ('EPF_GENAI', 'epf_genai_db', 'jsboige@omnesintervenant.com'),
    'epita':     ('EPITA',     'epita_db',     'jsboige@omnesintervenant.com'),
    'esg':       ('ESG',       'esg_db',       'j.boige@intervenant-ggeedu.fr'),
    'pauwels':   ('PAUWELS',   'pauwels_db',   'jsboige@hotmail.com'),
}

SOURCE_DB = 'myia_db'


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


def get_pg_conn(dbname):
    """Connect to a PostgreSQL database."""
    return psycopg2.connect(
        host=os.environ.get('PG_HOST', 'localhost'),
        port=int(os.environ.get('PG_PORT', '5432')),
        dbname=dbname,
        user=os.environ.get('PG_USER', 'openwebui'),
        password=os.environ.get('PG_PASS', ''),
    )


def get_admin_user_id(conn, admin_email):
    """Get the user ID of the admin user in the target database."""
    cur = conn.cursor()
    cur.execute('SELECT id FROM "user" WHERE email = %s', (admin_email,))
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None


def get_myia_kbs(conn):
    """Get all knowledge bases from myia_db."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM knowledge ORDER BY name')
    kbs = cur.fetchall()
    cur.close()
    return kbs


def get_kb_files(conn, kb_id):
    """Get all file IDs associated with a knowledge base."""
    cur = conn.cursor()
    cur.execute('SELECT file_id FROM knowledge_file WHERE knowledge_id = %s', (kb_id,))
    file_ids = [row[0] for row in cur.fetchall()]
    cur.close()
    return file_ids


def get_files_by_ids(conn, file_ids):
    """Get file rows by IDs."""
    if not file_ids:
        return []
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM file WHERE id = ANY(%s)', (file_ids,))
    files = cur.fetchall()
    cur.close()
    return files


def get_knowledge_file_rows(conn, kb_id):
    """Get knowledge_file link rows for a KB."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM knowledge_file WHERE knowledge_id = %s', (kb_id,))
    rows = cur.fetchall()
    cur.close()
    return rows


def insert_row(cur, table, row_dict):
    """Insert a dict as a row into a table."""
    cols = list(row_dict.keys())
    vals = list(row_dict.values())
    # Handle JSON/dict values — psycopg2 needs Json wrapper
    for i, v in enumerate(vals):
        if isinstance(v, dict) or isinstance(v, list):
            vals[i] = psycopg2.extras.Json(v)
    cols_str = ', '.join(f'"{c}"' for c in cols)
    placeholders = ', '.join(['%s'] * len(cols))
    cur.execute(f'INSERT INTO "{table}" ({cols_str}) VALUES ({placeholders})', vals)


def copy_kb_to_tenant(source_conn, target_conn, kb, admin_user_id, dry_run):
    """Copy a single knowledge base and its files to the target database."""
    kb_id = kb['id']
    kb_name = kb['name']

    # Check if KB already exists in target
    cur = target_conn.cursor()
    cur.execute('SELECT id FROM knowledge WHERE id = %s', (kb_id,))
    exists = cur.fetchone()
    cur.close()

    if exists:
        print(f"      {kb_name}: already exists (skip)")
        return 0

    file_ids = get_kb_files(source_conn, kb_id)

    if dry_run:
        print(f"      [DRY RUN] Would copy KB: {kb_name} ({kb_id[:8]}...) with {len(file_ids)} files")
        return 1

    # Get associated data from source
    files = get_files_by_ids(source_conn, file_ids)
    kf_rows = get_knowledge_file_rows(source_conn, kb_id)

    cur = target_conn.cursor()

    try:
        # Disable FK constraints during insertion
        cur.execute("SET session_replication_role = 'replica'")

        # 1. Insert file rows (with user_id replaced)
        files_inserted = 0
        for f in files:
            # Check if file already exists (might be shared across KBs)
            cur.execute('SELECT id FROM file WHERE id = %s', (f['id'],))
            if cur.fetchone():
                continue

            f_copy = dict(f)
            f_copy['user_id'] = admin_user_id
            insert_row(cur, 'file', f_copy)
            files_inserted += 1

        # 2. Insert knowledge row (with user_id replaced)
        kb_copy = dict(kb)
        kb_copy['user_id'] = admin_user_id
        insert_row(cur, 'knowledge', kb_copy)

        # 3. Insert knowledge_file links (with user_id replaced if column exists)
        kf_inserted = 0
        for kf in kf_rows:
            kf_copy = dict(kf)
            if 'user_id' in kf_copy:
                kf_copy['user_id'] = admin_user_id
            insert_row(cur, 'knowledge_file', kf_copy)
            kf_inserted += 1

        # Re-enable FK constraints
        cur.execute("SET session_replication_role = 'origin'")
        target_conn.commit()

        print(f"      {kb_name}: OK ({files_inserted} new files, {kf_inserted} links)")
        return 1

    except Exception as e:
        target_conn.rollback()
        print(f"      {kb_name}: ERROR: {str(e)[:200]}")
        return 0


def create_symlinks_command(source_conn, kbs):
    """Generate WSL commands to create symlinks for file access."""
    print("\n=== Symlink Commands (run in WSL) ===")
    print("# These commands create symlinks so tenant containers can access myia's uploaded files.")
    print("# Run inside WSL (Ubuntu):\n")

    # Collect all unique user_id directories from file paths
    user_dirs = set()
    for kb in kbs:
        file_ids = get_kb_files(source_conn, kb['id'])
        files = get_files_by_ids(source_conn, file_ids)
        for f in files:
            path = f.get('path', '')
            if path and '/' in path:
                # path format: uploads/{user_id}/{file_id}
                parts = path.split('/')
                if len(parts) >= 2:
                    user_dirs.add(parts[1])

    myia_uploads = '/home/jesse/open-webui/uploads'
    tenant_paths = {
        'ece': '/home/jesse/ece/open-webui/uploads',
        'epf': '/home/jesse/epf/open-webui/uploads',
        'epf-genai': '/home/jesse/epf/genai-open-webui/uploads',
        'epita': '/home/jesse/Epita/open-webui/uploads',
        'esg': '/home/jesse/esg/open-webui/uploads',
        'pauwels': '/home/jesse/pauwels/open-webui/uploads',
    }

    for tenant, tenant_path in tenant_paths.items():
        print(f"# --- {tenant} ---")
        print(f"mkdir -p {tenant_path}")
        for user_dir in sorted(user_dirs):
            print(f"ln -sfn {myia_uploads}/{user_dir} {tenant_path}/{user_dir}")
        print()


def process_tenant(tenant_key, pg_db, admin_email, source_conn, kbs, args):
    """Copy all KBs to a tenant database."""
    print(f"\n{'='*60}")
    print(f"  {tenant_key} ({pg_db})")
    print(f"{'='*60}")

    try:
        target_conn = get_pg_conn(pg_db)
    except Exception as e:
        print(f"  ERROR: Cannot connect to {pg_db}: {e}")
        return

    # Find admin user ID
    admin_id = get_admin_user_id(target_conn, admin_email)
    if not admin_id:
        print(f"  ERROR: Admin user {admin_email} not found in {pg_db}")
        print(f"  (Has the admin logged in at least once?)")
        target_conn.close()
        return

    print(f"  Admin user: {admin_email} (id={admin_id[:8]}...)")
    print(f"  Copying {len(kbs)} knowledge bases...")

    copied = 0
    for kb in kbs:
        copied += copy_kb_to_tenant(source_conn, target_conn, kb, admin_id, args.dry_run)

    print(f"\n  Result: {copied}/{len(kbs)} KBs copied")
    target_conn.close()


def main():
    parser = argparse.ArgumentParser(description='Shallow-copy KBs from myia to tenants')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without executing')
    parser.add_argument('--tenants', nargs='+', choices=list(TENANTS.keys()),
                        help='Only process these tenants')
    parser.add_argument('--show-symlinks', action='store_true',
                        help='Print WSL symlink commands for file access')
    args = parser.parse_args()

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_env(env_path)

    # Connect to source database
    print(f"=== Connecting to source database: {SOURCE_DB} ===")
    try:
        source_conn = get_pg_conn(SOURCE_DB)
    except Exception as e:
        print(f"ERROR: Cannot connect to {SOURCE_DB}: {e}")
        sys.exit(1)

    # Get all KBs from myia
    kbs = get_myia_kbs(source_conn)
    print(f"  Found {len(kbs)} knowledge bases in {SOURCE_DB}")
    for kb in kbs:
        file_ids = get_kb_files(source_conn, kb['id'])
        print(f"    - {kb['name']} ({kb['id'][:8]}...): {len(file_ids)} files")

    if args.show_symlinks:
        create_symlinks_command(source_conn, kbs)
        source_conn.close()
        return

    if args.dry_run:
        print("\n=== DRY RUN MODE ===")

    # Process each tenant
    tenants_to_process = args.tenants or list(TENANTS.keys())

    for tenant_key in tenants_to_process:
        _, pg_db, admin_email = TENANTS[tenant_key]
        process_tenant(tenant_key, pg_db, admin_email, source_conn, kbs, args)

    source_conn.close()

    print(f"\n{'='*60}")
    print("Done.")
    if args.dry_run:
        print("(No changes made — re-run without --dry-run to execute)")
    print(f"\nNOTE: For file access, run with --show-symlinks to get WSL commands.")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
