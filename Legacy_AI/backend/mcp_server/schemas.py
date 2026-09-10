from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, model_validator


class McpToolSpec(BaseModel):
    """A single tool discovered from an MCP server, as cached in the DB."""

    name: str
    description: str = ""
    input_schema: Optional[Dict[str, Any]] = None


class McpServerCreate(BaseModel):
    organization_id: str
    agent_id: Optional[str] = None
    registry_key: Optional[str] = None       # mcp_server_registry entry (Flow A)
    connection_string: Optional[str] = None  # raw string (Flow B)
    placeholders: Optional[Dict[str, str]] = None  # fills <PLACEHOLDER> tokens (Flow A)
    name: Optional[str] = None          # display name; defaults to registry name / "Custom MCP"
    user_description: Optional[str] = None
    token: Optional[str] = None        # bearer token for remote servers
    headers: Optional[Dict[str, str]] = None
    timeout: float = 30.0

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "McpServerCreate":
        if bool(self.registry_key) == bool(self.connection_string):
            raise ValueError(
                "Provide exactly one of 'registry_key' (catalog) or "
                "'connection_string' (custom)."
            )
        return self


class McpServerUpdate(BaseModel):
    """Payload for updating an MCP instance (all fields optional)."""

    name: Optional[str] = None
    user_description: Optional[str] = None
    connection_string: Optional[str] = None
    token: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None
    is_active: Optional[bool] = None


class McpServerPublic(BaseModel):
    """MCP instance returned to clients."""

    id: Optional[str] = None
    organization_id: str
    agent_id: Optional[str] = None
    registry_key: Optional[str] = None   # set for catalog-sourced servers (Flow A)
    auth_type: str = "none"              # none | bearer | oauth
    name: Optional[str] = None
    user_description: Optional[str] = None

    connection_string: Optional[str] = None
    transport: Optional[str] = None

    # Discovery results.
    tools: List[McpToolSpec] = []
    tool_count: int = 0
    status: str = "pending"            # connected | error | pending
    last_error: Optional[str] = None
    discovered_at: Optional[datetime] = None

    timeout: float = 30.0
    is_active: bool = True
    created_at: datetime


class McpTestConnectionRequest(BaseModel):
    """Probe a connection string without saving it."""

    connection_string: str
    token: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: float = 30.0


class McpTestConnectionResult(BaseModel):
    """Result of a probe — what tools the server exposes (or why it failed)."""

    ok: bool
    transport: Optional[str] = None
    tools: List[McpToolSpec] = []
    tool_count: int = 0
    error: Optional[str] = None


class McpOAuthStartRequest(BaseModel):
    """Begin an interactive OAuth authorization for a remote MCP server."""

    organization_id: str
    agent_id: Optional[str] = None
    connection_string: str                 # the remote MCP URL (http/https)
    name: Optional[str] = None              # display name; defaults to the server's hostname
    user_description: Optional[str] = None
    scope: Optional[str] = None            # override discovered scopes if needed


class McpOAuthStartResponse(BaseModel):
    """The URL the user must open to consent, plus the opaque flow state."""

    authorization_url: str
    state: str


class McpCatalogEntry(BaseModel):
    """A browsable server from the `mcp_server_registry` catalog."""

    key: str
    name: str
    description: str = ""
    category: Optional[str] = None
    transport: Optional[str] = None
    connection_string: str = ""
    requires: List[str] = []
    source: str = "curated"
    homepage: Optional[str] = None


class McpAgentToolAttachRequest(BaseModel):
    tool_names: List[str]


class McpAgentToolPublic(BaseModel):
    id: Optional[str] = None
    organization_id: str
    agent_id: str
    mcp_server_id: str
    mcp_server_name: Optional[str] = None
    tool_name: str
    created_at: datetime
