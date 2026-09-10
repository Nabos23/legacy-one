import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import litellm
from bson import ObjectId
from fastapi import HTTPException, status

from ai.models import Model
from ai.schedule.recurrence import (
    RecurrenceError,
    compute_next_run_at,
    recurrence_to_cron,
    validate_timezone,
)
from backend.auth.constants import ROLE_ADMIN, ROLE_ORG_ADMIN, ROLE_ORG_MANAGER, ROLE_SUPER_ADMIN
from backend.auth.schemas import UserPublic
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.db.database import agent_orchestrations_collection
from backend.orchestration.services import assert_orchestration_doc_visible
from backend.agent.services import build_agent_visibility_clauses
from backend.db.database import (
    agents_collection,
    chat_sessions_collection,
    schedule_runs_collection,
    schedules_collection,
)
from backend.prompt_generator.schemas import PromptGeneratorRequest
from backend.prompt_generator.services import _build_agent_context
from backend.schedule.schemas import (
    PreviewQuestionsRequest,
    PreviewQuestionsResponse,
    ScheduleCreate,
    SchedulePublic,
    ScheduleRunPublic,
    ScheduleUpdate,
)

logger = logging.getLogger("schedule.services")

# Roles with unrestricted access to every schedule in their organization.
# Everything else (ROLE_USER, and its legacy alias ROLE_MEMBER) is scoped to
# schedules the requesting user created themselves -- see _assert_owner_or_admin.
_UNRESTRICTED_ROLES = {ROLE_SUPER_ADMIN, ROLE_ORG_ADMIN, ROLE_ADMIN}

_QUESTIONS_SYSTEM_PROMPT = """You are helping a user set up an unattended, recurring scheduled run of an AI agent or multi-agent orchestration.

Given the target's identity, prompt, and capabilities below, evaluate whether it has the tools and capability to perform the requested task.

CRITICAL CAPABILITY CHECK:
First, analyze if the requested task requires tools or capabilities that the target DOES NOT HAVE.
For example:
- Asking a Google Meet agent or Document Generator to run database/SQL queries when it has no database tools.
- Asking an agent without email tools to send emails.
- Asking an agent without payment capabilities to process credit cards.

If the target DOES NOT have the capability or tools to perform the requested core task, output ONLY:
{"status": "invalid"}

Otherwise, if the target HAS the required capabilities:
Return a JSON object of the shape:
{"status": "valid", "questions": ["...", ...]}

Rules for valid questions:
- Only ask about things that would materially change how the agent acts.
- If the task is already fully specific and unambiguous given capabilities, return "questions": [].
- Keep each question short, specific, and answerable in one sentence."""


# ---------------------------------------------------------------------------
# Agent validation (mirrors backend/direct_agent/services.py::_load_single_agent
# exactly -- a schedule must only ever be creatable/executable against an
# agent the owning user could otherwise reach through direct_chat)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Target validation
# ---------------------------------------------------------------------------

