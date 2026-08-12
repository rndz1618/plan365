# Plan365

**Lightweight self-hosted project & task manager** for Design & Engineering (CAD/CAM) teams.  
Optimized for **Linux single-board computers with ~2GB RAM**.

> Updated: 2026-08-07

## Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (async, 1 worker) |
| Database | SQLite (WAL, single file) |
| Auth | JWT + bcrypt, multi-role |
| Frontend | Alpine.js + local CSS (no Node build) |
| Charts | Frappe Gantt, SortableJS Kanban |
| Realtime | Server-Sent Events (`/api/events`) |
| AI | Local planner + optional OpenAI-compatible LLM |

## Features

- Multi-project, multi-user (admin / editor / viewer)
- Task types: **2D CAD · CAD · CAM · Tools · Others**
- Views: **Dashboard · Table · Kanban · Calendar · Gantt · Projects · Capacity · AI Planning**
- Project **task templates** (6 CAD/CAM presets) + edit-before-create wizard
- Dependencies (FS + lag), cycle detection, cascade schedule, critical path
- Team capacity (effort, weekly capacity, utilization)
- Theme: light-first (ClickUp / Monday style) + dark mode
- UI kit: shadcn-inspired components (`static/css/ui.css`)
- CSV export, DB backup (admin)

## Quick start (Docker)

```bash
unzip plan365-source.zip && cd plan365
docker compose up -d --build
# http://SERVER_IP:8000
```

Default login: **`admin` / `admin123`**

### Seed demo data

```bash
docker compose exec plan365 python -c "
from pathlib import Path
import seed_demo
seed_demo.DB = Path('/data/plan365.db')
seed_demo.main()
"
```

## Native run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python seed_demo.py
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

**Always use 1 worker** (SSE is in-memory).

## Environment

| Variable | Default | Note |
|----------|---------|------|
| `PLAN365_DB` | `./plan365.db` | SQLite path |
| `PLAN365_SECRET_KEY` | (dev) | **Change in production** |
| `PLAN365_JWT_HOURS` | `24` | Token TTL |
| `PLAN365_AI_KEY` | — | Optional LLM API key |
| `PLAN365_AI_URL` | OpenAI v1 | Compatible base URL |
| `PLAN365_AI_MODEL` | `gpt-4o-mini` | Model name |

## AI Planning

| Endpoint | Purpose |
|----------|---------|
| `GET /api/ai/sync` | Workspace snapshot JSON for agents |
| `GET /api/ai/analyze` | Local risks, actions, focus queue |
| `POST /api/ai/chat` | Chat (local always; LLM if enabled) |
| `GET/PUT /api/ai/settings` | Provider config (admin) |

Local heuristics work offline (no GPU / no model weights). Enable external LLM in the **AI Planning** page when needed.

## API

- Swagger: `/api/docs`
- Health: `/health`
- Static diagnostics: `/diag`
- Realtime SSE: `/api/events?token=<JWT>`

## Project layout

```text
plan365/
  main.py
  app/
    config.py database.py auth.py models.py
    deps_graph.py scheduling.py template_service.py
    ai_engine.py realtime.py templates_data.py
    routers/ (auth, projects, tasks, dependencies, settings,
              export, dashboard, realtime, ai)
  static/
    index.html
    css/ app.css utilities.css ui.css frappe-gantt.css
    js/ alpine.min.js app.js gantt.js deps.js kanban.js
        Sortable.min.js frappe-gantt.min.js
  Dockerfile docker-compose.yml
  deploy/plan365.service
  seed_demo.py DEPLOY.md SMOKE_TEST.md
```

## Documentation

- [DEPLOY.md](./DEPLOY.md) — Docker, systemd, troubleshooting
- [SMOKE_TEST.md](./SMOKE_TEST.md) — manual test checklist
- Notion hub (workspace): *Plan365 — Project & Task Manager*  
  - Architecture · Features & UI · Deploy & Operations

## Production checklist

- [ ] Set `PLAN365_SECRET_KEY`
- [ ] Change admin password
- [ ] Nginx + HTTPS; `proxy_buffering off` for `/api/events`
- [ ] Backup `plan365.db` regularly
- [ ] Keep **1** uvicorn worker
- [ ] Hard-refresh browser after UI updates (`Ctrl+Shift+R`)

## License

Private / internal use unless otherwise stated by the repository owner.
