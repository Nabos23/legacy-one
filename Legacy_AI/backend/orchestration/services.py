import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from ai.multi_orchestration.models import RunStatus
from backend.core.softdelete import NOT_DELETED
from backend.db.constants import ORCHESTRATION_CONVERSATIONS_COLLECTION, ORCHESTRATION_RUNS_COLLECTION
from backend.db.database import (
    agent_orchestrations_collection,
    agents_collection,
    chat_sessions_collection,
    sync_db,
    teams_collection,
    users_collection,
)
from backend.orchestration.schemas import (
    AgentBriefPublic,
    AgentConnectionOut,
    AgentStepPublic,
    OrchestrationConversationEntry,
    OrchestrationCreate,
    OrchestrationPublic,
    OrchestrationRunStatus,
    OrchestrationSessionHistoryResponse,
    OrchestrationUpdate,
    OrchestrationSessionListResponse,
    OrchestrationSessionBrief,
    BranchStatusPublic,
    SupervisorConfig,
)
from backend.orchestration.validators import find_orphan_agents, has_cycle
from backend.team import services as team_services

logger = logging.getLogger("orchestration.services")


def _doc_to_public(doc: dict, agent_map: dict | None = None) -> OrchestrationPublic:
    agent_map = agent_map or {}
    agents_brief = [
        AgentBriefPublic(
            agent_id=aid,
            name=agent_map.get(aid, {}).get("name", aid),
            description=agent_map.get(aid, {}).get("description"),
        )
        for aid in doc.get("sub_agent_ids", [])
    ]
    supervisor_config = doc.get("supervisor_config")
    return OrchestrationPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc["name"],
        description=doc.get("description"),
        # Absent on every document written before supervisor mode existed.
        mode=doc.get("mode") or "sequential",
        main_agent_id=doc.get("main_agent_id"),
        supervisor_config=SupervisorConfig(**supervisor_config) if supervisor_config else None,
        sub_agent_ids=doc.get("sub_agent_ids", []),
        connections=[
            AgentConnectionOut(
                from_agent_id=c["from_agent_id"],
                to_agent_id=c["to_agent_id"],
                label=c.get("label", ""),
            )
            for c in doc.get("connections", [])
        ],
        max_depth=doc.get("max_depth", 5),
        timeout_sec=doc.get("timeout_sec", 600),
        agents=agents_brief,
        created_by=doc.get("created_by", ""),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
        owner_scope=doc.get("owner_scope", "organization"),
        allowed_user_ids=doc.get("allowed_user_ids", []),
        team_id=doc.get("team_id"),
    )


async def _validate_allowed_user_ids(org_id: str, user_ids: List[str]) -> List[str]:
    """Validate that every id in `user_ids` is a real user belonging to `org_id`,
    dedupe, and return the cleaned list. Mirrors backend.agent.services'
    counterpart -- prevents an org_admin/org_manager from granting orchestration
    visibility to a user outside their own organization."""
    unique_ids = list(dict.fromkeys(uid for uid in user_ids if uid))
    if not unique_ids:
        return []
    object_ids = [ObjectId(uid) for uid in unique_ids if ObjectId.is_valid(uid)]
    if len(object_ids) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected user ids are invalid.",
        )
    count = await users_collection.count_documents(
        {"_id": {"$in": object_ids}, "organization_id": org_id}
    )
    if count != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected users do not belong to this organization.",
        )
    return unique_ids


