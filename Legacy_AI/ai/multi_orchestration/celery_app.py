"""Celery application for the multi-orchestration runtime.

Start workers with:
    celery -A ai.multi_orchestration.celery_app worker --loglevel=info -Q orchestration

Start the beat scheduler (for 24/7 cron triggers):
    celery -A ai.multi_orchestration.celery_app beat --loglevel=info
"""
import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "multi_orchestration",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["ai.multi_orchestration.tasks"],
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

    # Routing: all orchestration tasks land on the "orchestration" queue.
    # Add more queues here when you introduce priority lanes or org-level isolation.
    task_routes={
        "ai.multi_orchestration.tasks.run_orchestration_task": {"queue": "orchestration"},
    },

    # Result expiry: keep task results for 24h (useful for status polling)
    result_expires=86400,
)
