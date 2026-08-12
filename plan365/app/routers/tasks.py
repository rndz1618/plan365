"""Task CRUD routes."""
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import current_user, check_access
from app.database import db, row
from app.config import TYPES, PRIORITIES
from app.models import TaskCreate, TaskUpdate
from app.realtime import publish_sync
from app.scheduling import cascade_fs_after_update

router = APIRouter(tags=["tasks"])

def _split_csv(val: Optional[str]):
    if not val:
        return []
    return [x.strip() for x in str(val).split(",") if x.strip()]

@router.get("/tasks")
async def list_tasks(project_id: Optional[int] = None, type: Optional[str] = None,
                     status: Optional[str] = None, priority: Optional[str] = None,
                     assignee_id: Optional[int] = None, u=Depends(current_user)):
    """Filters type/status/priority accept single value or comma-separated multi values."""
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
        types = _split_csv(type)
        statuses = _split_csv(status)
        priorities = _split_csv(priority)
        if len(types) == 1: sql += " AND t.type=?"; params.append(types[0])
        elif len(types) > 1: sql += f" AND t.type IN ({','.join('?'*len(types))})"; params.extend(types)
        if len(statuses) == 1: sql += " AND t.status=?"; params.append(statuses[0])
        elif len(statuses) > 1: sql += f" AND t.status IN ({','.join('?'*len(statuses))})"; params.extend(statuses)
        if len(priorities) == 1: sql += " AND t.priority=?"; params.append(priorities[0])
        elif len(priorities) > 1: sql += f" AND t.priority IN ({','.join('?'*len(priorities))})"; params.extend(priorities)
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
            d["is_milestone"] = bool(int(d.get("is_milestone") or 0))
            out.append(d)
        return out

