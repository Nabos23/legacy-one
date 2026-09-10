from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.db.constants import CONVERSATION_LOGS_COLLECTION
from backend.memory.schemas import (
    ConversationDocument,
    ConversationEntry,
    TurnEntry,
    doc_from_mongo,
    entries_to_mongo,
)


class ConversationStore:
    """Async Mongo CRUD for per-agent conversation_logs documents."""

    def __init__(self, db) -> None:
        self._col = db[CONVERSATION_LOGS_COLLECTION]
        self._indexes_ready = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        # Partial filter excludes legacy ai/ flat-log rows that lack session_id.
        await self._col.create_index(
            [("session_id", 1), ("user_id", 1), ("agent_id", 1)],
            unique=True,
            background=True,
            name="conv_session_user_agent_unique",
            partialFilterExpression={"session_id": {"$type": "string"}},
        )
        self._indexes_ready = True

    def _filter(self, session_id: str, user_id: str, agent_id: str) -> dict:
        return {
            "session_id": session_id,
            "user_id": user_id,
            "agent_id": agent_id,
        }

    async def append_turn(
        self,
        session_id: str,
        user_id: str,
        organization_id: str,
        agent_id: str,
        human_message: str,
        agent_message: str,
        tool_called: bool = False,
        tool_name: Optional[str] = None,
        auth_errors: Optional[List[Dict[str, Optional[str]]]] = None,
    ) -> None:
        await self._ensure_indexes()
        now = datetime.now(timezone.utc)
        turn = TurnEntry(
            human_message=human_message,
            agent_message=agent_message,
            timestamp=now,
            tool_called=tool_called,
            tool_name=tool_name,
            auth_errors=auth_errors or [],
        )
        await self._col.update_one(
            self._filter(session_id, user_id, agent_id),
            {
                "$push": {"conversations": turn.model_dump()},
                "$inc": {
                    "total_messages": 1,
                    "new_messages_since_compression": 1,
                },
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "agent_id": agent_id,
                    "total_summaries": 0,
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def get_document(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
    ) -> Optional[ConversationDocument]:
        doc = await self._col.find_one(self._filter(session_id, user_id, agent_id))
        if not doc:
            return None
        return doc_from_mongo(doc)

    async def delete_by_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        query: dict = {"session_id": session_id}
        if user_id is not None:
            query["user_id"] = user_id
        await self._col.delete_many(query)

    async def find_by_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> list[ConversationDocument]:
        query: dict = {"session_id": session_id}
        if user_id is not None:
            query["user_id"] = user_id
        cursor = self._col.find(query)
        docs = await cursor.to_list(length=100)
        return [doc_from_mongo(d) for d in docs]

    async def replace_conversations(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
        conversations: list[ConversationEntry],
        *,
        increment_summaries: bool = False,
        reset_compression_counter: bool = False,
    ) -> None:
        now = datetime.now(timezone.utc)
        update: dict = {
            "$set": {
                "conversations": entries_to_mongo(conversations),
                "updated_at": now,
            },
        }
        if increment_summaries:
            update["$inc"] = {"total_summaries": 1}
        if reset_compression_counter:
            update["$set"]["new_messages_since_compression"] = 0

        await self._col.update_one(
            self._filter(session_id, user_id, agent_id),
            update,
        )

    async def get_new_messages_since_compression(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
    ) -> int:
        doc = await self._col.find_one(
            self._filter(session_id, user_id, agent_id),
            {"new_messages_since_compression": 1},
        )
        if not doc:
            return 0
        return doc.get("new_messages_since_compression", 0)
