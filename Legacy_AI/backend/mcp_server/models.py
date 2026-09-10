from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class McpServerBase(BaseModel):
    organization_id: str
    agent_id: Optional[str] = None
    registry_key: Optional[str] = None  # mcp_server_registry entry key (Flow A)
    auth_type: str = "none"            # none | bearer | oauth
    name: Optional[str] = None         # copied from the registry entry
    user_description: Optional[str] = None

    # Connection — the single string the user provided plus the resolved transport.
    connection_string: Optional[str] = None
    transport: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

    # Discovered tools, cached so agents use them without reconnecting.
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_count: int = 0
    status: str = "pending"            # connected | error | pending
    last_error: Optional[str] = None
    discovered_at: Optional[datetime] = None

    timeout: float = 30.0
    is_active: bool = True


class McpServer(McpServerBase):
    """MCP instance document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: bool = False


class McpRegistryEntry(BaseModel):
    """A connectable MCP server definition in the `mcp_server_registry` catalog.

    This is the global catalog agents pick from (Flow A). It is *not* tied to an
    org or agent — it's a reusable template. `connection_string` may contain
    ``<PLACEHOLDER>`` tokens (listed in `requires`) the user fills in at connect
    time. Custom bring-your-own servers (Flow B) skip the catalog entirely.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    key: str                                   # unique slug, e.g. "filesystem"
    name: str
    description: str = ""
    prompt: Optional[str] = None               # agent system-prompt block for this server
    category: Optional[str] = None
    transport: Optional[str] = None            # stdio | streamable_http | sse | websocket
    connection_string: str = ""                # template; may contain <PLACEHOLDERS>
    requires: List[str] = Field(default_factory=list)
    source: str = "curated"                    # curated | registry
    homepage: Optional[str] = None
    repo_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: bool = False


class McpAgentTool(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    organization_id: str
    agent_id: str
    mcp_server_id: str
    tool_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
