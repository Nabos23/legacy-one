import asyncio
import json
import logging
import uuid
import os
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import litellm
from bson import ObjectId
from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ai.tracing.tracer import AgentTracer
from backend.chat.auth_error_sink import get_auth_errors, reset_auth_errors
from backend.chat.event_sink import set_event_sink
from backend.chat.graph import AgentRuntime, get_or_build_graph
from backend.chat.tracing_ctx import set_tracer
from backend.chat.schemas import (
    AgentHistoryPublic,
    AgentSummary,
    ChatAttachment,
    ChatResponse,
    SessionHistoryResponse,
    SessionListItem,
    SessionPublic,
    SummaryPublic,
    TurnPublic,
)
from backend.core.config import settings
from backend.core.softdelete import NOT_DELETED
from backend.db.database import (
    agents_collection,
    chat_sessions_collection,
    db,
    db_connections_collection,
    tool_registry_collection,
    tools_collection,
)
from backend.memory.conversation_store import ConversationStore
from backend.memory.sub_agent_memory import SubAgentMemory
from ai.connectors.registry import CONNECTOR_CLASS_MAP
from backend.agent.services import build_agent_visibility_clauses
from backend.mcp_server.services import load_agent_mcp_tools_async
from backend.connectors.services import get_access_token, get_connector, resolve_owner_id

logger = logging.getLogger("chat.services")

_conversation_store = ConversationStore(db=db)
_sub_agent_memory = SubAgentMemory(store=_conversation_store, model=settings.DEFAULT_MODEL)

_NAME_SYSTEM_PROMPT = (
    "Generate a short 3–6 word title for this chat. "
    "No quotes. No period. Use simple words."
)


def _compose_message_with_attachments(
    message: str,
    attachments: Optional[List[ChatAttachment]] = None,
) -> str:
    """Inline processed attachment content into the user message as plain text.

    Documents contribute their extracted text; images contribute OCR text when
    available. The graph / sub-agent pipeline stays text-only — no multimodal
    message shapes are introduced here.
    """
    if not attachments:
        return message

    parts: List[str] = []
    if message and message.strip():
        parts.append(message.strip())

    for att in attachments:
        name = att.filename or "attachment"
        if att.kind == "document" and att.text:
            note = " (truncated)" if att.truncated else ""
            parts.append(
                f"[Attached document: {name}{note}]\n{att.text}"
            )
        elif att.kind == "image":
            ocr = (att.ocr_text or "").strip()
            if ocr:
                parts.append(
                    f"[Attached image: {name} — OCR text]\n{ocr}"
                )
            else:
                parts.append(
                    f"[Attached image: {name} — no readable text could be "
                    f"extracted via OCR. Describe or answer based on the "
                    f"filename and the user's question only.]"
                )

    return "\n\n".join(parts) if parts else message


async def _generate_chat_name(first_message: str) -> Optional[str]:
    """Call a small, cheap model to produce a short title for the chat session."""
    try:
        resp = await litellm.acompletion(
            model=settings.TITLE_MODEL,
            messages=[
                {"role": "system", "content": _NAME_SYSTEM_PROMPT},
                {"role": "user", "content": first_message[:500]},
            ],
            max_tokens=20,
            temperature=0.3,
        )
        name = resp.choices[0].message.content.strip().strip('"').rstrip(".")
        return name or None
    except Exception:
        logger.warning("Chat name generation failed", exc_info=True)
        return None


async def _set_chat_name_if_unset(thread_id: str, first_message: str) -> Optional[str]:
    """Generate and persist a session title, only if one isn't set yet.

    Designed to run concurrently with the main chat turn (see send_message): the
    cheap title call finishes during the much slower LLM invocation, so it adds
    ~no latency yet the name is ready to return in the response. The update
    filter won't overwrite a name set concurrently (e.g. a manual rename), so it
    is safe under repeated/parallel first messages. Returns the new title, or
    None on failure.
    """
    name = await _generate_chat_name(first_message)
    if not name:
        return None
    await chat_sessions_collection.update_one(
        {
            "thread_id": thread_id,
            "$or": [{"name": None}, {"name": {"$exists": False}}],
        },
        {"$set": {"name": name}},
    )
    return name


