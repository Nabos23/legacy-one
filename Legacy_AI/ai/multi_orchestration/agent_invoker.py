"""AgentInvoker — stateless executor for a single RuntimeAgentNode.

Agents know nothing about each other. They receive a task string + optional
conversation history, run the tool-use loop, and return (output, tool_records).
All state management is the RuntimeScheduler's responsibility.
"""
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Callable, Dict, List, Tuple

from ai.agents.loop import run_tool_loop
from ai.connectors.errors import is_connector_auth_error
from ai.connectors.reauth_interrupt import ConnectorReauthException
from ai.multi_orchestration.models import ToolInvocationRecord
from ai.multi_orchestration.runtime_graph import RuntimeAgentNode
from ai.multi_orchestration.supervisor import SupervisorHandbackException

logger = logging.getLogger(__name__)

# Human-readable dump of exactly what memory/context each agent receives.
# Purely for inspection; failures here never affect a run.
#
# Deliberately NOT in the working directory: that puts it inside the tree the
# dev-server file watcher monitors, so every agent turn triggered a reload —
# which restarts the process and silently kills in-flight background runs.
# Override with ORCHESTRATION_MEMORY_DUMP to place it elsewhere.
_MEMORY_DUMP_FILE = os.environ.get(
    "ORCHESTRATION_MEMORY_DUMP",
    os.path.join(tempfile.gettempdir(), "orchestration_memory.log"),
)


def _dump_agent_memory(agent_name: str, task: str) -> None:
    try:
        stamp = datetime.now(timezone.utc).isoformat()
        block = (
            f"\n{'=' * 80}\n"
            f"[{stamp}] MEMORY SENT TO AGENT: {agent_name}\n"
            f"{'-' * 80}\n"
            f"{task}\n"
            f"{'=' * 80}\n"
        )
        with open(_MEMORY_DUMP_FILE, "a", encoding="utf-8") as fh:
            fh.write(block)
    except Exception:  # never let logging break a run
        logger.warning("failed to write orchestration memory dump", exc_info=True)


UNATTENDED_SYSTEM_NOTE = (
    "You are executing as a scheduled, unattended run right now -- no human is "
    "present in this conversation to respond. If your instructions above say to "
    "confirm with the user before an action (sending an email, making a change, "
    "etc.), that does not apply here: there is no one to answer, and stopping to "
    "ask would just leave the task incomplete. Use the task message and any "
    "pre-provided answers to resolve ambiguity, then proceed and complete the "
    "task using your best judgment. Only stop short of completing an action if "
    "it is genuinely ambiguous in a way no reasonable judgment call can resolve "
    "-- in that case, state clearly what is blocking you and why."
)