async def _validate_team_id(org_id: str, team_id: Optional[str]) -> Optional[str]:
    """Validate that `team_id` is a real, non-deleted team belonging to `org_id`.
    Mirrors backend.agent.services' counterpart."""
    if not team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is required for team visibility.")
    if not ObjectId.is_valid(team_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is invalid.")
    doc = await teams_collection.find_one(
        {"_id": ObjectId(team_id), "organization_id": org_id, **NOT_DELETED}
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected team does not belong to this organization.")
    return team_id


async def _assert_visible(
    current_user_id: str,
    owner_scope: str,
    created_by: str,
    allowed_user_ids: List[str],
    team_id: Optional[str],
) -> None:
    if owner_scope == "user" and created_by != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    if (
        owner_scope == "selected_users"
        and created_by != current_user_id
        and current_user_id not in allowed_user_ids
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    if owner_scope == "team" and created_by != current_user_id:
        if not team_id or not await team_services.is_member(team_id, current_user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")


async def assert_orchestration_visible(current_user_id: str, orch: OrchestrationPublic) -> None:
    """Mirrors backend.agent.services.assert_agent_visible: personal orchestrations
    are visible/actionable only to their creator, "selected_users" orchestrations
    only to their creator + allowed_user_ids, and "team" orchestrations only to
    their creator + current team members -- 404 (not 403) for everyone else,
    including org_admin/org_manager/super_admin, so existence is never leaked.
    Must stay in sync with `build_orchestration_visibility_clauses`."""
    await _assert_visible(current_user_id, orch.owner_scope, orch.created_by, orch.allowed_user_ids, orch.team_id)


async def assert_orchestration_doc_visible(current_user_id: str, doc: dict) -> None:
    """Raw-Mongo-doc counterpart of `assert_orchestration_visible`, for callers
    (ai.multi_orchestration.executor's run/resume/resume_branch) that already
    have the doc and don't need the full public model. Keeps a personal/
    selected_users/team orchestration unreachable through direct chat/run/
    resume calls, not just the CRUD routes -- mirrors backend.agent.services'
    runtime enforcement in chat/direct_agent/widget."""
    await _assert_visible(
        current_user_id,
        doc.get("owner_scope", "organization"),
        doc.get("created_by", ""),
        doc.get("allowed_user_ids", []),
        doc.get("team_id"),
    )


async def build_orchestration_visibility_clauses(requesting_user_id: str) -> list[dict]:
    """Mongo `$or` clauses restricting results to orchestrations `requesting_user_id`
    may see. Mirrors backend.agent.services.build_agent_visibility_clauses."""
    team_ids = await team_services.get_team_ids_for_user(requesting_user_id)
    clauses = [
        {"owner_scope": {"$nin": ["user", "selected_users", "team"]}},
        {"owner_scope": "user", "created_by": requesting_user_id},
        {"owner_scope": "selected_users", "created_by": requesting_user_id},
        {"owner_scope": "selected_users", "allowed_user_ids": requesting_user_id},
        {"owner_scope": "team", "created_by": requesting_user_id},
    ]
    if team_ids:
        clauses.append({"owner_scope": "team", "team_id": {"$in": team_ids}})
    return clauses


async def _resolve_agents(org_id: str, agent_ids: List[str]) -> dict:
    """Return {agent_id: doc} for all given IDs scoped to org."""
    object_ids = [ObjectId(aid) for aid in agent_ids if ObjectId.is_valid(aid)]
    if not object_ids:
        return {}
    cursor = agents_collection.find(
        {"_id": {"$in": object_ids}, "organization_id": org_id, **NOT_DELETED}
    )
    docs = await cursor.to_list(length=200)
    return {str(d["_id"]): d for d in docs}


async def _validate_supervisor_build(
    payload_sub: List[str], org_id: str
) -> tuple[List[str], list, list]:
    """Validate a supervisor-mode orchestration.

    There are no edges to check, so cycle and orphan detection do not apply —
    the Supervisor reaches every attached agent directly. The only structural
    requirement is at least one real agent to route to.
    """
    sub_ids = list(dict.fromkeys(aid for aid in payload_sub if aid))
    if not sub_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A supervisor orchestration needs at least one connected agent.",
        )
    agent_map = await _resolve_agents(org_id, sub_ids)
    missing = [aid for aid in sub_ids if aid not in agent_map]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Agents not found or not in this organization: {missing}",
        )
    return sub_ids, [], []


async def _validate_and_build(
    payload_main: str,
    payload_sub: List[str],
    payload_connections: list,
    org_id: str,
) -> tuple[List[str], list, list]:
    """Validate agents exist + same org + no cycles + no self-edges. Returns (sub_agent_ids, connections_dicts, warnings)."""
    if not payload_main:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="main_agent_id is required for a sequential orchestration.",
        )
    all_ids = list({payload_main} | set(payload_sub))
    agent_map = await _resolve_agents(org_id, all_ids)

    missing = [aid for aid in all_ids if aid not in agent_map]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Agents not found or not in this organization: {missing}",
        )

    # Ensure main is in sub_agent_ids
    sub_ids = list({payload_main} | set(payload_sub))

    edges_raw = [(c.from_agent_id, c.to_agent_id) for c in payload_connections]
    # Remove self-edges
    edges_clean = [(f, t) for f, t in edges_raw if f != t]

    # Validate edge endpoints belong to this orchestration
    invalid_edge_agents = {
        aid for f, t in edges_clean for aid in (f, t) if aid not in agent_map
    }
    if invalid_edge_agents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Connection references agents not in this orchestration: {list(invalid_edge_agents)}",
        )

    if has_cycle(sub_ids, edges_clean):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Connections contain a cycle. Orchestrations must be acyclic.",
        )

    conn_lookup = {(c.from_agent_id, c.to_agent_id): c for c in payload_connections}
    conn_dicts = []
    for f, t in edges_clean:
        c = conn_lookup.get((f, t))
        conn_dicts.append({
            "from_agent_id": f,
            "to_agent_id": t,
            "label": getattr(c, "label", "") or "",
        })

    warnings = find_orphan_agents(payload_main, sub_ids, edges_clean)

    return sub_ids, conn_dicts, warnings


