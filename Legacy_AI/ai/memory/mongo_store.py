import logging
from typing import TYPE_CHECKING, Optional

from ai.memory.memory_schema import MemorySchema

if TYPE_CHECKING:
    from ai.tracing.tracer import AgentTracer

logger = logging.getLogger(__name__)


class MongoMemoryStore:
    """Persistent conversation log backed by MongoDB. Stateless — one instance per db."""

    COLLECTION = "conversation_logs"

    def __init__(self, db, tracer: Optional["AgentTracer"] = None) -> None:
        self._col = db[self.COLLECTION]
        self._tracer = tracer
        self._col.create_index(
            [("user_id", 1), ("organization_id", 1), ("timestamp", -1)],
            background=True,
        )

    def write(self, entry: MemorySchema) -> None:
        try:
            self._col.insert_one(entry.model_dump())
            if self._tracer:
                self._tracer.event("memory.long_term.write", metadata={
                    "user_id": entry.user_id,
                    "org_id": entry.organization_id,
                    "agent_id": entry.agent_id,
                    "agent_name": entry.agent_name,
                    "tool_called": entry.tool_called,
                    "tool_name": entry.tool_name,
                })
        except Exception as e:
            logger.warning("MongoMemoryStore.write failed — entry not persisted: %s", e)

    def get_by_user(self, user_id: str, limit: int = 50) -> list[MemorySchema]:
        docs = (
            self._col
            .find({"user_id": user_id}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limit)
        )
        result = [MemorySchema(**d) for d in reversed(list(docs))]
        if self._tracer:
            self._tracer.event("memory.long_term.read", metadata={
                "filter": "user_id",
                "user_id": user_id,
                "count": len(result),
            })
        return result

    def get_by_session(
        self,
        user_id: str,
        organization_id: str,
        limit: int = 20,
    ) -> list[MemorySchema]:
        docs = (
            self._col
            .find({"user_id": user_id, "organization_id": organization_id}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limit)
        )
        result = [MemorySchema(**d) for d in reversed(list(docs))]
        if self._tracer:
            self._tracer.event("memory.long_term.read", metadata={
                "filter": "session",
                "user_id": user_id,
                "org_id": organization_id,
                "count": len(result),
            })
        return result
