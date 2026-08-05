"""Project routes."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user, check_access, proj_role
from app.database import db, row
from app.models import ProjectCreate, MemberAdd

router = APIRouter(tags=["projects"])

@router.get("/projects")
async def list_projects(u=Depends(current_user)):
    with db() as c:
        if u["role"] == "admin":
            rows = c.execute("SELECT p.*, COUNT(t.id) as task_count FROM projects p LEFT JOIN tasks t ON t.project_id=p.id GROUP BY p.id ORDER BY p.name").fetchall()
            return [{**row(r), "role": "owner"} for r in rows]
        rows = c.execute("""SELECT p.*, pm.role, COUNT(t.id) as task_count FROM projects p
            JOIN project_members pm ON pm.project_id=p.id LEFT JOIN tasks t ON t.project_id=p.id
            WHERE pm.user_id=? GROUP BY p.id ORDER BY p.name""", (u["id"],)).fetchall()
        return [row(r) for r in rows]

@router.post("/projects")
async def create_project(p: ProjectCreate, u=Depends(current_user)):
    with db() as c:
        cur = c.execute("INSERT INTO projects (name,description,color,created_by) VALUES (?,?,?,?)",
                        (p.name, p.description, p.color, u["id"]))
        pid = cur.lastrowid
        c.execute("INSERT INTO project_members (project_id,user_id,role) VALUES (?,?, 'owner')", (pid, u["id"]))
        d = row(c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
        d["role"] = "owner"
        d["task_count"] = 0
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
async def update_project(pid: int, p: ProjectCreate, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], pid, ["owner"])
        c.execute("UPDATE projects SET name=?, description=?, color=?, updated_at=? WHERE id=?",
                  (p.name, p.description, p.color, datetime.utcnow().isoformat(), pid))
        return row(c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())

@router.delete("/projects/{pid}")
async def delete_project(pid: int, u=Depends(current_user)):
    with db() as c:
        check_access(c, u["id"], pid, ["owner"])
        c.execute("DELETE FROM projects WHERE id=?", (pid,))
        return {"ok": True}


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



