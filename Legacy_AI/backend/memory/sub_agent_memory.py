import asyncio
import logging
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ai.agents.summarizer.agent import Summarizer_Agent
from backend.memory.conversation_store import ConversationStore
from backend.memory.schemas import (
    SummaryEntry,
    TurnEntry,
    split_entries,
    turns_to_langchain,
)

logger = logging.getLogger(__name__)

TURNS_BEFORE_COMPRESS = 20  # minimum total_messages before any compression
COMPRESS_INTERVAL = 10  # compress when total_messages % 10 == 0
KEEP_AFTER_COMPRESS = 10


class SubAgentMemory:
    """Per-agent durable memory: fetch, append, compress, seed."""

    def __init__(self, store: ConversationStore, model: str) -> None:
        self._store = store
        self._model = model

    async def get_seed_messages(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
    ) -> list:
        doc = await self._store.get_document(session_id, user_id, agent_id)
        if not doc or not doc.conversations:
            return []

        summary, turns = split_entries(doc.conversations)
        seed: list = []
        if summary:
            seed.append(
                SystemMessage(
                    content=f"Previous conversation summary:\n{summary.content}"
                )
            )
        seed.extend(turns_to_langchain(turns))
        return seed

    async def record_turn(
        self,
        session_id: str,
        user_id: str,
        org_id: str,
        agent_id: str,
        human_message: str,
        agent_message: str,
        tool_called: bool = False,
        tool_name: str | None = None,
        auth_errors: list | None = None,
    ) -> None:
        await self._store.append_turn(
            session_id=session_id,
            user_id=user_id,
            organization_id=org_id,
            agent_id=agent_id,
            human_message=human_message,
            agent_message=agent_message,
            tool_called=tool_called,
            tool_name=tool_name,
            auth_errors=auth_errors,
        )

    async def needs_compression(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
    ) -> bool:
        doc = await self._store.get_document(session_id, user_id, agent_id)
        if not doc:
            return False
        total = doc.total_messages
        return (
            total >= TURNS_BEFORE_COMPRESS
            and total % COMPRESS_INTERVAL == 0
        )

    async def maybe_compress(
        self,
        session_id: str,
        user_id: str,
        agent_id: str,
    ) -> str:
        if not await self.needs_compression(session_id, user_id, agent_id):
            return ""

        doc = await self._store.get_document(session_id, user_id, agent_id)
        if not doc:
            return ""

        summary, turns = split_entries(doc.conversations)
        if len(turns) <= KEEP_AFTER_COMPRESS:
            return summary.content if summary else ""

        recent_turns = turns[-KEEP_AFTER_COMPRESS:]

        # Pass full history — Summarizer_Agent splits messages[:-10] internally.
        messages = []
        if summary:
            messages.append({
                "role": "summary",
                "agent_name": "Summarizer_Agent",
                "user_query": "[summarized]",
                "content": summary.content,
            })
        for turn in turns:
            messages.append({
                "role": "turn",
                "agent_name": doc.agent_id,
                "user_query": turn.human_message,
                "content": turn.agent_message,
            })

        state = {
            "messages": messages,
            "interaction_count": doc.total_messages,
        }
        summarizer = Summarizer_Agent(model=self._model)

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, summarizer.invoke, state)
        except Exception as exc:
            logger.error(
                "SubAgentMemory.compress failed for session=%s agent=%s: %s",
                session_id,
                agent_id,
                exc,
            )
            return summary.content if summary else ""

        if not result:
            return summary.content if summary else ""

        summary_text: str = result.get("memory_summary", "")
        now = datetime.now(timezone.utc)
        new_summary = SummaryEntry(content=summary_text, timestamp=now)
        new_conversations = [new_summary, *recent_turns]

        await self._store.replace_conversations(
            session_id,
            user_id,
            agent_id,
            new_conversations,
            increment_summaries=True,
            reset_compression_counter=True,
        )

        logger.info(
            "Compressed session=%s agent=%s: %d turns → summary + %d recent",
            session_id,
            agent_id,
            len(turns),
            len(recent_turns),
        )
        return summary_text

    async def build_session_seed(
        self,
        session_id: str,
        user_id: str,
    ) -> list:
        """Aggregate all agent docs in a session into a full message history."""
        docs = await self._store.find_by_session(session_id, user_id)
        if not docs:
            return []

        seed: list = []
        events: list[tuple[datetime, str, str]] = []

        for doc in docs:
            summary, turns = split_entries(doc.conversations)
            if summary:
                seed.append(
                    SystemMessage(
                        content=(
                            f"Previous conversation summary "
                            f"(agent {doc.agent_id}):\n{summary.content}"
                        )
                    )
                )
            for turn in turns:
                events.append((turn.timestamp, turn.human_message, turn.agent_message))

        events.sort(key=lambda e: e[0])
        for _, human, agent in events:
            seed.append(HumanMessage(content=human))
            seed.append(AIMessage(content=agent))

        return seed
