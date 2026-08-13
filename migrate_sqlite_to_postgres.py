#!/usr/bin/env python3
"""
Migrate Plan365 data from SQLite → PostgreSQL.

Usage:
  export PLAN365_DATABASE_URL=postgresql://plan365:plan365@localhost:5432/plan365
  python migrate_sqlite_to_postgres.py [--sqlite /path/to/plan365.db] [--wipe]

Options:
  --sqlite PATH   Source SQLite file (default: PLAN365_DB or ./plan365.db)
  --wipe          Truncate target tables before copy (DESTRUCTIVE)
  --dry-run       Count rows only, no writes

Preserves primary keys and foreign keys. Safe to re-run with --wipe.
After success, run app with:
  PLAN365_DB_BACKEND=postgresql
  PLAN365_DATABASE_URL=...
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

TABLES = [
    ("users", "id"),
    ("projects", "id"),
    ("project_members", "id"),
    ("tasks", "id"),
    ("task_dependencies", "id"),
    ("settings", None),
    ("user_preferences", None),
]


def connect_sqlite(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"SQLite file not found: {path}")
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def connect_pg(url: str):
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        raise SystemExit("Install psycopg2-binary: pip install psycopg2-binary")
    if not url:
        raise SystemExit("Set PLAN365_DATABASE_URL")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def ensure_pg_schema(pg_url: str) -> None:
    os.environ["PLAN365_DB_BACKEND"] = "postgresql"
    os.environ["PLAN365_DATABASE_URL"] = pg_url
    for mod in list(sys.modules):
        if mod == "app.config" or mod.startswith("app.database"):
            del sys.modules[mod]
    from app.database import init_db
    init_db()
    print(">>> PostgreSQL schema ready")


def column_names(sqlite_cur, table: str):
    return [r[1] for r in sqlite_cur.execute(f"PRAGMA table_info({table})").fetchall()]


def pg_columns(pg_cur, table: str):
    pg_cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
        (table,),
    )
    return {r[0] for r in pg_cur.fetchall()}


def wipe_pg(pg) -> None:
    cur = pg.cursor()
    for table, _ in reversed(TABLES):
        cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
    pg.commit()
    print(">>> Target tables truncated")


def copy_table(sqlite_conn, pg, table: str, id_col, dry_run: bool) -> int:
    sc = sqlite_conn.cursor()
    rows = sc.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        print(f"  {table}: 0 rows")
        return 0
    src_cols = column_names(sc, table)
    if dry_run:
        print(f"  {table}: would copy {len(rows)} rows ({', '.join(src_cols)})")
        return len(rows)
    pc = pg.cursor()
    dst_cols = pg_columns(pc, table)
    cols = [c for c in src_cols if c in dst_cols]
    if not cols:
        print(f"  {table}: no matching columns, skip")
        return 0
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(cols)
    if id_col and id_col in cols:
        conflict = f"({id_col})"
        updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c != id_col)
        if updates:
            sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT {conflict} DO UPDATE SET {updates}"
        else:
            sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT {conflict} DO NOTHING"
    elif table == "settings":
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT (key) DO UPDATE SET " + ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c != "key")
    elif table == "user_preferences":
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT (user_id) DO UPDATE SET " + ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c != "user_id")
    else:
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    batch = [tuple(r[c] for c in cols) for r in rows]
    pc.executemany(sql, batch)
    if id_col and id_col in cols:
        pc.execute(
            f"SELECT setval(pg_get_serial_sequence(%s, %s), COALESCE((SELECT MAX({id_col}) FROM {table}), 1))",
            (table, id_col),
        )
    print(f"  {table}: copied {len(batch)} rows")
    return len(batch)


def main():
    parser = argparse.ArgumentParser(description="Plan365 SQLite → PostgreSQL migration")
    parser.add_argument("--sqlite", default=os.environ.get("PLAN365_DB") or str(Path(__file__).resolve().parent / "plan365.db"))
    parser.add_argument("--url", default=os.environ.get("PLAN365_DATABASE_URL") or os.environ.get("DATABASE_URL"))
    parser.add_argument("--wipe", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sqlite_path = Path(args.sqlite)
    print(f"Source SQLite : {sqlite_path}")
    print(f"Target PG URL : {args.url or '(missing)'}")
    if not args.dry_run:
        ensure_pg_schema(args.url)
    sqlite_conn = connect_sqlite(sqlite_path)
    pg = None if args.dry_run else connect_pg(args.url)
    try:
        if not args.dry_run and args.wipe:
            wipe_pg(pg)
        total = 0
        print(">>> Copying tables")
        for table, id_col in TABLES:
            total += copy_table(sqlite_conn, pg, table, id_col, args.dry_run)
        if not args.dry_run:
            pg.commit()
            print(f">>> Migration complete ({total} rows).")
            print("Start with PLAN365_DB_BACKEND=postgresql and PLAN365_DATABASE_URL set.")
        else:
            print(f">>> Dry-run done ({total} rows would be copied).")
    except Exception:
        if pg is not None:
            pg.rollback()
        raise
    finally:
        sqlite_conn.close()
        if pg is not None:
            pg.close()


if __name__ == "__main__":
    main()
