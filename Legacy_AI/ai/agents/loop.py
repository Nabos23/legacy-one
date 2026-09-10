"""Shared synchronous tool-use loop for orchestration agents."""
import asyncio
import inspect
import json
import logging
import time
from typing import Dict, Optional, Tuple

from ai.connectors.reauth_interrupt import ConnectorReauthException
from ai.multi_orchestration.models import HumanInterruptException
from ai.multi_orchestration.supervisor.handback import SupervisorHandbackException

import litellm
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

logger = logging.getLogger(__name__)

_RETRYABLE = (RateLimitError, ServiceUnavailableError, Timeout)
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2


def _completion_with_retry(**kwargs):
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            return litellm.completion(**kwargs)
        except _RETRYABLE as e:
            last_exc = e
            wait = _RETRY_BACKOFF * (2 ** attempt)
            logger.warning("LiteLLM transient error (attempt %d/%d): %s — retrying in %ss", attempt + 1, _MAX_RETRIES, e, wait)
            time.sleep(wait)
        except (AuthenticationError, BadRequestError):
            raise
    raise last_exc


def run_tool_loop(
    model: str,
    tools: list,
    tool_callables: Dict[str, callable],
    messages: list,
    agent_name: str = "agent",
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Run LiteLLM tool-use loop until the model produces a final text response.

    Returns (output, last_tool_name, last_tool_output).
    """
    kwargs: dict = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools

    logger.info("[loop:%s] llm call — model=%s messages=%d tools=%d", agent_name, model, len(messages), len(tools))
    response = _completion_with_retry(**kwargs)

    last_tool_name: Optional[str] = None
    last_tool_output: Optional[str] = None
    tool_call_round = 0

    while response.choices[0].finish_reason == "tool_calls":
        tool_call_round += 1
        assistant_msg = response.choices[0].message
        messages.append(assistant_msg)

        for tc in assistant_msg.tool_calls:
            tool_name = tc.function.name
            fn = tool_callables.get(tool_name)
            if fn is None:
                tool_output = f"Unknown tool '{tool_name}' — skipping."
                logger.warning("[loop:%s] unknown tool '%s'", agent_name, tool_name)
            else:
                inp = json.loads(tc.function.arguments)
                logger.info("[loop:%s] tool call #%d — tool=%s args=%.200s", agent_name, tool_call_round, tool_name, str(inp))
                try:
                    result = fn(inp)
                    if inspect.iscoroutine(result):
                        result = asyncio.run(result)
                    tool_output = str(result)
                except HumanInterruptException:
                    raise  # propagate HITL signal up to the scheduler
                except ConnectorReauthException:
                    raise  # propagate connector-reauth signal up to the scheduler
                except SupervisorHandbackException:
                    raise  # propagate handback signal up to the scheduler
                except Exception as exc:
                    tool_output = f"Tool '{tool_name}' error: {exc}"
                    logger.error("[loop:%s] tool '%s' raised: %s", agent_name, tool_name, exc)

            logger.info("[loop:%s] tool result — tool=%s output_len=%d", agent_name, tool_name, len(tool_output))
            last_tool_name = tool_name
            last_tool_output = tool_output

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_output,
            })

        kwargs["messages"] = messages
        logger.info("[loop:%s] llm follow-up — round=%d messages=%d", agent_name, tool_call_round, len(messages))
        response = _completion_with_retry(**kwargs)

    output = response.choices[0].message.content or ""
    logger.info("[loop:%s] done — output_len=%d tool_rounds=%d", agent_name, len(output), tool_call_round)
    return output, last_tool_name, last_tool_output


def _image_generation_with_retry(**kwargs):
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            return litellm.image_generation(**kwargs)
        except _RETRYABLE as e:
            last_exc = e
            wait = _RETRY_BACKOFF * (2 ** attempt)
            logger.warning(
                "LiteLLM image_generation transient error (attempt %d/%d): %s — retrying in %ss",
                attempt + 1, _MAX_RETRIES, e, wait,
            )
            time.sleep(wait)
        except (AuthenticationError, BadRequestError):
            raise
    raise last_exc