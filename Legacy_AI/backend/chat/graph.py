"""Dynamic LangGraph builder for the Chat module.

Builds a supervisor + sub-agent graph at runtime from agent/tool documents
loaded from MongoDB.  All threads share a single MemorySaver so conversation
history persists across API calls within the same server process.
"""

import json
import logging
import operator
import re
from typing import Annotated, Any, Dict, List, Optional, Sequence

import litellm
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from langgraph.graph.message import add_messages
from starlette.concurrency import run_in_threadpool
from typing_extensions import TypedDict

from ai.connectors.errors import is_connector_auth_error
from ai.tools.tools import HumanInterruptException
from backend.chat.auth_error_sink import record_auth_error
from backend.chat.event_sink import emit_event, get_event_sink
from backend.chat.tracing_ctx import get_tracer, with_trace_metadata
from backend.core.config import settings
from bson import ObjectId
from backend.db.database import sync_db

logger = logging.getLogger("chat.graph")

# Max tool-call rounds an agent may take in a single turn before it must answer.
# Allows self-correction on query errors and multi-step lookups without looping forever.
MAX_TOOL_STEPS = 5

# Shared checkpointer for single-agent (HITL) graphs only.
# The supervisor graph is stateless (no checkpointer) — history is reconstructed
# from MongoDB on every call.  The single-agent graph MUST have a checkpointer
# so LangGraph can persist the interrupted state between HTTP requests.
_memory = MemorySaver()

# Cache: org_id -> compiled graph.  Invalidated when agents change (not yet wired).
_org_graphs: Dict[str, Any] = {}

_KB_SOURCE_LINE_RE = re.compile(r"^Source document: (.+)$", re.MULTILINE)


def _extract_kb_sources(tool_result: str) -> list[str]:
    """Pull the "Source document: ..." lines kb_retriever._format_hits emits
    out of a search_knowledge_base tool result, so the final response can
    cite them without the LLM having to paraphrase them faithfully."""
    return list(dict.fromkeys(m.strip() for m in _KB_SOURCE_LINE_RE.findall(tool_result)))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    next: str
    unattended: Optional[bool]   # True for scheduled/no-human runs (see UNATTENDED_SYSTEM_NOTE)
    # Knowledge-base source descriptions surfaced by search_knowledge_base calls this
    # turn, accumulated across every agent node so the final response can cite them.
    kb_sources: Annotated[list[str], operator.add]


# Injected as an extra system message (not baked into the cached per-agent
# sys_prompt, since that's shared with interactive chat) whenever state
# carries unattended=True. A base agent prompt/guardrail commonly says
# "always confirm with the user before sending an email" etc. -- correct for
# interactive chat, but with no human on the other end a scheduled run just
# stalls forever waiting for a reply that will never come. This explicitly
# tells the model to override that default and proceed unless something is
# genuinely unresolvable.
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


# ---------------------------------------------------------------------------
# Agent runtime
# ---------------------------------------------------------------------------