@router.post("/tasks")
async def create_task(p: TaskCreate, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], p.project_id, ["editor", "owner"])
        if p.type not in TYPES: p.type = "Others"
        if p.priority not in PRIORITIES: p.priority = "Medium"
        is_ms = 1 if p.is_milestone else 0
        # milestones: zero-duration (same start/due if only one set)
        start, due = p.start_date, p.due_date
        if is_ms:
            d = due or start
            start = due = d
            progress = 0 if p.progress is None else p.progress
        else:
            progress = p.progress
        cur = c.execute("""INSERT INTO tasks (project_id,title,description,type,status,priority,start_date,due_date,
            progress,effort,figma_url,pr_url,labels,assignee_id,created_by,is_milestone,attachment_url)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.project_id, p.title, p.description, p.type, p.status, p.priority, start, due,
             progress, p.effort, p.figma_url, p.pr_url, json.dumps(p.labels or []), p.assignee_id, u["id"],
             is_ms, p.attachment_url))
        tid = cur.lastrowid
        r = c.execute("""SELECT t.*, p.name as project_name, p.color as project_color, u.full_name as assignee_name
            FROM tasks t JOIN projects p ON p.id=t.project_id LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?""", (tid,)).fetchone()
        d = row(r)
        d["labels"] = p.labels or []
        publish_sync("task.created", {"id": tid, "project_id": p.project_id})
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
        # normalize milestone + bool fields
        cascade = upd.pop("cascade_schedule", True)
        if "is_milestone" in upd:
            upd["is_milestone"] = 1 if upd["is_milestone"] else 0
        if "is_milestone" in upd:
            pass  # already normalized
            # keep zero-length if milestone
            pass
        dates_changed = ("start_date" in upd or "due_date" in upd)
        upd["updated_at"] = datetime.utcnow().isoformat()
        sets = ", ".join(f"{k}=?" for k in upd)
        c.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*upd.values(), tid))
        # milestone: force start=due if flagged
        row_ms = c.execute("SELECT is_milestone, start_date, due_date FROM tasks WHERE id=?", (tid,)).fetchone()
        if row_ms and int(row_ms["is_milestone"] or 0) == 1:
            d0 = row_ms["due_date"] or row_ms["start_date"]
            if d0:
                c.execute("UPDATE tasks SET start_date=?, due_date=? WHERE id=?", (d0, d0, tid))
        shifted = []
        if cascade and dates_changed:
            shifted = cascade_fs_after_update(c, tid)
        r = c.execute("""SELECT t.*, p.name as project_name, p.color as project_color, u.full_name as assignee_name
            FROM tasks t JOIN projects p ON p.id=t.project_id LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?""", (tid,)).fetchone()
        d = row(r)
        try: d["labels"] = json.loads(d.get("labels") or "[]")
        except: d["labels"] = []
        d["is_milestone"] = bool(int(d.get("is_milestone") or 0))
        preds = c.execute("SELECT predecessor_id FROM task_dependencies WHERE successor_id=?", (tid,)).fetchall()
        d["predecessor_ids"] = [int(x["predecessor_id"]) for x in preds]
        d["schedule_shifted"] = shifted
        publish_sync("task.updated", {"id": tid, "project_id": d.get("project_id"), "shifted": len(shifted)})
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
        publish_sync("task.updated", {"id": tid, "status": status})
        return {"ok": True, "status": status}

@router.delete("/tasks/{tid}")
async def delete_task(tid: int, u=Depends(current_user)):
    with db() as c:
        ex = c.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()
        if not ex: raise HTTPException(404, "Not found")
        check_access(c, u["id"], ex["project_id"], ["editor", "owner"])
        c.execute("DELETE FROM tasks WHERE id=?", (tid,))
        publish_sync("task.deleted", {"id": tid})
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



@router.get("/workload")
async def workload(project_id: Optional[int] = None, u=Depends(current_user)):
    """Team capacity: open load, effort hours, utilization vs weekly_capacity."""
    with db() as c:
        if u["role"] == "admin":
            filt, params = "1=1", []
        else:
            pids = [r["project_id"] for r in c.execute(
                "SELECT project_id FROM project_members WHERE user_id=?", (u["id"],)).fetchall()]
            if not pids:
                return {"assignees": [], "milestones_upcoming": [], "team": {}}
            filt = f"t.project_id IN ({','.join('?'*len(pids))})"
            params = list(pids)
        if project_id is not None:
            filt += " AND t.project_id=?"
            params.append(project_id)
        rows = c.execute(f"""
            SELECT t.assignee_id,
                   u.full_name AS assignee_name, u.username AS assignee_username,
                   COALESCE(u.weekly_capacity, 40) AS weekly_capacity,
                   SUM(CASE WHEN t.status NOT IN ('Done','Handoff') THEN 1 ELSE 0 END) AS open_count,
                   SUM(CASE WHEN t.status IN ('Done','Handoff') THEN 1 ELSE 0 END) AS done_count,
                   SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                             AND t.due_date IS NOT NULL AND t.due_date < date('now') THEN 1 ELSE 0 END) AS overdue_count,
                   SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                             AND t.due_date IS NOT NULL
                             AND t.due_date >= date('now')
                             AND t.due_date <= date('now','+7 day') THEN 1 ELSE 0 END) AS due_week_count,
                   SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                             THEN COALESCE(t.effort, 0) ELSE 0 END) AS effort_open,
                   SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                             AND t.due_date IS NOT NULL
                             AND t.due_date >= date('now')
                             AND t.due_date <= date('now','+7 day')
                             THEN COALESCE(t.effort, 0) ELSE 0 END) AS effort_week
            FROM tasks t
            LEFT JOIN users u ON u.id=t.assignee_id
            WHERE {filt}
            GROUP BY t.assignee_id
            ORDER BY effort_open DESC, open_count DESC
        """, params).fetchall()
        assignees = []
        total_cap = 0
        total_effort = 0
        total_open = 0
        overloaded = 0
        for r in rows:
            d = row(r)
            d["assignee_id"] = d.get("assignee_id")
            d["assignee_name"] = d.get("assignee_name") or d.get("assignee_username") or "Unassigned"
            cap = int(d.get("weekly_capacity") or 40)
            if d["assignee_id"] is None:
                cap = 0  # unassigned has no capacity pool
            effort = int(d.get("effort_open") or 0)
            # if effort not filled, estimate 4h per open task (engineering default)
            open_c = int(d.get("open_count") or 0)
            if effort == 0 and open_c:
                effort = open_c * 4
                d["effort_estimated"] = True
            else:
                d["effort_estimated"] = False
            d["effort_open"] = effort
            d["weekly_capacity"] = cap
            util = round(100.0 * effort / cap, 1) if cap > 0 else (100.0 if effort else 0.0)
            d["utilization"] = util
            d["available_hours"] = max(0, cap - effort) if cap else 0
            d["status"] = (
                "overloaded" if util > 100 else
                "tight" if util >= 85 else
                "balanced" if util >= 40 else
                "available"
            )
            if d["assignee_id"] is not None:
                total_cap += cap
                total_effort += effort
                total_open += open_c
                if util > 100:
                    overloaded += 1
            assignees.append(d)
        ms_params = list(params)
        milestones = c.execute(f"""
            SELECT t.id, t.title, t.due_date, t.project_id, p.name AS project_name, t.status
            FROM tasks t JOIN projects p ON p.id=t.project_id
            WHERE {filt} AND COALESCE(t.is_milestone,0)=1 AND t.status NOT IN ('Done','Handoff')
            ORDER BY t.due_date IS NULL, t.due_date
            LIMIT 20
        """, ms_params).fetchall()
        team_util = round(100.0 * total_effort / total_cap, 1) if total_cap else 0.0
        return {
            "assignees": assignees,
            "milestones_upcoming": [row(m) for m in milestones],
            "team": {
                "capacity_hours": total_cap,
                "effort_open": total_effort,
                "open_tasks": total_open,
                "utilization": team_util,
                "overloaded_members": overloaded,
            },
        }


@router.post("/tasks/{tid}/baseline")
async def save_task_baseline(tid: int, u=Depends(current_user)):
    """Snapshot current plan dates into baseline_start / baseline_due."""
    with db() as c:
        ex = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        if not ex:
            raise HTTPException(404, "Not found")
        check_access(c, u["id"], ex["project_id"], ["editor", "owner"])
        c.execute(
            "UPDATE tasks SET baseline_start=?, baseline_due=?, updated_at=? WHERE id=?",
            (ex["start_date"], ex["due_date"], datetime.utcnow().isoformat(), tid),
        )
        publish_sync("task.updated", {"id": tid, "baseline": True})
        return {
            "ok": True,
            "id": tid,
            "baseline_start": ex["start_date"],
            "baseline_due": ex["due_date"],
        }
        # note: publish after build



