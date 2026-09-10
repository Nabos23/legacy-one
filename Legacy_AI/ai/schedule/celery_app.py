import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "schedule",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["ai.schedule.tasks"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Time
    timezone="UTC",
    enable_utc=True,

    # Reliability
    task_track_started=True,
    task_acks_late=True,           # Don't ack until the task completes (at-least-once delivery)
    worker_prefetch_multiplier=1,  # One task per worker slot — avoids head-of-line blocking

    # Routing: everything lands on the "schedules" queue.
    task_routes={
        "ai.schedule.tasks.tick_schedules": {"queue": "schedules"},
        "ai.schedule.tasks.run_schedule_task": {"queue": "schedules"},
    },

    # A single static periodic tick -- no per-schedule dynamic beat entries
    # (that would need RedBeat or a custom Scheduler class). tick_schedules
    # queries Mongo for whatever is actually due each time it fires.
    beat_schedule={
        "schedule-tick": {
            "task": "ai.schedule.tasks.tick_schedules",
            "schedule": 30.0,
        },
    },

    # Result expiry: keep task results for 24h (useful for debugging).
    result_expires=86400,
)
