#!/usr/bin/env python3
"""
Migration script for Open WebUI SQLite to PostgreSQL.
Non-interactive version of open-webui-postgres-migration.
"""

import sqlite3
import psycopg
import sys
from pathlib import Path

# Configuration
SQLITE_PATH = r"D:\Open-WebUI\myia-open-webui\webui_copy.db"
PG_HOST = "localhost"
PG_PORT = 5432
PG_DATABASE = "myia_db"
PG_USER = "openwebui"
PG_PASSWORD = "cRSIbO6xeAvsrGVxs0BV9tP3QNCc4tR"
BATCH_SIZE = 500

# Tables to migrate (in dependency order)
TABLES = [
    "user",
    "auth",
    "group",
    "group_member",
    "api_key",
    "config",
    "model",
    "prompt",
    "tool",
    "function",
    "memory",
    "document",
    "tag",
    "chatidtag",
    "folder",
    "chat",
    "chat_file",
    "file",
    "knowledge",
    "knowledge_file",
    "channel",
    "channel_member",
    "channel_webhook",
    "channel_file",
    "message",
    "message_reaction",
    "feedback",
    "note",
    "oauth_session",
]

def get_sqlite_tables(cursor):
    """Get list of tables in SQLite database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'migratehistory%'")
    return [row[0] for row in cursor.fetchall()]

def get_table_columns(cursor, table):
    """Get column names for a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]

def get_row_count(cursor, table):
    """Get row count for a table."""
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]

def migrate_table(sqlite_cur, pg_cur, table, batch_size=BATCH_SIZE):
    """Migrate a single table from SQLite to PostgreSQL."""
    columns = get_table_columns(sqlite_cur, table)
    if not columns:
        print(f"  Table {table}: No columns found, skipping")
        return 0

    # Get row count
    sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
    total_rows = sqlite_cur.fetchone()[0]

    if total_rows == 0:
        print(f"  Table {table}: 0 rows, skipping")
        return 0

    print(f"  Table {table}: {total_rows} rows to migrate...")

    # Build column list for SQL
    cols_str = ", ".join(f'"{col}"' for col in columns)
    placeholders = ", ".join(["%s"] * len(columns))

    # Clear existing data in PostgreSQL (in case of re-run)
    pg_cur.execute(f'TRUNCATE TABLE "{table}" CASCADE')

    # Migrate in batches
    offset = 0
    migrated = 0

    while offset < total_rows:
        sqlite_cur.execute(f"SELECT * FROM {table} LIMIT {batch_size} OFFSET {offset}")
        rows = sqlite_cur.fetchall()

        if not rows:
            break

        # Insert into PostgreSQL
        for row in rows:
            try:
                pg_cur.execute(
                    f'INSERT INTO "{table}" ({cols_str}) VALUES ({placeholders})',
                    row
                )
                migrated += 1
            except Exception as e:
                print(f"    Error inserting row: {e}")
                continue

        offset += batch_size
        print(f"    Progress: {min(offset, total_rows)}/{total_rows}")

    print(f"  Table {table}: Migrated {migrated}/{total_rows} rows")
    return migrated

def main():
    print("=" * 60)
    print("Open WebUI SQLite to PostgreSQL Migration")
    print("=" * 60)
    print(f"SQLite: {SQLITE_PATH}")
    print(f"PostgreSQL: {PG_HOST}:{PG_PORT}/{PG_DATABASE}")
    print()

    # Check SQLite file exists
    if not Path(SQLITE_PATH).exists():
        print(f"ERROR: SQLite file not found: {SQLITE_PATH}")
        sys.exit(1)

    # Connect to SQLite
    print("Connecting to SQLite...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()

    # Connect to PostgreSQL
    print("Connecting to PostgreSQL...")
    pg_conn = psycopg.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )
    pg_cur = pg_conn.cursor()

    # Get tables from SQLite
    sqlite_tables = get_sqlite_tables(sqlite_cur)
    print(f"Found {len(sqlite_tables)} tables in SQLite")

    # Migrate each table
    total_migrated = 0
    for table in TABLES:
        if table not in sqlite_tables:
            print(f"  Table {table}: Not found in SQLite, skipping")
            continue

        try:
            migrated = migrate_table(sqlite_cur, pg_cur, table)
            total_migrated += migrated
        except Exception as e:
            print(f"  ERROR migrating {table}: {e}")
            pg_conn.rollback()
            continue

    # Commit and close
    pg_conn.commit()
    sqlite_conn.close()
    pg_conn.close()

    print()
    print("=" * 60)
    print(f"Migration complete! Total rows migrated: {total_migrated}")
    print("=" * 60)

if __name__ == "__main__":
    main()
