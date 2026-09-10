"""Multi-orchestration entry point.

run_orchestration    — start a new run in the background, return its run_id
resume_orchestration — resume a WAITING_FOR_HUMAN run after the user answers

Both return immediately with status "running"; the run executes in a background
task and writes all state (status, current agent, final_response, human_question)
to the orchestration_runs document. The frontend polls
GET /orchestrations/{id}/runs/{run_id}/status to follow progress live.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from backend.core.config import settings
from backend.core.softdelete import NOT_DELETED
from backend.db.constants import ORCHESTRATION_RUNS_COLLECTION
from backend.db.database import (
    agent_orchestrations_collection,
    chat_sessions_collection,
    sync_db,
)
from backend.chat.schemas import ChatAttachment
from backend.chat.services import _compose_message_with_attachments, _generate_chat_name
from backend.orchestration.services import assert_orchestration_doc_visible
from ai.multi_orchestration.graph_loader import GraphLoader
from ai.multi_orchestration.memory_bus import MemoryBus
from ai.multi_orchestration.models import RunStatus, new_run_document,TERMINAL_STATUSES
from ai.multi_orchestration.run_context import RunContext
from ai.multi_orchestration.scheduler import RuntimeScheduler
from ai.multi_orchestration.supervisor import SUPERVISOR_AGENT_ID, SUPERVISOR_AGENT_NAME

logger = logging.getLogger("multi_orchestration.executor")

_BG_TASKS: set = set()


def _sticky_candidate(snapshot: dict, prior_run: dict) -> Optional[List[str]]:
    """Soft continuity hint for supervisor-mode follow-ups, or None.

    Returns the last turn's agent so the Supervisor can prefer them when the
    new request is still in-domain. The scheduler does *not* hard-invoke this
    agent — hard sticky skipped routing and let Time Trace answer HR questions
    via shared query_db instead of handing back.
    """
    config = snapshot.get("supervisor_config") or {}
    if not config.get("sticky_routing", True):
        return None
    attached = set(snapshot.get("sub_agent_ids") or [])
    for entry in reversed(prior_run.get("execution_path", [])):
        if entry.get("status") != "complete":
            continue
        agent_id = entry.get("agent_id")
        if not agent_id or agent_id == SUPERVISOR_AGENT_ID:
            continue
        if agent_id not in attached:
            continue  # detached or deleted since the last turn
        logger.info("[executor] sticky preference for next turn — agent=%s", agent_id)
        return [agent_id]
    return None


def _resolve_join_node(
    snapshot: dict,
    last_agent_id: str,
    prior_branches: list,
    execution_path: list,
    organization_id: str,
    user_id: str,
    sync_db,
) -> Optional[str]:
    """If the prior run ended with branches converging at a join point, return
    the join node ID. Otherwise return None.
    
    We detect this by checking:
    1. There are multiple complete branches in the prior run (fan-out happened)
    2. A join point exists whose predecessors all executed but the join node 
       itself hasn't executed yet (not in the execution_path)
    """
    if not prior_branches or len(prior_branches) < 2:
        return None
    
    # Build set of agent IDs that actually executed in the prior run
    executed_agents = {entry["agent_id"] for entry in execution_path}
    
    # Load the graph to check join points
    try:
        from ai.multi_orchestration.graph_loader import GraphLoader
        loader = GraphLoader(snapshot, sync_db, organization_id, user_id)
        graph = loader.load()
        
        # For each join point, check if all its predecessor agents executed
        # but the join node itself hasn't executed yet.
        for join_node_id in graph.join_points:
            incoming = graph.reverse_adjacency.get(join_node_id, [])
            if len(incoming) < 2:
                continue
            # Check if all predecessors executed but join node didn't
            if join_node_id not in executed_agents and all(pred in executed_agents for pred in incoming):
                logger.info(
                    "[executor] detected pending join — join_node=%s incoming_agents=%s",
                    join_node_id, incoming,
                )
                return join_node_id
    except Exception as exc:
        logger.warning("[executor] _resolve_join_node failed: %s", exc)
    
    return None


# ----------------------------------------------------------------------------
# Background execution
# ----------------------------------------------------------------------------

async def resume_branch(
    orchestration_id: str,
    run_id: str,
    branch_id: str,
    answer: str,
    user_id: str,
    organization_id: str,
) -> dict:
    """Resume ONE branch of a fan-out run after the user answers that
    branch's HITL question. Sibling branches are untouched — they keep
    running, or stay WAITING_FOR_HUMAN on their own question, independently.
    """
    run_doc = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one({
        "run_id": run_id,
        "orchestration_id": orchestration_id,
        "organization_id": organization_id,
    })
    if not run_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    branches = run_doc.get("branches", [])
    branch = next((b for b in branches if b.get("branch_id") == branch_id), None)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found.")
    branch_status = branch.get("status")
    if branch_status not in (RunStatus.WAITING_FOR_HUMAN.value, RunStatus.WAITING_FOR_REAUTH.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Branch is not waiting for human input or reauth (status={branch_status}).",
        )
    is_reauth_resume = branch_status == RunStatus.WAITING_FOR_REAUTH.value

    # Fetch orchestration doc + build snapshot via shared helper.
    snapshot = await _fetch_orch_snapshot(orchestration_id, organization_id, user_id)
    session_id = run_doc["session_id"]
    entry_message = run_doc["entry_message"]
    pending_agents = branch.get("pending_agents", [])
    human_question = branch.get("human_question", "")
    human_asked_by_agent = branch.get("human_asked_by_agent", "")
    model = settings.DEFAULT_MODEL
    timeout = float(snapshot.get("timeout_sec", 600))

    mem_flush = {}
    if is_reauth_resume:
        mem_flush = {"memory_log": run_doc["memory_log"]}
        logger.info(
            "[executor] resuming branch=%s after connector reauth — run_id=%s",
            branch_id, run_id,
        )
    else:
        memory_bus = MemoryBus(run_doc, sync_db, model)
        memory_bus.inject_human_answer(
            question=human_question,
            answer=answer,
            agent_id=human_asked_by_agent,
        )
        memory_bus.write_hitl_answer(answer, branch_id=branch_id)
        mem_flush = memory_bus.flush_to_run_doc()

    sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
        {"run_id": run_id},
        {
            "$set": {
                "branches.$[b].status": RunStatus.RUNNING.value,
                "branches.$[b].human_question": None,
                "branches.$[b].human_asked_by_agent": None,
                "branches.$[b].pending_reauth": None,
                "branches.$[b].completed_at": None,
                **mem_flush,
            }
        },
        array_filters=[{"b.branch_id": branch_id}],
    )

    other_still_waiting = any(
        b.get("branch_id") != branch_id
        and b.get("status") in (RunStatus.WAITING_FOR_HUMAN.value, RunStatus.WAITING_FOR_REAUTH.value)
        for b in branches
    )
    if not other_still_waiting:
        sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": {
                "status": RunStatus.RUNNING.value,
                "human_question": None,
                "human_asked_by_agent": None,
                "pending_reauth": None,
            }},
        )

    logger.info(
        "[executor] resuming branch=%s run_id=%s pending_agents=%s answer=%.80s",
        branch_id, run_id, pending_agents, answer,
    )

    await _launch_background_branch(
        run_id, branch_id, timeout, snapshot, session_id, entry_message,
        organization_id, user_id, model, pending_agents,
    )

    return {
        "response": "",
        "orchestration_id": orchestration_id,
        "session_id": session_id,
        "name": None,
        "status": RunStatus.RUNNING.value,
        "run_id": run_id,
        "branch_id": branch_id,
        "human_question": None,
    }

def _run_scheduler_sync(
    run_id: str,
    snapshot: dict,
    thread_id: str,
    message: str,
    organization_id: str,
    user_id: str,
    model: str,
    initial_queue: Optional[List[str]],
    resumed: bool = False,
) -> None:
    """Load the graph and drive the scheduler. Runs in a worker thread."""
    result = _build_run_context(run_id, snapshot, thread_id, organization_id, user_id, model)
    if result is None:
        return
    ctx, _ = result
    scheduler = RuntimeScheduler(ctx, model)
    scheduler.run(message, initial_queue=initial_queue, resumed=resumed)


async def _launch_background(
    run_id: str,
    timeout: float,
    snapshot: dict,
    thread_id: str,
    message: str,
    organization_id: str,
    user_id: str,
    model: str,
    initial_queue: Optional[List[str]],
    resumed: bool = False,
) -> None:
    """Schedule the scheduler run as a detached background task with a timeout."""

    async def _bg() -> None:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    _run_scheduler_sync,
                    run_id, snapshot, thread_id, message,
                    organization_id, user_id, model, initial_queue, resumed,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error("[executor] timeout after %ss — run_id=%s", timeout, run_id)
            sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
                {"run_id": run_id, "status": {"$nin": list(TERMINAL_STATUSES)}},
                {"$set": {
                    "status": RunStatus.TIMEOUT.value,
                    "completed_at": datetime.now(timezone.utc),
                }},
            )
        except Exception as exc:  # noqa: BLE001 - background task must not crash the loop
            logger.error("[executor] background run failed — run_id=%s: %s", run_id, exc, exc_info=True)
            sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
                {"run_id": run_id, "status": {"$nin": list(TERMINAL_STATUSES)}},
                {"$set": {
                    "status": RunStatus.FAILED.value,
                    "completed_at": datetime.now(timezone.utc),
                    "error_context": {
                        "agent_id": None,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                        "retry_count": 0,
                        "timestamp": datetime.now(timezone.utc),
                    },
                }},
            )

    task = asyncio.create_task(_bg())
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)

def _run_scheduler_sync_branch(
    run_id: str,
    branch_id: str,
    snapshot: dict,
    thread_id: str,
    message: str,
    organization_id: str,
    user_id: str,
    model: str,
    pending_agents: List[str],
) -> None:
    """Load the graph and resume ONE paused branch. Runs in a worker thread.

    Mirrors ``_run_scheduler_sync`` but calls ``scheduler.resume_branch()``
    instead of ``scheduler.run()`` — sibling branches are never touched or
    re-run.  Graph setup and RunContext construction are delegated to the
    ``_build_run_context`` helper; the returned ``run_doc`` is discarded here
    since the memory log was already injected by ``resume_branch()`` before
    this thread was launched.
    """
    result = _build_run_context(run_id, snapshot, thread_id, organization_id, user_id, model)
    if result is None:
        return
    ctx, _ = result
    scheduler = RuntimeScheduler(ctx, model)
    scheduler.resume_branch(branch_id, pending_agents, message)


async def _launch_background_branch(
    run_id: str,
    branch_id: str,
    timeout: float,
    snapshot: dict,
    thread_id: str,
    message: str,
    organization_id: str,
    user_id: str,
    model: str,
    pending_agents: List[str],
) -> None:
    """Schedule a single branch's resume as a detached background task with
    a timeout. Mirrors _launch_background, scoped to one branch."""

    async def _bg() -> None:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    _run_scheduler_sync_branch,
                    run_id, branch_id, snapshot, thread_id, message,
                    organization_id, user_id, model, pending_agents,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error("[executor] branch timeout after %ss — run_id=%s branch=%s", timeout, run_id, branch_id)
            sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
                {"run_id": run_id, "branches.branch_id": branch_id},
                {"$set": {
                    "branches.$.status": RunStatus.TIMEOUT.value,
                    "branches.$.completed_at": datetime.now(timezone.utc),
                }},
            )
        except Exception as exc:  # noqa: BLE001 - background task must not crash the loop
            logger.error("[executor] branch background run failed — run_id=%s branch=%s: %s", run_id, branch_id, exc, exc_info=True)
            sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
                {"run_id": run_id, "branches.branch_id": branch_id},
                {"$set": {
                    "branches.$.status": RunStatus.FAILED.value,
                    "branches.$.completed_at": datetime.now(timezone.utc),
                }},
            )

    task = asyncio.create_task(_bg())
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)

# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

async def run_orchestration(
    orchestration_id: str,
    message: str,
    user_id: str,
    organization_id: str,
    session_id: Optional[str] = None,
    attachments: Optional[List[ChatAttachment]] = None,
    unattended: bool = False,
) -> dict:
    # Fold attachment text/OCR into the user message so agents see file
    # content without any graph/multimodal changes — identical to how
    # backend.chat.services does it for the plain single-agent chat path.
    message = _compose_message_with_attachments(message, attachments)

    # Fetch orchestration doc + build snapshot via shared helper.
    snapshot = await _fetch_orch_snapshot(orchestration_id, organization_id, user_id)

    # Empty message indicates an initialization / pre-warm call via /chat route!
    if not message or not message.strip():
        init_result = await init_orchestration_session(orchestration_id, user_id, organization_id)
        return {
            "response": "graph loaded",
            "orchestration_id": orchestration_id,
            "session_id": init_result["session_id"],
            "name": "New Orchestration Session",
            "status": "ready",
            "run_id": None,
            "human_question": None,
        }

    if session_id:
        session = await chat_sessions_collection.find_one(
            {"thread_id": session_id, "organization_id": organization_id, **NOT_DELETED}
        )
        if not session or session.get("user_id") != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        thread_id = session_id

        # If this session has a run still waiting on human input or a connector
        # reauth, the incoming message resumes that run instead of starting a
        # second, parallel one (only for interactive runs; unattended scheduled runs
        # never resume past HITL runs).
        if not unattended:
            pending_run = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one(
                {
                    "session_id": thread_id,
                    "status": {"$in": [RunStatus.WAITING_FOR_HUMAN.value, RunStatus.WAITING_FOR_REAUTH.value]},
                },
                sort=[("started_at", -1)],
            )
            if pending_run:
                logger.info(
                    "[executor] session %s has a pending run %s (status=%s) — resuming instead of restarting",
                    thread_id, pending_run["run_id"], pending_run.get("status"),
                )
                return await resume_orchestration(
                    orchestration_id=orchestration_id,
                    run_id=pending_run["run_id"],
                    answer=message,
                    user_id=user_id,
                    organization_id=organization_id,
                )

        # On the first real message: replace the placeholder session name with an
        # LLM-generated title.
        session_name = session.get("name", "New Orchestration Session")
        if session_name == "New Orchestration Session":
            session_name = await _generate_chat_name(message)
            await chat_sessions_collection.update_one(
                {"thread_id": thread_id},
                {"$set": {"name": session_name}},
            )

    else:
        # No pre-init was performed — delegate session creation to
        # init_orchestration_session (single source of truth for session docs),
        # then immediately replace the placeholder name.
        init_result = await init_orchestration_session(orchestration_id, user_id, organization_id)
        thread_id = init_result["session_id"]
        session_name = await _generate_chat_name(message)
        await chat_sessions_collection.update_one(
            {"thread_id": thread_id},
            {"$set": {"name": session_name}},
        )

    model = settings.DEFAULT_MODEL
    timeout = float(snapshot.get("timeout_sec", 600))

    run_doc = new_run_document(
        orchestration_id=orchestration_id,
        session_id=thread_id,
        user_id=user_id,
        organization_id=organization_id,
        entry_message=message,
        main_agent_id=snapshot["main_agent_id"],
        max_depth=snapshot.get("max_depth", 5),
        timeout_sec=snapshot.get("timeout_sec", 600),
    )
    run_doc["unattended"] = unattended
    run_id = run_doc["run_id"]

    # Session-scoped memory: seed this run's log from the most recent prior run
    # of the same session so context carries across separate messages.
    initial_queue = None
    prior = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one(
        {"session_id": thread_id, "status": RunStatus.COMPLETE.value},
        sort=[("started_at", -1)],
    )
    if prior and prior.get("execution_path"):
        if snapshot.get("mode") == "supervisor":
            initial_queue = _sticky_candidate(snapshot, prior)
        else:
            last_agent_id = prior["execution_path"][-1]["agent_id"]
            # If the prior run ended with branches converging at a join point,
            # the join node hasn't executed yet. Start from the join node so we
            # don't re-run the last branch terminal agent.
            prior_branches = prior.get("branches", [])
            prior_execution_path = prior.get("execution_path", [])
            join_node_id = _resolve_join_node(snapshot, last_agent_id, prior_branches, prior_execution_path, organization_id, user_id, sync_db)
            if join_node_id:
                initial_queue = [join_node_id]
            else:
                initial_queue = [last_agent_id]
    if prior and prior.get("memory_log"):
        run_doc["memory_log"] = list(prior["memory_log"])
        logger.info(
            "[executor] seeded %d prior memory entries from session %s",
            len(run_doc["memory_log"]), thread_id,
        )

    sync_db[ORCHESTRATION_RUNS_COLLECTION].insert_one(run_doc)
    logger.info("[executor] run created — run_id=%s orch=%s", run_id, orchestration_id)

    await _launch_background(
        run_id, timeout, snapshot, thread_id, message,
        organization_id, user_id, model, initial_queue if 'initial_queue' in locals() else None,
    )

    return {
        "response": "",
        "orchestration_id": orchestration_id,
        "session_id": thread_id,
        "name": session_name,
        "status": RunStatus.RUNNING.value,
        "run_id": run_id,
        "human_question": None,
    }


async def resume_orchestration(
    orchestration_id: str,
    run_id: str,
    answer: str,
    user_id: str,
    organization_id: str,
) -> dict:
    """Resume a WAITING_FOR_HUMAN or WAITING_FOR_REAUTH run.

    For WAITING_FOR_HUMAN, `answer` is the human's reply to the agent's
    question. For WAITING_FOR_REAUTH there is no question — the caller is
    just signaling "the connector is reconnected now, retry" — so `answer`
    is ignored and no answer is injected into the memory log.
    """
    run_doc = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one({
        "run_id": run_id,
        "orchestration_id": orchestration_id,
        "organization_id": organization_id,
    })
    if not run_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    run_status = run_doc.get("status")
    if run_status not in (RunStatus.WAITING_FOR_HUMAN.value, RunStatus.WAITING_FOR_REAUTH.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run is not waiting for human input or reauth (status={run_status}).",
        )
    is_reauth_resume = run_status == RunStatus.WAITING_FOR_REAUTH.value

    # Fetch orchestration doc + build snapshot via shared helper.
    snapshot = await _fetch_orch_snapshot(orchestration_id, organization_id, user_id)
    session_id = run_doc["session_id"]
    entry_message = run_doc["entry_message"]
    pending_agents = run_doc.get("pending_agents", [])
    human_question = run_doc.get("human_question", "")
    model = settings.DEFAULT_MODEL
    timeout = float(snapshot.get("timeout_sec", 600))

    # Inject the human answer and flip back to RUNNING before dispatching, so a
    # poll immediately after this call sees the resumed state. Reauth resumes
    # skip this — there is no question/answer, just a retry.
    mem_flush = {"memory_log": run_doc["memory_log"]}
    if not is_reauth_resume:
        memory_bus = MemoryBus(run_doc, sync_db, model)
        memory_bus.inject_human_answer(
            question=human_question,
            answer=answer,
            agent_id=run_doc.get("human_asked_by_agent", ""),
        )
        memory_bus.write_hitl_answer(answer)  #adding to the new conversation collection
        mem_flush = memory_bus.flush_to_run_doc()
    sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
        {"run_id": run_id},
        {"$set": {
            "status": RunStatus.RUNNING.value,
            "human_question": None,
            "human_asked_by_agent": None,
            "pending_reauth": None,
            "pending_agents": [],
            "completed_at": None,
            **mem_flush,
        }},
    )
    logger.info(
        "[executor] resuming run_id=%s pending_agents=%s answer=%.80s",
        run_id, pending_agents, answer,
    )

    # resumed=True: the human's answer is already in the memory log, and it must
    # go straight back to the agent that asked — never through the Supervisor.
    await _launch_background(
        run_id, timeout, snapshot, session_id, entry_message,
        organization_id, user_id, model, pending_agents, resumed=True,
    )

    return {
        "response": "",
        "orchestration_id": orchestration_id,
        "session_id": session_id,
        "name": None,
        "status": RunStatus.RUNNING.value,
        "run_id": run_id,
        "human_question": None,
    }


# ----------------------------------------------------------------------------
# Public API — session pre-initialisation
# ----------------------------------------------------------------------------

async def init_orchestration_session(
    orchestration_id: str,
    user_id: str,
    organization_id: str,
) -> dict:
    """Pre-load graph and initialize session state before the user sends their first message.

    Reduces latency on initial message send by validating the graph topology
    up-front and returning a ready status with session ID and main agent name,
    so the frontend can display agent information while the user types.

    Empty-message /chat pre-warm is often fired more than once (React Strict Mode,
    dual mount). Reuse an unused placeholder session for this user+orch so the
    history list does not fill with identical "New Orchestration Session" rows.
    """
    # Fetch orchestration doc + build snapshot (validates ObjectId, raises 404).
    snapshot = await _fetch_orch_snapshot(orchestration_id, organization_id, user_id)

    try:
        loader = GraphLoader(snapshot, sync_db, organization_id, user_id)
        graph = loader.load()
        main_agent_name = (
            graph.nodes[graph.main_agent_id].name
            if graph.main_agent_id and graph.main_agent_id in graph.nodes
            else (SUPERVISOR_AGENT_NAME if snapshot.get("mode") == "supervisor" else None)
        )
    except Exception as exc:
        logger.warning("[executor] pre-load graph warning: %s", exc)
        main_agent_name = SUPERVISOR_AGENT_NAME if snapshot.get("mode") == "supervisor" else None

    # Prefer an existing unused placeholder over creating another one.
    existing = await chat_sessions_collection.find_one(
        {
            "orchestration_id": orchestration_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "name": "New Orchestration Session",
            **NOT_DELETED,
        },
        sort=[("created_at", -1)],
    )
    if existing:
        thread_id = existing["thread_id"]
        # Only reuse if no run has used this session yet (still a blank slate).
        prior_run = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one(
            {"session_id": thread_id},
            {"_id": 1},
        )
        if prior_run is None:
            logger.info(
                "[executor] reusing unused session pre-load — session_id=%s orch=%s",
                thread_id, orchestration_id,
            )
            return {
                "session_id": thread_id,
                "orchestration_id": orchestration_id,
                "status": "ready",
                "main_agent_id": snapshot.get("main_agent_id"),
                "main_agent_name": main_agent_name,
            }

    thread_id = str(uuid.uuid4())
    await chat_sessions_collection.insert_one({
        "thread_id": thread_id,
        "organization_id": organization_id,
        "user_id": user_id,
        "orchestration_id": orchestration_id,
        "mode": "orchestration",
        "name": "New Orchestration Session",
        "created_at": datetime.now(timezone.utc),
        "is_deleted": False,
    })

    logger.info("[executor] initialized session pre-load — session_id=%s orch=%s", thread_id, orchestration_id)

    return {
        "session_id": thread_id,
        "orchestration_id": orchestration_id,
        "status": "ready",
        "main_agent_id": snapshot.get("main_agent_id"),
        "main_agent_name": main_agent_name,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Private helper functions — shared across public executor API functions
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_orch_snapshot(orchestration_id: str, organization_id: str, user_id: str) -> dict:
    """Helper — fetch an orchestration document and return it as a snapshot dict.

    Validates the ObjectId format, queries MongoDB, and converts ``_id`` to a
    plain string so the snapshot is safe to pass across thread boundaries or
    serialise without further processing.

    Raises :class:`fastapi.HTTPException` 404 if the orchestration does not
    exist or has been soft-deleted.
    """
    if not ObjectId.is_valid(orchestration_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    orch_doc = await agent_orchestrations_collection.find_one(
        {"_id": ObjectId(orchestration_id), "organization_id": organization_id, **NOT_DELETED}
    )
    if not orch_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    
    await assert_orchestration_doc_visible(user_id, orch_doc)
    
    snapshot = dict(orch_doc)
    snapshot["_id"] = str(snapshot["_id"])
    return snapshot


def _build_run_context(
    run_id: str,
    snapshot: dict,
    thread_id: str,
    organization_id: str,
    user_id: str,
    model: str,
) -> Optional[tuple]:
    """Helper — load the graph and build a :class:`RunContext` for a scheduler run."""
    run_doc = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one({"run_id": run_id})
    if not run_doc:
        logger.error("[executor] run doc %s vanished before execution", run_id)
        return None

    try:
        loader = GraphLoader(snapshot, sync_db, organization_id, user_id)
        graph = loader.load()
    except Exception as exc:
        logger.error("[executor] graph load failed — run_id=%s: %s", run_id, exc)
        sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": {
                "status": RunStatus.FAILED.value,
                "completed_at": datetime.now(timezone.utc),
                "error_context": {
                    "agent_id": snapshot.get("main_agent_id"),
                    "error_type": "GraphLoadError",
                    "message": str(exc),
                    "retry_count": 0,
                    "timestamp": datetime.now(timezone.utc),
                },
            }},
        )
        return None

    memory_bus = MemoryBus(run_doc, sync_db, model)
    ctx = RunContext(
        run_id=run_id,
        orchestration_id=str(snapshot["_id"]),
        session_id=thread_id,
        org_id=organization_id,
        user_id=user_id,
        unattended=run_doc.get("unattended", False),
        runtime_graph=graph,
        memory_bus=memory_bus,
        sync_db=sync_db,
        model=model,
    )
    return ctx, run_doc