class AgentRuntime:
    """Runtime view of a DB agent document with its resolved tools."""

    def __init__(
        self,
        agent_doc: dict,
        tools: List[dict],
        db_conn_ids: Optional[List[str]] = None,
        rag_ids: Optional[List[str]] = None,
        mcp_tools: Optional[List[dict]] = None,
        mcp_callables: Optional[Dict[str, Any]] = None,
        connector_tools: Optional[List[dict]] = None,
        connector_callables: Optional[Dict[str, Any]] = None,
        # fn_name -> {"display_name", "connector_id", "provider_id"}
        connector_tool_owner: Optional[Dict[str, Dict[str, str]]] = None,
        # Connectors this agent references that had no usable token at load time —
        # each entry: {"fn_name": None, "connector_id", "provider_id", "display_name"}.
        connector_load_errors: Optional[List[Dict[str, Optional[str]]]] = None,
    ) -> None:
        self.agent_id = str(agent_doc["_id"])
        self.org_id = agent_doc.get("organization_id", "")
        self.name = agent_doc.get("name") or "Unnamed Agent"
        self.slug = _slugify(self.name)
        self.prompt = (
            agent_doc.get("prompt")
            or f"You are the {self.name} assistant. Be helpful and concise."
        )
        self.guardrails = agent_doc.get("guardrails") or ""
        self.tool_prompt = agent_doc.get("tool_prompt") or ""
        self.mcp_prompt = agent_doc.get("mcp_prompt") or ""
        self.connector_prompt = agent_doc.get("connector_prompt") or ""
        self.tools = tools
        self.db_conn_ids = db_conn_ids or []
        self.rag_ids = rag_ids or []
        self.mcp_tools = mcp_tools or []
        self.mcp_callables = mcp_callables or {}
        self.connector_tools = connector_tools or []
        self.connector_callables = connector_callables or {}
        self.connector_tool_owner = connector_tool_owner or {}
        self.connector_load_errors = connector_load_errors or []

    @property
    def node_name(self) -> str:
        return f"agent_{self.slug}"

    @property
    def route_fn_name(self) -> str:
        return f"delegate_to_{self.slug}"

    def to_context_dict(self, max_items: int = 8, desc_len: int = 100) -> dict:
        def _brief(name: str, description: str, db_conn_id: Optional[str] = None) -> dict:
            item = {"name": (name or "")[:60], "description": (description or "")[:desc_len]}
            if db_conn_id:
                item["db_conn_id"] = str(db_conn_id)
            return item

        tool_briefs = [
            _brief(
                t.get("name") or "tool",
                t.get("user_description") or t.get("description") or "",
                t.get("db_conn_id"),
            )
            for t in self.tools[:max_items]
        ]
        mcp_briefs = [
            _brief(t["function"]["name"], t["function"].get("description", ""))
            for t in self.mcp_tools[:max_items]
        ]
        connector_briefs = [
            _brief(t["function"]["name"], t["function"].get("description", ""))
            for t in self.connector_tools[:max_items]
        ]
        return {
            "id": self.agent_id,
            "name": self.name,
            "description": self.prompt[:200],
            "tools": tool_briefs,
            "mcp_servers": mcp_briefs,
            "connectors": connector_briefs,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: Optional[str]) -> str:
    if not name:
        return "unnamed"
    import re
    slug = name.strip().lower().replace(" ", "_").replace("-", "_")
    slug = re.sub(r"[^a-z0-9_]", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "unnamed"


def _msgs_to_litellm(messages: Sequence[AnyMessage]) -> list:
    # Gather all tool_call_ids that have a corresponding ToolMessage response in messages
    responded_tool_ids = {
        m.tool_call_id
        for m in messages
        if isinstance(m, ToolMessage) and getattr(m, "tool_call_id", None)
    }

    result: list = []
    active_tool_ids: set[str] = set()

    for m in messages:
        if isinstance(m, HumanMessage):
            result.append({"role": "user", "content": str(m.content)})
        elif isinstance(m, AIMessage):
            item: Dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            tool_calls = getattr(m, "tool_calls", None)
            if tool_calls:
                valid_tcs = []
                for tc in tool_calls:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                    tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    if tc_id and tc_id in responded_tool_ids:
                        valid_tcs.append(
                            {
                                "id": tc_id,
                                "type": "function",
                                "function": {
                                    "name": tc_name,
                                    "arguments": json.dumps(tc_args) if isinstance(tc_args, dict) else str(tc_args),
                                },
                            }
                        )
                        active_tool_ids.add(tc_id)
                if valid_tcs:
                    item["tool_calls"] = valid_tcs
            result.append(item)
        elif isinstance(m, SystemMessage):
            result.append({"role": "system", "content": str(m.content)})
        elif isinstance(m, ToolMessage):
            tc_id = getattr(m, "tool_call_id", None)
            if tc_id in active_tool_ids:
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": str(m.content),
                    }
                )
    return result


