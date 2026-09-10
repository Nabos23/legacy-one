from datetime import datetime, timezone
from typing import Annotated, List, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class KnowledgeBaseBase(BaseModel):
    """Shared fields for a Knowledge Base (an org's RAG source), stored in
    the existing `rag_sources` collection — the same collection Agent.rag_ids
    already references."""

    organization_id: str
    name: str
    description: Optional[str] = None
    created_by: str
    # Modeled with the same 4 values agents use, even though phase 1 only
    # activates "organization" — this lets user/agent-tier KBs reuse
    # build_agent_visibility_clauses-style logic unmodified later.
    owner_scope: Literal["user", "organization", "selected_users", "team"] = "organization"
    allowed_user_ids: List[str] = Field(default_factory=list)
    team_id: Optional[str] = None
    graph_expand_enabled: bool = True
    auto_created: bool = False


class KnowledgeBase(KnowledgeBaseBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KBDocumentBase(BaseModel):
    """A document filed into a Knowledge Base. Raw bytes live in GridFS;
    `description` is the short, LLM-generated summary used for fast
    document-level routing before the detailed chunk search."""

    kb_id: str
    organization_id: str
    filename: str
    doc_type: str = ""
    description: Optional[str] = None
    status: Literal["processing", "indexed", "failed"] = "processing"
    chunk_count: int = 0
    error: Optional[str] = None
    gridfs_id: Optional[str] = None
    created_by: str
    # True when this document's KB assignment came from the auto-classifier
    # rather than the admin picking a KB explicitly — surfaced in the review
    # screen so admins know which assignments to double-check.
    auto_classified: bool = False


class KBDocument(KBDocumentBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
