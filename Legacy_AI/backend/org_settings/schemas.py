from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrgSettingsUpdate(BaseModel):
    """Partial update payload — only provided fields are changed."""

    maintenance_mode: Optional[bool] = None
    require_2fa: Optional[bool] = None
    session_timeout_enabled: Optional[bool] = None
    session_duration: Optional[str] = None
    audit_logging: Optional[bool] = None
    default_model: Optional[str] = None


class OrgSettingsPublic(BaseModel):
    """Organization settings returned to clients (defaults applied)."""

    organization_id: str
    maintenance_mode: bool = False
    require_2fa: bool = False
    session_timeout_enabled: bool = True
    session_duration: str = "30m"
    audit_logging: bool = True
    default_model: str = "gpt-4o"
    updated_at: Optional[datetime] = None
