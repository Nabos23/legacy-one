from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class AgentSummary(BaseModel):
    agent_id: str
    name: str
    description: Optional[str] = None
    tool_count: int = 0


class SessionPublic(BaseModel):
    thread_id: str
    organization_id: str
    name: Optional[str] = None
    available_agents: List[AgentSummary]
    created_at: datetime


class ChatAttachment(BaseModel):
    """Processed attachment returned by POST /chat/attachments.

    For documents: kind="document", text is populated.
    For images:    kind="image", data_url and optionally ocr_text are populated.
    """
    kind: Literal["document", "image"]
    filename: str = ""
    # document fields
    text: Optional[str] = None
    truncated: bool = False
    # image fields
    mime: Optional[str] = None
    data_url: Optional[str] = None
    ocr_text: Optional[str] = None


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    organization_id: Optional[str] = None
    attachments: Optional[List[ChatAttachment]] = None


class ChatResponse(BaseModel):
    thread_id: str
    response: str
    messages_count: int
    name: Optional[str] = None
    # Connector tool calls that failed on auth this turn — each entry:
    # {"fn_name", "connector_id", "provider_id", "display_name"}.
    auth_errors: List[Dict[str, Optional[str]]] = Field(default_factory=list)
    # Knowledge-base document descriptions surfaced by search_knowledge_base
    # calls this turn, shown as citations under the reply.
    sources: List[str] = Field(default_factory=list)


class SessionRenameRequest(BaseModel):
    name: str


# --- Session listing ---

class SessionListItem(BaseModel):
    thread_id: str
    organization_id: str
    user_id: str
    name: Optional[str] = None
    epoch: int
    agent_ids: List[str]
    created_at: Optional[datetime] = None


# --- Session history ---

class TurnPublic(BaseModel):
    type: Literal["turn"]
    human_message: str
    agent_message: str
    timestamp: datetime
    tool_called: bool = False
    tool_name: Optional[str] = None
    auth_errors: List[Dict[str, Optional[str]]] = Field(default_factory=list)


class SummaryPublic(BaseModel):
    type: Literal["summary"]
    content: str
    timestamp: datetime


ConversationEntryPublic = Union[TurnPublic, SummaryPublic]


class AgentHistoryPublic(BaseModel):
    agent_id: str
    total_messages: int
    total_summaries: int
    conversations: List[ConversationEntryPublic]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SessionHistoryResponse(BaseModel):
    thread_id: str
    organization_id: str
    user_id: str
    name: Optional[str] = None
    epoch: int
    agents: List[AgentHistoryPublic]
    created_at: Optional[datetime] = None
