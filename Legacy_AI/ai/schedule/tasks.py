import asyncio
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
import time
from ai.multi_orchestration.executor import run_orchestration
from backend.db.constants import ORCHESTRATION_RUNS_COLLECTION
from backend.db.database import sync_db
from ai.multi_orchestration.models import TERMINAL_STATUSES, RunStatus
from backend.core.softdelete import NOT_DELETED
from backend.db.database import schedules_sync, schedule_runs_sync
from ai.schedule.celery_app import celery_app
from ai.schedule.recurrence import compute_next_run_at
from backend.direct_agent.services import direct_chat

logger = logging.getLogger(__name__)

MAX_CLAIMS_PER_TICK = 200
LOCK_TIMEOUT_MINUTES = 10


# ---------------------------------------------------------------------------
# Shared async event loop for run_schedule_task
# ---------------------------------------------------------------------------
# direct_chat()'s whole dependency chain (agents_collection, chat_sessions_
# collection, LangGraph's checkpoint store, ...) goes through the single
# module-level AsyncIOMotorClient in backend/db/database.py. Motor binds that
# client's background monitoring tasks to whichever event loop first uses it,
# and reusing it from a *different* loop afterwards raises "Event loop is
# closed" -- exactly what asyncio.run() does, since it creates a fresh loop
# and tears it down on every single call. With this worker's --pool=threads
# --concurrency=8, that teardown/recreate was happening on every scheduled
# run, across whichever of the 8 threads picked it up.
#
# Fix: one event loop, spun up once and kept running for the life of the
# worker process, and every run submits its coroutine to that same loop via
# run_coroutine_threadsafe(). This doesn't cap throughput to "one run at a
# time" -- asyncio freely interleaves many concurrent I/O-bound coroutines
# (Mongo calls, LLM calls) on a single loop, which is exactly the workload
# here. The 8 Celery threads still run their sync bookkeeping (claiming,
# retry/failure bookkeeping via the sync PyMongo client) concurrently; only
# the actual direct_chat() call is funneled through the shared loop.
#
# To scale schedule throughput beyond what one loop can interleave, scale
# horizontally -- run more celery_worker replicas. Each is its own process
# with its own loop and its own Motor client, so there's no cross-process
# contention to design around.
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


def _get_shared_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            threading.Thread(
                target=_loop.run_forever, name="schedule-async-loop", daemon=True,
            ).start()
        return _loop


def _run_async(coro):
    """Run `coro` on the shared loop from whichever Celery worker thread
    is executing this task, and block until it completes."""
    return asyncio.run_coroutine_threadsafe(coro, _get_shared_loop()).result()


# ---------------------------------------------------------------------------
# tick_schedules -- the single static Beat entry
# ---------------------------------------------------------------------------

def _claim_next_due_schedule(now: datetime, stale_before: datetime) -> Optional[dict]:
    

    candidate = schedules_sync.find_one({
        "$or": [
            {"status": "active", "next_run_at": {"$lte": now}},
            {"status": "running", "locked_at": {"$lt": stale_before}},  # stale-lock reclaim
        ],
        **NOT_DELETED,
    })
    if not candidate:
        return None

    update: dict = {
        "$set": {
            "lock_id": str(uuid.uuid4()),
            "locked_at": now,
            "status": "running",
        },
        "$inc": {"claim_epoch": 1},
    }
    if candidate.get("cron_expr"):
        update["$set"]["next_run_at"] = compute_next_run_at(
            candidate["cron_expr"], candidate["timezone"], now
        )
    # For "once" schedules (no cron_expr), next_run_at is left as-is -- it no
    # longer matters once status leaves "active"; run_schedule_task finalizes
    # this schedule to status="completed" regardless of outcome.

    # Gate the write on claim_epoch still matching what we just read -- the
    # compare-and-swap that makes this safe under concurrent claimers even
    # though the read and the write can't be one atomic Mongo call.
    return schedules_sync.find_one_and_update(
        {"_id": candidate["_id"], "claim_epoch": candidate["claim_epoch"]},
        update,
        return_document=ReturnDocument.AFTER,
    )


