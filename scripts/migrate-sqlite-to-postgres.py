#!/usr/bin/env python3
"""
Migration script for Open WebUI SQLite to PostgreSQL.

Designed to run INSIDE the Open WebUI container where both sqlite3
and psycopg2 are available, and the SQLite DB is at /app/backend/data/webui.db.

Usage (from host):
  docker exec myia-open-webui-open-webui-1 python3 /app/backend/data/migrate.py

Or copy into container first:
  docker cp scripts/migrate-sqlite-to-postgres.py myia-open-webui-open-webui-1:/tmp/migrate.py
  docker exec myia-open-webui-open-webui-1 python3 /tmp/migrate.py

Pre-requisites:
  1. PostgreSQL server running and accessible at hostname 'postgres'
  2. Target database created (e.g. myia_db) with tables created by Alembic
     (start Open WebUI once with DATABASE_URL pointing to PostgreSQL)
  3. Open WebUI container has psycopg2 installed (ships by default)
"""

import sqlite3
import psycopg2
import sys
import os

# === Configuration ===
# Can be overridden via environment variables
SQLITE_PATH = os.environ.get("SQLITE_PATH", "/app/backend/data/webui.db")
PG_HOST = os.environ.get("PG_HOST", "postgres")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ.get("PG_DB", "myia_db")
PG_USER = os.environ.get("PG_USER", "openwebui")
PG_PASS = os.environ.get("PG_PASS", "cRSIbO6xeAvsrGVxs0BV9tP3QNCc4tR")

# Tables in dependency order (FK constraints respected)
TABLES = [
    "user", "auth", "config",
    "group", "group_member", "api_key",
    "model", "prompt", "tool", "function", "memory", "document",
    "tag", "chatidtag",
    "folder", "chat", "file", "chat_file",
    "knowledge", "knowledge_file",
    "channel", "channel_member", "channel_webhook", "channel_file",
    "message", "message_reaction",
    "feedback", "note", "oauth_session",
]

# Boolean columns in PostgreSQL that store 0/1 in SQLite
BOOL_COLS = {
    "auth": {"active"},
    "channel": {"is_private"},
    "channel_member": {"is_active", "is_channel_muted", "is_channel_pinned"},
    "chat": {"archived", "pinned"},
    "folder": {"is_expanded"},
    "function": {"is_active", "is_global"},
    "prompt": {"is_active"},
    "message": {"is_pinned"},
    "model": {"is_active"},
}


def get_pg_columns(pg_cur, table):
    """Get column names from PostgreSQL table."""
    pg_cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
    """, (table,))
    return [r[0] for r in pg_cur.fetchall()]


def get_sqlite_columns(sqlite_cur, table):
    """Get column names from SQLite table."""
    sqlite_cur.execute(f"PRAGMA table_info([{table}])")
    return [r[1] for r in sqlite_cur.fetchall()]


def main():
    print("=" * 60)
    print("Open WebUI SQLite -> PostgreSQL Migration")
    print("=" * 60)
    print(f"SQLite: {SQLITE_PATH}")
    print(f"PostgreSQL: {PG_HOST}:{PG_PORT}/{PG_DB}")
    print()

    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite file not found: {SQLITE_PATH}")
        sys.exit(1)

    # Connect
    print("Connecting to SQLite...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()

    print("Connecting to PostgreSQL...")
    pg_conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS
    )
    pg_conn.autocommit = False
    pg_cur = pg_conn.cursor()

    # Disable FK constraints during migration
    pg_cur.execute("SET session_replication_role = 'replica'")

    total_migrated = 0
    errors = []

    for table in TABLES:
        # Check table exists in SQLite
        sqlite_cur.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if sqlite_cur.fetchone()[0] == 0:
            print(f"  {table}: not in SQLite, skip")
            continue

        # Get common columns
        sqlite_cols = get_sqlite_columns(sqlite_cur, table)
        pg_cols = get_pg_columns(pg_cur, table)
        common_cols = [c for c in sqlite_cols if c in pg_cols]

        if not common_cols:
            print(f"  {table}: no common columns, skip")
            continue

        # Count rows
        sqlite_cur.execute(f"SELECT COUNT(*) FROM [{table}]")
        row_count = sqlite_cur.fetchone()[0]
        if row_count == 0:
            print(f"  {table}: 0 rows, skip")
            continue

        print(f"  {table}: {row_count} rows...", end=" ", flush=True)

        # Truncate PG table (safe for re-runs)
        pg_cur.execute(f'TRUNCATE TABLE "{table}" CASCADE')

        # Build INSERT
        cols_str = ", ".join(f'"{c}"' for c in common_cols)
        placeholders = ", ".join(["%s"] * len(common_cols))
        insert_sql = f'INSERT INTO "{table}" ({cols_str}) VALUES ({placeholders})'

        # Boolean column indexes for this table
        bool_set = BOOL_COLS.get(table, set())
        bool_indexes = [i for i, c in enumerate(common_cols) if c in bool_set]

        # Fetch all rows and insert
        select_cols = ", ".join(f"[{c}]" for c in common_cols)
        sqlite_cur.execute(f"SELECT {select_cols} FROM [{table}]")

        migrated = 0
        for row in sqlite_cur.fetchall():
            row_list = list(row)

            # Convert boolean 0/1 -> True/False
            for idx in bool_indexes:
                val = row_list[idx]
                if val is not None:
                    row_list[idx] = bool(val)

            try:
                pg_cur.execute("SAVEPOINT row_sp")
                pg_cur.execute(insert_sql, row_list)
                pg_cur.execute("RELEASE SAVEPOINT row_sp")
                migrated += 1
            except Exception as e:
                err_msg = f"{table}: {str(e)[:150]}"
                if err_msg not in errors:
                    errors.append(err_msg)
                pg_cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                continue

        print(f"OK ({migrated}/{row_count})")
        total_migrated += migrated

    # Re-enable FK constraints
    pg_cur.execute("SET session_replication_role = 'origin'")

    # Commit
    pg_conn.commit()

    print()
    print("=" * 60)
    print(f"Migration complete: {total_migrated} total rows migrated")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    print("=" * 60)

    # Verification
    print("\nVerification (row counts):")
    mismatches = 0
    for table in TABLES:
        try:
            sqlite_cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            sq_count = sqlite_cur.fetchone()[0]
        except Exception:
            sq_count = 0
        if sq_count == 0:
            continue

        pg_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        pg_count = pg_cur.fetchone()[0]
        status = "OK" if sq_count == pg_count else "MISMATCH"
        if status == "MISMATCH":
            mismatches += 1
        print(f"  {table}: SQLite={sq_count} PG={pg_count} [{status}]")

    if mismatches > 0:
        print(f"\nWARNING: {mismatches} table(s) with row count mismatch!")
    else:
        print("\nAll tables match!")

    sqlite_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
