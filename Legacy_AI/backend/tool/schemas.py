from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ImageGenerationCredentials(BaseModel):
    """User-supplied custom model credentials for this tool instance."""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class ToolCreate(BaseModel):
    """Payload for creating a tool."""

    organization_id: str
    agent_id: str
    user_description: str
    tool_id: str
    name: Optional[str] = None
    db_conn_id: Optional[str] = None
    credentials: Optional[ImageGenerationCredentials] = None


class ToolUpdate(BaseModel):
    """Payload for updating a tool (all fields optional)."""

    name: Optional[str] = None
    user_description: Optional[str] = None
    tool_id: Optional[str] = None
    db_conn_id: Optional[str] = None
    credentials: Optional[ImageGenerationCredentials] = None


class ToolPublic(BaseModel):
    """Tool data returned to clients."""

    id: Optional[str] = None
    organization_id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_avatar_type: Optional[str] = None
    agent_avatar_value: Optional[str] = None
    agent_avatar_url: Optional[str] = None
    name: Optional[str] = None
    user_description: Optional[str] = None
    tool_id: str
    db_conn_id: Optional[str] = None
    has_custom_credentials: bool = False
    created_at: datetime
