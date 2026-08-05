"""Task dependency routes + cycle checks."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user, check_access
from app.database import db, row
from app.deps_graph import would_create_cycle, graph_has_cycle, _dep_adjacency
from app.models import DependencyCreate

router = APIRouter(tags=["dependencies"])

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


@router.get("/dependencies")
async def list_dependencies(project_id: Optional[int] = None, task_id: Optional[int] = None,
                            u=Depends(current_user)):
    with db() as c:
        if u["role"] == "admin":
            filt, params = "1=1", []
        else:
            pids = [r["project_id"] for r in c.execute(
                "SELECT project_id FROM project_members WHERE user_id=?", (u["id"],)).fetchall()]
            if not pids:
                return []
            filt = f"(tp.project_id IN ({','.join('?'*len(pids))}) OR ts.project_id IN ({','.join('?'*len(pids))}))"
            params = list(pids) + list(pids)
        sql = f"""
            SELECT d.*,
                   tp.title AS predecessor_title, tp.status AS predecessor_status, tp.project_id AS predecessor_project_id,
                   ts.title AS successor_title, ts.status AS successor_status, ts.project_id AS successor_project_id
            FROM task_dependencies d
            JOIN tasks tp ON tp.id = d.predecessor_id
            JOIN tasks ts ON ts.id = d.successor_id
            WHERE {filt}
        """
        if project_id is not None:
            sql += " AND (tp.project_id=? OR ts.project_id=?)"; params.extend([project_id, project_id])
        if task_id is not None:
            sql += " AND (d.predecessor_id=? OR d.successor_id=?)"; params.extend([task_id, task_id])
        sql += " ORDER BY d.id"
        return [row(r) for r in c.execute(sql, params).fetchall()]

@router.get("/tasks/{tid}/dependencies")
async def task_dependencies(tid: int, u=Depends(current_user)):
    with db() as c:
        t = c.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()
        if not t: raise HTTPException(404, "Task not found")
        check_access(c, u["id"], t["project_id"], ["viewer", "editor", "owner"])
        preds = [row(r) for r in c.execute("""
            SELECT d.*, tp.title AS predecessor_title, tp.status AS predecessor_status
            FROM task_dependencies d JOIN tasks tp ON tp.id=d.predecessor_id
            WHERE d.successor_id=?
        """, (tid,)).fetchall()]
        succs = [row(r) for r in c.execute("""
            SELECT d.*, ts.title AS successor_title, ts.status AS successor_status
            FROM task_dependencies d JOIN tasks ts ON ts.id=d.successor_id
            WHERE d.predecessor_id=?
        """, (tid,)).fetchall()]
        blocked = any(p.get("predecessor_status") not in ("Done", "Handoff") for p in preds)
        return {
            "task_id": tid,
            "predecessors": preds,
            "successors": succs,
            "blocked": blocked,
            "predecessor_ids": [p["predecessor_id"] for p in preds],
            "successor_ids": [s["successor_id"] for s in succs],
        }

@router.post("/dependencies/check-cycle")
async def check_cycle(p: DependencyCreate, u=Depends(current_user)):
    """Dry-run: would this edge create a cycle? Does not write."""
    with db() as c:
        for tid in (p.predecessor_id, p.successor_id):
            t = c.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()
            if not t: raise HTTPException(404, f"Task {tid} not found")
            check_access(c, u["id"], t["project_id"], ["viewer", "editor", "owner"])
        has, path = would_create_cycle(c, p.predecessor_id, p.successor_id)
        return {
            "would_create_cycle": has,
            "cycle_path": path,
            "predecessor_id": p.predecessor_id,
            "successor_id": p.successor_id,
        }

@router.post("/dependencies")
async def create_dependency(p: DependencyCreate, u=Depends(current_user)):
    if p.type not in ("FS", "SS", "FF", "SF"):
        p.type = "FS"
    if p.lag_days < 0:
        p.lag_days = 0
    with db() as c:
        pred = c.execute("SELECT id, project_id, title FROM tasks WHERE id=?", (p.predecessor_id,)).fetchone()
        succ = c.execute("SELECT id, project_id, title FROM tasks WHERE id=?", (p.successor_id,)).fetchone()
        if not pred or not succ:
            raise HTTPException(404, "Predecessor or successor task not found")
        check_access(c, u["id"], pred["project_id"], ["editor", "owner"])
        check_access(c, u["id"], succ["project_id"], ["editor", "owner"])
        if p.predecessor_id == p.successor_id:
            raise HTTPException(400, "Self-dependency is not allowed")
        exists = c.execute(
            "SELECT id FROM task_dependencies WHERE predecessor_id=? AND successor_id=?",
            (p.predecessor_id, p.successor_id)).fetchone()
        if exists:
            raise HTTPException(409, "Dependency already exists")
        has_cycle, cycle_path = would_create_cycle(c, p.predecessor_id, p.successor_id)
        if has_cycle:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Adding this dependency would create a cycle",
                    "cycle_path": cycle_path,
                    "predecessor_id": p.predecessor_id,
                    "successor_id": p.successor_id,
                },
            )
        cur = c.execute(
            "INSERT INTO task_dependencies (predecessor_id, successor_id, type, lag_days) VALUES (?,?,?,?)",
            (p.predecessor_id, p.successor_id, p.type, p.lag_days),
        )
        return _dep_row(c, cur.lastrowid)

@router.delete("/dependencies/{dep_id}")
async def delete_dependency(dep_id: int, u=Depends(current_user)):
    with db() as c:
        d = c.execute("SELECT * FROM task_dependencies WHERE id=?", (dep_id,)).fetchone()
        if not d: raise HTTPException(404, "Not found")
        t = c.execute("SELECT project_id FROM tasks WHERE id=?", (d["successor_id"],)).fetchone()
        if t:
            check_access(c, u["id"], t["project_id"], ["editor", "owner"])
        c.execute("DELETE FROM task_dependencies WHERE id=?", (dep_id,))
        return {"ok": True}

@router.get("/dependencies/graph")
async def dependency_graph(project_id: Optional[int] = None, u=Depends(current_user)):
    """Full edge list + cycle status for AI/sync and Gantt."""
    with db() as c:
        if u["role"] == "admin":
            filt, params = "1=1", []
        else:
            pids = [r["project_id"] for r in c.execute(
                "SELECT project_id FROM project_members WHERE user_id=?", (u["id"],)).fetchall()]
            if not pids:
                return {"edges": [], "has_cycle": False, "cycle_path": None, "edge_count": 0}
            filt = f"(tp.project_id IN ({','.join('?'*len(pids))}) OR ts.project_id IN ({','.join('?'*len(pids))}))"
            params = list(pids) + list(pids)
        sql = f"""
            SELECT d.*,
                   tp.title AS predecessor_title, tp.status AS predecessor_status,
                   ts.title AS successor_title, ts.status AS successor_status
            FROM task_dependencies d
            JOIN tasks tp ON tp.id = d.predecessor_id
            JOIN tasks ts ON ts.id = d.successor_id
            WHERE {filt}
        """
        if project_id is not None:
            sql += " AND (tp.project_id=? OR ts.project_id=?)"; params.extend([project_id, project_id])
        edges = [row(r) for r in c.execute(sql, params).fetchall()]
        adj = _dep_adjacency(c)
        has, path = graph_has_cycle(adj)
        return {
            "edges": edges,
            "has_cycle": has,
            "cycle_path": path,
            "edge_count": len(edges),
        }