@celery_app.task(name="ai.schedule.tasks.tick_schedules", bind=True)
def tick_schedules(self) -> dict:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=LOCK_TIMEOUT_MINUTES)

    claimed_count = 0
    for _ in range(MAX_CLAIMS_PER_TICK):
        claimed = _claim_next_due_schedule(now, stale_before)
        if claimed is None:
            # Either nothing is due, or this particular claim lost a race to
            # another concurrent tick (rare -- only possible if a previous
            # tick is still running when the next one fires). Either way,
            # stopping here is safe: a lost race just means the doc is
            # already someone else's responsibility, and anything genuinely
            # still due gets picked up on the next tick 30s later.
            break
        claimed_count += 1
        run_schedule_task.apply_async(
            kwargs={
                "schedule_id": str(claimed["_id"]),
                "lock_id": claimed["lock_id"],
                "claim_epoch": claimed["claim_epoch"],
            },
            queue="schedules",
        )
    if claimed_count:
        logger.info("[schedule] tick claimed %d schedule(s)", claimed_count)
    return {"claimed": claimed_count}


# ---------------------------------------------------------------------------
# run_schedule_task -- does the actual work
# ---------------------------------------------------------------------------

def _compose_message(schedule: dict) -> str:
    """Task text + any pre-answered clarifications from the schedule-creation
    wizard. The "no human available, don't wait for confirmation" framing
    lives in the system prompt rather than here."""
    message = schedule.get("message", "")
    clarifications = schedule.get("clarifications") or []
    if not clarifications:
        return message
    qa = "\n".join(f"Q: {c.get('question', '')}\nA: {c.get('answer', '')}" for c in clarifications)
    return f"{message}\n\n---\nPre-provided answers to resolve ambiguity:\n\n{qa}"


async def _call_direct_chat(schedule: dict, augmented_message: str):

    # Every scheduled run execution starts a fresh, isolated session
    return await direct_chat(
        agent_id=schedule.get("agent_id"),
        message=augmented_message,
        org_id=schedule.get("organization_id"),
        user_id=schedule.get("created_by"),
        session_id=None,
        unattended=True,
    )


async def _call_orchestration_chat(schedule: dict, augmented_message: str):

    orch_id = schedule.get("orchestration_id")
    # Every scheduled run execution starts a fresh, isolated session
    res = await run_orchestration(
        orchestration_id=orch_id,
        message=augmented_message,
        user_id=schedule.get("created_by"),
        organization_id=schedule.get("organization_id"),
        session_id=None,
        unattended=True,
    )
    orch_run_id = res.get("run_id")

    class OrchestrationRunResult:
        def __init__(self, reply: str = "", auth_errors: Optional[list] = None):
            self.reply = reply
            self.auth_errors = auth_errors or []

    if not orch_run_id:
        return OrchestrationRunResult(reply=res.get("response", "Orchestration initialized."))

    # Poll until the background orchestration run reaches a terminal state (up to 600s)
    deadline = time.time() + 600
    while time.time() < deadline:
        run_doc = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one({"run_id": orch_run_id})
        if run_doc:
            status_val = run_doc.get("status")
            if status_val in TERMINAL_STATUSES:
                if status_val in (RunStatus.FAILED.value, RunStatus.TIMEOUT.value):
                    err_ctx = run_doc.get("error_context") or {}
                    err_msg = err_ctx.get("message") or f"Orchestration run failed with status: {status_val}"
                    raise RuntimeError(err_msg)
                
                reply = run_doc.get("final_response")
                if not reply or reply == "Orchestration run completed." or reply == "The orchestration completed without a final response.":
                    path = run_doc.get("execution_path") or []
                    if path and isinstance(path, list) and path[-1].get("output"):
                        reply = path[-1]["output"]
                    else:
                        reply = "Orchestration run completed."
                return OrchestrationRunResult(reply=reply)
        await asyncio.sleep(1)

    return OrchestrationRunResult(reply="Orchestration run timed out waiting for completion.")


