import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("direct_agent.services")

from bson import ObjectId
from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage

from ai.tracing.tracer import AgentTracer
from backend.chat.auth_error_sink import get_auth_errors, reset_auth_errors
from backend.chat.event_sink import set_event_sink
from backend.chat.graph import AgentRuntime, get_or_build_single_agent_graph
from backend.chat.tracing_ctx import set_tracer
from backend.chat.services import (
    _has_db_query_tool,
    _set_chat_name_if_unset,
    load_agent_connectors,
    load_agent_mcp,
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
from backend.direct_agent.schemas import DirectChatResponse
from backend.memory.conversation_store import ConversationStore
from backend.memory.sub_agent_memory import SubAgentMemory
from langgraph.types import Command

_conversation_store = ConversationStore(db=db)
_sub_agent_memory = SubAgentMemory(store=_conversation_store, model=settings.DEFAULT_MODEL)


async def _load_single_agent(org_id: str, agent_id: str, user_id: str = "") -> AgentRuntime:
    """Load one agent for direct/single-agent chat (including widget
    "single_agent" mode, where `user_id` is a synthetic visitor id).
    Restricted to agents `user_id` may see -- see
    agent.services.build_agent_visibility_clauses -- so a personal or
    selected_users agent can't be chatted with directly just by knowing its
    id, even from within the same org."""
    from backend.agent.services import build_agent_visibility_clauses

    if not ObjectId.is_valid(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    agent_doc = await agents_collection.find_one({
        "_id": ObjectId(agent_id),
        "organization_id": org_id,
        **NOT_DELETED,
        "$or": await build_agent_visibility_clauses(user_id),
    })
    if not agent_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    agent_name = agent_doc.get("name", agent_id)
    tool_ids = agent_doc.get("tool_ids", [])
    logger.info("[TOOLS] agent=%s (id=%s) tool_ids=%s", agent_name, agent_id, tool_ids or "[]")
    tools: list = []
    for tid in tool_ids:
        if ObjectId.is_valid(tid):
            tool_doc = await tools_collection.find_one({"_id": ObjectId(tid), **NOT_DELETED})
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
    if not db_conn_ids and await _has_db_query_tool(tools):
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
    runtime = AgentRuntime(agent_doc, tools, db_conn_ids=db_conn_ids, rag_ids=visible_rag_ids)
    runtime.mcp_tools = mcp_tools
    runtime.mcp_callables = mcp_callables
    runtime.connector_tools = connector_tools
    runtime.connector_callables = connector_callables
    runtime.connector_tool_owner = connector_tool_owner
    runtime.connector_load_errors = connector_load_errors
    return runtime


@dataclass
class _DirectChatCtx:
    agent: AgentRuntime
    agent_id: str
    thread_id: str
    message: str
    org_id: str
    user_id: str
    existing_name: Optional[str]
    title_task: Optional[asyncio.Task]
    graph: Any
    config: dict
    tracer: AgentTracer
    is_interrupted: bool
    graph_input: Any


async def _prepare_direct_chat(
    agent_id: str,
    message: str,
    org_id: str,
    user_id: str,
    session_id: Optional[str] = None,
    unattended: bool = False,
) -> _DirectChatCtx:
    """Everything that can fail with a real HTTP status (agent/session not
    found), plus history/graph loading and the interrupted-vs-fresh decision.
    Shared by the blocking and streaming entry points; must run BEFORE a
    StreamingResponse is returned, since a streaming response's status code
    is committed as soon as it starts."""
    agent = await _load_single_agent(org_id, agent_id, user_id=user_id)

    existing_name: Optional[str] = None
    if session_id:
        session = await chat_sessions_collection.find_one(
            {"thread_id": session_id, **NOT_DELETED}
        )
        if not session or session.get("user_id") != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        if agent_id not in session.get("agent_ids", []):
            await chat_sessions_collection.update_one(
                {"thread_id": session_id},
                {"$addToSet": {"agent_ids": agent_id}},
            )
        thread_id = session_id
        existing_name = session.get("name")
    else:
        thread_id = str(uuid.uuid4())
        await chat_sessions_collection.insert_one(
            {
                "thread_id": thread_id,
                "organization_id": org_id,
                "user_id": user_id,
                "agent_ids": [agent_id],
                "mode": "single",
                "created_at": datetime.now(timezone.utc),
                "is_deleted": False,
            }
        )

    # --- Kick off title generation in parallel -------------------------
    # On the first message of an untitled session, start generating the title
    # NOW so the cheap nano call runs concurrently with seeding + the graph
    # turn below. Mirrors the multi-agent path in chat.services.send_message.
    title_task: Optional[asyncio.Task] = None
    if not existing_name:
        title_task = asyncio.create_task(_set_chat_name_if_unset(thread_id, message))

    seed = await _sub_agent_memory.get_seed_messages(thread_id, user_id, agent_id)
    logger.info("[HISTORY] thread=%s agent=%s loaded %d messages from MongoDB", thread_id, agent_id, len(seed))
    messages_for_graph = seed + [HumanMessage(content=message)]
    graph = get_or_build_single_agent_graph(org_id, agent, settings.DEFAULT_MODEL)
    config = {"configurable": {"thread_id": thread_id}}
    tracer = AgentTracer(org_id=org_id, user_id=user_id, session_id=thread_id)

    snapshot = await graph.aget_state(config)
    is_interrupted = bool(snapshot.next) and any(
        t.interrupts for t in snapshot.tasks
    )

    if is_interrupted:
        graph_input: Any = Command(resume=message)
    else:
        has_existing_checkpoint = bool(snapshot.values.get("messages"))
        if has_existing_checkpoint:
            graph_input = {
                "messages": [HumanMessage(content=message)],
                "unattended": unattended,
            }
        else:
            graph_input = {
                "messages": messages_for_graph,
                "next": "",
                "unattended": unattended,
            }

    return _DirectChatCtx(
        agent=agent,
        agent_id=agent_id,
        thread_id=thread_id,
        message=message,
        org_id=org_id,
        user_id=user_id,
        existing_name=existing_name,
        title_task=title_task,
        graph=graph,
        config=config,
        tracer=tracer,
        is_interrupted=is_interrupted,
        graph_input=graph_input,
    )


async def _finalize_direct_chat(ctx: _DirectChatCtx, result: dict) -> DirectChatResponse:
    reply = ""
    for m in reversed(result.get("messages", [])):
        if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
            reply = str(m.content)
            break

    final_reply = reply or "Request processed."

    ctx.tracer.end_trace(output={"response": final_reply[:500], "agent": ctx.agent.name})
    set_tracer(None)

    # --- Collect the title generated in parallel above -----------------
    # The task ran alongside the graph turn; it's effectively done by now.
    session_name: Optional[str] = ctx.existing_name
    if ctx.title_task is not None:
        try:
            generated = await ctx.title_task
            session_name = generated or session_name
        except Exception:
            logger.warning("Title task failed", exc_info=True)

    auth_errors = get_auth_errors()
    await _sub_agent_memory.record_turn(
        session_id=ctx.thread_id,
        user_id=ctx.user_id,
        org_id=ctx.org_id,
        agent_id=ctx.agent_id,
        human_message=ctx.message,
        agent_message=final_reply,
        auth_errors=auth_errors,
    )
    await _sub_agent_memory.maybe_compress(ctx.thread_id, ctx.user_id, ctx.agent_id)

    sources = list(dict.fromkeys(result.get("kb_sources", [])))

    return DirectChatResponse(
        reply=final_reply, session_id=ctx.thread_id, name=session_name, auth_errors=auth_errors,
        sources=sources,
    )


async def direct_chat(
    agent_id: str,
    message: str,
    org_id: str,
    user_id: str,
    session_id: Optional[str] = None,
    unattended: bool = False,
) -> DirectChatResponse:
    ctx = await _prepare_direct_chat(agent_id, message, org_id, user_id, session_id, unattended)

    set_tracer(ctx.tracer)
    reset_auth_errors()
    ctx.tracer.start_trace("direct_chat.turn", input={"query": message[:500]})
    ctx.tracer.tag_agent(ctx.agent.agent_id, ctx.agent.name)
    try:
        result = await ctx.graph.ainvoke(ctx.graph_input, config=ctx.config)
    except Exception:
        ctx.tracer.end_trace(output={"error": "direct chat turn failed"})
        set_tracer(None)
        raise

    return await _finalize_direct_chat(ctx, result)


async def prepare_direct_chat_stream(
    agent_id: str,
    message: str,
    org_id: str,
    user_id: str,
    session_id: Optional[str] = None,
) -> _DirectChatCtx:
    """Exposed so the route can await it (letting a 404 surface as a real
    HTTP status) before returning a StreamingResponse."""
    return await _prepare_direct_chat(agent_id, message, org_id, user_id, session_id)


async def direct_chat_stream(ctx: _DirectChatCtx):
    """Async generator of SSE `data: ...\\n\\n` lines: live `tool_call` events
    as the agent runs, ending in a `done` event carrying the same payload
    shape as DirectChatResponse, or an `error` event on failure."""
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
    ctx.tracer.start_trace("direct_chat.turn", input={"query": ctx.message[:500]})
    ctx.tracer.tag_agent(ctx.agent.agent_id, ctx.agent.name)

    graph_task = asyncio.create_task(
        ctx.graph.ainvoke(ctx.graph_input, config=ctx.config)
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
        while not queue.empty():
            event_type, payload = queue.get_nowait()
            yield f"data: {json.dumps({'type': event_type, 'payload': payload})}\n\n"
    except asyncio.CancelledError:
        graph_task.cancel()
        raise
    finally:
        set_event_sink(None)

    try:
        result = graph_task.result()
    except Exception:
        ctx.tracer.end_trace(output={"error": "direct chat turn failed"})
        set_tracer(None)
        yield f"data: {json.dumps({'type': 'error', 'payload': {'message': 'Something went wrong processing your message.'}})}\n\n"
        return

    response = await _finalize_direct_chat(ctx, result)
    yield f"data: {json.dumps({'type': 'done', 'payload': response.model_dump(mode='json')})}\n\n"
