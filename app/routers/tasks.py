"""Task CRUD routes."""
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import current_user, check_access
from app.database import db, row
from app.config import TYPES, PRIORITIES
from app.models import TaskCreate, TaskUpdate

router = APIRouter(tags=["tasks"])

@router.get("/tasks")
async def list_tasks(project_id: Optional[int] = None, type: Optional[str] = None,
                     status: Optional[str] = None, priority: Optional[str] = None,
                     assignee_id: Optional[int] = None, u=Depends(current_user)):
    with db() as c:
        if u["role"] == "admin":
            filt, params = "1=1", []
        else:
            pids = [r["project_id"] for r in c.execute("SELECT project_id FROM project_members WHERE user_id=?", (u["id"],)).fetchall()]
            if not pids: return []
            filt = f"t.project_id IN ({','.join('?'*len(pids))})"
            params = list(pids)
        sql = f"""SELECT t.*, p.name as project_name, p.color as project_color,
                  u.full_name as assignee_name, u.username as assignee_username
                  FROM tasks t JOIN projects p ON p.id=t.project_id
                  LEFT JOIN users u ON u.id=t.assignee_id WHERE {filt}"""
        if project_id is not None: sql += " AND t.project_id=?"; params.append(project_id)
        if type: sql += " AND t.type=?"; params.append(type)
        if status: sql += " AND t.status=?"; params.append(status)
        if priority: sql += " AND t.priority=?"; params.append(priority)
        if assignee_id is not None: sql += " AND t.assignee_id=?"; params.append(assignee_id)
        sql += " ORDER BY t.due_date IS NULL, t.due_date, t.id DESC"
        rows = c.execute(sql, params).fetchall()
        # batch load dependencies for Gantt / blocked badge
        dep_rows = c.execute("SELECT predecessor_id, successor_id FROM task_dependencies").fetchall()
        preds_map = {}
        for dr in dep_rows:
            preds_map.setdefault(int(dr["successor_id"]), []).append(int(dr["predecessor_id"]))
        out = []
        for r in rows:
            d = row(r)
            try: d["labels"] = json.loads(d.get("labels") or "[]")
            except: d["labels"] = []
            d["predecessor_ids"] = preds_map.get(int(d["id"]), [])
            out.append(d)
        return out

@router.post("/tasks")
async def create_task(p: TaskCreate, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], p.project_id, ["editor", "owner"])
        if p.type not in TYPES: p.type = "Others"
        if p.priority not in PRIORITIES: p.priority = "Medium"
        cur = c.execute("""INSERT INTO tasks (project_id,title,description,type,status,priority,start_date,due_date,
            progress,effort,figma_url,pr_url,labels,assignee_id,created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.project_id, p.title, p.description, p.type, p.status, p.priority, p.start_date, p.due_date,
             p.progress, p.effort, p.figma_url, p.pr_url, json.dumps(p.labels or []), p.assignee_id, u["id"]))
        tid = cur.lastrowid
        r = c.execute("""SELECT t.*, p.name as project_name, p.color as project_color, u.full_name as assignee_name
            FROM tasks t JOIN projects p ON p.id=t.project_id LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?""", (tid,)).fetchone()
        d = row(r)
        d["labels"] = p.labels or []
        return d

@router.put("/tasks/{tid}")
async def update_task(tid: int, p: TaskUpdate, u=Depends(current_user)):
    with db() as c:
        ex = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        if not ex: raise HTTPException(404, "Not found")
        check_access(c, u["id"], ex["project_id"], ["editor", "owner"])
        upd = {k: v for k, v in p.dict(exclude_unset=True).items()}
        if "labels" in upd and upd["labels"] is not None: upd["labels"] = json.dumps(upd["labels"])
        if not upd: raise HTTPException(400, "No fields")
        if upd.get("status") in ("Done", "Handoff"):
            preds = c.execute("""
                SELECT tp.id, tp.title, tp.status FROM task_dependencies d
                JOIN tasks tp ON tp.id = d.predecessor_id
                WHERE d.successor_id=? AND tp.status NOT IN ('Done','Handoff')
            """, (tid,)).fetchall()
            if preds:
                raise HTTPException(409, {
                    "message": "Task is blocked by unfinished predecessors",
                    "blocked_by": [{"id": r["id"], "title": r["title"], "status": r["status"]} for r in preds],
                })
        upd["updated_at"] = datetime.utcnow().isoformat()
        sets = ", ".join(f"{k}=?" for k in upd)
        c.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*upd.values(), tid))
        r = c.execute("""SELECT t.*, p.name as project_name, p.color as project_color, u.full_name as assignee_name
            FROM tasks t JOIN projects p ON p.id=t.project_id LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?""", (tid,)).fetchone()
        d = row(r)
        try: d["labels"] = json.loads(d.get("labels") or "[]")
        except: d["labels"] = []
        preds = c.execute("SELECT predecessor_id FROM task_dependencies WHERE successor_id=?", (tid,)).fetchall()
        d["predecessor_ids"] = [int(x["predecessor_id"]) for x in preds]
        return d

@router.patch("/tasks/{tid}/status")
async def patch_status(tid: int, status: str = Query(...), u=Depends(current_user)):
    with db() as c:
        ex = c.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()
        if not ex: raise HTTPException(404, "Not found")
        check_access(c, u["id"], ex["project_id"], ["editor", "owner"])
        if status in ("Done", "Handoff"):
            preds = c.execute("""
                SELECT tp.id, tp.title, tp.status FROM task_dependencies d
                JOIN tasks tp ON tp.id = d.predecessor_id
                WHERE d.successor_id=? AND tp.status NOT IN ('Done','Handoff')
            """, (tid,)).fetchall()
            if preds:
                raise HTTPException(409, {
                    "message": "Task is blocked by unfinished predecessors",
                    "blocked_by": [{"id": r["id"], "title": r["title"], "status": r["status"]} for r in preds],
                })
        c.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?", (status, datetime.utcnow().isoformat(), tid))
        return {"ok": True, "status": status}

@router.delete("/tasks/{tid}")
async def delete_task(tid: int, u=Depends(current_user)):
    with db() as c:
        ex = c.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()
        if not ex: raise HTTPException(404, "Not found")
        check_access(c, u["id"], ex["project_id"], ["editor", "owner"])
        c.execute("DELETE FROM tasks WHERE id=?", (tid,))
        return {"ok": True}

# ---- Task dependencies + cycle detection ----

def _dep_row(c, dep_id):
    r = c.execute("""
        SELECT d.*,
               tp.title AS predecessor_title, tp.status AS predecessor_status,
               ts.title AS successor_title, ts.status AS successor_status
        FROM task_dependencies d
        JOIN tasks tp ON tp.id = d.predecessor_id
        JOIN tasks ts ON ts.id = d.successor_id
        WHERE d.id=?
    """, (dep_id,)).fetchone()
    return row(r)