def _make_tool_spec(tool_doc: dict) -> dict:
    name = _slugify(tool_doc.get("name") or "tool")
    description = (
        tool_doc.get("user_description")
        or tool_doc.get("description")
        or "Database query tool"
    )
    db_conn_id = tool_doc.get("db_conn_id")
    db_conn_ids = tool_doc.get("_db_conn_ids") or []
    if db_conn_id:
        description = (
            f"{description}\nConnected database connection id: {db_conn_id}. "
            "Use this tool when the user is asking about data from that connection. "
            "For Firestore/Firebase, pass a JSON string like "
            '{"collection":"users","filters":[["status","==","active"]],"limit":20}. '
            "For MongoDB, pass JSON with collection/filter/limit. For SQL, pass one read-only SELECT."
        )
    elif db_conn_ids:
        joined_ids = ", ".join(str(cid) for cid in db_conn_ids)
        description = (
            f"{description}\nSearches schema for database connection id(s): {joined_ids}."
        )

    parameters = (
        tool_doc.get("tool_schema")
        or tool_doc.get("parameters")
        or tool_doc.get("input_schema")
    )
    if not parameters and tool_doc.get("tool_id") and ObjectId.is_valid(str(tool_doc["tool_id"])):
        try:
            reg_doc = sync_db.tool_registry.find_one({"_id": ObjectId(str(tool_doc["tool_id"]))})
            if reg_doc:
                parameters = (
                    reg_doc.get("tool_schema")
                    or reg_doc.get("parameters")
                    or reg_doc.get("input_schema")
                )
        except Exception:
            pass

    if not parameters or not isinstance(parameters, dict):
        parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query or operation to perform",
                }
            },
            "required": ["query"],
        }

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


async def _execute_tool(tool_doc: dict, args: dict, history: Optional[list] = None) -> str:
    """Execute a tool and return its result as a string.

    `history` (recent {"role", "content"} turns) is only consumed by
    search_knowledge_base, to rephrase the query against pronouns/follow-ups
    ("it", "that") before searching — every other tool ignores it.
    """
    tool_name = _slugify(tool_doc.get("name") or "tool")
    agent_id = tool_doc.get("_agent_id")
    if agent_id:
        args["_agent_id"] = agent_id
    logger.info("[TOOL] executing name=%s args=%s", tool_name, args)
    try:
        # search_schema is a synthetic tool — route to the RAG retriever
        if tool_doc.get("_is_search_schema"):
            from ai.rag.search_schema_tool import execute_search_schema
            result = await execute_search_schema(tool_doc, args)
            logger.info("[TOOL] search_schema result (%d chars): %s", len(result), result[:300])
            return result

        # search_knowledge_base is a synthetic tool — route to the KB retriever
        if tool_doc.get("_is_kb_search"):
            from ai.rag.kb_tool import execute_kb_search
            result = await execute_kb_search(tool_doc, args, history=history)
            logger.info("[TOOL] search_knowledge_base result (%d chars): %s", len(result), result[:300])
            return result

        from ai.tools.tools import Tools

        TOOL_DISPATCH = {
            "query_mongo": Tools.query_mongo_read,
            "query_mongo_read": Tools.query_mongo_read,
            "query_mongo_write": Tools.query_mongo_write,
            "query_sql": Tools.query_sql_read,
            "query_sql_read": Tools.query_sql_read,
            "query_sql_write": Tools.query_sql_write,
            "generate_image": Tools.generate_image,
        }

        if tool_name in TOOL_DISPATCH:
            result = TOOL_DISPATCH[tool_name](tool_doc, args)
        elif hasattr(Tools, tool_name):
            result = getattr(Tools, tool_name)(args)
        else:
            raise ValueError(f"Unknown tool '{tool_name}'")

        if hasattr(result, "__await__"):
            result = await result
        logger.info("[TOOL] %s executed (%d chars)", tool_name, len(result))
        return result
    except HumanInterruptException:
        raise
    except Exception as exc:
        logger.error("[TOOL] %s raised %s: %s", tool_name, type(exc).__name__, exc, exc_info=True)
        return f"Tool error ({type(exc).__name__}): {exc}"