async def _validate_agent_for_schedule(agent_id: str, org_id: str, user_id: str) -> dict:

    if not agent_id or not ObjectId.is_valid(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    agent_doc = await agents_collection.find_one({
        "_id": ObjectId(agent_id),
        "organization_id": org_id,
        **NOT_DELETED,
        "$or": await build_agent_visibility_clauses(user_id),
    })
    if not agent_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    return agent_doc


async def _validate_orchestration_for_schedule(orchestration_id: str, org_id: str, user_id: str) -> dict:

    if not orchestration_id or not ObjectId.is_valid(orchestration_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    orch_doc = await agent_orchestrations_collection.find_one({
        "_id": ObjectId(orchestration_id),
        "organization_id": org_id,
        **NOT_DELETED,
    })
    if not orch_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration not found.")
    await assert_orchestration_doc_visible(user_id, orch_doc)
    return orch_doc


async def _validate_target_for_schedule(
    target_type: str, target_id: Optional[str], org_id: str, user_id: str
) -> dict:
    validators = {
        "agent": _validate_agent_for_schedule,
        "orchestration": _validate_orchestration_for_schedule,
    }
    validator = validators.get(target_type)
    if not validator or not target_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid target configuration for '{target_type}'.")
    return await validator(target_id, org_id, user_id)


def _assert_owner_or_admin(doc: dict, current_user: UserPublic) -> None:
    """Ownership scoping for schedules -- strictly user-specific (created_by == current_user.id)."""
    if doc.get("created_by") != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found.")


def _to_public(doc: dict) -> SchedulePublic:
    return SchedulePublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        created_by=doc["created_by"],
        name=doc["name"],
        description=doc.get("description"),
        target_type=doc.get("target_type", "agent"),
        agent_id=doc.get("agent_id"),
        orchestration_id=doc.get("orchestration_id"),
        message=doc["message"],
        clarifications=doc.get("clarifications", []),
        thread_id=doc["thread_id"],
        recurrence=doc["recurrence"],
        cron_expr=doc.get("cron_expr"),
        timezone=doc["timezone"],
        status=doc["status"],
        next_run_at=doc["next_run_at"],
        last_run_at=doc.get("last_run_at"),
        last_run_status=doc.get("last_run_status"),
        last_run_error=doc.get("last_run_error"),
        consecutive_failure_count=doc.get("consecutive_failure_count", 0),
        max_consecutive_failures=doc.get("max_consecutive_failures", 3),
        run_count=doc.get("run_count", 0),
        needs_attention=doc.get("needs_attention", False),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _to_run_public(doc: dict) -> ScheduleRunPublic:
    return ScheduleRunPublic(
        run_id=doc["run_id"],
        schedule_id=doc["schedule_id"],
        target_type=doc.get("target_type", "agent"),
        agent_id=doc.get("agent_id"),
        orchestration_id=doc.get("orchestration_id"),
        thread_id=doc["thread_id"],
        status=doc["status"],
        attempt=doc.get("attempt", 1),
        message_sent=doc.get("message_sent", ""),
        reply=doc.get("reply"),
        auth_errors=doc.get("auth_errors", []),
        error_type=doc.get("error_type"),
        error_message=doc.get("error_message"),
        started_at=doc["started_at"],
        completed_at=doc.get("completed_at"),
        duration_ms=doc.get("duration_ms"),
    )


# ---------------------------------------------------------------------------
# Pre-schedule clarifications wizard
# ---------------------------------------------------------------------------

async def generate_scheduling_questions(
    payload: PreviewQuestionsRequest, current_user: UserPublic
) -> PreviewQuestionsResponse:
    """Reuses prompt_generator's agent-context builder or orchestration metadata
    and makes one cheap-model call to surface clarifying questions."""
    target_type = payload.target_type
    target_id = payload.orchestration_id if target_type == "orchestration" else payload.agent_id
    doc = await _validate_target_for_schedule(target_type, target_id, current_user.organization_id, current_user.id)

    if target_type == "orchestration":
        sub_agent_ids = doc.get("sub_agent_ids") or []
        connections = doc.get("connections") or []

        # Gather all unique agent IDs in this orchestration
        all_agent_ids = set()
        for aid in sub_agent_ids:
            if aid and ObjectId.is_valid(str(aid)):
                all_agent_ids.add(ObjectId(str(aid)))
        for conn in connections:
            frm = conn.get("from_agent_id")
            to = conn.get("to_agent_id")
            if frm and ObjectId.is_valid(str(frm)):
                all_agent_ids.add(ObjectId(str(frm)))
            if to and ObjectId.is_valid(str(to)):
                all_agent_ids.add(ObjectId(str(to)))

        # Batch load agent documents
        agent_docs = []
        if all_agent_ids:
            cursor = agents_collection.find({
                "_id": {"$in": list(all_agent_ids)},
                "organization_id": current_user.organization_id,
                **NOT_DELETED,
            })
            agent_docs = await cursor.to_list(length=100)

        agent_map = {str(a["_id"]): a for a in agent_docs}

        # Build agent capabilities summary
        agent_summaries = []
        for aid_str, a in agent_map.items():
            name = a.get("name", "Unknown Agent")
            desc = a.get("description") or (a.get("prompt", "")[:150])
            agent_summaries.append(f"  - Agent '{name}': {desc}")

        context_parts = [
            f"Orchestration Name: {doc.get('name', '')}",
            f"Description: {doc.get('description', '')}",
            f"Mode: {doc.get('mode') or doc.get('strategy', 'supervisor')}",
            "\nParticipating Agents & Capabilities:\n" + ("\n".join(agent_summaries) if agent_summaries else "  (None)"),
        ]
        agent_context = "\n".join(context_parts)
    else:
        agent_context = await _build_agent_context(
            PromptGeneratorRequest(agent_id=payload.agent_id), current_user
        )
    user_msg = f"{agent_context}\n\nScheduled Task: {payload.message}"

    try:
        resp = await litellm.acompletion(
            model=Model.GPT_5_4_NANO.value,
            messages=[
                {"role": "system", "content": _QUESTIONS_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content or "{}")

        status_val = str(parsed.get("status", "")).lower()
        if status_val == "invalid" or parsed.get("invalid") is True or parsed.get("is_valid") is False:
            target_label = "Orchestration" if target_type == "orchestration" else "Agent"
            return PreviewQuestionsResponse(
                questions=[],
                is_capable=False,
                invalid_reason=f"The selected {target_label} doesn't have the capability to run this specific task.",
            )

        questions = parsed.get("questions", [])
        clean_questions = [str(q).strip() for q in questions if isinstance(questions, list) and str(q).strip()]
        return PreviewQuestionsResponse(questions=clean_questions, is_capable=True)
    except Exception:
        logger.warning("[SCHEDULE] question generation failed for target=%s", target_id, exc_info=True)
        return PreviewQuestionsResponse(questions=[], is_capable=True)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_schedule(payload: ScheduleCreate, org_id: str, current_user: UserPublic) -> SchedulePublic:
    target_type = payload.target_type
    target_id = payload.orchestration_id if target_type == "orchestration" else payload.agent_id
    await _validate_target_for_schedule(target_type, target_id, org_id, current_user.id)

    recurrence = payload.recurrence.model_dump()
    try:
        validate_timezone(payload.timezone)
        cron_expr = recurrence_to_cron(recurrence)
    except RecurrenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    if cron_expr is None:  # kind == "once"
        next_run_at = recurrence["run_at"]
    else:
        next_run_at = compute_next_run_at(cron_expr, payload.timezone, now)

    thread_id = str(uuid.uuid4())
    session_doc = {
        "thread_id": thread_id,
        "organization_id": org_id,
        "user_id": current_user.id,
        "created_at": now,
        "is_deleted": False,
    }
    if target_type == "orchestration":
        session_doc.update({
            "orchestration_id": payload.orchestration_id,
            "mode": "orchestration",
        })
    else:
        session_doc.update({
            "agent_ids": [payload.agent_id],
            "mode": "single",
        })
    await chat_sessions_collection.insert_one(session_doc)

    doc = {
        "organization_id": org_id,
        "created_by": current_user.id,
        "name": payload.name,
        "description": payload.description,
        "target_type": target_type,
        "agent_id": payload.agent_id,
        "orchestration_id": payload.orchestration_id,
        "message": payload.message,
        "clarifications": [c.model_dump() for c in payload.clarifications],
        "thread_id": thread_id,
        "recurrence": recurrence,
        "cron_expr": cron_expr,
        "timezone": payload.timezone,
        "status": "active",
        "next_run_at": next_run_at,
        "lock_id": None,
        "locked_at": None,
        "claim_epoch": 0,
        "last_run_at": None,
        "last_run_status": None,
        "last_run_error": None,
        "consecutive_failure_count": 0,
        "max_consecutive_failures": payload.max_consecutive_failures,
        "run_count": 0,
        "needs_attention": False,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    result = await schedules_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_public(doc)


async def list_schedules(
    org_id: str,
    current_user: UserPublic,
    needs_attention: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[List[SchedulePublic], int]:
    query: dict = {
        "organization_id": org_id,
        "created_by": current_user.id,
        **NOT_DELETED,
    }
    if needs_attention is not None:
        query["needs_attention"] = needs_attention
    total = await schedules_collection.count_documents(query)
    cursor = schedules_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def _get_schedule_doc(schedule_id: str, org_id: str) -> dict:
    if not ObjectId.is_valid(schedule_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found.")
    doc = await schedules_collection.find_one(
        {"_id": ObjectId(schedule_id), "organization_id": org_id, **NOT_DELETED}
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found.")
    return doc


async def get_schedule(schedule_id: str, org_id: str, current_user: UserPublic) -> SchedulePublic:
    doc = await _get_schedule_doc(schedule_id, org_id)
    _assert_owner_or_admin(doc, current_user)
    return _to_public(doc)


async def update_schedule(
    schedule_id: str, payload: ScheduleUpdate, org_id: str, current_user: UserPublic
) -> SchedulePublic:
    doc = await _get_schedule_doc(schedule_id, org_id)
    _assert_owner_or_admin(doc, current_user)

    if doc["status"] in ("completed", "terminated") and (payload.status or payload.recurrence):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This schedule has already finished and can no longer be modified.",
        )

    updates: dict = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.message is not None:
        updates["message"] = payload.message
    if payload.clarifications is not None:
        updates["clarifications"] = [c.model_dump() for c in payload.clarifications]
    if payload.max_consecutive_failures is not None:
        updates["max_consecutive_failures"] = payload.max_consecutive_failures

    tz = payload.timezone or doc["timezone"]
    if payload.timezone is not None:
        try:
            validate_timezone(payload.timezone)
        except RecurrenceError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        updates["timezone"] = payload.timezone

    if payload.recurrence is not None:
        recurrence = payload.recurrence.model_dump()
        try:
            cron_expr = recurrence_to_cron(recurrence)
        except RecurrenceError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        now = datetime.now(timezone.utc)
        updates["recurrence"] = recurrence
        updates["cron_expr"] = cron_expr
        updates["next_run_at"] = recurrence["run_at"] if cron_expr is None else compute_next_run_at(cron_expr, tz, now)
    elif payload.timezone is not None and doc.get("cron_expr"):
        # timezone alone changed -- re-anchor next_run_at to the new zone so it
        # doesn't keep firing at the old zone's wall-clock time.
        updates["next_run_at"] = compute_next_run_at(doc["cron_expr"], tz, datetime.now(timezone.utc))

    if payload.status is not None:
        updates["status"] = payload.status

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update.")

    updates["updated_at"] = datetime.now(timezone.utc)
    await schedules_collection.update_one({"_id": doc["_id"]}, {"$set": updates})
    refreshed = await schedules_collection.find_one({"_id": doc["_id"]})
    return _to_public(refreshed)


async def pause_schedule(schedule_id: str, org_id: str, current_user: UserPublic) -> SchedulePublic:
    doc = await _get_schedule_doc(schedule_id, org_id)
    _assert_owner_or_admin(doc, current_user)
    if doc["status"] not in ("active", "running"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot pause a schedule in '{doc['status']}' status.")
    await schedules_collection.update_one(
        {"_id": doc["_id"]}, {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}}
    )
    refreshed = await schedules_collection.find_one({"_id": doc["_id"]})
    return _to_public(refreshed)


async def resume_schedule(schedule_id: str, org_id: str, current_user: UserPublic) -> SchedulePublic:
    doc = await _get_schedule_doc(schedule_id, org_id)
    _assert_owner_or_admin(doc, current_user)
    if doc["status"] != "paused":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot resume a schedule in '{doc['status']}' status.")

    now = datetime.now(timezone.utc)
    if doc.get("cron_expr"):
        next_run_at = compute_next_run_at(doc["cron_expr"], doc["timezone"], now)
    else:
        # "once" schedule: fire immediately if its run_at already passed while paused.
        next_run_at = doc["next_run_at"] if doc["next_run_at"] > now else now

    await schedules_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {
            "status": "active",
            "next_run_at": next_run_at,
            "consecutive_failure_count": 0,
            "updated_at": now,
        }},
    )
    refreshed = await schedules_collection.find_one({"_id": doc["_id"]})
    return _to_public(refreshed)


async def delete_schedule(schedule_id: str, org_id: str, current_user: UserPublic) -> None:
    doc = await _get_schedule_doc(schedule_id, org_id)
    _assert_owner_or_admin(doc, current_user)
    await schedules_collection.update_one({"_id": doc["_id"]}, soft_delete_update())


async def list_schedule_runs(
    schedule_id: str, org_id: str, current_user: UserPublic, skip: int = 0, limit: int = 50
) -> List[ScheduleRunPublic]:
    doc = await _get_schedule_doc(schedule_id, org_id)
    _assert_owner_or_admin(doc, current_user)
    cursor = (
        schedule_runs_collection.find({"schedule_id": schedule_id})
        .sort("started_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_to_run_public(doc) for doc in docs]
