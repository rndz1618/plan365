"""Users, settings, preferences, AI sync."""
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user, require_admin
from app.database import db, row
from app.models import PrefUpdate

router = APIRouter(tags=["settings"])

@router.get("/users")
async def list_users(u=Depends(current_user)):
    with db() as c:
        return [row(r) for r in c.execute("SELECT id,username,full_name,email,role FROM users WHERE is_active=1 ORDER BY full_name,username").fetchall()]

@router.get("/settings")
async def get_settings(u=Depends(current_user)):
    with db() as c:
        data = {r["key"]: r["value"] for r in c.execute("SELECT key,value FROM settings").fetchall()}
        for k in ("task_types", "priorities", "statuses"):
            if k in data:
                try: data[k] = json.loads(data[k])
                except: pass
        return data

@router.put("/settings")
async def put_settings(payload: Dict[str, Any], u=Depends(require_admin)):
    with db() as c:
        for k, v in payload.items():
            if isinstance(v, (list, dict)): v = json.dumps(v)
            c.execute("""INSERT INTO settings (key,value,updated_at,updated_by) VALUES (?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at, updated_by=excluded.updated_by""",
                (k, str(v), datetime.utcnow().isoformat(), u["id"]))
        return {"ok": True}


@router.get("/settings/preferences")
async def get_prefs(u=Depends(current_user)):
    with db() as c:
        r = c.execute("SELECT * FROM user_preferences WHERE user_id=?", (u["id"],)).fetchone()
        if not r:
            c.execute("INSERT INTO user_preferences (user_id) VALUES (?)", (u["id"],))
            r = c.execute("SELECT * FROM user_preferences WHERE user_id=?", (u["id"],)).fetchone()
        return row(r)

@router.put("/settings/preferences")
async def put_prefs(p: PrefUpdate, u=Depends(current_user)):
    with db() as c:
        upd = {k: v for k, v in p.dict(exclude_unset=True).items()}
        if not upd: return {"ok": True}
        c.execute("INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)", (u["id"],))
        if "sidebar_collapsed" in upd: upd["sidebar_collapsed"] = 1 if upd["sidebar_collapsed"] else 0
        upd["updated_at"] = datetime.utcnow().isoformat()
        sets = ", ".join(f"{k}=?" for k in upd)
        c.execute(f"UPDATE user_preferences SET {sets} WHERE user_id=?", (*upd.values(), u["id"]))
        return {"ok": True}

@router.get("/ai/sync")
async def ai_sync(u=Depends(current_user)):
    with db() as c:
        if u["role"] == "admin":
            projects = c.execute("SELECT * FROM projects ORDER BY name").fetchall()
        else:
            projects = c.execute("""SELECT p.* FROM projects p JOIN project_members pm ON pm.project_id=p.id
                WHERE pm.user_id=? ORDER BY p.name""", (u["id"],)).fetchall()
        out = {"synced_at": datetime.utcnow().isoformat()+"Z",
               "user": {"id": u["id"], "username": u["username"], "role": u["role"]}, "projects": []}
        for p in projects:
            tasks = c.execute("""SELECT id,title,type,status,priority,start_date,due_date,progress,effort,assignee_id,labels
                FROM tasks WHERE project_id=? ORDER BY due_date IS NULL, due_date""", (p["id"],)).fetchall()
            summary = {}
            tlist = []
            for t in tasks:
                summary[t["status"]] = summary.get(t["status"], 0) + 1
                td = row(t)
                try: td["labels"] = json.loads(td.get("labels") or "[]")
                except: td["labels"] = []
                tlist.append(td)
            out["projects"].append({"id": p["id"], "name": p["name"], "description": p["description"],
                                    "color": p["color"], "summary": summary, "tasks": tlist})
        return out