# ---------------------------------------------------------------------------
# Node builders
# ---------------------------------------------------------------------------

async def _acompletion_with_token_events(kwargs: Dict[str, Any]) -> Any:
    """litellm.acompletion that, when an SSE event sink is active for this
    request, streams the call and forwards content deltas as `token` events --
    then rebuilds the full non-streaming response object so every caller's
    existing `resp.choices[0].message` handling is untouched.

    Consumers that don't understand `token` (older embeds, the playground's
    if/else-if event loop) simply ignore it and keep working off `done`.
    Tokens may occasionally include preamble from a round that turns out to be
    a tool call; the final `done` payload is always authoritative and replaces
    streamed text client-side. Falls back to a plain call on any stream error."""
    if get_event_sink() is None:
        return await litellm.acompletion(**with_trace_metadata(kwargs))
    try:
        stream = await litellm.acompletion(
            **with_trace_metadata({**kwargs, "stream": True, "stream_options": {"include_usage": True}})
        )
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
            choices = getattr(chunk, "choices", None)
            delta = choices[0].delta if choices else None
            content = getattr(delta, "content", None) if delta else None
            if content:
                await emit_event("token", {"content": content})
        rebuilt = litellm.stream_chunk_builder(chunks, messages=kwargs.get("messages"))
        if rebuilt is None:
            raise ValueError("empty stream")
        return rebuilt
    except Exception:  # noqa: BLE001 - streaming is an enhancement, never the failure mode
        logger.warning("[GRAPH] streamed completion failed; retrying non-streamed", exc_info=True)
        return await litellm.acompletion(**with_trace_metadata(kwargs))


