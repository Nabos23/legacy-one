import logging
import os

from ai.tracing.context import TracingContext
from ai.tracing.tracer import AgentTracer

logger = logging.getLogger(__name__)


def setup_tracing() -> bool:
    """
    Activate the LiteLLM → Langfuse callback.

    Call once at application startup — before any MainAgent.invoke() calls.
    Safe to call even when Langfuse keys are not set (returns False, no-ops).

    Returns True if Langfuse is configured and callbacks are active.
    """
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        logger.info("LANGFUSE_PUBLIC_KEY / SECRET_KEY not set — LLM call tracing disabled")
        return False

    try:
        import litellm
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]
        logger.info("Langfuse tracing enabled (host: %s)", os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))
        return True
    except Exception as e:
        logger.warning("Failed to activate Langfuse callback: %s", e)
        return False


__all__ = ["AgentTracer", "TracingContext", "setup_tracing"]
