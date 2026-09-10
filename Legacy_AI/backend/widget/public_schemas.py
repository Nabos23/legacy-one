from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.chat.schemas import ChatAttachment
from backend.widget.schemas import (
    LeadFieldPublic,
    WidgetAccessibilityPublic,
    WidgetAvailabilityPublic,
    WidgetBrandingPublic,
    WidgetLayoutPublic,
    WidgetTriggersPublic,
)


class WidgetBehaviorPublicSlim(BaseModel):
    """`tone_instructions` is deliberately omitted -- it's an internal prompt
    overlay for the LLM, not something meant for the visitor to read."""

    response_language: str
    welcome_sound: bool
    allow_attachments: bool


class WidgetPublicConfig(BaseModel):
    """What an embedded widget is allowed to see about itself. Never includes
    security settings, webhook URLs/secrets, agent_id, or organization_id."""

    widget_id: str
    branding: WidgetBrandingPublic
    layout: WidgetLayoutPublic
    triggers: WidgetTriggersPublic
    behavior: WidgetBehaviorPublicSlim
    availability: WidgetAvailabilityPublic
    accessibility: WidgetAccessibilityPublic
    lead_fields: List[LeadFieldPublic]


class WidgetHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    # ISO timestamp of the turn (both sides of a turn share it).
    at: Optional[str] = None


class WidgetHistoryResponse(BaseModel):
    messages: List[WidgetHistoryMessage]


class WidgetSessionResponse(BaseModel):
    visitor_session_id: str


class WidgetMessageRequest(BaseModel):
    visitor_session_id: str
    message: str
    # Processed attachments from POST /widget/{id}/upload -- same shape the
    # authenticated chat endpoints accept (see backend/chat/schemas.py).
    attachments: Optional[List[ChatAttachment]] = Field(default=None, max_length=5)


class WidgetAttachmentUploadResponse(BaseModel):
    """Returned by POST /widget/{id}/upload. `attachment` is the ready-to-send
    payload the client passes back inside WidgetMessageRequest.attachments --
    identical in shape to what POST /chat/attachments returns for the
    authenticated dashboard chat."""

    attachment_id: str
    url: str
    attachment: ChatAttachment


class WidgetMessageResponse(BaseModel):
    reply: str
    name: Optional[str] = None
    auth_errors: List[Dict[str, Optional[str]]] = Field(default_factory=list)


class WidgetLeadRequest(BaseModel):
    visitor_session_id: str
    values: Dict[str, str]


class WidgetFeedbackRequest(BaseModel):
    visitor_session_id: str
    # Client-generated (minted when the assistant reply is rendered) --
    # there's no server-side message id in the widget's lightweight
    # request/response model, so this is the only stable handle available.
    message_id: str
    rating: Literal["up", "down"]
    message_excerpt: Optional[str] = Field(default=None, max_length=500)