def _build_agent_node(agent: AgentRuntime, model: str, stream_final: bool = False):
    # Stamp org/agent identity onto each tool doc so _execute_tool can scope DB
    # lookups to the right tenant and attribute audit-log entries.
    stamped_tools = [
        {**t, "_org_id": agent.org_id, "_agent_id": agent.agent_id} for t in agent.tools
    ]
    # Auto-inject search_schema when this agent has a query_db tool so the agent
    # can fetch the relevant schema on demand instead of having it pre-injected
    # for every message regardless of content.
    if agent.db_conn_ids:
        from ai.rag.search_schema_tool import build_search_schema_tool
        stamped_tools.append(build_search_schema_tool(agent.org_id, agent.db_conn_ids))
    # Auto-inject search_knowledge_base for agents with rag_ids attached, same
    # on-demand pattern as search_schema above.
    if agent.rag_ids:
        from ai.rag.kb_tool import build_kb_search_tool
        stamped_tools.append(build_kb_search_tool(agent.org_id, agent.rag_ids))

    # DB tools (slugified names, executed via _execute_tool) + MCP tools (raw
    # names, executed via the lazy MCP callables) + connector tools. All bound to LLM.
    tool_specs = [_make_tool_spec(t) for t in stamped_tools] + list(agent.mcp_tools) + list(agent.connector_tools)
    tool_map = {_slugify(t.get("name") or "tool"): t for t in stamped_tools}
    mcp_callables = agent.mcp_callables
    connector_callables = agent.connector_callables
    connector_tool_owner = agent.connector_tool_owner
    connector_load_errors = agent.connector_load_errors
    sys_prompt = agent.prompt
    if agent.guardrails:
        sys_prompt += f"\n\nGuardrails: {agent.guardrails}"
    if tool_specs and agent.db_conn_ids:
        conn_list = ", ".join(str(cid) for cid in agent.db_conn_ids)
        sys_prompt += (
            f"\n\nDatabase connection ids available to this agent: {conn_list}."
            "\n\nWhen the request involves querying a database, call search_schema first "
            "to discover the exact table and column names, then call query_db_read (for "
            "retrievals) or query_db_write (for inserts/updates/deletes) using those exact "
            "names. If the schema says Firestore/Firebase, the query tool expects a JSON "
            "string with collection, optional filters, optional order_by, and limit; do not "
            "write SQL for Firestore. If the schema says MongoDB, the query tool expects JSON "
            "with collection/filter/projection/sort/limit. If the schema says SQL, "
            "query_db_read expects one SELECT statement and query_db_write expects one "
            "INSERT/UPDATE/DELETE statement."
        )

    logger.info(
        "[AGENT:%s] (id=%s) prompt loaded — "
        "base=%d chars | tool_prompt=%s | mcp_prompt=%s | guardrails=%s | sys_prompt=%d chars total",
        agent.slug, agent.agent_id,
        len(agent.prompt),
        f"{len(agent.tool_prompt)} chars" if agent.tool_prompt else "none",
        f"{len(agent.mcp_prompt)} chars" if agent.mcp_prompt else "none",
        f"{len(agent.guardrails)} chars" if agent.guardrails else "none",
        len(sys_prompt),
    )
    if agent.tool_prompt:
        logger.debug("[AGENT:%s] tool_prompt:\n%s", agent.slug, agent.tool_prompt)
    if agent.mcp_prompt:
        logger.debug("[AGENT:%s] mcp_prompt:\n%s", agent.slug, agent.mcp_prompt)

    async def agent_fn(state: ChatState) -> dict:
        tracer = get_tracer()
        if tracer:
            tracer.tag_agent(agent.agent_id, agent.name)

        # Surface connectors this agent needs but couldn't get a token for —
        # this agent may never call a tool at all (no tools loaded for that
        # connector), so this is the only place that failure would ever
        # otherwise be reported to the caller.
        for err in connector_load_errors:
            record_auth_error(err)

        base_msgs: list = [{"role": "system", "content": sys_prompt}]
        if state.get("unattended"):
            base_msgs.append({"role": "system", "content": UNATTENDED_SYSTEM_NOTE})
        base_msgs += _msgs_to_litellm(state["messages"])

        logger.info(
            "[AGENT:%s] invoked — %d msgs in context, %d tools available",
            agent.slug, len(state["messages"]), len(tool_specs),
        )

        # Tool-use loop: keep letting the model call tools (seeing each result,
        # so it can self-correct on errors or chain multi-step lookups) until it
        # returns a final answer or we hit the step cap.
        new_msgs: list = []
        turn_kb_sources: list[str] = []
        final_content = ""
        for step in range(MAX_TOOL_STEPS):
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": base_msgs + _msgs_to_litellm(new_msgs),
            }
            if tool_specs:
                kwargs["tools"] = tool_specs
                kwargs["tool_choice"] = "auto"

            # Only single-agent graphs stream the reply: under a supervisor
            # this node's output gets re-synthesized, and streaming both would
            # show two different texts back to back.
            if stream_final:
                resp = await _acompletion_with_token_events(kwargs)
            else:
                resp = await litellm.acompletion(**with_trace_metadata(kwargs))
            rm = resp.choices[0].message

            if not getattr(rm, "tool_calls", None):
                final_content = rm.content or ""
                logger.info("[AGENT:%s] final output (step %d): %s", agent.slug, step, final_content[:300])
                new_msgs.append(AIMessage(content=final_content))
                break

            logger.info(
                "[AGENT:%s] step %d — %d tool call(s): %s",
                agent.slug, step, len(rm.tool_calls),
                [tc.function.name for tc in rm.tool_calls],
            )
            new_msgs.append(
                AIMessage(
                    content=rm.content or "",
                    tool_calls=[
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "args": json.loads(tc.function.arguments or "{}"),
                        }
                        for tc in rm.tool_calls
                    ],
                )
            )
            try:
                for tc in rm.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    fn_name = tc.function.name
                    if fn_name in mcp_callables:
                        await emit_event("tool_call", {
                            "kind": "mcp", "fn_name": fn_name,
                            "display_name": fn_name,
                        })
                        result = await run_in_threadpool(mcp_callables[fn_name], args)
                    elif fn_name in connector_callables:
                        meta = connector_tool_owner.get(fn_name, {})
                        await emit_event("tool_call", {
                            "kind": "connector", "fn_name": fn_name,
                            "display_name": meta.get("display_name", fn_name),
                        })
                        result = await run_in_threadpool(connector_callables[fn_name], args)
                        logger.info("[CONNECTOR TOOL] %s executed (%d chars) result=%s", fn_name, len(str(result)), str(result)[:200])
                        if is_connector_auth_error(result):
                            record_auth_error({
                                "fn_name": fn_name,
                                "connector_id": meta.get("connector_id"),
                                "provider_id": meta.get("provider_id"),
                                "display_name": meta.get("display_name", fn_name),
                            })
                    else:
                        tool_doc = tool_map.get(fn_name)
                        await emit_event("tool_call", {
                            "kind": "tool", "fn_name": fn_name,
                            "display_name": (tool_doc or {}).get("name", fn_name),
                        })
                        if tool_doc:
                            recent_history = _msgs_to_litellm(state["messages"])[-6:]
                            result = await _execute_tool(tool_doc, args, history=recent_history)
                            if tool_doc.get("_is_kb_search"):
                                turn_kb_sources.extend(_extract_kb_sources(result))
                        else:
                            result = f"Unknown tool: {fn_name}"
                    new_msgs.append(ToolMessage(content=result, tool_call_id=tc.id))
            except HumanInterruptException as hitl:
                question = str(hitl)
                logger.info("[AGENT:%s] ask_human interrupt triggered: %s", agent.slug, question)
                for tc in rm.tool_calls:
                    if not any(isinstance(m, ToolMessage) and getattr(m, "tool_call_id", None) == tc.id for m in new_msgs):
                        new_msgs.append(ToolMessage(content=f"Human interrupt: {question}", tool_call_id=tc.id))
                new_msgs.append(AIMessage(content=question))
                return {"messages": new_msgs, "next": "supervisor", "kb_sources": turn_kb_sources}
        else:
            # Hit the step cap with tools still pending — force a final answer
            # without tools so the turn always ends with a usable reply.
            cap_kwargs = {
                "model": model,
                "messages": base_msgs + _msgs_to_litellm(new_msgs),
            }
            if stream_final:
                resp = await _acompletion_with_token_events(cap_kwargs)
            else:
                resp = await litellm.acompletion(**with_trace_metadata(cap_kwargs))
            final_content = resp.choices[0].message.content or (
                "I wasn't able to complete this within the allowed steps."
            )
            logger.info("[AGENT:%s] step cap reached — forced synthesis: %s", agent.slug, final_content[:300])
            new_msgs.append(AIMessage(content=final_content))

        return {"messages": new_msgs, "next": "supervisor", "kb_sources": turn_kb_sources}

    return agent_fn


