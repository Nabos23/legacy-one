from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

AvatarType = Literal["color", "emoji", "sticker", "image", "brand"]


class AgentCreate(BaseModel):
    """Payload for creating an agent."""

    organization_id: str
    name: str
    prompt: str = ""
    guardrails: str = ""
    description: Optional[str] = None
    user_description: Optional[str] = None
    tool_ids: Optional[List[str]] = None
    rag_ids: Optional[List[str]] = None
    mcp_server_ids: Optional[List[str]] = None
    connector_ids: Optional[List[str]] = None
    connector_permissions: Optional[Dict[str, Dict[str, bool]]] = None
    avatar_type: Optional[AvatarType] = None
    avatar_value: Optional[str] = None
    owner_scope: Optional[Literal["user", "organization", "selected_users", "team"]] = None
    allowed_user_ids: Optional[List[str]] = None
    team_id: Optional[str] = None


class AgentUpdate(BaseModel):
    """Payload for updating an agent (all fields optional)."""

    name: Optional[str] = None
    prompt: Optional[str] = None
    guardrails: Optional[str] = None
    description: Optional[str] = None
    user_description: Optional[str] = None
    tool_ids: Optional[List[str]] = None
    rag_ids: Optional[List[str]] = None
    mcp_server_ids: Optional[List[str]] = None
    connector_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None
    avatar_type: Optional[AvatarType] = None
    avatar_value: Optional[str] = None
    owner_scope: Optional[Literal["user", "organization", "selected_users", "team"]] = None
    allowed_user_ids: Optional[List[str]] = None
    team_id: Optional[str] = None


class AgentPublic(BaseModel):
    """Agent data returned to clients."""

    id: Optional[str] = None
    organization_id: str
    name: str
    prompt: str = ""
    guardrails: str = ""
    description: Optional[str] = None
    user_description: Optional[str] = None
    instructions: Optional[str] = None
    tool_ids: List[str] = []
    rag_ids: List[str] = []
    mcp_server_ids: List[str] = []
    connector_ids: List[str] = []
    connectors: List[Dict[str, Any]] = []
    is_active: bool = True
    tool_prompt: Optional[str] = None
    mcp_prompt: Optional[str] = None
    connector_prompt: Optional[str] = None
    avatar_type: AvatarType = "color"
    avatar_value: Optional[str] = None
    avatar_url: Optional[str] = None
    created_by: str
    created_at: datetime
    owner_scope: Literal["user", "organization", "selected_users", "team"] = "organization"
    allowed_user_ids: List[str] = []
    team_id: Optional[str] = None


class AgentPermissionsDoc(BaseModel):
    id: Optional[str] = None
    agent_id: str
    organization_id: str
    permissions: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class ConnectorPermissions(BaseModel):
    write: Optional[bool] = None
    read: Optional[bool] = None
    delete: Optional[bool] = None
    payment: Optional[bool] = None

class AgentPermissionsPatch(BaseModel):
    connectors: Optional[Dict[str, ConnectorPermissions]] = None