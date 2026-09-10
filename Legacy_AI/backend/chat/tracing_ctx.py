"""Per-request Langfuse tracer for the chat LangGraph pipeline."""

from contextvars import ContextVar
from typing import Any, Dict, Optional

from ai.tracing.tracer import AgentTracer

_tracer: ContextVar[Optional[AgentTracer]] = ContextVar("chat_tracer", default=None)


def set_tracer(tracer: Optional[AgentTracer]) -> None:
    _tracer.set(tracer)


def get_tracer() -> Optional[AgentTracer]:
    return _tracer.get()


def with_trace_metadata(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge Langfuse linking metadata into a litellm.acompletion kwargs dict."""
    tracer = get_tracer()
    if not tracer:
        return kwargs
    meta = tracer.litellm_metadata()
    if not meta:
        return kwargs
    merged = dict(kwargs)
    existing = merged.get("metadata") or {}
    if isinstance(existing, dict):
        merged["metadata"] = {**existing, **meta}
    else:
        merged["metadata"] = meta
    return merged
