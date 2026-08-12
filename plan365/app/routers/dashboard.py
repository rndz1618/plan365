"""Dashboard overview + team capacity analysis — single-query aggregates for low RAM."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.auth import current_user
from app.database import db, row

router = APIRouter(tags=["dashboard"])


def _scope(c, u) -> tuple[str, list]:
    if u["role"] == "admin":
        return "1=1", []
    pids = [
        r["project_id"]
        for r in c.execute(
            "SELECT project_id FROM project_members WHERE user_id=?", (u["id"],)
        ).fetchall()
    ]
    if not pids:
        return "0=1", []
    return f"t.project_id IN ({','.join('?' * len(pids))})", list(pids)


def _project_scope(c, u) -> tuple[str, list]:
    if u["role"] == "admin":
        return "1=1", []
    pids = [
        r["project_id"]
        for r in c.execute(
            "SELECT project_id FROM project_members WHERE user_id=?", (u["id"],)
        ).fetchall()
    ]
    if not pids:
        return "0=1", []
    return f"p.id IN ({','.join('?' * len(pids))})", list(pids)


@router.get("/dashboard")
async def dashboard(
    days: int = Query(30, ge=7, le=365),
    u=Depends(current_user),
):
    """Overview KPIs, project health, capacity analysis, upcoming work."""
    with db() as c:
        tfilt, tparams = _scope(c, u)
        pfilt, pparams = _project_scope(c, u)

        # ---- KPI counts ----
        kpi = row(
            c.execute(
                f"""
                SELECT
                  COUNT(*) AS total_tasks,
                  SUM(CASE WHEN t.status NOT IN ('Done','Handoff') THEN 1 ELSE 0 END) AS open_tasks,
                  SUM(CASE WHEN t.status IN ('Done','Handoff') THEN 1 ELSE 0 END) AS done_tasks,
                  SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                            AND t.due_date IS NOT NULL AND t.due_date < date('now') THEN 1 ELSE 0 END) AS overdue,
                  SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                            AND t.due_date IS NOT NULL
                            AND t.due_date >= date('now')
                            AND t.due_date <= date('now','+7 day') THEN 1 ELSE 0 END) AS due_week,
                  SUM(CASE WHEN t.status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress,
                  SUM(CASE WHEN COALESCE(t.is_milestone,0)=1
                            AND t.status NOT IN ('Done','Handoff') THEN 1 ELSE 0 END) AS open_milestones,
                  ROUND(AVG(CASE WHEN t.status NOT IN ('Done','Handoff') THEN t.progress END), 1) AS avg_open_progress
                FROM tasks t
                WHERE {tfilt}
                """,
                tparams,
            ).fetchone()
        ) or {}

        proj_kpi = row(
            c.execute(
                f"""
                SELECT
                  COUNT(*) AS total_projects,
                  SUM(CASE WHEN COALESCE(p.status,'Active')='Active' THEN 1 ELSE 0 END) AS active_projects,
                  SUM(CASE WHEN COALESCE(p.status,'Active')='On Hold' THEN 1 ELSE 0 END) AS on_hold,
                  SUM(CASE WHEN COALESCE(p.status,'Active')='Completed' THEN 1 ELSE 0 END) AS completed_projects,
                  SUM(CASE WHEN COALESCE(p.status,'Active')='Archived' THEN 1 ELSE 0 END) AS archived
                FROM projects p
                WHERE {pfilt}
                """,
                pparams,
            ).fetchone()
        ) or {}

        # ---- Per-project summary ----
        projects = [
            row(r)
            for r in c.execute(
                f"""
                SELECT p.id, p.name, p.color, COALESCE(p.status,'Active') AS status,
                       p.start_date, p.due_date, p.reference,
                       COUNT(t.id) AS task_count,
                       SUM(CASE WHEN t.status NOT IN ('Done','Handoff') THEN 1 ELSE 0 END) AS open_count,
                       SUM(CASE WHEN t.status IN ('Done','Handoff') THEN 1 ELSE 0 END) AS done_count,
                       SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                                 AND t.due_date IS NOT NULL AND t.due_date < date('now') THEN 1 ELSE 0 END) AS overdue_count,
                       ROUND(AVG(COALESCE(t.progress,0)), 0) AS progress
                FROM projects p
                LEFT JOIN tasks t ON t.project_id = p.id
                WHERE {pfilt} AND COALESCE(p.status,'Active') != 'Archived'
                GROUP BY p.id
                ORDER BY
                  CASE COALESCE(p.status,'Active')
                    WHEN 'Active' THEN 0 WHEN 'On Hold' THEN 1 WHEN 'Completed' THEN 2 ELSE 3 END,
                  p.name
                LIMIT 50
                """,
                pparams,
            ).fetchall()
        ]
        for p in projects:
            open_c = int(p.get("open_count") or 0)
            overdue = int(p.get("overdue_count") or 0)
            prog = float(p.get("progress") or 0)
            due = p.get("due_date")
            health = "on_track"
            if overdue > 0:
                health = "at_risk"
            if due:
                try:
                    d = datetime.strptime(due[:10], "%Y-%m-%d")
                    if d < datetime.utcnow() and open_c > 0:
                        health = "delayed"
                except ValueError:
                    pass
            if p.get("status") == "Completed" or (open_c == 0 and int(p.get("done_count") or 0) > 0):
                health = "completed"
            p["health"] = health

        # ---- Type mix (CAD/engineering) ----
        type_mix = [
            row(r)
            for r in c.execute(
                f"""
                SELECT t.type AS label,
                       COUNT(*) AS total,
                       SUM(CASE WHEN t.status NOT IN ('Done','Handoff') THEN 1 ELSE 0 END) AS open_count
                FROM tasks t
                WHERE {tfilt}
                GROUP BY t.type
                ORDER BY total DESC
                """,
                tparams,
            ).fetchall()
        ]

        # ---- Status mix ----
        status_mix = [
            row(r)
            for r in c.execute(
                f"""
                SELECT t.status AS label, COUNT(*) AS total
                FROM tasks t
                WHERE {tfilt}
                GROUP BY t.status
                ORDER BY total DESC
                """,
                tparams,
            ).fetchall()
        ]

        # ---- Capacity analysis (same rules as /workload) ----
        cap_rows = c.execute(
            f"""
            SELECT t.assignee_id,
                   u.full_name AS assignee_name, u.username AS assignee_username,
                   COALESCE(u.weekly_capacity, 40) AS weekly_capacity,
                   SUM(CASE WHEN t.status NOT IN ('Done','Handoff') THEN 1 ELSE 0 END) AS open_count,
                   SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                             THEN COALESCE(t.effort, 0) ELSE 0 END) AS effort_raw,
                   SUM(CASE WHEN t.status NOT IN ('Done','Handoff')
                             AND t.due_date IS NOT NULL AND t.due_date < date('now') THEN 1 ELSE 0 END) AS overdue_count
            FROM tasks t
            LEFT JOIN users u ON u.id = t.assignee_id
            WHERE {tfilt}
            GROUP BY t.assignee_id
            """,
            tparams,
        ).fetchall()

        capacity: List[Dict[str, Any]] = []
        team_cap = 0
        team_effort = 0
        overloaded = 0
        available_hours = 0
        for r in cap_rows:
            d = row(r)
            aid = d.get("assignee_id")
            name = d.get("assignee_name") or d.get("assignee_username") or "Unassigned"
            cap = int(d.get("weekly_capacity") or 40) if aid is not None else 0
            open_c = int(d.get("open_count") or 0)
            effort = int(d.get("effort_raw") or 0)
            estimated = False
            if effort == 0 and open_c:
                effort = open_c * 4
                estimated = True
            util = round(100.0 * effort / cap, 1) if cap > 0 else (100.0 if effort else 0.0)
            status = (
                "overloaded"
                if util > 100
                else "tight"
                if util >= 85
                else "balanced"
                if util >= 40
                else "available"
            )
            free = max(0, cap - effort) if cap else 0
            if aid is not None:
                team_cap += cap
                team_effort += effort
                available_hours += free
                if util > 100:
                    overloaded += 1
            capacity.append(
                {
                    "assignee_id": aid,
                    "assignee_name": name,
                    "weekly_capacity": cap,
                    "effort_open": effort,
                    "effort_estimated": estimated,
                    "open_count": open_c,
                    "overdue_count": int(d.get("overdue_count") or 0),
                    "utilization": util,
                    "available_hours": free,
                    "status": status,
                }
            )
        capacity.sort(key=lambda x: (-(x["utilization"] or 0), x["assignee_name"] or ""))

        team_util = round(100.0 * team_effort / team_cap, 1) if team_cap else 0.0

        # Bottlenecks: top overloaded + projects at risk
        bottlenecks = [x for x in capacity if x["status"] in ("overloaded", "tight") and x["assignee_id"]]
        free_members = [
            x for x in capacity if x["status"] == "available" and x["assignee_id"] and x["available_hours"] > 0
        ]

        # ---- Today / upcoming tasks ----
        today_tasks = [
            row(r)
            for r in c.execute(
                f"""
                SELECT t.id, t.title, t.status, t.priority, t.type, t.due_date, t.progress,
                       p.name AS project_name, u.full_name AS assignee_name
                FROM tasks t
                JOIN projects p ON p.id = t.project_id
                LEFT JOIN users u ON u.id = t.assignee_id
                WHERE {tfilt}
                  AND t.status NOT IN ('Done','Handoff')
                  AND t.due_date IS NOT NULL
                  AND t.due_date <= date('now','+7 day')
                ORDER BY t.due_date, CASE t.priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END
                LIMIT 15
                """,
                tparams,
            ).fetchall()
        ]

        done = int(kpi.get("done_tasks") or 0)
        total = int(kpi.get("total_tasks") or 0)
        overall_pct = round(100.0 * done / total, 1) if total else 0.0

        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "kpi": {
                **kpi,
                **proj_kpi,
                "overall_progress": overall_pct,
            },
            "projects": projects,
            "type_mix": type_mix,
            "status_mix": status_mix,
            "capacity": {
                "members": capacity,
                "team": {
                    "capacity_hours": team_cap,
                    "effort_open": team_effort,
                    "utilization": team_util,
                    "overloaded_members": overloaded,
                    "available_hours": available_hours,
                },
                "bottlenecks": bottlenecks[:8],
                "available": free_members[:8],
            },
            "upcoming": today_tasks,
        }
