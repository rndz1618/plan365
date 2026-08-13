"""Database connection helpers — SQLite (default) or PostgreSQL.

Env:
  PLAN365_DB_BACKEND=sqlite|postgresql
  PLAN365_DB=/path/to/plan365.db          (sqlite)
  PLAN365_DATABASE_URL=postgresql://...   (postgresql)
"""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from typing import Any, Iterable, Optional

from app.config import (
    DB_BACKEND,
    DB_PATH,
    DATABASE_URL,
    TYPES,
    PRIORITIES,
    STATUSES,
)
from app.auth_utils import hash_pw

# Conflict targets for INSERT OR IGNORE → ON CONFLICT DO NOTHING (PostgreSQL)
_IGNORE_CONFLICT = {
    "settings": "(key)",
    "user_preferences": "(user_id)",
    "project_members": "(project_id, user_id)",
}


def is_postgres() -> bool:
    return DB_BACKEND == "postgresql"


def is_sqlite() -> bool:
    return DB_BACKEND == "sqlite"


def _adapt_sql(sql: str) -> str:
    """Translate SQLite-flavored SQL to the active backend."""
    if is_sqlite():
        return sql

    out = sql
    out = out.replace("?", "%s")
    out = re.sub(r"ON CONFLICT\s*\(", "ON CONFLICT (", out, flags=re.IGNORECASE)
    out = re.sub(r"ON CONFLICT\((\w+)\)", r"ON CONFLICT (\1)", out, flags=re.IGNORECASE)

    m = re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)", out, flags=re.IGNORECASE)
    if m:
        table = m.group(1).lower()
        out = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO",
            "INSERT INTO",
            out,
            count=1,
            flags=re.IGNORECASE,
        )
        if "ON CONFLICT" not in out.upper():
            target = _IGNORE_CONFLICT.get(table)
            if target:
                out = out.rstrip().rstrip(";") + f" ON CONFLICT {target} DO NOTHING"

    return out


class _CursorResult:
    """Unified cursor result: fetchone/fetchall/lastrowid + mapping rows."""

    def __init__(self, cursor, backend: str):
        self._cursor = cursor
        self._backend = backend
        self.lastrowid = getattr(cursor, "lastrowid", None)

    def fetchone(self):
        r = self._cursor.fetchone()
        return _as_row(r)

    def fetchall(self):
        return [_as_row(r) for r in self._cursor.fetchall()]

    def __iter__(self):
        for r in self._cursor:
            yield _as_row(r)


