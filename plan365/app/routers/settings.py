"""Users, settings, preferences, AI sync."""
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Body, Request

from app.template_service import get_templates, save_templates, ensure_default_templates
from app.templates_data import DEFAULT_TEMPLATES
from app.auth import current_user, require_admin
from app.database import db, row
from app.models import PrefUpdate

router = APIRouter(tags=["settings"])

@router.get("/users")
async def list_users(u=Depends(current_user)):
    with db() as c:
        return [row(r) for r in c.execute(
            "SELECT id,username,full_name,email,role,is_active,COALESCE(weekly_capacity,40) AS weekly_capacity FROM users WHERE is_active=1 ORDER BY full_name,username"
        ).fetchall()]


@router.post("/users")
async def create_user(payload: Dict[str, Any], u=Depends(require_admin)):
    from app.auth_utils import hash_pw
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    full_name = (payload.get("full_name") or "").strip() or None
    role = payload.get("role") or "user"
    if role not in ("user", "admin"):
        raise HTTPException(400, "Invalid role")
    if not username or not email or len(password) < 6:
        raise HTTPException(400, "username, email, and password (min 6) required")
    with db() as c:
        if c.execute("SELECT id FROM users WHERE username=? OR email=?", (username, email)).fetchone():
            raise HTTPException(400, "Username or email already exists")
        cur = c.execute(
            "INSERT INTO users (username,email,hashed_password,full_name,role) VALUES (?,?,?,?,?)",
            (username, email, hash_pw(password), full_name, role),
        )
        uid = cur.lastrowid
        c.execute("INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)", (uid,))
        return row(c.execute(
            "SELECT id,username,full_name,email,role,is_active,weekly_capacity FROM users WHERE id=?", (uid,)
        ).fetchone())


@router.patch("/users/{user_id}")
async def patch_user(user_id: int, payload: Dict[str, Any], u=Depends(require_admin)):
    with db() as c:
        target = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(404, "User not found")
        if "role" in payload:
            role = payload["role"]
            if role not in ("user", "admin"):
                raise HTTPException(400, "Invalid role")
            if user_id == u["id"] and role != "admin":
                raise HTTPException(400, "Cannot demote yourself")
            c.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        if "is_active" in payload:
            active = 1 if payload["is_active"] else 0
            if user_id == u["id"] and not active:
                raise HTTPException(400, "Cannot deactivate yourself")
            c.execute("UPDATE users SET is_active=? WHERE id=?", (active, user_id))
        if "full_name" in payload:
            c.execute("UPDATE users SET full_name=? WHERE id=?", (payload["full_name"], user_id))
        if "email" in payload and payload["email"]:
            email = str(payload["email"]).strip()
            exists = c.execute(
                "SELECT id FROM users WHERE email=? AND id!=?", (email, user_id)
            ).fetchone()
            if exists:
                raise HTTPException(400, "Email already used")
            c.execute("UPDATE users SET email=? WHERE id=?", (email, user_id))
        if "weekly_capacity" in payload:
            try:
                cap = int(payload["weekly_capacity"])
            except (TypeError, ValueError):
                raise HTTPException(400, "Invalid capacity")
            if cap < 0 or cap > 168:
                raise HTTPException(400, "Capacity 0–168 hours/week")
            c.execute("UPDATE users SET weekly_capacity=? WHERE id=?", (cap, user_id))
        if "password" in payload and payload["password"]:
            from app.auth_utils import hash_pw
            if len(str(payload["password"])) < 6:
                raise HTTPException(400, "Password min 6 chars")
            c.execute(
                "UPDATE users SET hashed_password=? WHERE id=?",
                (hash_pw(str(payload["password"])), user_id),
            )
        c.execute(
            "UPDATE users SET updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), user_id),
        )
        return row(c.execute(
            "SELECT id,username,full_name,email,role,is_active,weekly_capacity FROM users WHERE id=?", (user_id,)
        ).fetchone())

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



@router.get("/templates")
async def list_templates(u=Depends(current_user)):
    with db() as c:
        ensure_default_templates(c)
        return get_templates(c)


@router.put("/templates")
async def put_templates(request: Request, u=Depends(require_admin)):
    """Replace full template list (admin). Body: array of {id,name,description,tasks[]}."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if not isinstance(payload, list):
        raise HTTPException(400, "Expected array of templates")
    with db() as c:
        saved = save_templates(c, payload, u["id"])
        return saved


@router.post("/templates/reset")
async def reset_templates(u=Depends(require_admin)):
    with db() as c:
        saved = save_templates(c, DEFAULT_TEMPLATES, u["id"])
        return saved