async def load_agent_mcp(agent_doc: dict) -> Tuple[list, dict]:
    """Build (mcp_tools, mcp_callables) for an agent from its per-tool MCP attachments.

    Reads the agent_mcp_tools junction (which tools of which servers this
    agent has been individually attached to, not whole servers via the
    legacy agent.mcp_server_ids) via
    backend.mcp_server.services.load_agent_mcp_tools_async. Returns ([], {})
    when the agent has no MCP tools attached.
    """
    agent_id = str(agent_doc.get("_id", "?"))
    agent_name = agent_doc.get("name", agent_id)

    try:

        tools, callables = await load_agent_mcp_tools_async(agent_id)
        tool_names = [t.get("function", {}).get("name") for t in tools]
        logger.info(
            "[MCP] agent=%s (id=%s) loaded %d attached tool(s)=%s",
            agent_name, agent_id, len(tools), tool_names,
        )
        return tools, callables
    except Exception:  # never fail agent load on an MCP issue
        logger.warning("[MCP] failed to build MCP tools for agent", exc_info=True)
        return [], {}


async def load_agent_connectors(
    agent_doc: dict, user_id: str
) -> Tuple[list, dict, Dict[str, Dict[str, str]], List[Dict[str, Optional[str]]]]:
    """Build (connector_tools, connector_callables, connector_tool_owner, connector_load_errors)
    for an agent from its connector_ids. connector_tool_owner maps each tool's function name to
    {"display_name", "connector_id", "provider_id"} — used both to label live
    "querying X" progress events and to identify which connector needs reconnecting
    if a tool call fails on auth (see ai.connectors.errors.is_connector_auth_error).
    connector_load_errors lists connectors that couldn't produce a usable token at all
    (never connected, or refresh failed) — same shape as a call-time auth failure, so the
    Reconnect UI still shows up even though the agent never got a tool to call and fail."""
    connector_ids = agent_doc.get("connector_ids", [])
    if not connector_ids:
        return [], {}, {}, []


    agent_id = str(agent_doc.get("_id", "?"))
    org_id = str(agent_doc.get("organization_id", ""))
    all_tools: list = []
    all_callables: dict = {}
    connector_tool_owner: Dict[str, Dict[str, str]] = {}
    connector_load_errors: List[Dict[str, Optional[str]]] = []

    for connector_id in connector_ids:
        try:
            connector_doc = await get_connector(connector_id)
            provider_id = connector_doc["provider_id"]
            display_name = connector_doc.get("name", provider_id)
            owner_id = resolve_owner_id(connector_doc, user_id, org_id)
            token = await get_access_token(connector_id, owner_id)
            if not token:
                logger.warning("[CONNECTORS] agent=%s no token for connector=%s provider=%s", agent_id, connector_id, provider_id)
                connector_load_errors.append({
                    "fn_name": None,
                    "connector_id": connector_id,
                    "provider_id": provider_id,
                    "display_name": display_name,
                })
                continue
            cls = CONNECTOR_CLASS_MAP.get(provider_id)
            if not cls:
                logger.warning("[CONNECTORS] agent=%s no class for provider=%s", agent_id, provider_id)
                continue
            tools, callables = cls(token, agent_id=agent_id).as_tools()
            all_tools.extend(tools)
            all_callables.update(callables)
            meta = {"display_name": display_name, "connector_id": connector_id, "provider_id": provider_id}
            for t in tools:
                fn_name = t.get("function", {}).get("name")
                if fn_name:
                    connector_tool_owner[fn_name] = meta
            logger.info("[CONNECTORS] agent=%s loaded %d tools for provider=%s", agent_id, len(tools), provider_id)
        except Exception:
            logger.warning("[CONNECTORS] agent=%s failed to load connector=%s", agent_id, connector_id, exc_info=True)

    return all_tools, all_callables, connector_tool_owner, connector_load_errors


_org_agent_runtimes_cache: Dict[str, List[AgentRuntime]] = {}


def invalidate_org_agent_cache(org_id: str) -> None:
    """Clear cached org agent runtimes."""
    for k in list(_org_agent_runtimes_cache.keys()):
        if k.startswith(f"{org_id}:"):
            _org_agent_runtimes_cache.pop(k, None)


