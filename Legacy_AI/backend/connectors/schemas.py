from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class OAuthConfig(BaseModel):
    auth_url: str
    token_url: str
    scopes: list[str]
    requires_credentials: bool
    requires_signing_secret: bool = False


class SetupGuide(BaseModel):
    docs_url: str
    steps: list[str]


class ConnectorRegistryItem(BaseModel):
    id: str
    provider_id: str
    name: str
    category: str
    description: str
    icon: str
    owner_scope: Literal["user", "organization"]
    auth_type: Literal["oauth2", "bot_token", "api_key", "basic"]
    oauth: Optional[OAuthConfig] = None
    setup_guide: Optional[SetupGuide] = None
    available_actions: list[str]
    permissions: Optional[dict[str, list[str]]] = None
    prompt: Optional[str] = None
    is_active: bool
    is_visible: bool = True


class ConnectorRegistryPage(BaseModel):
    items: list[ConnectorRegistryItem]
    total: int
    page: int
    page_size: int
    pages: int


class ConnectorVisibilityUpdate(BaseModel):
    is_visible: bool


class ConnectorActiveUpdate(BaseModel):
    is_active: bool


class ConnectorCredentialsSave(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    signing_secret: Optional[str] = None
    bot_token: Optional[str] = None
    api_key: Optional[str] = None
    subdomain: Optional[str] = None


class ConnectorSetupInfo(BaseModel):
    has_credentials: bool
    client_id: Optional[str] = None
    redirect_uri: str
    provider_id: str
    auth_type: str


class ConnectorStatus(BaseModel):
    connected: bool
    connection_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    connected_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: Optional[int] = None


class ConnectorStatusBatchRequest(BaseModel):
    connector_ids: list[str] = Field(default_factory=list, max_length=200)


class ConnectorStatusEntry(ConnectorStatus):
    check_failed: bool = False


class ConnectorStatusBatchResponse(BaseModel):
    statuses: dict[str, ConnectorStatusEntry] = Field(default_factory=dict)


class AuthUrlResponse(BaseModel):
    url: str
    already_connected: bool = False


class MessageResponse(BaseModel):
    message: str


class ConnectorTestConnectionResult(BaseModel):
    ok: bool
    error: Optional[str] = None
