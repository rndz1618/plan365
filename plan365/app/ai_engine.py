"""AI planning helpers — local heuristics + optional OpenAI-compatible chat.

Designed for 2GB SBC: no local LLM weights. External API is optional.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.database import row


def _today() -> datetime:
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d")
    except ValueError:
        return None


def build_snapshot(c, user: dict) -> Dict[str, Any]:
    """Structured package for AI agents / external tools."""
    if user.get("role") == "admin":
        projects = c.execute("SELECT * FROM projects ORDER BY name").fetchall()
    else:
        projects = c.execute(
            """SELECT p.* FROM projects p
               JOIN project_members pm ON pm.project_id=p.id
               WHERE pm.user_id=? ORDER BY p.name""",
            (user["id"],),
        ).fetchall()

    users = {
        r["id"]: row(r)
        for r in c.execute(
            "SELECT id,username,full_name,role,COALESCE(weekly_capacity,40) AS weekly_capacity FROM users WHERE is_active=1"
        ).fetchall()
    }
    deps = [
        {"predecessor_id": r["predecessor_id"], "successor_id": r["successor_id"], "type": r["type"], "lag_days": r["lag_days"]}
        for r in c.execute("SELECT predecessor_id, successor_id, type, lag_days FROM task_dependencies").fetchall()
    ]

    out_projects = []
    for p in projects:
        tasks = c.execute(
            """SELECT id,title,type,status,priority,start_date,due_date,progress,effort,
                      assignee_id,labels,is_milestone,project_id
               FROM tasks WHERE project_id=? ORDER BY due_date IS NULL, due_date""",
            (p["id"],),
        ).fetchall()
        summary: Dict[str, int] = {}
        tlist = []
        for t in tasks:
            summary[t["status"]] = summary.get(t["status"], 0) + 1
            td = row(t)
            try:
                td["labels"] = json.loads(td.get("labels") or "[]")
            except Exception:
                td["labels"] = []
            tlist.append(td)
        out_projects.append(
            {
                "id": p["id"],
                "name": p["name"],
                "description": p.get("description"),
                "status": p.get("status") or "Active",
                "color": p.get("color"),
                "start_date": p.get("start_date"),
                "due_date": p.get("due_date"),
                "summary": summary,
                "tasks": tlist,
            }
        )

    return {
        "synced_at": datetime.utcnow().isoformat() + "Z",
        "schema_version": "plan365-ai-1",
        "user": {"id": user["id"], "username": user.get("username"), "role": user.get("role")},
        "users": list(users.values()),
        "dependencies": deps,
        "projects": out_projects,
    }


def analyze_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based planning analysis — works offline, zero RAM model cost."""
    today = _today()
    week = today + timedelta(days=7)

    insights: List[Dict[str, Any]] = []
    risks: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    schedule_hints: List[Dict[str, Any]] = []

    # Index tasks
    all_tasks: List[Dict[str, Any]] = []
    for p in snap.get("projects") or []:
        for t in p.get("tasks") or []:
            tt = dict(t)
            tt["_project_id"] = p["id"]
            tt["_project_name"] = p["name"]
            all_tasks.append(tt)

    task_by_id = {t["id"]: t for t in all_tasks if t.get("id") is not None}
    preds: Dict[int, List[int]] = {}
    for d in snap.get("dependencies") or []:
        preds.setdefault(int(d["successor_id"]), []).append(int(d["predecessor_id"]))

    open_statuses = {"Todo", "In Progress", "Review", "Testing", "Blocked", "Handoff"}
    done_statuses = {"Done", "Handoff"}  # Handoff counted open above for safety; treat Done only
    done_statuses = {"Done"}

    overdue = []
    due_week = []
    blocked = []
    unassigned = []
    high_open = []

    effort_by_user: Dict[Any, float] = {}
    capacity_by_user = {
        u["id"]: float(u.get("weekly_capacity") or 40) for u in (snap.get("users") or [])
    }

    for t in all_tasks:
        st = t.get("status") or "Todo"
        if st in done_statuses:
            continue
        due = _parse_date(t.get("due_date"))
        if due and due < today:
            overdue.append(t)
        elif due and due <= week:
            due_week.append(t)
        if st == "Blocked":
            blocked.append(t)
        # dependency blocked
        pred_ids = preds.get(int(t["id"]), [])
        open_preds = [
            task_by_id[pid]
            for pid in pred_ids
            if pid in task_by_id and (task_by_id[pid].get("status") not in done_statuses)
        ]
        if open_preds and st not in done_statuses:
            blocked.append(t) if t not in blocked else None
            risks.append(
                {
                    "severity": "high",
                    "code": "dep_blocked",
                    "title": f"Blocked by dependency: {t.get('title')}",
                    "detail": f"Waiting on: {', '.join(p.get('title') or '?' for p in open_preds[:3])}",
                    "task_id": t.get("id"),
                    "project_id": t.get("_project_id"),
                }
            )
        if not t.get("assignee_id") and st not in done_statuses:
            unassigned.append(t)
        if (t.get("priority") or "") == "High" and st not in done_statuses:
            high_open.append(t)
        aid = t.get("assignee_id")
        if aid is not None:
            effort_by_user[aid] = effort_by_user.get(aid, 0) + float(t.get("effort") or 0)

    if overdue:
        risks.append(
            {
                "severity": "critical",
                "code": "overdue",
                "title": f"{len(overdue)} overdue task(s)",
                "detail": ", ".join((t.get("title") or "?")[:40] for t in overdue[:5]),
                "task_ids": [t["id"] for t in overdue[:20]],
            }
        )
        actions.append(
            {
                "priority": 1,
                "action": "Reschedule or complete overdue tasks first",
                "why": "Overdue work blocks downstream CAD/CAM handoffs",
                "task_ids": [t["id"] for t in overdue[:10]],
            }
        )

    if due_week:
        insights.append(
            {
                "type": "deadline",
                "title": f"{len(due_week)} task(s) due within 7 days",
                "detail": ", ".join((t.get("title") or "?")[:40] for t in due_week[:5]),
            }
        )
        actions.append(
            {
                "priority": 2,
                "action": "Focus capacity on this-week deadlines",
                "why": "Protect near-term delivery dates",
                "task_ids": [t["id"] for t in due_week[:10]],
            }
        )

    overloaded = []
    for uid, effort in effort_by_user.items():
        cap = capacity_by_user.get(uid, 40)
        util = (effort / cap * 100) if cap else 0
        if util > 100:
            name = next(
                (
                    (u.get("full_name") or u.get("username") or str(uid))
                    for u in (snap.get("users") or [])
                    if u["id"] == uid
                ),
                str(uid),
            )
            overloaded.append({"user_id": uid, "name": name, "effort": effort, "capacity": cap, "utilization": round(util, 1)})
            risks.append(
                {
                    "severity": "high",
                    "code": "overload",
                    "title": f"Over capacity: {name}",
                    "detail": f"{effort:.0f}h effort vs {cap:.0f}h weekly capacity ({util:.0f}%)",
                    "user_id": uid,
                }
            )
            actions.append(
                {
                    "priority": 2,
                    "action": f"Rebalance load from {name} (or raise capacity)",
                    "why": f"Utilization {util:.0f}% exceeds weekly capacity",
                    "user_id": uid,
                }
            )

    if unassigned:
        insights.append(
            {
                "type": "assignment",
                "title": f"{len(unassigned)} open task(s) without assignee",
                "detail": "Assign owners to improve accountability",
            }
        )
        actions.append(
            {
                "priority": 3,
                "action": "Assign owners to unassigned open tasks",
                "why": "Unowned work tends to slip",
                "task_ids": [t["id"] for t in unassigned[:10]],
            }
        )

    if high_open:
        schedule_hints.append(
            {
                "hint": "Prioritize High priority open tasks on the critical path",
                "tasks": [
                    {
                        "id": t["id"],
                        "title": t.get("title"),
                        "project": t.get("_project_name"),
                        "due_date": t.get("due_date"),
                        "status": t.get("status"),
                    }
                    for t in sorted(
                        high_open,
                        key=lambda x: (_parse_date(x.get("due_date")) or datetime.max, x.get("title") or ""),
                    )[:8]
                ],
            }
        )

    # Project health
    for p in snap.get("projects") or []:
        tasks = p.get("tasks") or []
        if not tasks:
            insights.append({"type": "empty_project", "title": f"Project “{p.get('name')}” has no tasks", "project_id": p["id"]})
            continue
        open_n = sum(1 for t in tasks if (t.get("status") not in done_statuses))
        done_n = len(tasks) - open_n
        progress = round(100 * done_n / len(tasks)) if tasks else 0
        pdue = _parse_date(p.get("due_date"))
        if pdue and pdue < today and open_n:
            risks.append(
                {
                    "severity": "critical",
                    "code": "project_overdue",
                    "title": f"Project past due: {p.get('name')}",
                    "detail": f"{open_n} open tasks after project due {p.get('due_date')}",
                    "project_id": p["id"],
                }
            )

    # Suggested focus order (heuristic score)
    def score(t: Dict[str, Any]) -> Tuple:
        due = _parse_date(t.get("due_date"))
        overdue_days = (today - due).days if due and due < today else 0
        pri = {"High": 0, "Medium": 1, "Low": 2}.get(t.get("priority") or "Medium", 1)
        return (-overdue_days, pri, due or datetime.max)

    focus = sorted(
        [t for t in all_tasks if (t.get("status") not in done_statuses)],
        key=score,
    )[:12]

    actions.sort(key=lambda a: a.get("priority", 99))
    risks.sort(key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r.get("severity"), 9))

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "engine": "plan365-local-heuristics",
        "summary": {
            "projects": len(snap.get("projects") or []),
            "open_tasks": sum(1 for t in all_tasks if t.get("status") not in done_statuses),
            "overdue": len(overdue),
            "due_this_week": len(due_week),
            "unassigned": len(unassigned),
            "overloaded_members": len(overloaded),
        },
        "risks": risks[:30],
        "insights": insights[:20],
        "recommended_actions": actions[:15],
        "schedule_hints": schedule_hints,
        "focus_queue": [
            {
                "id": t["id"],
                "title": t.get("title"),
                "project": t.get("_project_name"),
                "project_id": t.get("_project_id"),
                "status": t.get("status"),
                "priority": t.get("priority"),
                "due_date": t.get("due_date"),
                "assignee_id": t.get("assignee_id"),
            }
            for t in focus
        ],
        "capacity": {"overloaded": overloaded},
    }


