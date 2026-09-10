from datetime import datetime, timezone
from typing import Annotated, Dict, List, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]

WidgetSourceType = Literal["single_agent", "supervisor"]
DayKey = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WebhookEvent = Literal["conversation_started", "lead_captured", "message_sent", "feedback_submitted"]


class WidgetLocaleCopy(BaseModel):
    """Per-locale overrides for the widget's visitor-facing copy. Any field
    left None falls back to the base branding value. Keyed in
    `WidgetBranding.locales` by a BCP-47-ish tag ("es", "fr-CA"); the loader
    matches the visitor's navigator.language (exact, then base language)."""

    header_title: Optional[str] = None
    header_subtitle: Optional[str] = None
    greeting_message: Optional[str] = None
    input_placeholder: Optional[str] = None
    loading_text: Optional[str] = None
    empty_state_text: Optional[str] = None
    error_message_text: Optional[str] = None
    # Overrides availability.offline_message (copy lives here so all
    # translations sit in one place).
    offline_message: Optional[str] = None
    # None = keep the base quick replies; [] = hide them for this locale.
    quick_replies: Optional[List[str]] = None


class WidgetBranding(BaseModel):
    """Visual customization applied to the embedded chat surface."""

    theme_color: str = "#4F46E5"
    position: Literal["bottom-right", "bottom-left"] = "bottom-right"
    header_title: str = "Chat with us"
    header_subtitle: Optional[str] = None
    header_logo_url: Optional[str] = None
    header_text_color: str = "#111827"
    # None = falls back to theme_color at render time.
    header_bg_color: Optional[str] = None
    greeting_message: str = "Hi! How can I help you today?"
    dark_mode: bool = False
    font_family: str = "system-ui"
    font_size_base: int = 14
    font_weight: Literal["normal", "medium", "bold"] = "normal"
    secondary_color: str = "#818CF8"
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    border_color: Optional[str] = None
    assistant_avatar_url: Optional[str] = None
    user_avatar_url: Optional[str] = None
    show_avatars_in_messages: bool = False
    user_bubble_color: Optional[str] = None
    assistant_bubble_color: Optional[str] = None
    show_timestamps: bool = False
    input_placeholder: str = "Type a message…"
    send_button_color: Optional[str] = None
    loading_text: str = "Thinking…"
    empty_state_text: str = "No messages yet. Say hello!"
    error_message_text: str = "Something went wrong. Please try again."
    # Canned questions rendered as clickable chips under the greeting.
    quick_replies: List[str] = Field(default_factory=list)
    # "Powered by" footer shown in the embedded chat surface.
    show_branding: bool = True
    # Raw CSS injected into the embed for orgs that need styling beyond the
    # structured fields above. None = no custom styles.
    custom_css: Optional[str] = None
    # "auto" defers to the browser/content; "ltr"/"rtl" force a direction.
    text_direction: Literal["auto", "ltr", "rtl"] = "auto"
    # Per-locale copy overrides, e.g. {"es": {...}, "fr": {...}}.
    locales: Dict[str, WidgetLocaleCopy] = Field(default_factory=dict)


class WidgetLayout(BaseModel):
    """Structural and motion customization for the launcher/iframe shell."""

    widget_width: int = 380
    widget_height: int = 600
    widget_min_width: int = 300
    widget_min_height: int = 400
    widget_max_width: int = 480
    widget_max_height: int = 760
    launcher_size: int = 56
    launcher_shape: Literal["circle", "rounded-square"] = "circle"
    launcher_icon: Literal["chat", "message", "robot", "custom"] = "chat"
    launcher_icon_url: Optional[str] = None
    launcher_hover_effect: Literal["none", "scale", "shadow", "both"] = "scale"
    offset_x: int = 20
    offset_y: int = 20
    border_radius: int = 16
    shadow_style: Literal["none", "soft", "medium", "strong"] = "medium"
    bubble_style: Literal["rounded", "square", "soft"] = "rounded"
    send_button_shape: Literal["circle", "rounded", "square"] = "square"
    spacing_density: Literal["compact", "comfortable", "spacious"] = "comfortable"
    animation_style: Literal["none", "fade", "slide", "scale"] = "fade"
    mobile_full_screen: bool = True
    mobile_breakpoint_px: int = 640


class TargetedGreeting(BaseModel):
    """Overrides `branding.greeting_message` when the host page's path matches
    `path_pattern` (a simple glob: `*` wildcard, e.g. "/pricing*")."""

    path_pattern: str
    greeting: str


class WidgetTriggers(BaseModel):
    auto_open: bool = False
    auto_open_delay_ms: int = 4000
    # None disables the scroll trigger; otherwise 0-100, percent of page scrolled.
    open_on_scroll_percent: Optional[int] = None
    targeted_greetings: List[TargetedGreeting] = Field(default_factory=list)


