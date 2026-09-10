from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class FirebaseConnectionConfig(BaseModel):
    """Structured Firestore credentials accepted by the API.

    The service account is converted into the internal encrypted
    ``firebase://firestore`` connection string before storage.
    """

    service_account: dict
    database_id: str = "(default)"


class DbConnectionCreate(BaseModel):
    """Payload for creating a database connection.

    The database schema is fetched automatically from the connection — it is not
    supplied by the client.

    Pass ``table_descriptions`` (from the preview endpoint) to persist
    LLM-generated descriptions in the same request, so no separate
    /descriptions call is needed.
    """

    organization_id: str
    name: Optional[str] = None
    connection_type: Optional[str] = None
    connection_string: Optional[str] = None
    firebase: Optional[FirebaseConnectionConfig] = None
    table_descriptions: Optional[dict[str, str]] = None

    @model_validator(mode="after")
    def require_one_connection_target(self):
        if bool(self.connection_string) == bool(self.firebase):
            raise ValueError("Provide exactly one of connection_string or firebase.")
        return self


class DbConnectionUpdate(BaseModel):
    """Payload for updating a database connection (all fields optional).

    If `connection_string` changes, the schema is re-fetched automatically.
    """

    name: Optional[str] = None
    connection_type: Optional[str] = None
    connection_string: Optional[str] = None
    firebase: Optional[FirebaseConnectionConfig] = None

    @model_validator(mode="after")
    def reject_multiple_connection_targets(self):
        if self.connection_string and self.firebase:
            raise ValueError("Provide only one of connection_string or firebase.")
        return self


class DbConnectionPublic(BaseModel):
    """Database connection returned to clients.

    `connection_string` is masked, and the fetched `schema` is intentionally NOT
    included here — read it via GET /db-connections/{id}/schema.
    """

    id: Optional[str] = None
    organization_id: str
    name: Optional[str] = None
    connection_type: Optional[str] = None
    connection_string: str
    created_at: datetime


class DbConnectionPreviewRequest(BaseModel):
    """Payload for the preview endpoint — fetches schema and generates LLM
    descriptions without persisting anything."""

    organization_id: str
    name: Optional[str] = None
    connection_string: Optional[str] = None
    connection_type: Optional[str] = None
    firebase: Optional[FirebaseConnectionConfig] = None

    @model_validator(mode="after")
    def require_one_connection_target(self):
        if bool(self.connection_string) == bool(self.firebase):
            raise ValueError("Provide exactly one of connection_string or firebase.")
        return self


class SaveDescriptionsRequest(BaseModel):
    """Payload for saving LLM-generated descriptions into a stored connection's schema.

    Keys are table names (SQL) or ``db.collection`` names (MongoDB).
    Unknown keys are silently ignored.
    """

    table_descriptions: dict[str, str]


class DbConnectionQueryRequest(BaseModel):
    """Read-only query payload for testing a saved DB connection."""

    query: str

class DbConnectionFormatRequest(BaseModel):
    connection_string: str
    connection_type: Optional[str] = None
    name: Optional[str] = None

class DbConnectionFormatResponse(BaseModel):
    connection_string: str
    connection_type: Optional[str] = None
    name: Optional[str] = None

