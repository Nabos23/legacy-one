from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from backend.schedule.models import Clarification, RecurrenceConfig


class PreviewQuestionsRequest(BaseModel):
    target_type: Literal["agent", "orchestration"] = "agent"
    agent_id: Optional[str] = None
    orchestration_id: Optional[str] = None
    message: str


class PreviewQuestionsResponse(BaseModel):
    questions: List[str] = Field(default_factory=list)
    is_capable: bool = True
    invalid_reason: Optional[str] = None


class ScheduleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_type: Literal["agent", "orchestration"] = "agent"
    agent_id: Optional[str] = None
    orchestration_id: Optional[str] = None
    message: str
    clarifications: List[Clarification] = Field(default_factory=list)
    recurrence: RecurrenceConfig
    timezone: str = "UTC"
    max_consecutive_failures: int = Field(default=3, ge=1, le=20)

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank.")
        return v


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    message: Optional[str] = None
    clarifications: Optional[List[Clarification]] = None
    recurrence: Optional[RecurrenceConfig] = None
    timezone: Optional[str] = None
    max_consecutive_failures: Optional[int] = Field(default=None, ge=1, le=20)
    status: Optional[Literal["active", "paused"]] = None


class SchedulePublic(BaseModel):
    id: str
    organization_id: str
    created_by: str
    name: str
    description: Optional[str] = None
    target_type: str = "agent"
    agent_id: Optional[str] = None
    orchestration_id: Optional[str] = None
    message: str
    clarifications: List[Clarification] = Field(default_factory=list)
    thread_id: str
    recurrence: RecurrenceConfig
    cron_expr: Optional[str] = None
    timezone: str
    status: str
    next_run_at: datetime
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_error: Optional[str] = None
    consecutive_failure_count: int = 0
    max_consecutive_failures: int = 3
    run_count: int = 0
    needs_attention: bool = False
    created_at: datetime
    updated_at: datetime


class ScheduleRunPublic(BaseModel):
    run_id: str
    schedule_id: str
    target_type: str = "agent"
    agent_id: Optional[str] = None
    orchestration_id: Optional[str] = None
    thread_id: str
    status: str
    attempt: int
    message_sent: str
    reply: Optional[str] = None
    auth_errors: list = Field(default_factory=list)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
