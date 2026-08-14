"""CSV export and PostgreSQL backup guidance."""
import csv
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, JSONResponse

from app.auth import current_user
from app.database import db

router = APIRouter(tags=["export"])


@router.get("/export/tasks.csv")
async def export_tasks_csv(project_id: Optional[int] = None, u=Depends(current_user)):
    with db() as c:
        if u["role"] == "admin":
            filt, params = "1=1", []
        else:
            pids = [
                r["project_id"]
                for r in c.execute(
                    "SELECT project_id FROM project_members WHERE user_id=?",
                    (u["id"],),
                ).fetchall()
            ]
            if not pids:
                filt, params = "0=1", []
            else:
                filt = f"t.project_id IN ({','.join('?' * len(pids))})"
                params = list(pids)
        if project_id is not None:
            filt += " AND t.project_id=?"
            params.append(project_id)
        rows = c.execute(
            f"""
            SELECT t.id, p.name AS project, t.title, t.type, t.status, t.priority,
                   t.start_date, t.due_date, t.progress, t.effort,
                   u.username AS assignee, t.figma_url, t.pr_url
            FROM tasks t JOIN projects p ON p.id=t.project_id
            LEFT JOIN users u ON u.id=t.assignee_id
            WHERE {filt}
            ORDER BY p.name, t.due_date IS NULL, t.due_date, t.id
            """,
            params,
        ).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([
            "id", "project", "title", "type", "status", "priority",
            "start_date", "due_date", "progress", "effort",
            "assignee", "figma_url", "pr_url",
        ])
        for r in rows:
            w.writerow([
                r["id"], r["project"], r["title"], r["type"], r["status"], r["priority"],
                r["start_date"] or "", r["due_date"] or "", r["progress"] or 0,
                r["effort"] or "", r["assignee"] or "", r["figma_url"] or "", r["pr_url"] or "",
            ])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=plan365-tasks.csv"},
        )


@router.get("/backup")
async def backup_db(u=Depends(current_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Admin only")
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return JSONResponse({
        "backend": "postgresql",
        "message": "Use pg_dump for database backup.",
        "example": f"pg_dump -U plan365 plan365 > plan365-backup-{stamp}.sql",
        "docker_example": (
            "docker compose exec postgres pg_dump -U plan365 plan365 "
            f"> plan365-backup-{stamp}.sql"
        ),
    })
