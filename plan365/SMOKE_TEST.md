# Plan365 — Smoke Test Checklist

Default login: **admin / admin123** (ganti segera setelah test).

## 0. Start

### Docker
```bash
unzip plan365-source.zip -d plan365 && cd plan365
docker compose up -d --build
curl -s http://127.0.0.1:8000/health
```

### Local (venv)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn python-jose bcrypt python-multipart
python main.py
# open http://127.0.0.1:8000
```

### Seed dummy data
```bash
# container
docker compose exec app python seed_demo.py
# local
python seed_demo.py
```

---

## 1. Auth
- [ ] Login admin/admin123 → dashboard
- [ ] Logout → login lagi
- [ ] Wrong password → error (bukan 500)

## 2. Projects
- [ ] Sidebar filter **Active only** menampilkan project aktif
- [ ] Buat project baru (warna + status)
- [ ] Settings → Project management → edit start/due/reference
- [ ] Set project **Archived** → hilang dari Active filter

## 3. Tasks (Table)
- [ ] Inline edit title / status / priority
- [ ] Filter type / status / priority
- [ ] Badge **type** berwarna (2D CAD, CAD, CAM, Tools, Others)
- [ ] Open task detail → save

## 4. Milestone & attachment
- [ ] Detail → centang **Milestone** → save → badge ◆ MS di list
- [ ] Isi **Attachment / file link** → save → data tetap

## 5. Dependencies
- [ ] Detail task B → add predecessor A (FS)
- [ ] Coba set B = Done sementara A belum Done → **blocked** (409/toast)
- [ ] Self-loop / cycle ditolak

## 6. Kanban
- [ ] Drag card antar kolom
- [ ] Drag ke Done saat blocked → ditolak

## 7. Calendar
- [ ] Task dengan due_date muncul di tanggal benar

## 8. Gantt
- [ ] Switch Day / Week / Month (cepat, tanpa freeze lama)
- [ ] Collapse / expand group + side list
- [ ] Label tanggal header terbaca (teks terang di header gelap)
- [ ] **Cascade ON** → geser due predecessor → successor maju
- [ ] **Cascade OFF** → successor tidak ikut
- [ ] **Baseline** (project) → baseline_start/due terisi
- [ ] Export **SVG** / **PNG** terunduh

## 9. Workload
- [ ] Sidebar → Workload
- [ ] Kartu assignee: open / overdue / this week
- [ ] Upcoming milestones tampil

## 10. Settings
- [ ] Theme / accent
- [ ] Task parameters (types, statuses, priorities)
- [ ] User list (admin)

## 11. API quick
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin&password=admin123' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/projects | head -c 200
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/workload | head -c 300
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/tasks | head -c 200
```

## 12. Production notes (setelah smoke OK)
```bash
# ganti secret
export PLAN365_SECRET_KEY="$(openssl rand -hex 32)"
# ganti password admin lewat UI Settings / users
# backup
cp data/plan365.db "backup/plan365-$(date +%F).db"
```

Pass criteria: semua kotak 1–11 OK, tidak ada 500, memory container stabil (<300MB target).