def _finalize_run(
    run_id: str,
    run_status: str,
    *,
    started_at: datetime,
    reply: Optional[str] = None,
    auth_errors: Optional[list] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:

    completed_at = datetime.now(timezone.utc)
    schedule_runs_sync.update_one(
        {"run_id": run_id},
        {"$set": {
            "status": run_status,
            "reply": reply,
            "auth_errors": auth_errors or [],
            "error_type": error_type,
            "error_message": error_message,
            "completed_at": completed_at,
            "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
        }},
    )


def _on_run_success(schedule: dict, lock_id: str, auth_errors: list) -> None:

    now = datetime.now(timezone.utc)
    is_once = schedule.get("cron_expr") is None
    schedules_sync.update_one(
        # Matching on lock_id (not just _id) means this is a no-op if the
        # lock was already reclaimed as stale (e.g. this run took > 10 min)
        # -- we never overwrite state a newer claim already owns.
        {"_id": schedule.get("_id"), "lock_id": lock_id},
        {
            "$set": {
                "lock_id": None,
                "locked_at": None,
                "last_run_at": now,
                "last_run_status": "success",
                "last_run_error": None,
                "consecutive_failure_count": 0,
                "needs_attention": bool(auth_errors),
                "status": "completed" if is_once else "active",
                "updated_at": now,
            },
            "$inc": {"run_count": 1},
        },
    )


def _on_run_failure(schedule: dict, lock_id: str, error_message: str) -> None:

    now = datetime.now(timezone.utc)
    is_once = schedule.get("cron_expr") is None
    new_count = schedule.get("consecutive_failure_count", 0) + 1
    max_failures = schedule.get("max_consecutive_failures", 3)

    if is_once:
        # Fires exactly once, successfully or not -- the failure is recorded
        # (last_run_status/last_run_error + the schedule_runs row), no retry
        # of its own accord.
        new_status = "completed"
    elif new_count >= max_failures:
        new_status = "paused"
    else:
        new_status = "active"

    schedules_sync.update_one(
        {"_id": schedule.get("_id"), "lock_id": lock_id},
        {
            "$set": {
                "lock_id": None,
                "locked_at": None,
                "last_run_at": now,
                "last_run_status": "failed",
                "last_run_error": error_message,
                "consecutive_failure_count": new_count,
                "status": new_status,
                "updated_at": now,
            },
            "$inc": {"run_count": 1},
        },
    )


@celery_app.task(
    name="ai.schedule.tasks.run_schedule_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def run_schedule_task(self, *, schedule_id: str, lock_id: str, claim_epoch: int) -> dict:

    schedule = schedules_sync.find_one({
        "_id": ObjectId(schedule_id), "lock_id": lock_id, "claim_epoch": claim_epoch,
    })
    if not schedule:
        # Another claim already superseded this one (stale-lock reclaim) --
        # nothing to do, this invocation is stale.
        logger.info("[schedule] stale claim, skipping -- schedule_id=%s", schedule_id)
        return {"status": "skipped", "schedule_id": schedule_id}

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    augmented_message = _compose_message(schedule)

    target_type = schedule.get("target_type") or ("orchestration" if schedule.get("orchestration_id") else "agent")

    schedule_runs_sync.insert_one({
        "run_id": run_id,
        "schedule_id": schedule_id,
        "organization_id": schedule.get("organization_id"),
        "target_type": target_type,
        "agent_id": schedule.get("agent_id"),
        "orchestration_id": schedule.get("orchestration_id"),
        "user_id": schedule.get("created_by"),
        "thread_id": schedule.get("thread_id"),
        "claim_epoch": claim_epoch,
        "status": "running",
        "attempt": self.request.retries + 1,
        "message_sent": augmented_message,
        "reply": None,
        "auth_errors": [],
        "error_type": None,
        "error_message": None,
        "started_at": started_at,
        "completed_at": None,
        "duration_ms": None,
    })

    handlers = {
        "agent": _call_direct_chat,
        "orchestration": _call_orchestration_chat,
    }
    handler = handlers.get(target_type, _call_direct_chat)

    try:
        response = _run_async(handler(schedule, augmented_message))
    except HTTPException as exc:
        _finalize_run(
            run_id, "failed", started_at=started_at,
            error_type="HTTPException", error_message=str(exc.detail),
        )
        _on_run_failure(schedule, lock_id, str(exc.detail))
        return {"status": "failed", "run_id": run_id}
    except Exception as exc:
        logger.error(
            "[schedule] run failed -- schedule_id=%s run_id=%s: %s",
            schedule_id, run_id, exc, exc_info=True,
        )
        _finalize_run(
            run_id, "failed", started_at=started_at,
            error_type=type(exc).__name__, error_message=str(exc),
        )
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _on_run_failure(schedule, lock_id, str(exc))
            return {"status": "failed", "run_id": run_id}

    _finalize_run(
        run_id, "success", started_at=started_at,
        reply=response.reply, auth_errors=response.auth_errors,
    )
    _on_run_success(schedule, lock_id, response.auth_errors)
    return {"status": "success", "run_id": run_id}
