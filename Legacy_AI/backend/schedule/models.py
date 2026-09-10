from datetime import datetime, timezone
from typing import Annotated, List, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class Clarification(BaseModel):
    question: str
    answer: str


class RecurrenceConfig(BaseModel):
    kind: Literal["once", "daily", "weekly", "monthly", "always", "custom"]
    time_of_day: Optional[str] = None          # "HH:MM", local to `timezone` -- daily/weekly/monthly
    day_of_week: List[int] = Field(default_factory=list)   # ISO 1=Mon..7=Sun -- weekly
    day_of_month: Optional[int] = None         # 1-31, or -1 for "last day" -- monthly
    interval_minutes: Optional[int] = None     # "always" -- minimum enforced in recurrence.py
    custom_cron: Optional[str] = None          # "custom"
    run_at: Optional[datetime] = None          # "once"


class ScheduleBase(BaseModel):
    organization_id: str
    created_by: str
    name: str
    description: Optional[str] = None
    target_type: Literal["agent", "orchestration"] = "agent"
    agent_id: Optional[str] = None
    orchestration_id: Optional[str] = None
    message: str
    clarifications: List[Clarification] = Field(default_factory=list)
    recurrence: RecurrenceConfig
    timezone: str = "UTC"
    max_consecutive_failures: int = 3


class Schedule(ScheduleBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    thread_id: str
    cron_expr: Optional[str] = None
    status: Literal["active", "paused", "running", "completed", "terminated"] = "active"
    next_run_at: datetime
    lock_id: Optional[str] = None
    locked_at: Optional[datetime] = None
    claim_epoch: int = 0
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[Literal["success", "failed"]] = None
    last_run_error: Optional[str] = None
    consecutive_failure_count: int = 0
    run_count: int = 0
    needs_attention: bool = False
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = None


class ScheduleRun(BaseModel):
    model_config = ConfigDict(json_encoders={ObjectId: str})

    run_id: str
    schedule_id: str
    organization_id: str
    target_type: Literal["agent", "orchestration"] = "agent"
    agent_id: Optional[str] = None
    orchestration_id: Optional[str] = None
    user_id: str
    thread_id: str
    claim_epoch: int
    status: Literal["running", "success", "failed"] = "running"
    attempt: int = 1
    message_sent: str
    reply: Optional[str] = None
    auth_errors: list = Field(default_factory=list)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
