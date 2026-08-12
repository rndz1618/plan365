"""SQLite connection helpers and schema init."""
import json
"""SQLAlchemy connection helpers and schema init."""
import json
import sqlite3
import os
from contextlib import contextmanager

from app.config import DB_PATH, TYPES, PRIORITIES, STATUSES
from app.auth_utils import hash_pw
from app.template_service import ensure_default_templates

# Database configuration from environment
USE_POSTGRES = os.environ.get("USE_POSTGRES", "false").lower() == "true"
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "plan365")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")


def get_conn():
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.extras import DictCursor
        
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            cursor_factory=DictCursor
        )
        conn.autocommit = False
        return conn
    else:
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
        if USE_POSTGRES:
            # PostgreSQL schema initialization
            c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                weekly_capacity INTEGER DEFAULT 40,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                color VARCHAR(20) DEFAULT '#3b82f6',
                status VARCHAR(50) DEFAULT 'Active',
                start_date VARCHAR(20),
                due_date VARCHAR(20),
                reference TEXT,
                supporting_data TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS project_members (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role VARCHAR(50) NOT NULL DEFAULT 'editor',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                type VARCHAR(50) NOT NULL DEFAULT 'Others',
                status VARCHAR(50) NOT NULL DEFAULT 'Todo',
                priority VARCHAR(20) NOT NULL DEFAULT 'Medium',
                start_date VARCHAR(20),
                due_date VARCHAR(20),
                progress INTEGER DEFAULT 0,
                effort INTEGER,
                figma_url VARCHAR(500),
                pr_url VARCHAR(500),
                labels JSON DEFAULT '[]'::json,
                is_milestone INTEGER DEFAULT 0,
                attachment_url VARCHAR(500),
                baseline_start VARCHAR(20),
                baseline_due VARCHAR(20),
                assignee_id INTEGER REFERENCES users(id),
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER
            );
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                theme VARCHAR(20) DEFAULT 'system',
                accent_color VARCHAR(20) DEFAULT 'blue',
                default_view VARCHAR(20) DEFAULT 'list',
                density VARCHAR(20) DEFAULT 'comfortable',
                sidebar_collapsed INTEGER DEFAULT 0,
                items_per_page INTEGER DEFAULT 50,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS task_dependencies (
                id SERIAL PRIMARY KEY,
                predecessor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                successor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                type VARCHAR(2) NOT NULL DEFAULT 'FS',
                lag_days INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
            CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_milestone ON tasks(is_milestone);
            """)
        else:
            # SQLite schema initialization (existing code)
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL, full_name TEXT, role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER DEFAULT 1, weekly_capacity INTEGER DEFAULT 40,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT, color TEXT DEFAULT '#3b82f6',
                status TEXT DEFAULT 'Active', start_date TEXT, due_date TEXT,
                reference TEXT, supporting_data TEXT,
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
                is_milestone INTEGER DEFAULT 0,
                attachment_url TEXT,
                baseline_start TEXT, baseline_due TEXT,
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

        # Migrate projects columns on existing DBs
        if USE_POSTGRES:
            cols = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'projects'").fetchall()}
        else:
            cols = {r[1] for r in c.execute("PRAGMA table_info(projects)").fetchall()}

        for col, ddl in [
            ("status", "TEXT DEFAULT 'Active'"),
            ("start_date", "TEXT"),
            ("due_date", "TEXT"),
            ("reference", "TEXT"),
            ("supporting_data", "TEXT"),
        ]:
            if col not in cols:
                if USE_POSTGRES:
                    c.execute(f"ALTER TABLE projects ADD COLUMN IF NOT EXISTS {col} {ddl}")
                else:
                    c.execute(f"ALTER TABLE projects ADD COLUMN {col} {ddl}")

        if USE_POSTGRES:
            tcols = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'tasks'").fetchall()}
        else:
            tcols = {r[1] for r in c.execute("PRAGMA table_info(tasks)").fetchall()}

        for col, ddl in [
            ("is_milestone", "INTEGER DEFAULT 0"),
            ("attachment_url", "TEXT"),
            ("baseline_start", "TEXT"),
            ("baseline_due", "TEXT"),
        ]:
            if col not in tcols:
                if USE_POSTGRES:
                    c.execute(f"ALTER TABLE tasks ADD COLUMN IF NOT EXISTS {col} {ddl}")
                else:
                    c.execute(f"ALTER TABLE tasks ADD COLUMN {col} {ddl}")

        if USE_POSTGRES:
            c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_milestone ON tasks(is_milestone)")
        else:
            c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_milestone ON tasks(is_milestone)")

        if USE_POSTGRES:
            ucols = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'").fetchall()}
        else:
            ucols = {r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()}

        if "weekly_capacity" not in ucols:
            if USE_POSTGRES:
                c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_capacity INTEGER DEFAULT 40")
            else:
                c.execute("ALTER TABLE users ADD COLUMN weekly_capacity INTEGER DEFAULT 40")

        if not c.execute("SELECT id FROM users WHERE username='admin'").fetchone():
            h = hash_pw("admin123")
            c.execute(
                "INSERT INTO users (username,email,hashed_password,full_name,role) VALUES (?,?,?,?,?)",
                ("admin", "admin@plan365.local", h, "Administrator", "admin"),
            )
            print(">>> Default admin created: admin / admin123")

        ensure_default_templates(c)
