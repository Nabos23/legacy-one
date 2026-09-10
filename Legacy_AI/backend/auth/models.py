from datetime import datetime, timezone
from typing import Annotated, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

PyObjectId = Annotated[str, BeforeValidator(str)]

_MODEL_CONFIG = ConfigDict(
    populate_by_name=True,
    arbitrary_types_allowed=True,
    json_encoders={ObjectId: str},
)


class UserBase(BaseModel):
    """Shared fields used when creating or updating a user."""

    organization_id: str
    name: str
    email: EmailStr
    role: str
    password: str
    avatar_url: Optional[str] = None
    oauth_identities: Optional[dict[str, str]] = None
    waiting_approval: str = "approved"


class User(UserBase):
    """User document as stored in MongoDB."""

    model_config = _MODEL_CONFIG

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PermissionBase(BaseModel):
    """Shared fields for a permission definition."""

    name: str        # unique slug, e.g. "create_agent"
    label: str       # human-readable, e.g. "Create Agent"
    description: str
    resource: str    # grouping: "system" | "org" | "user" | "agent" | "tool" | "db_connection"


class PermissionModel(PermissionBase):
    """Permission document as stored in the `permissions` collection."""

    model_config = _MODEL_CONFIG

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RolePermissionBase(BaseModel):
    """Shared fields for a role-to-permissions mapping."""

    role: str                    # unique role slug, e.g. "org_admin"
    label: str                   # human-readable, e.g. "Org Admin"
    description: str
    permission_names: list[str]  # list of PermissionModel.name values assigned to this role


class RolePermission(RolePermissionBase):
    """RolePermission document as stored in the `role_permissions` collection."""

    model_config = _MODEL_CONFIG

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))