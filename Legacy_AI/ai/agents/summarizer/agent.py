import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Optional

from ai.agents.sub_agent import _completion_with_retry
from ai.agents.summarizer.prompt import SYSTEM_PROMPT

if TYPE_CHECKING:
    from ai.tracing.tracer import AgentTracer

logger = logging.getLogger(__name__)


class Summarizer_Agent:
    """
    Sliding-window compression: once message history reaches 20 entries,
    everything except the last 10 is compressed into a single summary message.
    The last 10 messages are always kept intact.

    Flow:
      At 20 msgs  → compress first 10 → [summary, last_10]         = 11 entries
      At 21 msgs  → compress [summary + 10 middle] → [new_summary, latest_10] = 11 entries
      (repeats as new messages accumulate back to 20+)

    Runs between Langfuse turn-traces (after end_trace in human_interrupt,
    before start_trace in router), so it opens its own dedicated trace.
    """

    def __init__(self, model: str, tracer: Optional["AgentTracer"] = None) -> None:
        self._model = model
        self._tracer = tracer

    def invoke(self, state: dict) -> dict[str, Any]:
        messages = state.get("messages", [])
        interaction_count = state.get("interaction_count", 0)

        # Must have more than 10 messages so there's something to compress
        # beyond the 10 we always keep.
        if len(messages) <= 10:
            return {}

        to_summarize = messages[:-10]   # everything except the last 10
        recent       = messages[-10:]   # always keep the latest 10 intact

        # Open a dedicated trace — summarizer fires between turn-traces.
        if self._tracer:
            self._tracer.start_trace(
                "summarizer.compress",
                input={
                    "interaction_count": interaction_count,
                    "message_count": len(messages),
                    "compressing": len(to_summarize),
                    "keeping": len(recent),
                },
            )

        lines = []
        for i, msg in enumerate(to_summarize, 1):
            if msg.get("role") == "summary":
                # Previous compression result — feed it back verbatim
                lines.append(f"[Previous summary]: {msg.get('content', '')}")
            else:
                agent = msg.get("agent_name", "Agent")
                lines.append(f"Turn {i}:")
                lines.append(f"  User: {msg.get('user_query', '')}")
                lines.append(f"  {agent}: {msg.get('content', '')}")
        context_block = "\n".join(lines)

        try:
            with (self._tracer.span(
                "compress.llm",
                input={"message_count": len(to_summarize)},
                metadata={"model": self._model},
            ) if self._tracer else _noop_span()) as span:
                response = _completion_with_retry(
                    lf_metadata=self._tracer.litellm_metadata() if self._tracer else None,
                    model=self._model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": f"Summarize these past turns:\n\n{context_block}"},
                    ],
                    max_tokens=500,
                )
                summary_text = response.choices[0].message.content.strip()
                span.end(output={"summary_length": len(summary_text)})
        except Exception as e:
            logger.error("Summarizer LLM call failed: %s — skipping summarisation", e)
            if self._tracer:
                self._tracer.end_trace(output={"error": str(e)})
            return {}

        summary_message = {
            "role":       "summary",
            "agent_name": "Summarizer_Agent",
            "user_query": "[summarized]",
            "content":    summary_text,
        }

        logger.info(
            "Summarizer compressed %d messages → 1 summary + %d recent",
            len(to_summarize), len(recent),
        )

        if self._tracer:
            self._tracer.end_trace(output={
                "compressed": len(to_summarize),
                "kept": len(recent),
                "summary_length": len(summary_text),
            })

        return {
            "messages":       [summary_message] + recent,
            "memory_summary": summary_text,
        }

    def as_node(self):
        return self.invoke


@contextmanager
def _noop_span():
    """Fallback context manager used when no tracer is configured."""
    class _Noop:
        def end(self, **_): pass
    yield _Noop()
