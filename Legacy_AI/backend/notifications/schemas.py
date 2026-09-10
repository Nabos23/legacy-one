from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel



class NotificationPublic(BaseModel):
    """A notification as returned to clients."""

    id: Optional[str] = None
    organization_id: str
    # None means the notification is org-wide (visible to every member).
    user_id: Optional[str] = None
    type: str
    title: str
    message: str
    read: bool = False
    created_at: datetime


class UnreadCountResponse(BaseModel):
    unread: int
