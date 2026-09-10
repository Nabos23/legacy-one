"""Save-time validation for orchestrations: cycle detection, self-edges, org isolation."""
from typing import List


def has_cycle(node_ids: List[str], edges: List[tuple[str, str]]) -> bool:
    """Return True if the directed graph described by edges contains a cycle."""
    graph: dict[str, list[str]] = {n: [] for n in node_ids}
    for frm, to in edges:
        if frm in graph:
            graph[frm].append(to)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in node_ids}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color.get(neighbor) == GRAY:
                return True
            if color.get(neighbor) == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    return any(color[n] == WHITE and dfs(n) for n in node_ids)


def find_orphan_agents(main_agent_id: str, agent_ids: List[str], edges: List[tuple[str, str]]) -> List[str]:
    """Return agents that are unreachable from main_agent_id."""
    reachable = set()
    adjacency: dict[str, list[str]] = {a: [] for a in agent_ids}
    for frm, to in edges:
        if frm in adjacency:
            adjacency[frm].append(to)

    stack = [main_agent_id]
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(adjacency.get(current, []))

    return [a for a in agent_ids if a not in reachable and a != main_agent_id]
