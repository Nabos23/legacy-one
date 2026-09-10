class AgentPermissions:
    """Adjacency-map wrapper for O(1) 'can X call Y?' lookups."""

    def __init__(self, orchestration_snapshot: dict):
        self._edges: set[tuple[str, str]] = {
            (c["from_agent_id"], c["to_agent_id"])
            for c in orchestration_snapshot.get("connections", [])
            if c["from_agent_id"] != c["to_agent_id"]  # strip self-edges
        }

    def can_call(self, from_agent_id: str, to_agent_id: str) -> bool:
        if from_agent_id == to_agent_id:
            return False
        return (from_agent_id, to_agent_id) in self._edges
