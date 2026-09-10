from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ToolRegistryCreate(BaseModel):
    """Payload for creating a tool registry entry."""

    name: str
    type: str
    description: Optional[str] = None
    is_active: bool = True
    tool_schema: Optional[Dict[str, Any]] = None


class ToolRegistryUpdate(BaseModel):
    """Payload for updating a tool registry entry (all fields optional)."""

    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    tool_schema: Optional[Dict[str, Any]] = None


class ToolRegistryPublic(BaseModel):
    """Tool registry data returned to clients."""

    id: Optional[str] = None
    name: str
    type: str
    description: Optional[str] = None
    is_active: bool = True
    tool_schema: Optional[Dict[str, Any]] = None
    created_at: datetime
