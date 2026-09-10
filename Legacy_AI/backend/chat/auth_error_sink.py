"""Per-request collector for connector auth failures encountered during a chat turn.

Mirrors tracing_ctx.py / event_sink.py's contextvar pattern: agent_fn (in
graph.py) has no direct return channel back to _finalize_send_message, since
it runs as a LangGraph node reached through ainvoke(). A ContextVar carrying a
mutable list is set up before the graph task starts, appended to from deep
inside the tool-calling loop, and read back once the turn completes.
"""
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

_auth_errors: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("chat_auth_errors", default=None)


def reset_auth_errors() -> None:
    """Call before starting a turn (and before create_task, if streaming —
    contextvars are copied into a task at creation time)."""
    _auth_errors.set([])


def record_auth_error(payload: Dict[str, Any]) -> None:
    errors = _auth_errors.get()
    if errors is None:
        return  # not initialized for this request — no-op, never break the turn
    errors.append(payload)


def get_auth_errors() -> List[Dict[str, Any]]:
    return list(_auth_errors.get() or [])