def _build_supervisor_node(agents: List[AgentRuntime], model: str):
    routing_tools = [
        {
            "type": "function",
            "function": {
                "name": a.route_fn_name,
                "description": (
                    f"Delegate task to {a.name}. Agent context: "
                    f"{json.dumps(a.to_context_dict(max_items=5, desc_len=60), separators=(',', ':'))}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Specific task to delegate",
                        }
                    },
                    "required": ["task"],
                },
            },
        }
        for a in agents
    ]
    route_to_node = {a.route_fn_name: a.node_name for a in agents}
    # Reverse map: routing function name -> human-readable agent name (used in fallback message)
    fn_to_agent_name = {a.route_fn_name: a.name for a in agents}
    fn_to_agent_id = {a.route_fn_name: a.agent_id for a in agents}

    agent_contexts = [a.to_context_dict() for a in agents]
    agent_list = json.dumps(agent_contexts, separators=(",", ":"))
    system = (
        "You are a supervisor coordinating specialized agents.\n"
        "Each agent below is a JSON object with fields: id, name, description, "
        "tools (name+description), mcp_servers (name+description), connectors (name+description).\n"
        f"Available agents:\n```json\n{agent_list}\n```\n\n"
        "Rules:\n"
        "1. If the user's request matches an agent's domain — judging by its "
        "description, tools, mcp_servers, or connectors — delegate to that agent.\n"
        "2. After an agent responds, synthesize its answer into a final helpful reply "
        "and do NOT delegate again.\n"
        "3. If you can answer directly without delegation, do so."
    )
    logger.debug("[SUPERVISOR] agent contexts built for %d agents: %s", len(agents), agent_list)
    if len(agent_list) > 20_000:
        logger.warning(
            "[SUPERVISOR] agent_list JSON is %d chars — consider lowering max_items/desc_len",
            len(agent_list),
        )

    async def supervisor_fn(state: ChatState) -> dict:
        tracer = get_tracer()
        if tracer:
            tracer.tag_supervisor()

        msgs_raw = state["messages"]

        # Scope the routing/response check to the CURRENT TURN only (messages
        # after the last HumanMessage).  Without this, Turn 1's routing history
        # causes every subsequent turn to skip routing and go straight to synthesis.
        last_human_idx = next(
            (i for i in range(len(msgs_raw) - 1, -1, -1)
             if isinstance(msgs_raw[i], HumanMessage)),
            -1,
        )
        current_turn = msgs_raw[last_human_idx + 1:] if last_human_idx >= 0 else []

        has_agent_response = any(
            isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)
            for m in current_turn
        )
        has_routing = any(
            isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
            for m in current_turn
        )

        logger.info(
            "[SUPERVISOR] turn has_routing=%s has_agent_response=%s (%d msgs this turn)",
            has_routing, has_agent_response, len(current_turn),
        )

        if has_agent_response and has_routing:
            # An agent already replied — synthesize final answer
            logger.info("[SUPERVISOR] agent already replied → synthesizing final answer")
            synth_msgs: list = [
                {
                    "role": "system",
                    "content": "Provide a clear, concise final answer synthesizing the agent's response.",
                }
            ]
            synth_msgs += _msgs_to_litellm(msgs_raw)
            # This synthesis IS the user-visible reply in supervisor mode.
            resp = await _acompletion_with_token_events({
                "model": model,
                "messages": synth_msgs,
            })
            return {
                "messages": [AIMessage(content=resp.choices[0].message.content or "")],
                "next": END,
            }

        # First pass: decide routing. Streamed because the no-routing branch's
        # content is itself the final user-visible answer; when it routes
        # instead, content is rare and the client's done payload wins anyway.
        resp = await _acompletion_with_token_events({
            "model": model,
            "messages": [{"role": "system", "content": system}] + _msgs_to_litellm(msgs_raw),
            "tools": routing_tools,
            "tool_choice": "auto",
        })
        rm = resp.choices[0].message

        if getattr(rm, "tool_calls", None):
            tc = rm.tool_calls[0]
            next_node = route_to_node.get(tc.function.name, END)
            task = json.loads(tc.function.arguments or "{}").get("task", "")
            logger.info(
                "[SUPERVISOR] ROUTING → %s (node=%s) task=%s",
                fn_to_agent_name.get(tc.function.name, "?"), next_node, task[:200],
            )
            await emit_event("routing", {
                "agent_id": fn_to_agent_id.get(tc.function.name, ""),
                "agent_name": fn_to_agent_name.get(tc.function.name, "?"),
            })
            ai_msg = AIMessage(
                content=rm.content or f"Routing to {fn_to_agent_name.get(tc.function.name, 'agent')}...",
                tool_calls=[
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "args": {"task": task},
                    }
                ],
            )
            ack = ToolMessage(content=f"Delegating: {task}", tool_call_id=tc.id)
            return {"messages": [ai_msg, ack], "next": next_node}

        # No routing — direct answer
        logger.info("[SUPERVISOR] NO routing — answering directly: %s", (rm.content or "")[:300])
        return {
            "messages": [AIMessage(content=rm.content or "I can help with that.")],
            "next": END,
        }

    return supervisor_fn


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(agents: List[AgentRuntime], model: str) -> Any:
    """Compile a LangGraph for the given agent set."""
    workflow: StateGraph = StateGraph(ChatState)

    # Deduplicate node names — agents with similar display names can produce
    # the same slug (e.g. "New Agent" vs "new agent").  Append a short id
    # suffix when a collision is detected.
    seen_names: dict[str, int] = {}
    for agent in agents:
        base = agent.node_name
        if base in seen_names:
            seen_names[base] += 1
            agent.slug = f"{agent.slug}_{agent.agent_id[-6:]}"
        else:
            seen_names[base] = 1

    supervisor_fn = _build_supervisor_node(agents, model)
    workflow.add_node("supervisor", supervisor_fn)

    for agent in agents:
        workflow.add_node(agent.node_name, _build_agent_node(agent, model))

    workflow.add_edge(START, "supervisor")

    edge_map: Dict[str, Any] = {a.node_name: a.node_name for a in agents}
    edge_map[END] = END

    def route_supervisor(state: ChatState) -> str:
        return state.get("next", END)

    workflow.add_conditional_edges("supervisor", route_supervisor, edge_map)

    for agent in agents:
        workflow.add_edge(agent.node_name, "supervisor")

    return workflow.compile()


