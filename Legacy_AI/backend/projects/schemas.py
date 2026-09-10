from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

class ProjectFilePublic(BaseModel):

    id: str
    filename: str
    original_filename: str
    file_type: str = "other"  # skill, markdown, code, text, document, other
    file_size: int = 0
    content: Optional[str] = None
    content_summary: Optional[str] = None
    uploaded_by: str
    uploaded_at: datetime


class ProjectCreate(BaseModel):

    organization_id: str
    name: str
    description: Optional[str] = None
    system_prompt: str = ""
    guardrails: Optional[str] = ""
    tool_ids: Optional[List[str]] = None
    connector_ids: Optional[List[str]] = None
    connector_permissions: Optional[Dict[str, Dict[str, bool]]] = None
    knowledge_base_ids: Optional[List[str]] = None
    owner_scope: Optional[Literal["user", "organization", "selected_users", "team"]] = None
    allowed_user_ids: Optional[List[str]] = None
    team_id: Optional[str] = None


class ProjectUpdate(BaseModel):

    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    guardrails: Optional[str] = None
    tool_ids: Optional[List[str]] = None
    connector_ids: Optional[List[str]] = None
    connector_permissions: Optional[Dict[str, Dict[str, bool]]] = None
    knowledge_base_ids: Optional[List[str]] = None
    owner_scope: Optional[Literal["user", "organization", "selected_users", "team"]] = None
    allowed_user_ids: Optional[List[str]] = None
    team_id: Optional[str] = None


class ProjectPublic(BaseModel):

    id: Optional[str] = None
    organization_id: str
    name: str
    description: Optional[str] = None
    system_prompt: str = ""
    guardrails: Optional[str] = ""
    tool_ids: List[str] = Field(default_factory=list)
    connector_ids: List[str] = Field(default_factory=list)
    connectors: List[Dict[str, Any]] = Field(default_factory=list)
    connector_permissions: Optional[Dict[str, Dict[str, bool]]] = None
    knowledge_base_ids: List[str] = Field(default_factory=list)
    files: List[ProjectFilePublic] = Field(default_factory=list)
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    owner_scope: Literal["user", "organization", "selected_users", "team"] = "organization"
    allowed_user_ids: List[str] = Field(default_factory=list)
    team_id: Optional[str] = None


class ProjectChatMessagePublic(BaseModel):

    id: str
    project_id: str
    organization_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    auth_errors: List[Dict[str, Any]] = Field(default_factory=list)
    user_id: Optional[str] = None
    created_at: datetime


class ProjectChatRequest(BaseModel):

    message: str
    session_id: Optional[str] = None


class ProjectChatResponse(BaseModel):

    reply: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    auth_errors: List[Dict[str, Any]] = Field(default_factory=list)
