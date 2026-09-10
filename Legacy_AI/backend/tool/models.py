from datetime import datetime, timezone
from typing import Annotated, Any, Dict, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class ToolRegistryBase(BaseModel):
    """Shared fields used when creating or updating a tool registry entry."""

    name: str
    description: Optional[str] = None
    type: str
    is_active: bool = True
    tool_schema: Optional[Dict[str, Any]] = None  # JSON schema for the tool


class ToolRegistry(ToolRegistryBase):
    """Tool registry document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatSessionBase(BaseModel):
    """Shared fields used when creating a chat session."""

    user_id: str
    agent_id: str


class ChatSession(ChatSessionBase):
    """Chat session document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageBase(BaseModel):
    """Shared fields used when creating a message."""

    session_id: str
    role: str
    content: str


class Message(MessageBase):
    """Message document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RagSourceBase(BaseModel):
    """Shared fields used when creating or updating a RAG source."""

    organization_id: str
    name: str
    vector_collection: str


class RagSource(RagSourceBase):
    """RAG source document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolBase(BaseModel):
    """Shared fields used when creating or updating a tool."""

    organization_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    user_description: Optional[str] = None
    db_conn_id: Optional[str] = None
    tool_id: str
    encrypted_api_key: Optional[str] = None
    custom_base_url: Optional[str] = None
    custom_model: Optional[str] = None


class Tool(ToolBase):
    """Tool document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DbConnectionBase(BaseModel):
    """Shared fields used when creating or updating a database connection."""

    organization_id: str
    tool_id: str
    connection_string: str
    # JSON schema of the connected database; aliased because `schema` shadows
    # a reserved BaseModel attribute.
    db_schema: Optional[Dict[str, Any]] = Field(default=None, alias="schema")


class DbConnection(DbConnectionBase):
    """Database connection document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