async def _load_single_org_agent_runtime(agent_doc: dict, org_id: str, user_id: str) -> AgentRuntime:
    agent_id = str(agent_doc.get("_id", "?"))
    agent_name = agent_doc.get("name", agent_id)
    tool_ids = agent_doc.get("tool_ids", [])
    logger.info("[TOOLS] agent=%s (id=%s) tool_ids=%s", agent_name, agent_id, tool_ids or "[]")
    tools: list = []
    for tid in tool_ids:
        if ObjectId.is_valid(tid):
            tool_doc = await tools_collection.find_one(
                {"_id": ObjectId(tid), **NOT_DELETED}
            )
            if tool_doc:
                reg_id = tool_doc.get("tool_id")
                if reg_id and ObjectId.is_valid(str(reg_id)):
                    reg_doc = await tool_registry_collection.find_one({"_id": ObjectId(str(reg_id))})
                    if reg_doc:
                        for field in ("tool_schema", "name", "description"):
                            if field in reg_doc and field not in tool_doc:
                                tool_doc[field] = reg_doc[field]
                tools.append(tool_doc)
    logger.info(
        "[TOOLS] agent=%s (id=%s) resolved %d/%d tool(s): %s",
        agent_name, agent_id, len(tools), len(tool_ids),
        [t.get("name") or t.get("user_description", "?")[:40] for t in tools],
    )

    db_conn_ids = [t["db_conn_id"] for t in tools if t.get("db_conn_id")]
    if await _has_db_query_tool(tools):
        if not db_conn_ids:
            conn_cursor = db_connections_collection.find(
                {"organization_id": org_id, **NOT_DELETED}
            )
            conn_docs = await conn_cursor.to_list(length=100)
            db_conn_ids = [str(c["_id"]) for c in conn_docs]

    mcp_tools, mcp_callables = await load_agent_mcp(agent_doc)
    connector_tools, connector_callables, connector_tool_owner, connector_load_errors = (
        await load_agent_connectors(agent_doc, user_id)
    )
    from backend.knowledgebase.services import filter_visible_kb_ids

    visible_rag_ids = await filter_visible_kb_ids(org_id, agent_doc.get("rag_ids", []), user_id)

    return AgentRuntime(
        agent_doc,
        tools,
        db_conn_ids=db_conn_ids,
        rag_ids=visible_rag_ids,
        mcp_tools=mcp_tools,
        mcp_callables=mcp_callables,
        connector_tools=connector_tools,
        connector_callables=connector_callables,
        connector_tool_owner=connector_tool_owner,
        connector_load_errors=connector_load_errors,
    )


async def _load_org_agents(org_id: str, user_id: str = "") -> List[AgentRuntime]:
    """Fetch all active agents for an org in parallel, caching runtimes in RAM."""
    cache_key = f"{org_id}:{user_id}"
    if cache_key in _org_agent_runtimes_cache:
        return _org_agent_runtimes_cache[cache_key]

    cursor = agents_collection.find({
        "organization_id": org_id,
        "is_active": True,
        **NOT_DELETED,
        "$or": await build_agent_visibility_clauses(user_id),
    })
    agent_docs = await cursor.to_list(length=100)

    if not agent_docs:
        return []

    runtimes = await asyncio.gather(
        *[_load_single_org_agent_runtime(doc, org_id, user_id) for doc in agent_docs]
    )
    _org_agent_runtimes_cache[cache_key] = list(runtimes)
    return _org_agent_runtimes_cache[cache_key]


async def _has_db_query_tool(tools: List[dict]) -> bool:
    """True if any of the agent's tools is the query_db tool."""
    for t in tools:
        if t.get("name") == "Query DB Tool":
            return True
        reg_id = t.get("tool_id")
        if reg_id and ObjectId.is_valid(reg_id):
            reg = await tool_registry_collection.find_one({"_id": ObjectId(reg_id)})
            if reg and reg.get("type") == "db_query":
                return True
    return False


def _extract_agent(
    messages: list,
    agents: List[AgentRuntime],
) -> Tuple[str, str]:
    """Infer which sub-agent handled a turn by inspecting tool_calls."""
    route_map = {a.route_fn_name: (a.agent_id, a.name) for a in agents}
    for m in messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            fn = m.tool_calls[0].get("name", "")
            if fn in route_map:
                return route_map[fn]
    return "supervisor", "Supervisor"


