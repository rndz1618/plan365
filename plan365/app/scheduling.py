"""Lightweight FS scheduling helpers (auto-shift successors). RAM-friendly, no graph lib."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple


def parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return None


def fmt_date(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def task_duration_days(start: Optional[str], due: Optional[str]) -> int:
    a = parse_date(start)
    b = parse_date(due)
    if not a and not b:
        return 1
    if a and not b:
        return 1
    if b and not a:
        return 1
    return max(1, (b - a).days)


def cascade_fs_after_update(
    c,
    root_task_id: int,
    *,
    max_nodes: int = 500,
) -> List[dict]:
    """
    After root task dates change, shift FS successors so:
      successor.start >= predecessor.due + lag_days
    Duration of each successor is preserved.
    Returns list of {id, start_date, due_date} that were updated.
    """
    # Load edges + tasks once
    dep_rows = c.execute(
        "SELECT predecessor_id, successor_id, lag_days, type FROM task_dependencies"
    ).fetchall()
    # adjacency: pred -> [(succ, lag, type)]
    succ_map: Dict[int, List[Tuple[int, int, str]]] = {}
    for r in dep_rows:
        pid, sid = int(r["predecessor_id"]), int(r["successor_id"])
        lag = int(r["lag_days"] or 0)
        typ = r["type"] or "FS"
        succ_map.setdefault(pid, []).append((sid, lag, typ))

    task_rows = c.execute(
        "SELECT id, start_date, due_date FROM tasks"
    ).fetchall()
    tasks: Dict[int, dict] = {
        int(r["id"]): {
            "id": int(r["id"]),
            "start_date": r["start_date"],
            "due_date": r["due_date"],
        }
        for r in task_rows
    }
    if root_task_id not in tasks:
        return []

    # BFS from root through successors only
    queue = [root_task_id]
    seen: Set[int] = set()
    order: List[int] = []
    while queue and len(order) < max_nodes:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        order.append(u)
        for v, lag, typ in succ_map.get(u, []):
            if v not in seen:
                queue.append(v)

    updated: List[dict] = []
    now = datetime.utcnow().isoformat()

    # Skip root itself; only shift downstream
    for uid in order[1:]:
        t = tasks.get(uid)
        if not t:
            continue
        # earliest allowed start from all FS predecessors already in graph
        earliest = None
        preds = [
            (int(r["predecessor_id"]), int(r["lag_days"] or 0), r["type"] or "FS")
            for r in dep_rows
            if int(r["successor_id"]) == uid
        ]
        for pid, lag, typ in preds:
            if typ != "FS":
                continue
            pred = tasks.get(pid)
            if not pred:
                continue
            pred_end = parse_date(pred["due_date"] or pred["start_date"])
            if not pred_end:
                continue
            # next day after finish + lag
            cand = pred_end + timedelta(days=1 + max(0, lag))
            if earliest is None or cand > earliest:
                earliest = cand
        if earliest is None:
            continue

        dur = task_duration_days(t["start_date"], t["due_date"])
        cur_start = parse_date(t["start_date"])
        # Only push forward (never pull earlier automatically — safer for engineering plans)
        if cur_start and cur_start >= earliest:
            continue
        new_start = earliest
        new_due = new_start + timedelta(days=dur)
        ns, nd = fmt_date(new_start), fmt_date(new_due)
        if ns == t["start_date"] and nd == t["due_date"]:
            continue
        c.execute(
            "UPDATE tasks SET start_date=?, due_date=?, updated_at=? WHERE id=?",
            (ns, nd, now, uid),
        )
        t["start_date"], t["due_date"] = ns, nd
        updated.append({"id": uid, "start_date": ns, "due_date": nd})

    return updated
