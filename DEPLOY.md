# Plan365 — Deploy (PostgreSQL only)

Default login: **admin** / **admin123**  
Set `PLAN365_SECRET_KEY` and DB password before production.

## Requirements

- PostgreSQL 14+
- `PLAN365_DATABASE_URL=postgresql://USER:PASS@HOST:5432/DBNAME`

SQLite is **not supported**.

## Docker Compose

```bash
cd /opt/plan365
docker compose up -d --build
curl -s http://127.0.0.1:8000/health
docker compose exec plan365 python seed_demo.py
```

Default URL: `postgresql://plan365:plan365@postgres:5432/plan365`  
Postgres port: `127.0.0.1:5432` only · App 256m · 1 worker

## Existing host PostgreSQL

```sql
CREATE USER plan365 WITH PASSWORD 'SECRET';
CREATE DATABASE plan365 OWNER plan365;
```

```bash
export PLAN365_DATABASE_URL=postgresql://plan365:SECRET@127.0.0.1:5432/plan365
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

## Migrate legacy SQLite (one-time)

```bash
export PLAN365_DATABASE_URL=postgresql://...
python migrate_sqlite_to_postgres.py --sqlite ./plan365.db --wipe
```

## Backup

```bash
pg_dump -U plan365 plan365 > backup.sql
```
