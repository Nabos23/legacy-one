from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    """Payload for creating a team."""

    organization_id: str
    name: str
    description: Optional[str] = None
    member_ids: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)


class TeamUpdate(BaseModel):
    """Payload for updating a team (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class TeamMembersUpdate(BaseModel):
    """Payload for adding one or more members to a team."""

    user_ids: List[str]


class TeamPermissionsUpdate(BaseModel):
    """Payload for updating a team's permissions."""

    permissions: List[str] = Field(default_factory=list)


class TeamPublic(BaseModel):
    """Team data returned to clients."""

    id: Optional[str] = None
    organization_id: str
    name: str
    description: Optional[str] = None
    member_ids: List[str] = []
    permissions: List[str] = []
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