async def create_session(organization_id: str, user_id: str) -> SessionPublic:
    agents = await _load_org_agents(organization_id, user_id=user_id)
    if not agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active agents found for this organization.",
        )

    get_or_build_graph(organization_id, agents, settings.DEFAULT_MODEL)

    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Note: Lazy session creation — session document is created on the first message turn in MongoDB,
    # ensuring zero empty sessions pollute the database.

    return SessionPublic(
        thread_id=thread_id,
        organization_id=organization_id,
        name=None,
        available_agents=[
            AgentSummary(
                agent_id=a.agent_id,
                name=a.name,
                description=a.prompt[:100] if a.prompt else None,
                tool_count=len(a.tools),
            )
            for a in agents
        ],
        created_at=now,
    )


@dataclass
class _SendMessageCtx:
    thread_id: str
    message: str
    user_id: str
    org_id: str
    agents: List[AgentRuntime]
    graph: Any
    messages_for_graph: list
    tracer: AgentTracer
    title_task: Optional[asyncio.Task]
    session_name: Optional[str]


async def _prepare_send_message(
    thread_id: str,
    message: str,
    user_id: str,
    organization_id: str,
    attachments: Optional[List[ChatAttachment]] = None,
) -> _SendMessageCtx:
    """Everything that can fail with a real HTTP status (session/agents not
    found), plus history/graph loading. Shared by the blocking and streaming
    entry points; must run BEFORE a StreamingResponse is returned, since a
    streaming response's status code is committed as soon as it starts."""
    session = await chat_sessions_collection.find_one(
        {"thread_id": thread_id, "organization_id": organization_id, **NOT_DELETED}
    )

    org_id: str = organization_id

    agents = await _load_org_agents(org_id, user_id=user_id)
    if not agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active agents found for this organization.",
        )

    if not session:
        now = datetime.now(timezone.utc)
        session = {
            "thread_id": thread_id,
            "lg_thread_id": f"{thread_id}::e1",
            "epoch": 1,
            "organization_id": org_id,
            "user_id": user_id,
            "agent_ids": [a.agent_id for a in agents],
            "name": None,
            "created_at": now,
            "is_deleted": False,
        }
        await chat_sessions_collection.insert_one(session)

    # Fold attachment text/OCR into the user message so sub-agents see file
    # content without any graph/multimodal changes.
    composed = _compose_message_with_attachments(message, attachments)

    logger.info(
        "[INPUT] thread=%s user=%s attachments=%d msg=%s",
        thread_id, user_id, len(attachments or []), composed[:300],
    )

    # --- Kick off title generation in parallel -------------------------
    # On the first message, start generating the session title NOW so it runs
    # concurrently with seeding + the graph invocation below. The cheap nano
    # call finishes well within the main LLM turn, so the title is ready to
    # return in this same response with ~no added latency.
    # Use the raw user message (not attachment dump) for a cleaner title.
    title_task: Optional[asyncio.Task] = None
    if not session.get("name"):
        title_task = asyncio.create_task(
            _set_chat_name_if_unset(thread_id, message or composed)
        )

    graph = get_or_build_graph(org_id, agents, settings.DEFAULT_MODEL)

    # Reconstruct full conversation history from MongoDB on every call.
    history = await _sub_agent_memory.build_session_seed(thread_id, user_id)
    logger.info(
        "[HISTORY] thread=%s loaded %d messages from MongoDB",
        thread_id, len(history),
    )

    # --- Pre-fetch relevant DB schema for THIS message --------------------
    # Retrieve the top-k tables (name, columns, PK, FKs, description) matching
    # the user's request and inject them up front, so the agent already has the
    # exact schema and skips the extra fetch_schema tool round-trip.
    prefetch_messages: list = []
    schema_conn_ids = next(
        (a.db_conn_ids for a in agents if a.db_conn_ids),
        None,
    )
    if schema_conn_ids:
        from ai.rag.schema_retriever import get_relevant_schema
        schema_text = await get_relevant_schema(composed, schema_conn_ids)
        logger.info(
            "[SCHEMA] pre-fetched relevant schema (%d chars) for conn_ids=%s",
            len(schema_text), schema_conn_ids,
        )
        prefetch_messages = [
            SystemMessage(
                content=(
                    "Connected database schema relevant to the user's request "
                    "(use these EXACT table and column names):\n\n" + schema_text
                )
            )
        ]

    messages_for_graph = (
        prefetch_messages + history + [HumanMessage(content=composed)]
    )

    tracer = AgentTracer(org_id=org_id, user_id=user_id, session_id=thread_id)

    return _SendMessageCtx(
        thread_id=thread_id,
        message=composed,
        user_id=user_id,
        org_id=org_id,
        agents=agents,
        graph=graph,
        messages_for_graph=messages_for_graph,
        tracer=tracer,
        title_task=title_task,
        session_name=session.get("name"),
    )


