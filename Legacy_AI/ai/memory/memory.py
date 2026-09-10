from typing import TYPE_CHECKING, List, Optional

from ai.memory.memory_schema import MemorySchema

if TYPE_CHECKING:
    from ai.tracing.tracer import AgentTracer


class LocalMemory:
    def __init__(self):
        self._store: List[MemorySchema] = []
        self._tracer: Optional["AgentTracer"] = None

    def set_tracer(self, tracer: "AgentTracer") -> None:
        self._tracer = tracer

    def append_memory(self, entry: MemorySchema) -> None:
        self._store.append(entry)
        if self._tracer:
            self._tracer.event("memory.write", metadata={
                "user_id": entry.user_id,
                "agent_id": entry.agent_id,
                "agent_name": entry.agent_name,
                "tool_called": entry.tool_called,
                "tool_name": entry.tool_name,
            })

    def get_memory(self) -> List[MemorySchema]:
        result = self._store.copy()
        if self._tracer:
            self._tracer.event("memory.read", metadata={"filter": "all", "count": len(result)})
        return result

    def get_memory_by_user(self, user_id: str) -> List[MemorySchema]:
        result = [e for e in self._store if e.user_id == user_id]
        if self._tracer:
            self._tracer.event("memory.read", metadata={
                "filter": "user_id", "user_id": user_id, "count": len(result),
            })
        return result

    def get_memory_by_agent(self, agent_id: str) -> List[MemorySchema]:
        result = [e for e in self._store if e.agent_id == agent_id]
        if self._tracer:
            self._tracer.event("memory.read", metadata={
                "filter": "agent_id", "agent_id": agent_id, "count": len(result),
            })
        return result

    def get_memory_by_session(self, user_id: str, agent_id: str) -> List[MemorySchema]:
        result = [e for e in self._store if e.user_id == user_id and e.agent_id == agent_id]
        if self._tracer:
            self._tracer.event("memory.read", metadata={
                "filter": "session", "user_id": user_id, "agent_id": agent_id, "count": len(result),
            })
        return result

    def clear(self) -> None:
        self._store = []
