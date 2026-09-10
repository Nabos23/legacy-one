from datetime import datetime, timezone
from typing import Annotated, List, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]

class AgentBase(BaseModel):
    """Shared fields used when creating or updating an agent."""

    organization_id: str
    name: str
    description: Optional[str] = None
    user_description: Optional[str] = None
    prompt: Optional[str] = None
    instructions: Optional[str] = None
    guardrails: Optional[str] = None
    tool_ids: List[str] = Field(default_factory=list)
    rag_ids: List[str] = Field(default_factory=list)
    mcp_server_ids: List[str] = Field(default_factory=list)
    connector_ids: List[str] = Field(default_factory=list)
    avatar_type: str = "color"
    avatar_value: Optional[str] = None
    avatar_url: Optional[str] = None
    created_by: str
    owner_scope: Literal["user", "organization", "selected_users", "team"] = "organization"
    allowed_user_ids: List[str] = Field(default_factory=list)
    team_id: Optional[str] = None


class Agent(AgentBase):
    """Agent document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