async def _finalize_send_message(ctx: _SendMessageCtx, result: dict) -> ChatResponse:
    messages = result.get("messages", [])
    final_response = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
            final_response = str(m.content)
            break

    # --- Collect the title generated in parallel above -----------------
    # The task ran alongside the graph turn; it's effectively done by now.
    session_name: Optional[str] = ctx.session_name
    if ctx.title_task is not None:
        try:
            generated = await ctx.title_task
            session_name = generated or session_name
        except Exception:
            logger.warning("Title task failed", exc_info=True)

    agent_id, _agent_name = _extract_agent(messages, ctx.agents)
    final_reply = final_response or "Request processed."
    ctx.tracer.end_trace(output={"response": final_reply[:500], "agent": _agent_name})
    set_tracer(None)
    logger.info(
        "[OUTPUT] handled_by=%s (id=%s) total_msgs=%d response=%s",
        _agent_name, agent_id, len(messages), final_reply[:300],
    )
    logger.info(
        "[MEMORY] dumping turn → conversation_logs (session=%s agent=%s): %s",
        ctx.thread_id, agent_id,
        {"human_message": ctx.message[:120], "agent_message": final_reply[:120]},
    )
    auth_errors = get_auth_errors()
    await _sub_agent_memory.record_turn(
        session_id=ctx.thread_id,
        user_id=ctx.user_id,
        org_id=ctx.org_id,
        agent_id=agent_id,
        human_message=ctx.message,
        agent_message=final_reply,
        auth_errors=auth_errors,
    )

    # --- Compress if threshold reached ---------------------------------
    summary = await _sub_agent_memory.maybe_compress(ctx.thread_id, ctx.user_id, agent_id)
    if summary:
        logger.info("[MEMORY] compression triggered for thread=%s agent=%s", ctx.thread_id, agent_id)

    sources = list(dict.fromkeys(result.get("kb_sources", [])))

    return ChatResponse(
        thread_id=ctx.thread_id,
        response=final_response or "Request processed.",
        messages_count=len(messages),
        name=session_name,
        auth_errors=auth_errors,
        sources=sources,
    )


async def send_message(
    thread_id: str,
    message: str,
    user_id: str,
    organization_id: str,
    attachments: Optional[List[ChatAttachment]] = None,
) -> ChatResponse:
    ctx = await _prepare_send_message(
        thread_id, message, user_id, organization_id, attachments=attachments
    )

    set_tracer(ctx.tracer)
    reset_auth_errors()
    ctx.tracer.start_trace("chat.turn", input={"query": ctx.message[:500]})
    try:
        result = await ctx.graph.ainvoke(
            {"messages": ctx.messages_for_graph, "next": ""},
        )
    except Exception:
        ctx.tracer.end_trace(output={"error": "chat turn failed"})
        set_tracer(None)
        raise

    return await _finalize_send_message(ctx, result)


async def send_message_stream_prepare(
    thread_id: str,
    message: str,
    user_id: str,
    organization_id: str,
    attachments: Optional[List[ChatAttachment]] = None,
) -> _SendMessageCtx:
    """Exposed so the route can await it (letting a 404 surface as a real
    HTTP status) before returning a StreamingResponse."""
    return await _prepare_send_message(
        thread_id, message, user_id, organization_id, attachments=attachments
    )


