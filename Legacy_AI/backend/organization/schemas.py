from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    """Payload for creating an organization."""

    name: str
    description: Optional[str] = None


class OrganizationUpdate(BaseModel):
    """Payload for updating an organization (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None


class OrganizationPublic(BaseModel):
    """Organization data returned to clients."""

    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
