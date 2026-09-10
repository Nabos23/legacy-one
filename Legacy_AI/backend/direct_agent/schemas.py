from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DirectChatRequest(BaseModel):
    agent_id: str
    message: str
    session_id: Optional[str] = None


class DirectChatResponse(BaseModel):
    reply: str
    session_id: str
    name: Optional[str] = None
    trace_id: Optional[str] = None
    ended: bool = False
    # Connector tool calls that failed on auth this turn — each entry:
    # {"fn_name", "connector_id", "provider_id", "display_name"}.
    auth_errors: List[Dict[str, Optional[str]]] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