async def send_message_stream(ctx: _SendMessageCtx):
    """Async generator of SSE `data: ...\\n\\n` lines: live `routing`/`tool_call`
    events as the graph runs, ending in a `done` event carrying the same
    payload shape as ChatResponse, or an `error` event on failure."""
    queue: asyncio.Queue = asyncio.Queue()

    async def sink(event_type: str, payload: dict) -> None:
        await queue.put((event_type, payload))

    # Must set the tracer/event sink/auth-error collector BEFORE creating the
    # task below: contextvars are copied into a task at creation time, so
    # setting them after create_task() would leave the spawned task with none
    # of them.
    set_tracer(ctx.tracer)
    set_event_sink(sink)
    reset_auth_errors()
    ctx.tracer.start_trace("chat.turn", input={"query": ctx.message[:500]})

    graph_task = asyncio.create_task(
        ctx.graph.ainvoke({"messages": ctx.messages_for_graph, "next": ""})
    )

    try:
        pending_get: Optional[asyncio.Task] = None
        while not graph_task.done():
            if pending_get is None:
                pending_get = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait(
                {graph_task, pending_get}, return_when=asyncio.FIRST_COMPLETED
            )
            if pending_get in done:
                event_type, payload = pending_get.result()
                yield f"data: {json.dumps({'type': event_type, 'payload': payload})}\n\n"
                pending_get = None
        if pending_get is not None:
            pending_get.cancel()
        # Drain anything queued between the last check and graph_task completing.
        while not queue.empty():
            event_type, payload = queue.get_nowait()
            yield f"data: {json.dumps({'type': event_type, 'payload': payload})}\n\n"
    except asyncio.CancelledError:
        # Client disconnected — stop the graph turn instead of burning LLM
        # calls for a response nobody will see.
        graph_task.cancel()
        raise
    finally:
        set_event_sink(None)

    try:
        result = graph_task.result()
    except Exception:
        ctx.tracer.end_trace(output={"error": "chat turn failed"})
        set_tracer(None)
        yield f"data: {json.dumps({'type': 'error', 'payload': {'message': 'Something went wrong processing your message.'}})}\n\n"
        return

    response = await _finalize_send_message(ctx, result)
    yield f"data: {json.dumps({'type': 'done', 'payload': response.model_dump(mode='json')})}\n\n"


async def get_sessions_for_admin(
    organization_id: Optional[str] = None, agent_id: Optional[str] = None
) -> List[SessionListItem]:
    query: dict = {**NOT_DELETED}
    if organization_id:
        query["organization_id"] = organization_id
    if agent_id:
        query["$or"] = [
            {"agent_ids": agent_id, "mode": "single"},
            {"agent_ids": [agent_id]},
        ]
    else:
        query["$or"] = [
            {"mode": {"$ne": "single"}},
            {"agent_ids": {"$size": 0}},
            {"mode": "supervisor"},
        ]
    cursor = chat_sessions_collection.find(query, sort=[("created_at", -1)])
    docs = await cursor.to_list(length=500)
    return [
        SessionListItem(
            thread_id=d["thread_id"],
            organization_id=d["organization_id"],
            user_id=d["user_id"],
            name=d.get("name"),
            epoch=d.get("epoch", 1),
            agent_ids=d.get("agent_ids", []),
            created_at=d.get("created_at"),
        )
        for d in docs
    ]


