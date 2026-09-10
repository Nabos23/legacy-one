from datetime import datetime, timezone
from typing import Annotated, List, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class ProjectFile(BaseModel):

    id: str
    filename: str
    original_filename: str
    file_type: str = "other"  # skill, markdown, code, text, document, other
    file_size: int = 0
    content: Optional[str] = None  # Text/markdown content saved directly in MongoDB
    content_summary: Optional[str] = None
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectBase(BaseModel):

    organization_id: str
    name: str
    description: Optional[str] = None
    system_prompt: str = ""
    guardrails: Optional[str] = None
    tool_ids: List[str] = Field(default_factory=list)
    connector_ids: List[str] = Field(default_factory=list)
    knowledge_base_ids: List[str] = Field(default_factory=list)
    files: List[ProjectFile] = Field(default_factory=list)
    created_by: str
    owner_scope: Literal["user", "organization", "selected_users", "team"] = "organization"
    allowed_user_ids: List[str] = Field(default_factory=list)
    team_id: Optional[str] = None


class Project(ProjectBase):

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectChatMessage(BaseModel):

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    project_id: str
    organization_id: str
    user_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    auth_errors: List[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: bool = False
