# Plan365 — Deploy on Linux SBC (2GB RAM)

Default login: **admin** / **admin123**  
Change `SECRET_KEY` in `app/config.py` before production.

---

## A) Native (venv + systemd)

```bash
sudo useradd -r -m -d /opt/plan365 plan365 || true
sudo mkdir -p /opt/plan365
# copy source (unzip plan365-source.zip or git pull)
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
# logs
journalctl -u plan365 -f
```

---

## B) Docker Compose

```bash
docker compose build
docker compose up -d
docker compose logs -f
```

DB lives in volume `plan365-data`. Memory capped at **256MB**.

```bash
docker compose down          # stop
docker compose up -d --build # rebuild after code change
```

---

## C) One-shot from zip

```bash
mkdir -p /opt/plan365 && cd /opt/plan365
unzip -o plan365-source.zip
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python seed_demo.py
.venv/bin/python main.py
```

---

## Firewall

```bash
sudo ufw allow 8000/tcp
# or put nginx reverse-proxy on :80 → 127.0.0.1:8000
```

---

## Backup

- UI: Settings → **Download DB backup** (admin)
- CLI: copy `plan365.db` (stop service first if possible)
- Docker: `docker compose exec plan365 ls /data`


## Real-time (SSE)
- Endpoint: `GET /api/events?token=<JWT>`
- Status: `GET /api/events/status`
- Requires **1 Uvicorn worker** (in-memory broker). Do not scale workers without external pub/sub.
- Nginx: disable buffering for `/api/events` (`proxy_buffering off;`).


## UI kit (shadcn-inspired)
- Stylesheet: `/static/css/ui.css` (no React/Node)
- Classes: `.btn-primary|secondary|outline|ghost|destructive`, `.ui-input`, `.ui-card`, `.ui-badge-*`, `.ui-overlay`, `.ui-dialog`, `.ui-tabs`, `.ui-toast`, `.ui-menu`
- Tokens come from `app.css` `:root` / `.dark`