async def get_session_history_for_admin(thread_id: str) -> SessionHistoryResponse:
    session = await chat_sessions_collection.find_one(
        {"thread_id": thread_id, **NOT_DELETED}
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    conv_docs = await _conversation_store.find_by_session(thread_id)

    agents: List[AgentHistoryPublic] = []
    for doc in conv_docs:
        entries = []
        for entry in doc.conversations:
            if entry.type == "summary":
                entries.append(SummaryPublic(type="summary", content=entry.content, timestamp=entry.timestamp))
            else:
                entries.append(TurnPublic(
                    type="turn",
                    human_message=entry.human_message,
                    agent_message=entry.agent_message,
                    timestamp=entry.timestamp,
                    tool_called=entry.tool_called,
                    tool_name=entry.tool_name,
                    auth_errors=entry.auth_errors,
                ))
        agents.append(AgentHistoryPublic(
            agent_id=doc.agent_id,
            total_messages=doc.total_messages,
            total_summaries=doc.total_summaries,
            conversations=entries,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ))

    return SessionHistoryResponse(
        thread_id=thread_id,
        organization_id=session["organization_id"],
        user_id=session["user_id"],
        name=session.get("name"),
        epoch=session.get("epoch", 1),
        agents=agents,
        created_at=session.get("created_at"),
    )


async def get_user_sessions(
    organization_id: str, user_id: str, agent_id: Optional[str] = None
) -> List[SessionListItem]:
    query: dict = {"organization_id": organization_id, "user_id": user_id, **NOT_DELETED}
    if agent_id:
        query["$or"] = [
            {"agent_ids": agent_id, "mode": "single"},
            {"agent_ids": [agent_id]},
        ]
    else:
        query["$or"] = [
            {"mode": {"$ne": "single"}},
            {"agent_ids": {"$size": 0}},
            {"mode": "supervisor"},
        ]
    cursor = chat_sessions_collection.find(
        query,
        sort=[("created_at", -1)],
    )
    docs = await cursor.to_list(length=500)
    return [
        SessionListItem(
            thread_id=d["thread_id"],
            organization_id=d["organization_id"],
            user_id=d["user_id"],
            name=d.get("name"),
            epoch=d.get("epoch", 1),
            agent_ids=d.get("agent_ids", []),
            created_at=d.get("created_at"),
        )
        for d in docs
    ]


async def rename_session(
    thread_id: str, organization_id: str, user_id: str, name: str
) -> SessionListItem:
    """Manually set a session's title. Validates ownership; trims/rejects empty."""
    new_name = name.strip()
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name must not be empty.",
        )

    result = await chat_sessions_collection.find_one_and_update(
        {
            "thread_id": thread_id,
            "organization_id": organization_id,
            "user_id": user_id,
            **NOT_DELETED,
        },
        {"$set": {"name": new_name}},
        return_document=True,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    return SessionListItem(
        thread_id=result["thread_id"],
        organization_id=result["organization_id"],
        user_id=result["user_id"],
        name=result.get("name"),
        epoch=result.get("epoch", 1),
        agent_ids=result.get("agent_ids", []),
        created_at=result.get("created_at"),
    )


async def delete_session(thread_id: str, organization_id: str, user_id: str) -> None:
    """Soft-delete a chat session and its conversation history."""
    result = await chat_sessions_collection.find_one_and_update(
        {
            "thread_id": thread_id,
            "organization_id": organization_id,
            "user_id": user_id,
            **NOT_DELETED,
        },
        {"$set": {"is_deleted": True}},
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    await _conversation_store.delete_by_session(thread_id, user_id)
    logger.info("[DELETE] session=%s org=%s user=%s", thread_id, organization_id, user_id)


async def get_session_history(
    thread_id: str, organization_id: str, user_id: str
) -> SessionHistoryResponse:
    session = await chat_sessions_collection.find_one(
        {"thread_id": thread_id, "organization_id": organization_id, **NOT_DELETED}
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    conv_docs = await _conversation_store.find_by_session(thread_id, user_id)

    agents: List[AgentHistoryPublic] = []
    for doc in conv_docs:
        entries = []
        for entry in doc.conversations:
            if entry.type == "summary":
                entries.append(SummaryPublic(type="summary", content=entry.content, timestamp=entry.timestamp))
            else:
                entries.append(TurnPublic(
                    type="turn",
                    human_message=entry.human_message,
                    agent_message=entry.agent_message,
                    timestamp=entry.timestamp,
                    tool_called=entry.tool_called,
                    tool_name=entry.tool_name,
                    auth_errors=entry.auth_errors,
                ))
        agents.append(AgentHistoryPublic(
            agent_id=doc.agent_id,
            total_messages=doc.total_messages,
            total_summaries=doc.total_summaries,
            conversations=entries,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ))

    return SessionHistoryResponse(
        thread_id=thread_id,
        organization_id=organization_id,
        user_id=user_id,
        name=session.get("name"),
        epoch=session.get("epoch", 1),
        agents=agents,
        created_at=session.get("created_at"),
    )


REPORTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "backend", "storage", "reports")
)


async def get_report_for_download(filename: str) -> str:
    """Validate and resolve the filepath for a report that will be downloaded
    and then deleted. The filename is sanitized against path traversal.
    Returns the absolute filepath."""
    safe_name = os.path.basename(filename)
    if safe_name != filename or safe_name.startswith("."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report filename.",
        )

    filepath = os.path.join(REPORTS_DIR, safe_name)
    if not os.path.isfile(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    return filepath


async def get_report_for_preview(filename: str) -> Tuple[str, str]:
    """Validate and resolve the filepath for a report/image that will be
    previewed inline (side-effect free, safe to call repeatedly). The
    filename is sanitized against path traversal. Returns (filepath, media_type)."""
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report filename.",
        )

    filepath = os.path.join(REPORTS_DIR, safe_name)
    if not os.path.isfile(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    media_type, _ = mimetypes.guess_type(safe_name)
    return filepath, media_type or "application/octet-stream"