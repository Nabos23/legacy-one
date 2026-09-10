import logging
from contextlib import contextmanager
from typing import Any, Optional

from ai.tracing.tags import agent_tag, org_tag

logger = logging.getLogger(__name__)


class _NoopSpan:
    """Returned by AgentTracer when Langfuse is not configured."""
    id = None

    def end(self, **kwargs) -> None: pass
    def update(self, **kwargs) -> None: pass
    def event(self, **kwargs) -> None: pass
    def span(self, **kwargs) -> "_NoopSpan": return _NoopSpan()


class AgentTracer:
    """
    Thin wrapper around the Langfuse Python SDK.

    One instance lives on MainAgent for its entire lifetime.
    Call start_trace() at the top of each MainAgent.invoke() turn and
    end_trace() when that turn is done — every span opened in between
    is automatically nested under the active trace.

    Falls back to noop (no errors, no-ops) when:
      - the `langfuse` package is not installed, or
      - LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not set.

    Parameters
    ----------
    org_id     : organisation that owns this trace
    user_id    : individual user making the request
    session_id : groups multiple turns into one conversation thread
    """

    def __init__(self, org_id: str, user_id: str, session_id: Optional[str] = None):
        self.org_id = org_id
        self.user_id = user_id
        self.session_id = session_id or user_id

        self._langfuse = None
        self._trace = None
        self._span_stack: list = []

        # Set by SubAgent.invoke() so LiteLLM metadata carries agent identity
        self._agent_id: Optional[str] = None
        self._agent_name: Optional[str] = None

        try:
            from langfuse import Langfuse
            self._langfuse = Langfuse()
        except Exception as e:
            logger.debug("Langfuse not configured — tracing disabled: %s", e)

    # ------------------------------------------------------------------
    # Agent context  (updated per SubAgent invocation)
    # ------------------------------------------------------------------

    def set_agent_context(self, agent_id: Optional[str], agent_name: Optional[str]) -> None:
        """
        Call this in SubAgent.invoke() after load_agent() so that every
        LiteLLM generation produced by that agent carries its identity in
        Langfuse metadata and tags.
        """
        self._agent_id = agent_id
        self._agent_name = agent_name

    def clear_agent_context(self) -> None:
        self._agent_id = None
        self._agent_name = None

    def tag_supervisor(self) -> None:
        """Mark the current turn as handled by the supervisor (no sub-agent)."""
        self.set_agent_context(None, "Supervisor")

    def tag_agent(self, agent_id: Optional[str], agent_name: Optional[str]) -> None:
        """Set agent context and sync org/agent tags to the root Langfuse trace."""
        self.set_agent_context(agent_id, agent_name)
        if not agent_name:
            return
        self.update_trace(
            tags=[org_tag(self.org_id), agent_tag(agent_name)],
            metadata={
                "org_id": self.org_id,
                "user_id": self.user_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
            },
        )

    # ------------------------------------------------------------------
    # Trace lifecycle  (one per MainAgent.invoke() call)
    # ------------------------------------------------------------------

    def start_trace(self, name: str, input: Any = None) -> None:
        if not self._langfuse:
            return
        try:
            self._trace = self._langfuse.trace(
                name=name,
                user_id=self.user_id,
                session_id=self.session_id,
                input=input,
                metadata={"org_id": self.org_id, "user_id": self.user_id},
                tags=[org_tag(self.org_id)],
            )
        except Exception as e:
            logger.warning("Failed to start Langfuse trace: %s", e)

    def update_trace(self, tags: Optional[list] = None, metadata: Optional[dict] = None) -> None:
        """
        Update the root Trace object with additional tags or metadata fields.

        Call this in MainAgent._delegate() after the sub-agent is loaded so
        that the Trace itself carries agent identity — enabling per-agent trace
        filtering in Langfuse (tags=agent:finance_advisor) and the custom UI
        (/api/agents/{id}/traces).
        """
        if not self._trace:
            return
        try:
            update_kwargs = {}
            if tags:
                update_kwargs["tags"] = tags
            if metadata:
                update_kwargs["metadata"] = metadata
            if update_kwargs:
                self._trace.update(**update_kwargs)
        except Exception as e:
            logger.warning("Failed to update Langfuse trace: %s", e)

    def end_trace(self, output: Any = None) -> None:
        if not self._trace:
            return
        try:
            self._trace.update(output=output)
            self._langfuse.flush()
        except Exception as e:
            logger.warning("Failed to end Langfuse trace: %s", e)
        finally:
            self._trace = None
            self._span_stack.clear()
            self.clear_agent_context()

    # ------------------------------------------------------------------
    # Span context manager
    # ------------------------------------------------------------------

    @contextmanager
    def span(self, name: str, input: Any = None, metadata: Optional[dict] = None):
        """
        Open a Langfuse span, yield it to the caller, then close it.

        Usage::

            with self._tracer.span("routing", input=query) as span:
                result = do_work()
                span.end(output=result)

        If the block raises, the span is closed with the error message
        in its metadata and the exception re-raised.
        """
        if not self._langfuse or not self._trace:
            yield _NoopSpan()
            return

        parent = self._span_stack[-1] if self._span_stack else self._trace
        try:
            s = parent.span(name=name, input=input, metadata=metadata or {})
        except Exception as e:
            logger.warning("Failed to open span '%s': %s", name, e)
            yield _NoopSpan()
            return

        self._span_stack.append(s)
        try:
            yield s
        except Exception as exc:
            try:
                s.end(metadata={"error": str(exc)})
            except Exception:
                pass
            raise
        finally:
            self._span_stack.pop()

    # ------------------------------------------------------------------
    # Events  (point-in-time observations, no duration)
    # ------------------------------------------------------------------

    def event(self, name: str, metadata: Optional[dict] = None) -> None:
        if not self._langfuse or not self._trace:
            return
        try:
            parent = self._span_stack[-1] if self._span_stack else self._trace
            parent.event(name=name, metadata=metadata or {})
        except Exception as e:
            logger.warning("Failed to emit event '%s': %s", name, e)

    # ------------------------------------------------------------------
    # LiteLLM linking metadata
    # ------------------------------------------------------------------

    def litellm_metadata(self) -> dict:
        """
        Returns a metadata dict to pass into _completion_with_retry so that
        LiteLLM's Langfuse callback links the generation to the correct trace,
        span, org, and agent.

        Key names match what LiteLLM 1.87's Langfuse callback reads directly
        from kwargs["litellm_params"]["metadata"] — no langfuse_ prefix here;
        that prefix is only stripped from HTTP proxy request headers.
        """
        if not self._trace:
            return {}

        tags = [org_tag(self.org_id)]
        if self._agent_name:
            tags.append(agent_tag(self._agent_name))

        meta = {
            "existing_trace_id": self._trace.id,
            "user_id":           self.user_id,
            "session_id":        self.session_id,
            "tags":              tags,
            "metadata": {
                "org_id":     self.org_id,
                "user_id":    self.user_id,
                "agent_id":   self._agent_id,
                "agent_name": self._agent_name,
            },
        }
        if self._span_stack:
            meta["parent_observation_id"] = self._span_stack[-1].id
        return meta