def get_or_build_graph(
    org_id: str, agents: List[AgentRuntime], model: str
) -> Any:
    """Return cached graph for org or build a new one."""
    if org_id not in _org_graphs:
        _org_graphs[org_id] = build_graph(agents, model)
    return _org_graphs[org_id]


def invalidate_org_graph(org_id: str) -> None:
    """Remove cached graph so it rebuilds on next request."""
    _org_graphs.pop(org_id, None)
    try:
        from backend.chat.services import invalidate_org_agent_cache
        invalidate_org_agent_cache(org_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Single-agent graph
# ---------------------------------------------------------------------------

# Cache: f"{org_id}:{agent_id}" -> compiled graph.  Separate from _org_graphs
# so supervisor graphs are never invalidated by single-agent operations.
_single_agent_graphs: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Single Agent Graph
# ---------------------------------------------------------------------------

def build_single_agent_graph(agent: AgentRuntime, model: str) -> Any:
    """Compile a START → agent_node → END graph for 1:1 agent/project chat."""
    workflow: StateGraph = StateGraph(ChatState)
    workflow.add_node(agent.node_name, _build_agent_node(agent, model, stream_final=True))

    workflow.add_edge(START, agent.node_name)
    workflow.add_edge(agent.node_name, END)

    return workflow.compile(checkpointer=_memory)


def get_or_build_single_agent_graph(
    org_id: str, agent: AgentRuntime, model: str
) -> Any:
    """Return cached single-agent graph or build a new one."""
    key = f"{org_id}:{agent.agent_id}"
    if key not in _single_agent_graphs:
        _single_agent_graphs[key] = build_single_agent_graph(agent, model)
    return _single_agent_graphs[key]


def invalidate_single_agent_graph(org_id: str, agent_id: str) -> None:
    """Remove cached single-agent graph so it rebuilds on next request."""
    _single_agent_graphs.pop(f"{org_id}:{agent_id}", None)
