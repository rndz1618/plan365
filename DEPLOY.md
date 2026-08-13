# Plan365 — Deploy on Linux SBC (2GB RAM)

Default login: **admin** / **admin123**  
Change `PLAN365_SECRET_KEY` before production.

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
sudo -u plan365 .venv/bin/python seed_demo.py   # optional

sudo cp deploy/plan365.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now plan365
```

Open: `http://SERVER_IP:8000` — logs: `journalctl -u plan365 -f`

---

## B) Docker Compose (SQLite default)

```bash
docker compose build && docker compose up -d
docker compose logs -f
```

DB volume `plan365-data`, memory **256MB**, **1 worker** (SSE).

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
# Prefer nginx :80/:443 → 127.0.0.1:8000
# Do NOT expose PostgreSQL publicly
```

---

## Backup

| Backend | Cara |
|---------|------|
| SQLite | UI Download DB / copy `plan365.db` |
| PostgreSQL | `pg_dump -U plan365 plan365 > backup.sql` |
| Docker | `docker compose exec plan365 ls /data` |

---

## Real-time (SSE)

- `GET /api/events?token=<JWT>`
- Requires **1 Uvicorn worker** (in-memory broker)
- Nginx: `proxy_buffering off` for `/api/events`

---

## D) PostgreSQL backend (optional)

Default remains **SQLite** (best for 2GB SBC).

| Variable | Example |
|----------|--------|
| `PLAN365_DB_BACKEND` | `postgresql` or `sqlite` |
| `PLAN365_DATABASE_URL` | `postgresql://plan365:SECRET@127.0.0.1:5432/plan365` |
| `POSTGRES_PASSWORD` | override compose default `plan365` |

### Existing PostgreSQL on server (recommended)

**Do not** use `--profile postgres` if host already runs Postgres.

```sql
CREATE USER plan365 WITH PASSWORD 'SECRET';
CREATE DATABASE plan365 OWNER plan365;
```

```bash
export PLAN365_DB_BACKEND=postgresql
export PLAN365_DATABASE_URL=postgresql://plan365:SECRET@127.0.0.1:5432/plan365
docker compose up -d --build
# or: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Bundled Postgres container (dev only)

```bash
export PLAN365_DB_BACKEND=postgresql
export PLAN365_DATABASE_URL=postgresql://plan365:plan365@postgres:5432/plan365
docker compose --profile postgres up -d --build
```

Port is bound to `127.0.0.1:5432` only.

---

## E) Migrasi SQLite → PostgreSQL

Script (repo root): `migrate_sqlite_to_postgres.py`

```bash
cp plan365.db plan365.db.bak
export PLAN365_DATABASE_URL=postgresql://plan365:SECRET@127.0.0.1:5432/plan365
python migrate_sqlite_to_postgres.py --sqlite ./plan365.db --dry-run
python migrate_sqlite_to_postgres.py --sqlite ./plan365.db --wipe
export PLAN365_DB_BACKEND=postgresql
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
curl -s http://127.0.0.1:8000/health
```

Copy order: users → projects → project_members → tasks → task_dependencies → settings → user_preferences

Rollback: `PLAN365_DB_BACKEND=sqlite` + restore `.db.bak`
