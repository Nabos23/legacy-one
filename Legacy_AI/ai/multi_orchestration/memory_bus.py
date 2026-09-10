"""MemoryBus — single append-only memory log for a run.

The log IS the context. Every agent output and human clarification is appended
verbatim: no summarization, no truncation. Each agent receives the entire log
so far as its input, so memory is the single source of context.

Trade-off (accepted for now): with no cap, a very long chain or a looping /
24-7 run can eventually exceed the model's context window. Revisit a cap only
when that wall is actually hit.
"""
import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


class MemoryBus:
    def __init__(self, run_doc: dict, sync_db, model: str = ""):
        self._run_id: str = run_doc["run_id"]
        self._session_id: str = run_doc["session_id"]
        self._user_id: str = run_doc["user_id"]
        self._org_id: str = run_doc["organization_id"]
        self._orchestration_id: str = run_doc.get("orchestration_id", "")
        self._db = sync_db
        self._model = model  # unused; kept for constructor compatibility
        self._lock = threading.Lock()  # protects the log for parallel branches

        # Single append-only log — flushed to MongoDB via flush_to_run_doc().
        self._log: List[dict] = list(run_doc.get("memory_log", []))

    # ------------------------------------------------------------------
    # Append API
    # ------------------------------------------------------------------

    def append_user(self, content: str) -> None:
        self._append("user", "user", content)

    def append_agent(self, agent_name: str, content: str) -> None:
        self._append("agent", agent_name, content)

    def append_human(self, content: str) -> None:
        self._append("human", "human", content)

    def _append(self, role: str, name: str, content: str) -> None:
        with self._lock:
            self._log.append({
                "role": role,
                "name": name,
                "content": content,
                "timestamp": datetime.now(timezone.utc),
            })

    def has_entries(self) -> bool:
        with self._lock:
            return bool(self._log)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_context(self) -> str:
        """Render the entire log verbatim — no truncation, no summary."""
        with self._lock:
            parts = [f"[{e['name']}]: {e['content']}" for e in self._log]
        return "\n\n".join(parts)

    def get_messages(self) -> List[dict]:
        """The log as chat turns, for agents that take real conversation history.

        Preferred over `get_context()` when handing history to an agent: the
        rendered `[name]: content` form is a *document*, and an agent asked to
        email or write it out will happily paste the internal role tags into
        user-facing content. Roles here carry the same information without
        embedding it in the text.

        Agent turns become `assistant`; user and human-answer turns become
        `user`. Names are kept as a prefix on assistant turns only, since which
        specialist produced an output is genuinely useful downstream.
        """
        with self._lock:
            entries = list(self._log)
        messages: List[dict] = []
        for entry in entries:
            content = entry.get("content") or ""
            if not content:
                continue
            if entry.get("role") == "agent":
                name = entry.get("name") or "agent"
                messages.append({"role": "assistant", "content": f"{name}: {content}"})
            else:
                messages.append({"role": "user", "content": content})
        return messages

    # ------------------------------------------------------------------
    # HITL
    # ------------------------------------------------------------------

    def inject_human_answer(self, question: str, answer: str, agent_id: str = "") -> None:
        """Append a human clarification so the resuming agent sees it in context."""
        self.append_human(f"Question: {question}\nAnswer: {answer}")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def flush_to_run_doc(self) -> dict:
        """Return a $set-ready dict for the run document's memory field."""
        with self._lock:
            return {"memory_log": list(self._log)}

#New methods to store messages, seperate for node/hitl/user input 
    def write_user_input(self, user_input: str, branch_id: Optional[str] = None) -> None:
        """Push the initial user message into orchestration_conversations."""
        now = datetime.now(timezone.utc)
        entry = {
            "type": "user_input",
            "user_input": user_input,
            "node_name": None,
            "node_num": 0,
            "tools_called": [],
            "node_output": None,
            "timestamp": now,
            "branch_id": branch_id,
        }
        self._db.orchestration_conversations.update_one(
            {
                "session_id": self._session_id,
                "organization_id": self._org_id,
                "orchestration_id": self._orchestration_id,   # <-- add this line
            },
            {
                "$push": {"conversations": entry},
                "$inc": {"total_messages": 1},
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "user_id": self._user_id,
                    "created_at": now,
                },
            },
            upsert=True,
        )

    def write_orchestration_turn(
        self,
        node_name: str,
        node_num: int,
        tools_called: List[str],
        node_output: str,
        branch_id: Optional[str] = None,
    ) -> None:
        """Push a completed node turn into orchestration_conversations."""
        now = datetime.now(timezone.utc)
        entry = {
            "type": "node",
            "user_input": None,
            "node_name": node_name,
            "node_num": node_num,
            "tools_called": tools_called,
            "node_output": node_output,
            "timestamp": now,
            "branch_id": branch_id,
        }
        self._db.orchestration_conversations.update_one(
            {"session_id": self._session_id, "organization_id": self._org_id, "orchestration_id": self._orchestration_id},
            {
                "$push": {"conversations": entry},
                "$inc": {"total_messages": 1},
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "user_id": self._user_id,
                    "created_at": now,
                },
            },
            upsert=True,
        )
    def write_hitl_question(self, node_name: str, question: str, branch_id: Optional[str] = None) -> None:
        """Push a HITL pause into orchestration_conversations. The matching
        answer is filled in later via write_hitl_answer when the run resumes."""
        now = datetime.now(timezone.utc)
        entry = {
            "type": "hitl",
            "user_input": None,
            "node_name": node_name,
            "node_num": 0,
            "tools_called": [],
            "node_output": question,
            "timestamp": now,
            "branch_id": branch_id,
        }
        self._db.orchestration_conversations.update_one(
            {"session_id": self._session_id, "organization_id": self._org_id, "orchestration_id": self._orchestration_id},
            {
                "$push": {"conversations": entry},
                "$inc": {"total_messages": 1},
                "$set": {"updated_at": now},
                "$setOnInsert": {"user_id": self._user_id, "created_at": now},
            },
            upsert=True,
        )

    def write_hitl_answer(self, answer: str, branch_id: Optional[str] = None) -> None:
        """Fill in the answer on the most recent unanswered hitl entry."""
        now = datetime.now(timezone.utc)
        self._db.orchestration_conversations.update_one(
            {
                "session_id": self._session_id,
                "organization_id": self._org_id,
                "orchestration_id": self._orchestration_id,
            },
            {
                "$set": {
                    "conversations.$[elem].user_input": answer,
                    "conversations.$[elem].timestamp": now,
                    "updated_at": now,
                }
            },
            array_filters=[{"elem.type": "hitl", "elem.user_input": None, "elem.branch_id": branch_id}],
        )
