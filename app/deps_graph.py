"""Task dependency graph helpers: adjacency, cycle detection."""

def _dep_adjacency(c, extra_edge=None):
    adj = {}
    for r in c.execute("SELECT predecessor_id, successor_id FROM task_dependencies").fetchall():
        adj.setdefault(int(r["predecessor_id"]), []).append(int(r["successor_id"]))
    if extra_edge:
        p, s = int(extra_edge[0]), int(extra_edge[1])
        adj.setdefault(p, []).append(s)
    return adj

def graph_has_cycle(adj):
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}
    cycle_path = None

    def dfs(u, stack):
        nonlocal cycle_path
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, []):
            cv = color.get(v, WHITE)
            if cv == GRAY:
                if v in stack:
                    i = stack.index(v)
                    cycle_path = stack[i:] + [v]
                else:
                    cycle_path = [u, v]
                return True
            if cv == WHITE:
                if dfs(v, stack):
                    return True
        stack.pop()
        color[u] = BLACK
        return False

    nodes = set(adj.keys())
    for vs in adj.values():
        nodes.update(vs)
    for n in nodes:
        if color.get(n, WHITE) == WHITE:
            if dfs(n, []):
                return True, cycle_path
    return False, None

def would_create_cycle(c, predecessor_id, successor_id):
    pid, sid = int(predecessor_id), int(successor_id)
    if pid == sid:
        return True, [pid, sid]
    adj = _dep_adjacency(c, extra_edge=(pid, sid))
    return graph_has_cycle(adj)

def dependency_path_exists(c, start_id, target_id):
    adj = _dep_adjacency(c)
    stack = [int(start_id)]
    seen = set()
    target = int(target_id)
    while stack:
        u = stack.pop()
        if u == target:
            return True
        if u in seen:
            continue
        seen.add(u)
        stack.extend(adj.get(u, []))
    return False
