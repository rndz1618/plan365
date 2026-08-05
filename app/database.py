"""SQLite connection helpers and schema init."""
import json
import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH, TYPES, PRIORITIES, STATUSES
from app.auth_utils import hash_pw


def get_conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    c.execute("PRAGMA foreign_keys=ON")
    return c


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
    return dict(r) if r else {}


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL, full_name TEXT, role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT, color TEXT DEFAULT '#3b82f6',
            created_by INTEGER REFERENCES users(id), created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, role TEXT NOT NULL DEFAULT 'editor',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(project_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL, description TEXT, type TEXT NOT NULL DEFAULT 'Others', status TEXT NOT NULL DEFAULT 'Todo',
            priority TEXT NOT NULL DEFAULT 'Medium', start_date TEXT, due_date TEXT, progress INTEGER DEFAULT 0,
            effort INTEGER, figma_url TEXT, pr_url TEXT, labels TEXT DEFAULT '[]',
            assignee_id INTEGER REFERENCES users(id), created_by INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_by INTEGER
        );
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            theme TEXT DEFAULT 'system', accent_color TEXT DEFAULT 'blue', default_view TEXT DEFAULT 'list',
            density TEXT DEFAULT 'comfortable', sidebar_collapsed INTEGER DEFAULT 0, items_per_page INTEGER DEFAULT 50,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id INTEGER PRIMARY KEY,
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
        """)
        defaults = {
            "app_name": "Plan365", "allow_registration": "true", "jwt_expire_hours": "24",
            "task_types": json.dumps(TYPES), "priorities": json.dumps(PRIORITIES), "statuses": json.dumps(STATUSES),
            "default_type": "Others", "default_priority": "Medium", "default_status": "Todo",
            "accent_color": "blue", "date_format": "YYYY-MM-DD", "timezone": "Asia/Jakarta"
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        if not c.execute("SELECT id FROM users WHERE username='admin'").fetchone():
            h = hash_pw("admin123")
            c.execute(
                "INSERT INTO users (username,email,hashed_password,full_name,role) VALUES (?,?,?,?,?)",
                ("admin", "admin@plan365.local", h, "Administrator", "admin"),
            )
            print(">>> Default admin created: admin / admin123")
