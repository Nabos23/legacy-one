"""Celery tasks for the multi-orchestration runtime.

These tasks are the queue consumer side. They are called either:
  - Directly from the FastAPI executor (reactive / chat-triggered runs)
  - By Celery Beat or a webhook handler (proactive / 24-7 runs)

The heavy lifting lives in RuntimeScheduler — these tasks are thin wrappers
that handle Celery-level retry and update the run document on terminal failure.
"""
import logging
from datetime import datetime, timezone

from ai.multi_orchestration.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="ai.multi_orchestration.tasks.run_orchestration_task",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def run_orchestration_task(
    self,
    *,
    orchestration_id: str,
    message: str,
    user_id: str,
    organization_id: str,
    session_id: str,
    run_id: str,
) -> dict:
    """
    Execute a single orchestration run identified by run_id.

    The run document must already exist in orchestration_runs before this task
    is called (created by the executor). This task loads the graph, builds the
    context, and drives RuntimeScheduler to completion.

    Returns {"status": "complete"|"failed", "response": str, "run_id": str}.
    """
    from bson import ObjectId

    from backend.core.config import settings
    from backend.db.constants import ORCHESTRATION_RUNS_COLLECTION
    from backend.db.database import sync_db
    from ai.multi_orchestration.graph_loader import GraphLoader
    from ai.multi_orchestration.memory_bus import MemoryBus
    from ai.multi_orchestration.models import RunStatus
    from ai.multi_orchestration.run_context import RunContext
    from ai.multi_orchestration.scheduler import RuntimeScheduler

    logger.info("[task] start — run_id=%s orch=%s", run_id, orchestration_id)

    try:
        orch_doc = sync_db.agent_orchestrations.find_one({
            "_id": ObjectId(orchestration_id),
            "organization_id": organization_id,
            "is_deleted": {"$ne": True},
        })
        if not orch_doc:
            logger.error("[task] orchestration %s not found", orchestration_id)
            return {"status": "failed", "error": "Orchestration not found", "run_id": run_id}

        snapshot = dict(orch_doc)
        snapshot["_id"] = str(snapshot["_id"])

        run_doc = sync_db[ORCHESTRATION_RUNS_COLLECTION].find_one({"run_id": run_id})
        if not run_doc:
            logger.error("[task] run document %s not found", run_id)
            return {"status": "failed", "error": "Run document not found", "run_id": run_id}

        model = settings.DEFAULT_MODEL
        loader = GraphLoader(snapshot, sync_db, organization_id)
        graph = loader.load()

        memory_bus = MemoryBus(run_doc, sync_db, model)
        ctx = RunContext(
            run_id=run_id,
            orchestration_id=orchestration_id,
            session_id=session_id,
            org_id=organization_id,
            user_id=user_id,
            runtime_graph=graph,
            memory_bus=memory_bus,
            sync_db=sync_db,
            model=model,
        )

        scheduler = RuntimeScheduler(ctx, model)
        response = scheduler.run(message)

        logger.info("[task] complete — run_id=%s", run_id)
        return {"status": "complete", "response": response, "run_id": run_id}

    except Exception as exc:
        logger.error("[task] unexpected error — run_id=%s: %s", run_id, exc, exc_info=True)
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_failed(run_id, type(exc).__name__, str(exc), self.request.retries)
            return {"status": "failed", "error": str(exc), "run_id": run_id}


@celery_app.task(
    name="ai.multi_orchestration.tasks.run_scheduled_epoch",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def run_scheduled_epoch(self, *, instance_id: str) -> dict:
    """
    Triggered by Celery Beat for 24/7 orchestrations.
    Looks up the OrchestrationInstance, increments epoch, creates a new run document,
    and dispatches run_orchestration_task.
    """
    import uuid
    from datetime import datetime, timezone

    from backend.db.constants import ORCHESTRATION_RUNS_COLLECTION
    from backend.db.database import sync_db
    from ai.multi_orchestration.models import new_run_document

    INSTANCES_COLLECTION = "orchestration_instances"

    logger.info("[epoch] scheduled epoch start — instance_id=%s", instance_id)

    instance = sync_db[INSTANCES_COLLECTION].find_one({"instance_id": instance_id})
    if not instance or instance.get("status") != "active":
        logger.info("[epoch] instance %s not active — skipping", instance_id)
        return {"status": "skipped", "instance_id": instance_id}

    now = datetime.now(timezone.utc)
    new_epoch = instance.get("epoch_count", 0) + 1
    last_handoff = instance.get("last_handoff") or {}
    entry_message = last_handoff.get("summary", "Continue the scheduled workflow.")
    session_id = str(uuid.uuid4())  # fresh session per epoch

    run_doc = new_run_document(
        orchestration_id=instance["orchestration_id"],
        session_id=session_id,
        user_id=instance["user_id"],
        organization_id=instance["organization_id"],
        entry_message=entry_message,
        main_agent_id="",  # filled during graph load
        max_depth=10,
        timeout_sec=600,
        epoch=new_epoch,
        instance_id=instance_id,
    )
    # main_agent_id will be resolved by GraphLoader; placeholder avoids null
    sync_db[ORCHESTRATION_RUNS_COLLECTION].insert_one(run_doc)

    sync_db[INSTANCES_COLLECTION].update_one(
        {"instance_id": instance_id},
        {"$set": {"epoch_count": new_epoch, "updated_at": now}},
    )

    run_orchestration_task.apply_async(
        kwargs={
            "orchestration_id": instance["orchestration_id"],
            "message": entry_message,
            "user_id": instance["user_id"],
            "organization_id": instance["organization_id"],
            "session_id": session_id,
            "run_id": run_doc["run_id"],
        },
        queue="orchestration",
    )

    logger.info("[epoch] dispatched epoch %d — run_id=%s", new_epoch, run_doc["run_id"])
    return {"status": "dispatched", "epoch": new_epoch, "run_id": run_doc["run_id"]}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _mark_failed(run_id: str, error_type: str, message: str, retry_count: int) -> None:
    from backend.db.constants import ORCHESTRATION_RUNS_COLLECTION
    from backend.db.database import sync_db

    sync_db[ORCHESTRATION_RUNS_COLLECTION].update_one(
        {"run_id": run_id},
        {"$set": {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc),
            "error_context": {
                "agent_id": None,
                "error_type": error_type,
                "message": message,
                "retry_count": retry_count,
                "timestamp": datetime.now(timezone.utc),
            },
        }},
    )