async def create_orchestration(
    payload: OrchestrationCreate,
    org_id: str,
    user_id: str,
    owner_scope: str = "organization",
    allowed_user_ids: Optional[List[str]] = None,
    team_id: Optional[str] = None,
) -> OrchestrationPublic:
    supervised = payload.mode == "supervisor"
    if supervised:
        sub_ids, conn_dicts, orphans = await _validate_supervisor_build(payload.sub_agent_ids, org_id)
    else:
        sub_ids, conn_dicts, orphans = await _validate_and_build(
            payload.main_agent_id, payload.sub_agent_ids, payload.connections, org_id
        )
    if orphans:
        logger.warning("Orchestration has unreachable agents: %s", orphans)

    cleaned_allowed_user_ids: List[str] = []
    if owner_scope == "selected_users":
        cleaned_allowed_user_ids = await _validate_allowed_user_ids(org_id, allowed_user_ids or [])
    cleaned_team_id: Optional[str] = None
    if owner_scope == "team":
        cleaned_team_id = await _validate_team_id(org_id, team_id)

    doc = {
        "organization_id": org_id,
        "name": payload.name,
        "description": payload.description,
        "mode": payload.mode,
        # No entry-point agent in supervisor mode: the hardcoded Supervisor is
        # the entry point, and it is not an agent document.
        "main_agent_id": None if supervised else payload.main_agent_id,
        "sub_agent_ids": sub_ids,
        "connections": conn_dicts,
        "supervisor_config": (
            (payload.supervisor_config or SupervisorConfig()).model_dump() if supervised else None
        ),
        "max_depth": payload.max_depth,
        "timeout_sec": payload.timeout_sec,
        "created_by": user_id,
        "created_at": datetime.now(timezone.utc),
        "is_deleted": False,
        "owner_scope": owner_scope,
        "allowed_user_ids": cleaned_allowed_user_ids,
        "team_id": cleaned_team_id,
    }
    result = await agent_orchestrations_collection.insert_one(doc)
    doc["_id"] = result.inserted_id

    agent_map = await _resolve_agents(org_id, sub_ids)
    return _doc_to_public(doc, agent_map)


