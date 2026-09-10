from pymongo import ASCENDING, DESCENDING, IndexModel

from backend.db.database import schedule_runs_collection, schedules_collection


async def ensure_schedule_indexes() -> None:
    """Create the indexes schedule lookups need.

    `(status, next_run_at)` on `schedules` is the critical one -- it's the
    exact shape of the atomic claim query `tick_schedules` runs every 30s
    (see ai/schedule/tasks.py), so it must stay cheap regardless of how large
    the collection grows. `(organization_id, created_at)` backs the list
    view; `agent_id` backs the reverse lookup when an agent is deleted.

    `schedule_runs` is an append-only audit log -- `run_id` unique (the
    unpause/fencing invariant depends on there being exactly one doc per
    fired run_id), `(schedule_id, started_at desc)` backs the run-history
    view, and a 90-day TTL keeps it self-pruning like
    widget_webhook_deliveries.
    """
    await schedules_collection.create_indexes([
        IndexModel([("status", ASCENDING), ("next_run_at", ASCENDING)], name="tick_claim_idx"),
        IndexModel([("organization_id", ASCENDING), ("created_at", DESCENDING)], name="org_created_at"),
        IndexModel([("agent_id", ASCENDING)], name="agent_id_lookup"),
        IndexModel([("orchestration_id", ASCENDING)], name="orchestration_id_lookup"),
    ])
    await schedule_runs_collection.create_indexes([
        IndexModel([("run_id", ASCENDING)], unique=True, name="run_id_unique"),
        IndexModel([("schedule_id", ASCENDING), ("started_at", DESCENDING)], name="schedule_started_at"),
        IndexModel([("started_at", ASCENDING)], name="ttl_90d", expireAfterSeconds=90 * 24 * 3600),
    ])
