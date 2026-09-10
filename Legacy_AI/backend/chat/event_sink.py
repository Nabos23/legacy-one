"""Per-request live-event sink for the chat LangGraph pipeline.

Mirrors tracing_ctx.py's contextvar pattern: node closures have no direct
access to the request, so per-request state (like where to publish live
progress events for an SSE stream) is threaded through a ContextVar instead.
"""

from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Dict, Optional

EventSink = Callable[[str, Dict[str, Any]], Awaitable[None]]

_event_sink: ContextVar[Optional[EventSink]] = ContextVar("chat_event_sink", default=None)


def set_event_sink(sink: Optional[EventSink]) -> None:
    _event_sink.set(sink)


def get_event_sink() -> Optional[EventSink]:
    return _event_sink.get()


async def emit_event(event_type: str, payload: Dict[str, Any]) -> None:
    """Publish a live progress event if a sink is set for this request.

    No-op when no sink is set, so the existing blocking chat endpoints are
    unaffected. Swallows sink errors so a broken/disconnected client can
    never break the graph turn itself.
    """
    sink = get_event_sink()
    if sink is None:
        return
    try:
        await sink(event_type, payload)
    except Exception:
        pass