async def list_orchestrations(
    org_id: str, requesting_user_id: Optional[str] = None, skip: int = 0, limit: int = 200,
) -> tuple[List[OrchestrationPublic], int]:
    query: dict = {"organization_id": org_id, **NOT_DELETED}
    if requesting_user_id is not None:
        query["$or"] = await build_orchestration_visibility_clauses(requesting_user_id)
    total = await agent_orchestrations_collection.count_documents(query)
    cursor = agent_orchestrations_collection.find(
        query,
        sort=[("created_at", -1)],
    ).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    result = []
    for doc in docs:
        all_ids = list(set(doc.get("sub_agent_ids", [])))
        agent_map = await _resolve_agents(org_id, all_ids)
        result.append(_doc_to_public(doc, agent_map))
    return result, total


async def get_orchestration(orchestration_id: str, org_id: str) -> OrchestrationPublic:
    if not ObjectId.is_valid(orchestration_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    doc = await agent_orchestrations_collection.find_one(
        {"_id": ObjectId(orchestration_id), "organization_id": org_id, **NOT_DELETED}
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    agent_map = await _resolve_agents(org_id, doc.get("sub_agent_ids", []))
    return _doc_to_public(doc, agent_map)


async def update_orchestration(
    orchestration_id: str, payload: OrchestrationUpdate, org_id: str
) -> OrchestrationPublic:
    if not ObjectId.is_valid(orchestration_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")

    doc = await agent_orchestrations_collection.find_one(
        {"_id": ObjectId(orchestration_id), "organization_id": org_id, **NOT_DELETED}
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")

    updates: dict = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.max_depth is not None:
        updates["max_depth"] = payload.max_depth
    if payload.timeout_sec is not None:
        updates["timeout_sec"] = payload.timeout_sec

    if payload.owner_scope is not None:
        updates["owner_scope"] = payload.owner_scope
        if payload.owner_scope != "team":
            updates["team_id"] = None
        if payload.owner_scope != "selected_users":
            updates["allowed_user_ids"] = []

    if payload.allowed_user_ids is not None:
        updates["allowed_user_ids"] = await _validate_allowed_user_ids(org_id, payload.allowed_user_ids)
    if payload.team_id is not None:
        if payload.team_id:
            updates["team_id"] = await _validate_team_id(org_id, payload.team_id)
        else:
            updates["team_id"] = None


    new_main = payload.main_agent_id or doc.get("main_agent_id")
    new_sub = payload.sub_agent_ids if payload.sub_agent_ids is not None else doc.get("sub_agent_ids", [])
    new_connections = payload.connections if payload.connections is not None else [
        SimpleNamespace(
            from_agent_id=c["from_agent_id"],
            to_agent_id=c["to_agent_id"],
            label=c.get("label", ""),
        )
        for c in doc.get("connections", [])
    ]
    new_mode = payload.mode or doc.get("mode") or "sequential"
    if payload.mode is not None:
        updates["mode"] = payload.mode
    if payload.supervisor_config is not None:
        updates["supervisor_config"] = payload.supervisor_config.model_dump()

    structure_changed = (
        payload.main_agent_id is not None
        or payload.sub_agent_ids is not None
        or payload.connections is not None
        or payload.mode is not None
    )
    if structure_changed and new_mode == "supervisor":
        sub_ids, _, _ = await _validate_supervisor_build(new_sub, org_id)
        # Switching to supervisor mode drops the graph: the Supervisor routes
        # dynamically, so edges and a fixed entry point no longer mean anything.
        updates["sub_agent_ids"] = sub_ids
        updates["main_agent_id"] = None
        updates["connections"] = []
        if not doc.get("supervisor_config") and "supervisor_config" not in updates:
            updates["supervisor_config"] = SupervisorConfig().model_dump()
    elif structure_changed:
        sub_ids, conn_dicts, orphans = await _validate_and_build(new_main, new_sub, new_connections, org_id)
        if orphans:
            logger.warning("Updated orchestration has unreachable agents: %s", orphans)
        updates["main_agent_id"] = new_main
        updates["sub_agent_ids"] = sub_ids
        updates["connections"] = conn_dicts

    if updates:
        await agent_orchestrations_collection.update_one(
            {"_id": ObjectId(orchestration_id)}, {"$set": updates}
        )

    return await get_orchestration(orchestration_id, org_id)


async def get_run_status(run_id: str, orchestration_id: str, org_id: str) -> OrchestrationRunStatus:
    run_doc = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one({
        "run_id": run_id,
        "orchestration_id": orchestration_id,
        "organization_id": org_id,
    })
    if not run_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    # Build the step trace: completed agents (from execution_path) plus the
    # currently-running one if the run is still active.
    #
    # Handback steps are excluded. A handback is an internal control transfer —
    # one agent telling the Supervisor "not my domain" — so surfacing it would
    # show the user an agent that was tried and declined, and its output_summary
    # ("handback: ...") as if it were an answer. The entry stays in
    # execution_path for logs and audit.
    steps: list[AgentStepPublic] = [
        AgentStepPublic(
            agent_id=e.get("agent_id") or "",
            agent_name=e.get("agent_name", ""),
            status=e.get("status") or "complete",
            output=e.get("output") or e.get("output_summary"),
            branch_id=e.get("branch_id"),
        )
        for e in run_doc.get("execution_path", [])
        if e.get("status") != "handback"
    ]
    run_status = run_doc["status"]
    current_id = run_doc.get("current_agent_id")
    current_name = run_doc.get("current_agent_name")
    if run_status in ("running", "routing", "loading") and current_id:
        # Only show a running step if it isn't already the last completed one.
        if not steps or steps[-1].agent_id != current_id:
            steps.append(AgentStepPublic(
                agent_id=current_id,
                agent_name=current_name or current_id,
                status="running",
            ))
    # Build branches list from branches array
    branches = [
        BranchStatusPublic(
            branch_id=b.get("branch_id", ""),
            status=b.get("status", ""),
            human_question=b.get("human_question"),
            human_asked_by_agent=b.get("human_asked_by_agent"),
            pending_reauth=b.get("pending_reauth"),
            pending_agents=b.get("pending_agents", []),
            label=b.get("label"),
        )
        for b in run_doc.get("branches", [])
    ]

    return OrchestrationRunStatus(
        run_id=run_doc["run_id"],
        orchestration_id=run_doc["orchestration_id"],
        status=run_status,
        current_agent_id=current_id,
        current_agent_name=current_name,
        steps=steps,
        human_question=run_doc.get("human_question"),
        pending_reauth=run_doc.get("pending_reauth"),
        final_response=run_doc.get("final_response"),
        started_at=run_doc.get("started_at"),
        completed_at=run_doc.get("completed_at"),
        branches=branches,
    )


async def delete_orchestration(orchestration_id: str, org_id: str) -> None:
    if not ObjectId.is_valid(orchestration_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    result = await agent_orchestrations_collection.update_one(
        {"_id": ObjectId(orchestration_id), "organization_id": org_id, **NOT_DELETED},
        {"$set": {"is_deleted": True}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")


#service method for listing all sessions of an orchestration for a user
async def get_branch_messages(
    session_id: str,
    orchestration_id: str,
    org_id: str,
    branch_id: str,
) -> OrchestrationSessionHistoryResponse:
    """Get messages for a specific branch within a session."""
    from backend.db.database import db
    doc = await db[ORCHESTRATION_CONVERSATIONS_COLLECTION].find_one({
        "session_id": session_id,
        "orchestration_id": orchestration_id,
        "organization_id": org_id,
    })
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No conversation history found.")
    
    # Filter conversations by branch_id
    branch_conversations = [
        OrchestrationConversationEntry(
            type=e.get("type", "node"),
            user_input=e.get("user_input"),
            node_name=e.get("node_name"),
            node_num=e.get("node_num", 0),
            tools_called=e.get("tools_called", []),
            node_output=e.get("node_output"),
            timestamp=e.get("timestamp"),
            branch_id=e.get("branch_id"),
        )
        for e in doc.get("conversations", [])
        if e.get("branch_id") == branch_id or (branch_id == "main" and not e.get("branch_id"))
    ]
    
    # Load pending run for this session
    pending_run = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one(
        {
            "session_id": session_id,
            "organization_id": org_id,
            "status": {"$in": [RunStatus.WAITING_FOR_HUMAN.value, RunStatus.WAITING_FOR_REAUTH.value]},
        },
        sort=[("started_at", -1)],
    )
    pending_branches: List[BranchStatusPublic] = []
    if pending_run:
        for b in pending_run.get("branches", []):
            if b.get("status") in (RunStatus.WAITING_FOR_HUMAN.value, RunStatus.WAITING_FOR_REAUTH.value) and b.get("branch_id") == branch_id:
                pending_branches.append(BranchStatusPublic(
                    branch_id=b.get("branch_id", ""),
                    status=b.get("status", ""),
                    human_question=b.get("human_question"),
                    human_asked_by_agent=b.get("human_asked_by_agent"),
                    pending_reauth=b.get("pending_reauth"),
                    pending_agents=b.get("pending_agents", []),
                    label=b.get("label"),
                ))

    return OrchestrationSessionHistoryResponse(
        session_id=session_id,
        orchestration_id=orchestration_id,
        organization_id=org_id,
        user_id=doc.get("user_id", ""),
        total_messages=doc.get("total_messages", len(branch_conversations)),
        conversations=branch_conversations,
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        pending_run_id=pending_run["run_id"] if pending_run else None,
        pending_branches=pending_branches,
    )


async def list_orchestration_sessions(
    orchestration_id: str, org_id: str, user_id: str
) -> OrchestrationSessionListResponse:
    from backend.db.database import chat_sessions_collection, db

    cursor = chat_sessions_collection.find(
        {
            "orchestration_id": orchestration_id,
            "organization_id": org_id,
            "user_id": user_id,
            "mode": "orchestration",
            **NOT_DELETED,
        },
        sort=[("created_at", -1)],
    )
    session_docs = await cursor.to_list(length=200)
    if not session_docs:
        return OrchestrationSessionListResponse(orchestration_id=orchestration_id, sessions=[])

    thread_ids = [s["thread_id"] for s in session_docs]
    conv_cursor = db[ORCHESTRATION_CONVERSATIONS_COLLECTION].find(
        {"session_id": {"$in": thread_ids}, "orchestration_id": orchestration_id, "organization_id": org_id}
    )
    conv_docs = await conv_cursor.to_list(length=200)
    conv_map = {c["session_id"]: c for c in conv_docs}

    sessions: List[OrchestrationSessionBrief] = []
    for s in session_docs:
        conv = conv_map.get(s["thread_id"])
        last_msg = None
        total_messages = 0
        updated_at = s.get("created_at")
        if conv and conv.get("conversations"):
            last_entry = conv["conversations"][-1]
            last_msg = last_entry.get("user_input") or last_entry.get("node_output")
            total_messages = conv.get("total_messages", len(conv["conversations"]))
            updated_at = conv.get("updated_at", updated_at)

        sessions.append(OrchestrationSessionBrief(
            session_id=s["thread_id"],
            name=s.get("name"),
            last_message=(last_msg[:120] if last_msg else None),
            total_messages=total_messages,
            created_at=s.get("created_at"),
            updated_at=updated_at,
        ))

    return OrchestrationSessionListResponse(orchestration_id=orchestration_id, sessions=sessions)


async def delete_orchestration_session(
    session_id: str, orchestration_id: str, org_id: str, user_id: str,
) -> None:
    """Soft-delete an orchestration chat session and its conversation history —
    mirrors backend.chat.services.delete_session for the plain-chat stack."""
    from backend.db.database import db

    result = await chat_sessions_collection.find_one_and_update(
        {
            "thread_id": session_id,
            "orchestration_id": orchestration_id,
            "organization_id": org_id,
            "user_id": user_id,
            "mode": "orchestration",
            **NOT_DELETED,
        },
        {"$set": {"is_deleted": True}},
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    await db[ORCHESTRATION_CONVERSATIONS_COLLECTION].delete_many(
        {"session_id": session_id, "organization_id": org_id}
    )
    logger.info("[DELETE] orchestration session=%s org=%s user=%s", session_id, org_id, user_id)


#service method for getting sessions history
async def get_orchestration_session_history(
    session_id: str, orchestration_id: str, org_id: str
) -> OrchestrationSessionHistoryResponse:
    from backend.db.database import db
    doc = await db[ORCHESTRATION_CONVERSATIONS_COLLECTION].find_one({
        "session_id": session_id,
        "orchestration_id": orchestration_id,
        "organization_id": org_id,
    })
    if not doc:
        # A conversation document only appears on the first message, so a session
        # that exists but hasn't been used yet has *empty* history, not missing
        # history. The pre-load flow creates the session before the user types
        # and the chat page fetches history immediately, so 404-ing here made
        # every new session open with a failed request.
        session = await chat_sessions_collection.find_one({
            "thread_id": session_id,
            "orchestration_id": orchestration_id,
            "organization_id": org_id,
            **NOT_DELETED,
        })
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        return OrchestrationSessionHistoryResponse(
            session_id=session_id,
            orchestration_id=orchestration_id,
            organization_id=org_id,
            user_id=session.get("user_id", ""),
            total_messages=0,
            conversations=[],
            created_at=session.get("created_at"),
            updated_at=session.get("created_at"),
        )
    conversations = [
        OrchestrationConversationEntry(
            type=e.get("type", "node"),
            user_input=e.get("user_input"),
            node_name=e.get("node_name"),
            node_num=e.get("node_num", 0),
            tools_called=e.get("tools_called", []),
            node_output=e.get("node_output"),
            timestamp=e.get("timestamp"),
            branch_id=e.get("branch_id"),
        )
        for e in doc.get("conversations", [])
    ]
    # -------------------------------------
    # Load pending run for this session
    # -------------------------------------
    pending_run = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one(
        {
            "session_id": session_id,
            "organization_id": org_id,
            "status": {"$in": [RunStatus.WAITING_FOR_HUMAN.value, RunStatus.WAITING_FOR_REAUTH.value]},
        },
        sort=[("started_at", -1)],
    )
    pending_branches: List[BranchStatusPublic] = []
    if pending_run:
        for b in pending_run.get("branches", []):
            if b.get("status") in (RunStatus.WAITING_FOR_HUMAN.value, RunStatus.WAITING_FOR_REAUTH.value):
                pending_branches.append(BranchStatusPublic(
                    branch_id=b.get("branch_id", ""),
                    status=b.get("status", ""),
                    human_question=b.get("human_question"),
                    human_asked_by_agent=b.get("human_asked_by_agent"),
                    pending_reauth=b.get("pending_reauth"),
                    pending_agents=b.get("pending_agents", []),
                    label=b.get("label"),
                ))

    return OrchestrationSessionHistoryResponse(
        session_id=session_id,
        orchestration_id=orchestration_id,
        organization_id=org_id,
        user_id=doc.get("user_id", ""),
        total_messages=doc.get("total_messages", len(conversations)),
        conversations=conversations,
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        pending_run_id=pending_run["run_id"] if pending_run else None,
        pending_branches=pending_branches,
    )
