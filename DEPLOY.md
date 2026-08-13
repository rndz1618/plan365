# Plan365 — Deploy on Linux SBC (2GB RAM)

Default login: **admin** / **admin123**  
Change `PLAN365_SECRET_KEY` before production.

---

## A) Native (venv + systemd)

```bash
sudo useradd -r -m -d /opt/plan365 plan365 || true
sudo mkdir -p /opt/plan365
# copy source (unzip plan365-pg-source.zip or git pull)
sudo cp -a . /opt/plan365/
sudo chown -R plan365:plan365 /opt/plan365

cd /opt/plan365
sudo -u plan365 python3 -m venv .venv
sudo -u plan365 .venv/bin/pip install -r requirements.txt
sudo -u plan365 .venv/bin/python seed_demo.py   # optional

sudo cp deploy/plan365.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now plan365
sudo systemctl status plan365
```

Open: `http://SERVER_IP:8000`

```bash
journalctl -u plan365 -f
```

---

## B) Docker Compose (SQLite default)

```bash
docker compose build
docker compose up -d
docker compose logs -f
```

DB lives in volume `plan365-data`. Memory capped at **256MB**.

```bash
docker compose down
docker compose up -d --build
```

---

## C) One-shot from zip

```bash
mkdir -p /opt/plan365 && cd /opt/plan365
unzip -o plan365-pg-source.zip
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python seed_demo.py
.venv/bin/python main.py
```

---

## Firewall

```bash
sudo ufw allow 8000/tcp
# Prefer nginx reverse-proxy on :80/:443 → 127.0.0.1:8000
# Do NOT expose PostgreSQL publicly
```

---

## Backup

- UI: Settings → **Download DB backup** (admin, SQLite only)
- CLI SQLite: copy `plan365.db` (stop service first if possible)
- Docker: `docker compose exec plan365 ls /data`
- PostgreSQL: `pg_dump -U plan365 plan365 > backup.sql`

---

## Real-time (SSE)

- Endpoint: `GET /api/events?token=<JWT>`
- Requires **1 Uvicorn worker** (in-memory broker)
- Nginx: `proxy_buffering off` for `/api/events`

---

## D) PostgreSQL backend (optional)

Default remains **SQLite** (best for 2GB SBC).

### Environment

| Variable | Example | Note |
|----------|---------|------|
| `PLAN365_DB_BACKEND` | `postgresql` | or `sqlite` (default) |
| `PLAN365_DATABASE_URL` | `postgresql://plan365:SECRET@127.0.0.1:5432/plan365` | required for PG |
| `PLAN365_DB` | `/data/plan365.db` | SQLite path only |
| `POSTGRES_PASSWORD` | override default `plan365` | compose profile only |

### Existing PostgreSQL on server (no Docker Postgres)

**Do not** start compose profile `postgres` if host already runs PostgreSQL.

```sql
CREATE USER plan365 WITH PASSWORD 'SECRET';
CREATE DATABASE plan365 OWNER plan365;
```

```bash
export PLAN365_DB_BACKEND=postgresql
export PLAN365_DATABASE_URL=postgresql://plan365:SECRET@127.0.0.1:5432/plan365
docker compose up -d --build   # app only
# or: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Docker Compose + bundled Postgres

```bash
export PLAN365_DB_BACKEND=postgresql
export PLAN365_DATABASE_URL=postgresql://plan365:plan365@postgres:5432/plan365
docker compose --profile postgres up -d --build
docker compose exec plan365 python seed_demo.py
```

---

## E) Migrasi data SQLite → PostgreSQL

Script: `migrate_sqlite_to_postgres.py` (repo root only)

```bash
cp plan365.db plan365.db.bak
export PLAN365_DATABASE_URL=postgresql://plan365:SECRET@127.0.0.1:5432/plan365
python migrate_sqlite_to_postgres.py --sqlite ./plan365.db --dry-run
python migrate_sqlite_to_postgres.py --sqlite ./plan365.db --wipe
export PLAN365_DB_BACKEND=postgresql
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
curl -s http://127.0.0.1:8000/health
```

### Yang di-copy
users → projects → project_members → tasks → task_dependencies → settings → user_preferences

### Rollback
```bash
export PLAN365_DB_BACKEND=sqlite
export PLAN365_DB=/path/to/plan365.db.bak
```

---

## Firewall

```bash
sudo ufw allow 8000/tcp
# Prefer nginx :80/:443 → 127.0.0.1:8000
# Do NOT expose PostgreSQL publicly
```

## Backup

- UI: Settings → Download DB backup (admin, SQLite only)
- CLI SQLite: copy `plan365.db`
- Docker: `docker compose exec plan365 ls /data`
- PostgreSQL: `pg_dump -U plan365 plan365 > backup.sql`

## Real-time (SSE)

- `GET /api/events?token=<JWT>`
- Requires **1 Uvicorn worker**
- Nginx: `proxy_buffering off` for `/api/events`
