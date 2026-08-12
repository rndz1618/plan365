from app.realtime import publish_sync
from app.template_service import find_template, expand_template_tasks, expand_task_list
"""Project routes."""
import sqlite3
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user, check_access, proj_role
from app.database import db, row
from app.models import ProjectCreate, ProjectUpdate, MemberAdd

router = APIRouter(tags=["projects"])

PROJECT_STATUSES = ("Active", "On Hold", "Completed", "Archived")

@router.get("/projects")
async def list_projects(
    status: Optional[str] = None,
    include_archived: bool = False,
    u=Depends(current_user),
):
    with db() as c:
        status_clause = ""
        params: list = []
        if status:
            status_clause = " AND COALESCE(p.status,'Active')=?"
            params.append(status)
        elif not include_archived:
            status_clause = " AND COALESCE(p.status,'Active') != 'Archived'"
        if u["role"] == "admin":
            rows = c.execute(
                f"""SELECT p.*, COUNT(t.id) as task_count FROM projects p
                    LEFT JOIN tasks t ON t.project_id=p.id
                    WHERE 1=1{status_clause}
                    GROUP BY p.id ORDER BY p.name""",
                params,
            ).fetchall()
            return [{**row(r), "role": "owner"} for r in rows]
        rows = c.execute(
            f"""SELECT p.*, pm.role, COUNT(t.id) as task_count FROM projects p
                JOIN project_members pm ON pm.project_id=p.id
                LEFT JOIN tasks t ON t.project_id=p.id
                WHERE pm.user_id=?{status_clause}
                GROUP BY p.id ORDER BY p.name""",
            [u["id"], *params],
        ).fetchall()
        return [row(r) for r in rows]

@router.post("/projects")
async def create_project(p: ProjectCreate, u=Depends(current_user)):
    status = p.status if p.status in PROJECT_STATUSES else "Active"
    with db() as c:
        cur = c.execute(
            """INSERT INTO projects (name,description,color,status,start_date,due_date,reference,supporting_data,created_by)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (p.name, p.description, p.color or "#3b82f6", status,
             p.start_date, p.due_date, p.reference, p.supporting_data, u["id"]),
        )
        pid = cur.lastrowid
        c.execute("INSERT INTO project_members (project_id,user_id,role) VALUES (?,?, 'owner')", (pid, u["id"]))
        applied = None
        custom = getattr(p, "template_tasks", None)
        if custom and isinstance(custom, list) and len(custom) > 0:
            applied = expand_task_list(
                c,
                project_id=pid,
                tasks_def=custom,
                start_date=p.start_date,
                created_by=u["id"],
            )
        elif getattr(p, "template_id", None):
            tpl = find_template(c, p.template_id)
            if tpl:
                applied = expand_template_tasks(
                    c,
                    project_id=pid,
                    template=tpl,
                    start_date=p.start_date,
                    created_by=u["id"],
                )
        d = row(c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
        d["role"] = "owner"
        d["task_count"] = (applied or {}).get("tasks_created", 0)
        d["template_applied"] = applied
        publish_sync("project.created", {"id": pid, "template_id": getattr(p, "template_id", None)})
        if applied:
            publish_sync("task.created", {"project_id": pid, "count": applied.get("tasks_created", 0)})
        return d

@router.get("/projects/{pid}")
async def get_project(pid: int, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], pid)
        r = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not r: raise HTTPException(404, "Not found")
        d = row(r)
        d["role"] = proj_role(c, u["id"], pid)
        return d

@router.put("/projects/{pid}")
async def update_project(pid: int, p: ProjectUpdate, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], pid, ["owner", "editor"])
        existing = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not existing:
            raise HTTPException(404, "Not found")
        data = row(existing)
        name = p.name if p.name is not None else data["name"]
        description = p.description if p.description is not None else data.get("description")
        color = p.color if p.color is not None else data.get("color")
        status = p.status if p.status is not None else data.get("status") or "Active"
        if status not in PROJECT_STATUSES:
            raise HTTPException(400, f"Invalid status. Use: {', '.join(PROJECT_STATUSES)}")
        start_date = p.start_date if p.start_date is not None else data.get("start_date")
        due_date = p.due_date if p.due_date is not None else data.get("due_date")
        reference = p.reference if p.reference is not None else data.get("reference")
        supporting_data = p.supporting_data if p.supporting_data is not None else data.get("supporting_data")
        c.execute(
            """UPDATE projects SET name=?, description=?, color=?, status=?, start_date=?, due_date=?,
               reference=?, supporting_data=?, updated_at=? WHERE id=?""",
            (name, description, color, status, start_date, due_date, reference, supporting_data,
             datetime.utcnow().isoformat(), pid),
        )
        publish_sync("project.updated", {"id": pid})
        return row(c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())

@router.delete("/projects/{pid}", )
async def delete_project(pid: int, cascade: bool = False, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], pid, ["owner"])
        if cascade:
            # 1) delete dependencies rows referencing this project's tasks
            c.execute("""
                DELETE FROM task_dependencies
                WHERE predecessor_id IN (SELECT id FROM tasks WHERE project_id=?)
                   OR successor_id IN (SELECT id FROM tasks WHERE project_id=?)
            """, (pid, pid))
            # 2) delete all tasks of the project
            c.execute("DELETE FROM tasks WHERE project_id=?", (pid,))
            # 3) delete memberships
            c.execute("DELETE FROM project_members WHERE project_id=?", (pid,))
        c.execute("DELETE FROM projects WHERE id=?", (pid,))
        publish_sync("project.deleted", {"id": pid, "cascade": cascade})
        return {"ok": True, "cascade": cascade}


@router.get("/projects/{pid}/members")
async def list_members(pid: int, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], pid)
        rows = c.execute("""SELECT pm.*, u.username, u.full_name, u.email FROM project_members pm
            JOIN users u ON u.id=pm.user_id WHERE pm.project_id=?""", (pid,)).fetchall()
        return [row(r) for r in rows]

@router.post("/projects/{pid}/members")
async def add_member(pid: int, p: MemberAdd, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], pid, ["owner"])
        try:
            c.execute("INSERT INTO project_members (project_id,user_id,role) VALUES (?,?,?)", (pid, p.user_id, p.role))
        except sqlite3.IntegrityError:
            raise HTTPException(400, "Already member")
        return {"ok": True}

@router.delete("/projects/{pid}/members/{uid}")
async def remove_member(pid: int, uid: int, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], pid, ["owner"])
        c.execute("DELETE FROM project_members WHERE project_id=? AND user_id=?", (pid, uid))
        return {"ok": True}





@router.post("/projects/{pid}/baseline")
async def save_project_baseline(pid: int, u=Depends(current_user)):
    """Snapshot all task plan dates in a project as baseline."""
    with db() as c:
        check_access(c, u["id"], pid, ["editor", "owner"])
        now = datetime.utcnow().isoformat()
        c.execute(
            """UPDATE tasks SET baseline_start=start_date, baseline_due=due_date, updated_at=?
               WHERE project_id=?""",
            (now, pid),
        )
        n = c.execute("SELECT changes()").fetchone()[0]
        publish_sync("project.updated", {"id": pid, "baseline": True, "tasks_updated": n})
        return {"ok": True, "project_id": pid, "tasks_updated": n}
