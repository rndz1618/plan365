"""Load/save templates from settings + expand into tasks."""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.templates_data import DEFAULT_TEMPLATES
from app.config import TYPES, PRIORITIES


def _normalize_template(t: Dict[str, Any]) -> Dict[str, Any]:
    tid = str(t.get("id") or "").strip() or f"tpl-{int(datetime.utcnow().timestamp())}"
    name = str(t.get("name") or "Untitled").strip()[:120]
    desc = str(t.get("description") or "")[:500]
    tasks_in = t.get("tasks") or []
    tasks: List[Dict[str, Any]] = []
    for i, raw in enumerate(tasks_in):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or f"Task {i+1}").strip()[:200]
        typ = raw.get("type") if raw.get("type") in TYPES else "Others"
        pri = raw.get("priority") if raw.get("priority") in PRIORITIES else "Medium"
        effort = max(0, int(raw.get("effort") or 0))
        off = max(0, int(raw.get("offset_start_days") or 0))
        dur = max(0, int(raw.get("duration_days") or 0))
        is_ms = bool(raw.get("is_milestone"))
        deps = raw.get("depends_on") or []
        if not isinstance(deps, list):
            deps = []
        deps = [int(d) for d in deps if str(d).isdigit() or isinstance(d, int)]
        deps = [d for d in deps if 0 <= d < len(tasks_in) and d != i]
        tasks.append(
            {
                "title": title,
                "type": typ,
                "priority": pri,
                "effort": effort,
                "offset_start_days": off,
                "duration_days": 0 if is_ms else dur,
                "is_milestone": is_ms,
                "depends_on": deps,
            }
        )
    return {"id": tid, "name": name, "description": desc, "tasks": tasks}


def get_templates(c) -> List[Dict[str, Any]]:
    r = c.execute("SELECT value FROM settings WHERE key='project_templates'").fetchone()
    if not r:
        return deepcopy(DEFAULT_TEMPLATES)
    try:
        data = json.loads(r["value"])
        if not isinstance(data, list) or not data:
            return deepcopy(DEFAULT_TEMPLATES)
        return [_normalize_template(t) for t in data]
    except Exception:
        return deepcopy(DEFAULT_TEMPLATES)


def save_templates(c, templates: List[Dict[str, Any]], user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    normalized = [_normalize_template(t) for t in templates]
    # ensure unique ids
    seen = set()
    for t in normalized:
        base = t["id"]
        n = 1
        while t["id"] in seen:
            t["id"] = f"{base}-{n}"
            n += 1
        seen.add(t["id"])
    c.execute(
        """INSERT INTO settings (key, value, updated_at, updated_by) VALUES (?,?,?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at,
           updated_by=excluded.updated_by""",
        (
            "project_templates",
            json.dumps(normalized),
            datetime.utcnow().isoformat(),
            user_id,
        ),
    )
    return normalized


def ensure_default_templates(c) -> None:
    r = c.execute("SELECT value FROM settings WHERE key='project_templates'").fetchone()
    if not r:
        save_templates(c, DEFAULT_TEMPLATES, None)


def find_template(c, template_id: str) -> Optional[Dict[str, Any]]:
    for t in get_templates(c):
        if t["id"] == template_id:
            return t
    return None


def expand_task_list(
    c,
    *,
    project_id: int,
    tasks_def: List[Dict[str, Any]],
    start_date: Optional[str],
    created_by: int,
) -> Dict[str, Any]:
    """Insert from user-edited task list (normalize first)."""
    normalized = _normalize_template({"id": "custom", "name": "custom", "tasks": tasks_def or []})
    return expand_template_tasks(
        c,
        project_id=project_id,
        template=normalized,
        start_date=start_date,
        created_by=created_by,
    )


def expand_template_tasks(
    c,
    *,
    project_id: int,
    template: Dict[str, Any],
    start_date: Optional[str],
    created_by: int,
) -> Dict[str, Any]:
    """Insert tasks + FS deps from template. Returns counts."""
    base = None
    if start_date:
        try:
            base = datetime.strptime(start_date[:10], "%Y-%m-%d")
        except ValueError:
            base = None
    if base is None:
        base = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    tasks_def = template.get("tasks") or []
    id_map: Dict[int, int] = {}
    created = 0
    now = datetime.utcnow().isoformat()

    for idx, td in enumerate(tasks_def):
        off = int(td.get("offset_start_days") or 0)
        dur = int(td.get("duration_days") or 0)
        is_ms = bool(td.get("is_milestone"))
        s = base + timedelta(days=off)
        if is_ms or dur == 0:
            e = s
            progress = 0
        else:
            e = s + timedelta(days=max(1, dur))
            progress = 0
        cur = c.execute(
            """INSERT INTO tasks (
                project_id, title, description, type, status, priority,
                start_date, due_date, progress, effort, labels,
                assignee_id, created_by, is_milestone, attachment_url, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                project_id,
                td["title"],
                None,
                td.get("type") or "Others",
                "Todo",
                td.get("priority") or "Medium",
                s.strftime("%Y-%m-%d"),
                e.strftime("%Y-%m-%d"),
                progress,
                int(td.get("effort") or 0) or None,
                "[]",
                None,
                created_by,
                1 if is_ms else 0,
                None,
                now,
            ),
        )
        id_map[idx] = cur.lastrowid
        created += 1

    edges = 0
    for idx, td in enumerate(tasks_def):
        succ = id_map.get(idx)
        if not succ:
            continue
        for pred_idx in td.get("depends_on") or []:
            pred = id_map.get(int(pred_idx))
            if not pred or pred == succ:
                continue
            try:
                c.execute(
                    """INSERT INTO task_dependencies (predecessor_id, successor_id, type, lag_days)
                       VALUES (?,?, 'FS', 0)""",
                    (pred, succ),
                )
                edges += 1
            except Exception:
                pass

    return {"tasks_created": created, "dependencies_created": edges}