class AgentInvoker:
    def __init__(self, model: str):
        self._model = model

    def invoke(
        self,
        node: RuntimeAgentNode,
        task: str,
        history: List[dict] = None,
        unattended: bool = False,
    ) -> Tuple[str, List[ToolInvocationRecord]]:
        """
        Invoke a single agent node synchronously.
        Returns (output_text, tool_invocation_records).
        """
        system = self._build_system_prompt(node, unattended=unattended)
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": task})

        tool_records: List[ToolInvocationRecord] = []
        instrumented = self._instrument_callables(
            node.tool_callables, tool_records, node.connector_tool_owner,
            unattended=unattended, history=history,
        )

        logger.info("[invoker:%s] start — task=%.150s history_msgs=%d unattended=%s", node.name, task, len(history or []), unattended)
        _dump_agent_memory(node.name, task)

        output, _, _ = run_tool_loop(
            model=self._model,
            tools=node.tools,
            tool_callables=instrumented,
            messages=messages,
            agent_name=node.name,
        )

        result = output or "I was unable to complete this task."
        logger.info("[invoker:%s] done — output_len=%d tools_called=%d", node.name, len(result), len(tool_records))
        return result, tool_records

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _instrument_callables(
        self,
        callables: Dict[str, Callable],
        records: List[ToolInvocationRecord],
        connector_tool_owner: Dict[str, Dict[str, str]],
        unattended: bool = False,
        history: List[dict] = None,
    ) -> Dict[str, Callable]:
        """Wrap each callable to capture ToolInvocationRecord on every call."""
        instrumented = {}
        for name, fn in callables.items():
            instrumented[name] = self._wrap(
                name, fn, records, connector_tool_owner.get(name), unattended=unattended, history=history,
            )
        return instrumented

    def _wrap(
        self,
        tool_name: str,
        fn: Callable,
        records: List[ToolInvocationRecord],
        connector_owner: Dict[str, str] = None,
        unattended: bool = False,
        history: List[dict] = None,
    ) -> Callable:
        def wrapper(inp: dict):
            if unattended and tool_name == "ask_human":
                return (
                    "You are executing an unattended schedule run right now -- no human is present to answer. "
                    "Do NOT stop or ask for confirmation. Use pre-provided answers or best judgment and proceed to complete your action immediately."
                )
            start = datetime.now(timezone.utc)
            try:
                # search_knowledge_base is the only callable that accepts recent
                # conversation history (for query rephrasing) — every other tool
                # keeps the plain single-arg signature, so args stored on
                # ToolInvocationRecord below never carry the history blob.
                raw = fn(inp, history) if tool_name == "search_knowledge_base" else fn(inp)
                end = datetime.now(timezone.utc)
                if connector_owner and is_connector_auth_error(raw):
                    records.append(ToolInvocationRecord(
                        tool_name=tool_name,
                        arguments=inp,
                        result="",
                        status="error",
                        started_at=start,
                        ended_at=end,
                        error=str(raw),
                    ))
                    raise ConnectorReauthException(
                        connector_id=connector_owner["connector_id"],
                        provider_id=connector_owner["provider_id"],
                        display_name=connector_owner["display_name"],
                        fn_name=tool_name,
                    )
                records.append(ToolInvocationRecord(
                    tool_name=tool_name,
                    arguments=inp,
                    result=str(raw)[:2000],
                    status="success",
                    started_at=start,
                    ended_at=end,
                ))
                return raw
            except (ConnectorReauthException, SupervisorHandbackException):
                # Control signals, not tool failures — no error record.
                raise
            except Exception as exc:
                end = datetime.now(timezone.utc)
                records.append(ToolInvocationRecord(
                    tool_name=tool_name,
                    arguments=inp,
                    result="",
                    status="error",
                    started_at=start,
                    ended_at=end,
                    error=str(exc),
                ))
                raise
        return wrapper

    def _build_system_prompt(self, node: RuntimeAgentNode, unattended: bool = False) -> str:
        """Compose the system prompt from the agent's stored blocks.

        Tool guidance (including the ask_human / human-in-the-loop block) is
        already baked into tool_prompt/mcp_prompt/connector_prompt at agent
        creation time, so nothing tool-related is injected here. The only
        genuinely runtime piece is the pipeline context, which depends on this
        agent's position in *this* orchestration.
        """
        blocks: List[str] = [node.prompt]
        if unattended:
            blocks.append(UNATTENDED_SYSTEM_NOTE)

        if node.guardrails:
            rules = "\n".join(f"- {g}" for g in node.guardrails)
            blocks.append(f"GUARDRAILS:\n{rules}")

        if node.tool_prompt:
            blocks.append(node.tool_prompt)
        if node.mcp_prompt:
            blocks.append(node.mcp_prompt)
        if node.connector_prompt:
            blocks.append(node.connector_prompt)

        # Supervisor mode: there is no static next-agent list, so the sequential
        # PIPELINE CONTEXT block below never fires. Without a replacement the
        # agent loses "the previous agent's output IS your input" and "actually
        # send, do not draft" — which is what makes a routed Sheets/Gmail agent
        # ask the user to re-paste data it can already see.
        if node.handback_prompt:
            blocks.append(node.handback_prompt)

        # Always inject PIPELINE CONTEXT for orchestration nodes so every node
        # understands it is part of a team, must execute ONLY its role's tool,
        # and must NOT complain about missing tools for other agents' tasks.
        lines = ""
        if node.next_agents:
            lines = "Once you finish, your output is handed to the following agent(s):\n" + "\n".join(
                f"  - {a['name']}: {a['description']}" if a.get("description") else f"  - {a['name']}"
                for a in node.next_agents
            ) + "\nDo NOT do those downstream agents' work. Complete only your own step, then stop."
        else:
            lines = "Complete your specific step now. and your final output should contain a complete summary of all the history of the run including previous agent's work and reponses."

        blocks.append(
            "PIPELINE CONTEXT:\n"
            "You are one step inside a multi-agent orchestration layer — you are connected to "
            "other agents and run as part of a larger pipeline. The conversation/memory above is "
            "the MAIN CONTEXT and the ultimate source of truth for you.\n"
            "You are a specialized node in a multi-agent pipeline.\n"
            "- Focus ONLY on tasks relevant to YOUR tools. Ignore all other tasks.\n"
            "- Use data produced by previous agents in the memory above directly in your tool calls.\n"
            "- Execute your action FULLY in this turn (call your real tool — do NOT create drafts, previews, or ask to confirm).\n"
            "- Call `ask_human` ONLY if a critical required tool parameter is missing from BOTH user input and memory.\n"
            "- DO NOT ask if the user is satisfied or not, or ask for preferences, Do your work with the best of the abilites and FINISH YOUR TURN.\n"
            f"{lines}"
        )

        return "\n\n".join(b for b in blocks if b)
