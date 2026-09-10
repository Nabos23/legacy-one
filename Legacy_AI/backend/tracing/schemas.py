from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class ObservationItem(BaseModel):
    id: str
    trace_id: Optional[str] = None
    type: str
    name: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    metadata: Optional[dict] = None
    parent_observation_id: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[dict] = None
    calculated_total_cost: Optional[float] = None
    latency: Optional[float] = None


class TraceListItem(BaseModel):
    id: str
    timestamp: datetime
    name: str
    input: Optional[Any] = None
    output: Optional[Any] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[dict] = None
    tags: List[str] = []
    latency: Optional[float] = None
    total_cost: Optional[float] = None
    agent_name: Optional[str] = None


class TraceDetail(TraceListItem):
    observations: List[ObservationItem] = []


class TracesResponse(BaseModel):
    items: List[TraceListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class AgentBreakdown(BaseModel):
    agent_name: str
    trace_count: int
    total_cost: float
    total_tokens: int


class UserBreakdown(BaseModel):
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    trace_count: int
    total_cost: float
    total_tokens: int


class TraceStats(BaseModel):
    total_traces: int
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    agent_breakdown: List[AgentBreakdown]
    user_breakdown: List[UserBreakdown] = []


class SessionItem(BaseModel):
    id: str
    created_at: Optional[datetime] = None
    user_id: Optional[str] = None
    trace_count: int = 0
    bookmarked: bool = False


class SessionsResponse(BaseModel):
    items: List[SessionItem]
    total: int
    page: int
    page_size: int
    total_pages: int