class WidgetBehavior(BaseModel):
    response_language: str = "auto"
    # Layered on top of the source agent's own prompt at message time -- never
    # replaces it, since the agent's prompt/guardrails remain the source of truth.
    tone_instructions: Optional[str] = None
    welcome_sound: bool = False
    # Whether visitors may upload file attachments with their messages.
    allow_attachments: bool = False
    # When on, each turn's hidden preamble teaches the agent the widget's
    # rich-message syntax (```buttons / ```cards fenced JSON blocks) so it can
    # offer tappable choices and cards. The embed always renders the syntax;
    # this flag only controls whether agents are told about it.
    rich_messages: bool = False


class DaySchedule(BaseModel):
    enabled: bool = False
    start: str = "09:00"
    end: str = "17:00"


def _default_week_schedule() -> Dict[str, DaySchedule]:
    return {day: DaySchedule() for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


class WidgetAvailability(BaseModel):
    """Business-hours gating, evaluated client-side (see the embed page's
    isCurrentlyAvailable) -- avoids needing a timezone library on the backend
    for something purely presentational. The visitor's device clock gives an
    absolute instant shared by every clock on Earth; Intl.DateTimeFormat then
    converts it into THIS widget's configured `timezone` below, independent
    of the visitor's own timezone. Overnight windows (e.g. 22:00-02:00) are
    supported by checking both today's and yesterday's schedule entry."""

    enabled: bool = False
    timezone: str = "UTC"
    schedule: Dict[str, DaySchedule] = Field(default_factory=_default_week_schedule)
    offline_message: str = "We're offline right now. Leave a message and we'll get back to you."


class WidgetAccessibility(BaseModel):
    reduced_motion: bool = False
    high_contrast: bool = False
    large_text: bool = False


class LeadField(BaseModel):
    """One field in the optional pre-chat lead-capture form."""

    field_name: str
    label: str
    field_type: Literal["text", "email", "phone"] = "text"
    required: bool = True


class WidgetWebhookTarget(BaseModel):
    """One event's outbound notification target -- at most one URL per event,
    which covers the realistic case without the update-time headache of
    matching/preserving secrets across a list the client never sees back."""

    url: Optional[str] = None
    secret_encrypted: Optional[str] = None
    is_active: bool = True


class WidgetWebhooks(BaseModel):
    """Outbound notifications fired (best-effort, fire-and-forget) on a widget
    lifecycle event. Folds Flow-bot's separate "API endpoints" + "webhooks"
    concepts into one mechanism -- One-AI's widgets don't create accounts, so
    there's no separate signup/login endpoint type to configure."""

    conversation_started: WidgetWebhookTarget = Field(default_factory=WidgetWebhookTarget)
    lead_captured: WidgetWebhookTarget = Field(default_factory=WidgetWebhookTarget)
    # Fired after each visitor message gets its reply (message + reply excerpts).
    message_sent: WidgetWebhookTarget = Field(default_factory=WidgetWebhookTarget)
    # Fired when a visitor thumbs a reply up or down.
    feedback_submitted: WidgetWebhookTarget = Field(default_factory=WidgetWebhookTarget)


class WidgetSecurity(BaseModel):
    """Public-facing access control for this widget.

    `allowed_origins` is the primary boundary (matched against the embedding
    page's `Origin` header). `widget_api_key_hash` is optional defense in
    depth for orgs that want a shared secret too — only the hash is ever
    persisted; the plaintext key is returned once, at creation/regeneration
    time, and never stored or retrievable again.
    """

    allowed_origins: List[str] = Field(default_factory=list)
    widget_api_key_hash: Optional[str] = None
    require_api_key: bool = False
    # None = no widget-specific cap (the global per-IP RateLimitMiddleware
    # still applies to every request regardless).
    rate_limit_per_minute: Optional[int] = None
    # Visitor-data retention: sessions (incl. captured leads) and message
    # feedback created AFTER this is set carry an expires_at that a Mongo TTL
    # index purges. None = keep indefinitely. Applies to new sessions only.
    retention_days: Optional[int] = None


class WidgetConfigBase(BaseModel):
    """Shared fields used when creating or updating a widget config."""

    organization_id: str
    name: str
    source_type: WidgetSourceType = "single_agent"
    # Required when source_type == "single_agent"; must be omitted/None for
    # "supervisor" (which implicitly targets every active agent in the org,
    # identical to what /chat/session already does today).
    agent_id: Optional[str] = None
    branding: WidgetBranding = Field(default_factory=WidgetBranding)
    layout: WidgetLayout = Field(default_factory=WidgetLayout)
    triggers: WidgetTriggers = Field(default_factory=WidgetTriggers)
    behavior: WidgetBehavior = Field(default_factory=WidgetBehavior)
    availability: WidgetAvailability = Field(default_factory=WidgetAvailability)
    accessibility: WidgetAccessibility = Field(default_factory=WidgetAccessibility)
    lead_fields: List[LeadField] = Field(default_factory=list)
    webhooks: WidgetWebhooks = Field(default_factory=WidgetWebhooks)
    security: WidgetSecurity = Field(default_factory=WidgetSecurity)
    created_by: str


class WidgetConfig(WidgetConfigBase):
    """Widget config document as stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    is_enabled: bool = True
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
