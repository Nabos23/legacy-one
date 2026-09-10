from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    organization_id: str
    name: str
    description: Optional[str] = None
    owner_scope: Literal["user", "organization", "selected_users", "team"] = "organization"
    allowed_user_ids: List[str] = Field(default_factory=list)
    team_id: Optional[str] = None
    graph_expand_enabled: bool = True


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner_scope: Optional[Literal["user", "organization", "selected_users", "team"]] = None
    allowed_user_ids: Optional[List[str]] = None
    team_id: Optional[str] = None
    graph_expand_enabled: Optional[bool] = None


class KnowledgeBasePublic(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    created_by: str
    owner_scope: str
    allowed_user_ids: List[str] = Field(default_factory=list)
    team_id: Optional[str] = None
    graph_expand_enabled: bool
    auto_created: bool
    document_count: int = 0
    created_at: datetime


class KBDocumentPublic(BaseModel):
    id: str
    kb_id: str
    organization_id: str
    filename: str
    doc_type: str
    description: Optional[str] = None
    status: str
    chunk_count: int
    error: Optional[str] = None
    auto_classified: bool
    created_by: str
    created_at: datetime


class ReassignDocumentRequest(BaseModel):
    kb_id: str
