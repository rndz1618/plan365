# Plan365 — Deploy on Linux SBC (2GB RAM)

Default login: **admin** / **admin123**  
Change `SECRET_KEY` in `app/config.py` before production.

---

## A) Native (venv + systemd)

```bash
sudo useradd -r -m -d /opt/plan365 plan365 || true
sudo mkdir -p /opt/plan365
sudo cp -a . /opt/plan365/
sudo chown -R plan365:plan365 /opt/plan365

cd /opt/plan365
sudo -u plan365 python3 -m venv .venv
sudo -u plan365 .venv/bin/pip install -r requirements.txt
sudo -u plan365 .venv/bin/python seed_demo.py

sudo cp deploy/plan365.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now plan365
```

Open: `http://SERVER_IP:8000`

---

## B) Docker Compose (SQLite default)

```bash
docker compose build
docker compose up -d
```

DB volume `plan365-data`, memory cap **256MB**, **1 worker** (SSE).

---

## C) PostgreSQL backend (optional)

| Variable | Example |
|----------|--------|
| `PLAN365_DB_BACKEND` | `postgresql` or `sqlite` (default) |
| `PLAN365_DATABASE_URL` | `postgresql://plan365:plan365@localhost:5432/plan365` |
| `PLAN365_DB` | SQLite path only |

```bash
export PLAN365_DB_BACKEND=postgresql
export PLAN365_DATABASE_URL=postgresql://plan365:plan365@postgres:5432/plan365
docker compose --profile postgres up -d --build
```

---

## D) Migrasi SQLite → PostgreSQL

Script: `migrate_sqlite_to_postgres.py`

```bash
cp plan365.db plan365.db.bak
export PLAN365_DATABASE_URL=postgresql://plan365:plan365@127.0.0.1:5432/plan365
python migrate_sqlite_to_postgres.py --sqlite ./plan365.db --dry-run
python migrate_sqlite_to_postgres.py --sqlite ./plan365.db --wipe

export PLAN365_DB_BACKEND=postgresql
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
curl -s http://127.0.0.1:8000/health
```

Tables: users → projects → project_members → tasks → task_dependencies → settings → user_preferences

Backup PG: `pg_dump -U plan365 plan365 > backup.sql`

Rollback: set `PLAN365_DB_BACKEND=sqlite` and restore `.db.bak`.
