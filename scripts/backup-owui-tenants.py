#!/usr/bin/env python3
"""Backup all Open WebUI tenant PostgreSQL databases (custom-format pg_dump).

Fills the RPO gap found 2026-07-09: the machine's only scheduled PG backup
(`Postgres-Dump-Daily`) targets the roo-state-manager `unified_store` DB on a
different instance (`postgres_production`). The 7 OWUI tenant DBs on
`open-webui-postgres` had no automated backup — only manual pre-upgrade
snapshots (last 2026-07-01). This script is the reusable, on-demand equivalent.

It does NOT schedule itself. Wire it into a scheduler (Task Scheduler / cron)
only after choosing storage location, retention, and cadence.

Design mirrors D:/postgres/myia_postgres/scripts/backup-pgdump.ps1 (poison-guard,
empty-guard, retention) but:
  - dumps via `docker exec ... pg_dump -Fc -f <tmp>` + `docker cp` (robust; avoids
    the PowerShell binary-pipe corruption that forces that script's cp fallback),
  - needs no password (container-local trust auth on the postgres socket),
  - poison-guards on OWUI's "user" table (OWUI has no `conversations` table).

Usage:
    python scripts/backup-owui-tenants.py                 # all 7 tenants -> backups/owui-daily/<date>/
    python scripts/backup-owui-tenants.py --globals       # + pg_dumpall --globals-only (roles)
    python scripts/backup-owui-tenants.py --keep-days 30   # prune date dirs older than 30 days
    python scripts/backup-owui-tenants.py --dry-run        # plan only, no dump/copy

Exit codes: 0 all dumps valid; 1 one or more DBs failed (poison-guard / empty / error).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys
from pathlib import Path

DEFAULT_CONTAINER = "open-webui-postgres"
DEFAULT_USER = "openwebui"
DEFAULT_DBS = [
    "myia_db",
    "epf_db",
    "esg_db",
    "ece_db",
    "epf_genai_db",
    "epita_db",
    "pauwels_db",
]
# A valid custom-format (-Fc) dump is never tiny; an empty-schema dump is ~8 KB.
# A populated OWUI tenant DB is tens of MB. Guard well below the smallest real one.
MIN_DUMP_BYTES = 50_000
PGDMP_MAGIC = b"PGDMP"


def _run(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True)


def poison_guard(container: str, user: str, db: str, min_users: int) -> tuple[bool, int]:
    """Refuse to back up a possibly-wiped DB. Returns (ok, user_count)."""
    cp = _run(["docker", "exec", container, "psql", "-U", user, "-d", db,
               "-tAc", 'SELECT count(*) FROM "user";'])
    if cp.returncode != 0:
        raise RuntimeError(f"poison-guard query failed: {cp.stderr.strip() or cp.stdout.strip()}")
    count = int((cp.stdout or "0").strip() or "0")
    return count >= min_users, count


def dump_db(container: str, user: str, db: str, dest_dir: Path, stamp: str,
            dry_run: bool) -> tuple[bool, int, str]:
    """Dump one DB to dest_dir/<db>.dump. Returns (ok, size_bytes, message)."""
    tmp_in_container = f"/tmp/{db}-{stamp}.dump"
    host_path = dest_dir / f"{db}.dump"
    if dry_run:
        return True, 0, f"(dry-run) would dump {db} -> {host_path}"

    dump = _run(["docker", "exec", container, "pg_dump", "-U", user, "-d", db,
                 "-Fc", "-f", tmp_in_container])
    if dump.returncode != 0:
        return False, 0, f"pg_dump failed: {dump.stderr.strip() or dump.stdout.strip()}"

    # Size + magic-byte validation inside the container before copying out.
    stat = _run(["docker", "exec", container, "stat", "-c", "%s", tmp_in_container])
    size = int((stat.stdout or "0").strip() or "0") if stat.returncode == 0 else 0
    magic = _run(["docker", "exec", container, "head", "-c", "5", tmp_in_container])
    ok_magic = (magic.stdout or "").encode("latin-1", "ignore").startswith(PGDMP_MAGIC)

    if size < MIN_DUMP_BYTES or not ok_magic:
        _run(["docker", "exec", container, "rm", "-f", tmp_in_container])
        return False, size, f"invalid dump (size={size} magic_ok={ok_magic})"

    dest_dir.mkdir(parents=True, exist_ok=True)
    cp = _run(["docker", "cp", f"{container}:{tmp_in_container}", str(host_path)])
    _run(["docker", "exec", container, "rm", "-f", tmp_in_container])
    if cp.returncode != 0:
        return False, size, f"docker cp failed: {cp.stderr.strip()}"
    return True, size, str(host_path)


def dump_globals(container: str, user: str, dest_dir: Path, dry_run: bool) -> str:
    """pg_dumpall --globals-only (roles/tablespaces) — needed for a full restore."""
    host_path = dest_dir / "globals.sql"
    if dry_run:
        return f"(dry-run) would dump globals -> {host_path}"
    cp = _run(["docker", "exec", container, "pg_dumpall", "-U", user, "--globals-only"])
    if cp.returncode != 0:
        return f"WARN: globals dump failed: {cp.stderr.strip()}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    host_path.write_text(cp.stdout, encoding="utf-8")
    return str(host_path)


def prune(root: Path, keep_days: int) -> int:
    """Delete date-named dirs older than keep_days. Returns count deleted."""
    if keep_days <= 0 or not root.exists():
        return 0
    import shutil
    kept = sorted(
        (d for d in root.iterdir() if d.is_dir() and _is_date(d.name)),
        key=lambda d: d.name, reverse=True,
    )[:keep_days]
    keep_names = {d.name for d in kept}
    deleted = 0
    for d in root.iterdir():
        if d.is_dir() and _is_date(d.name) and d.name not in keep_names:
            shutil.rmtree(d, ignore_errors=True)
            deleted += 1
    return deleted


def _is_date(name: str) -> bool:
    try:
        _dt.datetime.strptime(name, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Backup OWUI tenant PostgreSQL DBs (pg_dump -Fc).")
    ap.add_argument("--out-dir", default="backups/owui-daily",
                    help="Backup root (gitignored under backups/). A <date>/ subdir is created.")
    ap.add_argument("--container", default=DEFAULT_CONTAINER)
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--dbs", nargs="*", default=DEFAULT_DBS, help="Tenant DB names.")
    ap.add_argument("--min-users", type=int, default=1,
                    help="Poison-guard: skip a DB whose \"user\" table has fewer rows (default 1).")
    ap.add_argument("--globals", action="store_true", help="Also dump pg_dumpall --globals-only.")
    ap.add_argument("--keep-days", type=int, default=0, help="Prune date dirs older than N (0=keep all).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    stamp = _dt.datetime.now().strftime("%Y%m%d")
    today = _dt.datetime.now().strftime("%Y-%m-%d")
    root = Path(args.out_dir)
    dest_dir = root / today

    print(f"=== OWUI tenant backup — container={args.container} dest={dest_dir} "
          f"{'(DRY-RUN)' if args.dry_run else ''} ===")
    results = []
    for db in args.dbs:
        try:
            ok_guard, users = poison_guard(args.container, args.user, db, args.min_users)
        except Exception as e:  # noqa: BLE001
            print(f"  {db:<14} ERROR   poison-guard: {e}")
            results.append((db, False))
            continue
        if not ok_guard:
            print(f"  {db:<14} SKIP    poison-guard tripped (users={users} < {args.min_users})")
            results.append((db, False))
            continue
        ok, size, msg = dump_db(args.container, args.user, db, dest_dir, stamp, args.dry_run)
        mb = f"{size / 1_048_576:.1f}MB" if size else "-"
        print(f"  {db:<14} {'OK ' if ok else 'FAIL':<7} users={users:<5} {mb:<9} {msg if not ok else ''}".rstrip())
        results.append((db, ok))

    if args.globals:
        print(f"  globals        {dump_globals(args.container, args.user, dest_dir, args.dry_run)}")

    if args.keep_days and not args.dry_run:
        deleted = prune(root, args.keep_days)
        print(f"  retention: kept {args.keep_days} newest date dirs, deleted {deleted}")

    ok_count = sum(1 for _, ok in results if ok)
    print(f"=== SUMMARY: {ok_count}/{len(results)} tenant DBs backed up "
          f"{'(dry-run)' if args.dry_run else 'to ' + str(dest_dir)} ===")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
