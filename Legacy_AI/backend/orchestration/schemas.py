from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.chat.schemas import ChatAttachment


class AgentConnectionIn(BaseModel):
    from_agent_id: str
    to_agent_id: str
    label: Optional[str] = None


class AgentConnectionOut(BaseModel):
    from_agent_id: str
    to_agent_id: str
    label: Optional[str] = None


OrchestrationMode = Literal["sequential", "supervisor"]


class SupervisorConfig(BaseModel):
    """Tuning for supervisor mode. The Supervisor itself is hardcoded — these are
    the only knobs an operator has."""

    # Max agent invocations in one turn. Both limits fail the run with a clear
    # message rather than looping.
    max_hops: int = Field(default=6, ge=1, le=50)
    max_visits_per_agent: int = Field(default=3, ge=1, le=10)
    # How many agents may decline in a row before the turn gives up.
    max_consecutive_handbacks: int = Field(default=2, ge=1, le=10)
    # Try the previous turn's agent first, so an on-topic follow-up costs no
    # routing call. It hands back when the request is outside its domain.
    sticky_routing: bool = True
    # False = routing only: the Supervisor may not answer questions itself, it
    # must either route or say no connected agent covers the request.
    allow_direct_answer: bool = True
    custom_instructions: str = ""
    model: Optional[str] = None  # None → settings.DEFAULT_MODEL


class OrchestrationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    mode: OrchestrationMode = "sequential"
    # Required in sequential mode, ignored in supervisor mode (where the
    # hardcoded Supervisor is the entry point). Enforced in services.
    main_agent_id: Optional[str] = None
    sub_agent_ids: List[str] = Field(default_factory=list)
    connections: List[AgentConnectionIn] = Field(default_factory=list)
    supervisor_config: Optional[SupervisorConfig] = None
    max_depth: int = Field(default=5, ge=1, le=20)
    timeout_sec: int = Field(default=600, ge=10, le=3600)
    owner_scope: Optional[Literal["user", "organization", "selected_users", "team"]] = None
    allowed_user_ids: Optional[List[str]] = None
    team_id: Optional[str] = None


class OrchestrationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mode: Optional[OrchestrationMode] = None
    main_agent_id: Optional[str] = None
    sub_agent_ids: Optional[List[str]] = None
    connections: Optional[List[AgentConnectionIn]] = None
    supervisor_config: Optional[SupervisorConfig] = None
    max_depth: Optional[int] = Field(default=None, ge=1, le=20)
    timeout_sec: Optional[int] = Field(default=None, ge=10, le=3600)
    owner_scope: Optional[Literal["user", "organization", "selected_users", "team"]] = None
    allowed_user_ids: Optional[List[str]] = None
    team_id: Optional[str] = None


class AgentBriefPublic(BaseModel):
    agent_id: str
    name: str
    description: Optional[str] = None


class OrchestrationPublic(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    mode: OrchestrationMode = "sequential"
    main_agent_id: Optional[str] = None
    sub_agent_ids: List[str]
    connections: List[AgentConnectionOut]
    supervisor_config: Optional[SupervisorConfig] = None
    max_depth: int
    timeout_sec: int
    agents: List[AgentBriefPublic] = Field(default_factory=list)
    created_by: str
    created_at: datetime
    owner_scope: Literal["user", "organization", "selected_users", "team"] = "organization"
    allowed_user_ids: List[str] = Field(default_factory=list)
    team_id: Optional[str] = None


class OrchestrationChatRequest(BaseModel):
    message: str = ""
    session_id: Optional[str] = None
    attachments: Optional[List[ChatAttachment]] = None


class OrchestrationChatResponse(BaseModel):
    response: str
    orchestration_id: str
    session_id: str
    name: Optional[str] = None
    status: str = "complete"
    run_id: Optional[str] = None
    human_question: Optional[str] = None
    branch_id: Optional[str] = None
    pending_reauth: Optional[Dict[str, str]] = None


class OrchestrationInitResponse(BaseModel):
    session_id: str
    orchestration_id: str
    status: str  # "ready"
    main_agent_id: Optional[str] = None
    main_agent_name: Optional[str] = None



class OrchestrationResumeRequest(BaseModel):
    # Optional: a reauth resume has no question to answer, just "retry now".
    answer: str = ""
    branch_id: Optional[str] = None


class AgentStepPublic(BaseModel):
    agent_id: str
    agent_name: str
    status: str  # "complete" | "running"  ("handback" steps are filtered out)
    output: Optional[str] = None  # the agent's produced output (present when complete)
    branch_id: Optional[str] = None

class BranchStatusPublic(BaseModel):
    branch_id: str
    status: str
    human_question: Optional[str] = None
    human_asked_by_agent: Optional[str] = None
    pending_reauth: Optional[Dict[str, str]] = None
    pending_agents: List[str] = Field(default_factory=list)
    label: Optional[str] = None

class OrchestrationRunStatus(BaseModel):
    run_id: str
    orchestration_id: str
    status: str
    current_agent_id: Optional[str] = None
    current_agent_name: Optional[str] = None
    steps: List[AgentStepPublic] = Field(default_factory=list)
    human_question: Optional[str] = None
    pending_reauth: Optional[Dict[str, str]] = None
    final_response: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    branches: List[BranchStatusPublic] = Field(default_factory=list)

#Schemas for session history retrieval
class OrchestrationConversationEntry(BaseModel):
    type: str  # "user_input" | "node"
    user_input: Optional[str] = None
    node_name: Optional[str] = None
    node_num: int = 0
    tools_called: List[str] = Field(default_factory=list)
    node_output: Optional[str] = None
    timestamp: Optional[datetime] = None
    branch_id: Optional[str] = None


#response Schema for session history
class OrchestrationSessionHistoryResponse(BaseModel):
    session_id: str
    orchestration_id: str
    organization_id: str
    user_id: str
    total_messages: int
    conversations: List[OrchestrationConversationEntry]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pending_run_id: Optional[str] = None
    pending_branches: List[BranchStatusPublic] = Field(default_factory=list)

class OrchestrationSessionBrief(BaseModel):
    session_id: str
    name: Optional[str] = None
    last_message: Optional[str] = None
    total_messages: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrchestrationSessionListResponse(BaseModel):
    orchestration_id: str
    sessions: List[OrchestrationSessionBrief] = Field(default_factory=list)