def _as_row(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return r
    try:
        return dict(r)
    except Exception:
        return r


class DbConn:
    """Thin connection wrapper so routers keep using c.execute / lastrowid."""

    def __init__(self, raw):
        self._raw = raw
        self._backend = DB_BACKEND

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> _CursorResult:
        sql2 = _adapt_sql(sql)
        cur = self._raw.cursor()
        if params is None:
            cur.execute(sql2)
        else:
            cur.execute(sql2, tuple(params))
        result = _CursorResult(cur, self._backend)
        if self._backend == "postgresql" and result.lastrowid in (None, 0):
            su = sql2.lstrip().upper()
            if su.startswith("INSERT") and "ON CONFLICT" not in su:
                try:
                    cur2 = self._raw.cursor()
                    cur2.execute("SELECT lastval() AS id")
                    r = cur2.fetchone()
                    if r is not None:
                        result.lastrowid = r["id"] if isinstance(r, dict) else r[0]
                except Exception:
                    pass
        return result

    def executescript(self, script: str) -> None:
        cleaned = re.sub(r"--[^\n]*", "", script)
        for stmt in cleaned.split(";"):
            s = stmt.strip()
            if s:
                self.execute(s)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def get_conn() -> DbConn:
    if is_postgres():
        if not DATABASE_URL:
            raise RuntimeError(
                "PLAN365_DB_BACKEND=postgresql requires PLAN365_DATABASE_URL "
                "(e.g. postgresql://user:pass@host:5432/plan365)"
            )
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as e:
            raise RuntimeError(
                "psycopg2-binary is required for PostgreSQL. "
                "pip install psycopg2-binary"
            ) from e
        raw = psycopg2.connect(DATABASE_URL)
        raw.autocommit = False
        raw.cursor_factory = psycopg2.extras.RealDictCursor
        return DbConn(raw)

    import sqlite3

    raw = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA journal_mode=WAL")
    raw.execute("PRAGMA busy_timeout=5000")
    raw.execute("PRAGMA foreign_keys=ON")
    return DbConn(raw)


@contextmanager
def db():
    c = get_conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def row(r):
    if r is None:
        return {}
    if isinstance(r, dict):
        return dict(r)
    try:
        return dict(r)
    except Exception:
        return {}


def _pk_ddl() -> str:
    if is_postgres():
        return "SERIAL PRIMARY KEY"
    return "INTEGER PRIMARY KEY"


def _table_columns_safe(c: DbConn, table: str) -> set:
    if is_sqlite():
        cols = set()
        for r in c.execute(f"PRAGMA table_info({table})").fetchall():
            cols.add(r["name"] if isinstance(r, dict) else r[1])
        return cols
    rows = c.execute(
        "SELECT column_name AS name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ?",
        (table,),
    ).fetchall()
    return {r["name"] for r in rows}


def init_db():
    pk = _pk_ddl()
    schema = f"""
        CREATE TABLE IF NOT EXISTS users (
            id {pk},
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            weekly_capacity INTEGER DEFAULT 40,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS projects (
            id {pk},
            name TEXT NOT NULL,
            description TEXT,
            color TEXT DEFAULT '#3b82f6',
            status TEXT DEFAULT 'Active',
            start_date TEXT,
            due_date TEXT,
            reference TEXT,
            supporting_data TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS project_members (
            id {pk},
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'editor',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id {pk},
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT,
            type TEXT NOT NULL DEFAULT 'Others',
            status TEXT NOT NULL DEFAULT 'Todo',
            priority TEXT NOT NULL DEFAULT 'Medium',
            start_date TEXT,
            due_date TEXT,
            progress INTEGER DEFAULT 0,
            effort INTEGER,
            figma_url TEXT,
            pr_url TEXT,
            labels TEXT DEFAULT '[]',
            is_milestone INTEGER DEFAULT 0,
            attachment_url TEXT,
            baseline_start TEXT,
            baseline_due TEXT,
            assignee_id INTEGER REFERENCES users(id),
            created_by INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER
        );
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            theme TEXT DEFAULT 'system',
            accent_color TEXT DEFAULT 'blue',
            default_view TEXT DEFAULT 'list',
            density TEXT DEFAULT 'comfortable',
            sidebar_collapsed INTEGER DEFAULT 0,
            items_per_page INTEGER DEFAULT 50,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id {pk},
            predecessor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            successor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            type TEXT NOT NULL DEFAULT 'FS',
            lag_days INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(predecessor_id, successor_id),
            CHECK(predecessor_id != successor_id),
            CHECK(type IN ('FS','SS','FF','SF'))
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_project_members_user ON project_members(user_id);
        CREATE INDEX IF NOT EXISTS idx_dep_pred ON task_dependencies(predecessor_id);
        CREATE INDEX IF NOT EXISTS idx_dep_succ ON task_dependencies(successor_id);
    """

    with db() as c:
        c.executescript(schema)

        defaults = {
            "app_name": "Plan365",
            "allow_registration": "true",
            "jwt_expire_hours": "24",
            "task_types": json.dumps(TYPES),
            "priorities": json.dumps(PRIORITIES),
            "statuses": json.dumps(STATUSES),
            "default_type": "Others",
            "default_priority": "Medium",
            "default_status": "Todo",
            "accent_color": "blue",
            "date_format": "YYYY-MM-DD",
            "timezone": "Asia/Jakarta",
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        try:
            cols = _table_columns_safe(c, "projects")
            for col, ddl in [
                ("status", "TEXT DEFAULT 'Active'"),
                ("start_date", "TEXT"),
                ("due_date", "TEXT"),
                ("reference", "TEXT"),
                ("supporting_data", "TEXT"),
            ]:
                if col not in cols:
                    c.execute(f"ALTER TABLE projects ADD COLUMN {col} {ddl}")
        except Exception:
            pass

        try:
            tcols = _table_columns_safe(c, "tasks")
            for col, ddl in [
                ("is_milestone", "INTEGER DEFAULT 0"),
                ("attachment_url", "TEXT"),
                ("baseline_start", "TEXT"),
                ("baseline_due", "TEXT"),
            ]:
                if col not in tcols:
                    c.execute(f"ALTER TABLE tasks ADD COLUMN {col} {ddl}")
        except Exception:
            pass

        try:
            ucols = _table_columns_safe(c, "users")
            if "weekly_capacity" not in ucols:
                c.execute("ALTER TABLE users ADD COLUMN weekly_capacity INTEGER DEFAULT 40")
        except Exception:
            pass

        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_milestone ON tasks(is_milestone)")
        except Exception:
            pass

        if not c.execute("SELECT id FROM users WHERE username=?", ("admin",)).fetchone():
            h = hash_pw("admin123")
            c.execute(
                "INSERT INTO users (username,email,hashed_password,full_name,role) VALUES (?,?,?,?,?)",
                ("admin", "admin@plan365.local", h, "Administrator", "admin"),
            )
            print(">>> Default admin created: admin / admin123")

        from app.template_service import ensure_default_templates

        ensure_default_templates(c)

    print(f">>> Plan365 DB backend: {DB_BACKEND}")