def get_ai_settings(c) -> Dict[str, str]:
    keys = ("ai_enabled", "ai_api_url", "ai_api_key", "ai_model", "ai_system_prompt")
    out = {k: "" for k in keys}
    out["ai_enabled"] = "false"
    out["ai_api_url"] = os.environ.get("PLAN365_AI_URL", "https://api.openai.com/v1")
    out["ai_model"] = os.environ.get("PLAN365_AI_MODEL", "gpt-4o-mini")
    out["ai_system_prompt"] = (
        "You are Plan365 planning assistant for a CAD/CAM/engineering team. "
        "Be concise. Suggest concrete task order, capacity fixes, and schedule risks. "
        "Respond in the user's language when possible."
    )
    for r in c.execute(
        "SELECT key, value FROM settings WHERE key IN ('ai_enabled','ai_api_url','ai_api_key','ai_model','ai_system_prompt')"
    ).fetchall():
        out[r["key"]] = r["value"] if r["value"] is not None else out.get(r["key"], "")
    # env key override if settings empty
    if not out.get("ai_api_key"):
        out["ai_api_key"] = os.environ.get("PLAN365_AI_KEY", "")
    return out


async def chat_with_llm(
    *,
    settings: Dict[str, str],
    message: str,
    snapshot: Dict[str, Any],
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Optional OpenAI-compatible Chat Completions. Fails soft if unreachable."""
    import urllib.request
    import urllib.error

    if (settings.get("ai_enabled") or "").lower() not in ("1", "true", "yes"):
        return {
            "ok": False,
            "mode": "local",
            "reply": _local_reply(message, analysis),
            "analysis": analysis,
        }
    api_key = settings.get("ai_api_key") or ""
    if not api_key:
        return {
            "ok": False,
            "mode": "local",
            "reply": _local_reply(message, analysis) + "\n\n_(AI API key not configured — local planner used.)_",
            "analysis": analysis,
        }

    base = (settings.get("ai_api_url") or "https://api.openai.com/v1").rstrip("/")
    model = settings.get("ai_model") or "gpt-4o-mini"
    system = settings.get("ai_system_prompt") or "You are a project planning assistant."

    # Compact context to save tokens / RAM
    compact = {
        "summary": analysis.get("summary"),
        "risks": analysis.get("risks", [])[:12],
        "actions": analysis.get("recommended_actions", [])[:10],
        "focus_queue": analysis.get("focus_queue", [])[:10],
        "projects": [
            {
                "id": p["id"],
                "name": p["name"],
                "status": p.get("status"),
                "due_date": p.get("due_date"),
                "summary": p.get("summary"),
            }
            for p in (snapshot.get("projects") or [])[:20]
        ],
    }
    body = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 800,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "Workspace snapshot (JSON):\n"
                    + json.dumps(compact, ensure_ascii=False)
                    + "\n\nUser question:\n"
                    + message
                ),
            },
        ],
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
            or "(empty model response)"
        )
        return {"ok": True, "mode": "llm", "reply": reply, "model": model, "analysis": analysis}
    except Exception as e:
        return {
            "ok": False,
            "mode": "local-fallback",
            "reply": _local_reply(message, analysis) + f"\n\n_(LLM error: {e} — used local planner.)_",
            "analysis": analysis,
        }


def _local_reply(message: str, analysis: Dict[str, Any]) -> str:
    s = analysis.get("summary") or {}
    lines = [
        "**Plan365 local planner** (no external AI required)",
        "",
        f"- Open tasks: **{s.get('open_tasks', 0)}** · Overdue: **{s.get('overdue', 0)}** · Due this week: **{s.get('due_this_week', 0)}**",
        f"- Unassigned: **{s.get('unassigned', 0)}** · Overloaded members: **{s.get('overloaded_members', 0)}**",
        "",
    ]
    risks = analysis.get("risks") or []
    if risks:
        lines.append("**Top risks**")
        for r in risks[:5]:
            lines.append(f"- [{r.get('severity')}] {r.get('title')}: {r.get('detail', '')}")
        lines.append("")
    actions = analysis.get("recommended_actions") or []
    if actions:
        lines.append("**Recommended actions**")
        for a in actions[:5]:
            lines.append(f"- {a.get('action')} — _{a.get('why', '')}_")
        lines.append("")
    focus = analysis.get("focus_queue") or []
    if focus:
        lines.append("**Suggested focus order**")
        for i, t in enumerate(focus[:8], 1):
            lines.append(
                f"{i}. {t.get('title')} ({t.get('project')}) · {t.get('priority')}/{t.get('status')} · due {t.get('due_date') or '—'}"
            )
    if message:
        lines.extend(["", f"_Question noted:_ {message[:300]}"])
    return "\n".join(lines)
