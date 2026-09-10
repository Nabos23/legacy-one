import re
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

WidgetSourceType = Literal["single_agent", "supervisor"]
WidgetPosition = Literal["bottom-right", "bottom-left"]
LeadFieldType = Literal["text", "email", "phone"]
WidgetFontWeight = Literal["normal", "medium", "bold"]
WidgetLauncherShape = Literal["circle", "rounded-square"]
WidgetLauncherIcon = Literal["chat", "message", "robot", "custom"]
WidgetLauncherHoverEffect = Literal["none", "scale", "shadow", "both"]
WidgetShadowStyle = Literal["none", "soft", "medium", "strong"]
WidgetBubbleStyle = Literal["rounded", "square", "soft"]
WidgetSendButtonShape = Literal["circle", "rounded", "square"]
WidgetSpacingDensity = Literal["compact", "comfortable", "spacious"]
WidgetAnimationStyle = Literal["none", "fade", "slide", "scale"]
WidgetTextDirection = Literal["auto", "ltr", "rtl"]

# --- Shared field-validator helpers -----------------------------------------
# Used across the In-models below via `field_validator`, so every color/URL/
# time field is validated the same way regardless of which section it lives in.

_HEX_COLOR_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def hex_color_or_none(value: Optional[str]) -> Optional[str]:
    """Accept None or a CSS hex color (#RGB, #RRGGBB, #RRGGBBAA, any case).
    An empty string normalizes to None."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not _HEX_COLOR_RE.match(value):
        raise ValueError("must be a hex color like #RGB, #RRGGBB, or #RRGGBBAA")
    return value


def url_or_relative_path(value: Optional[str]) -> Optional[str]:
    """Accept None/empty (empty means "clear the stored value" -- see the
    exclude_none merge semantics in services.update_widget_config), an
    http(s):// URL, or a relative path starting with "/"."""
    if value is None or value == "":
        return value
    if value.startswith(("http://", "https://", "/")):
        return value
    raise ValueError("must be an http(s) URL or a relative path starting with '/'")


def hhmm_time(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not _HHMM_RE.match(value):
        raise ValueError("must be a time in HH:MM format (00:00-23:59)")
    return value


_LOCALE_TAG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


class WidgetLocaleCopyIn(BaseModel):
    header_title: Optional[str] = None
    header_subtitle: Optional[str] = None
    greeting_message: Optional[str] = None
    input_placeholder: Optional[str] = None
    loading_text: Optional[str] = None
    empty_state_text: Optional[str] = None
    error_message_text: Optional[str] = None
    offline_message: Optional[str] = None
    quick_replies: Optional[List[str]] = None


class WidgetLocaleCopyPublic(BaseModel):
    header_title: Optional[str] = None
    header_subtitle: Optional[str] = None
    greeting_message: Optional[str] = None
    input_placeholder: Optional[str] = None
    loading_text: Optional[str] = None
    empty_state_text: Optional[str] = None
    error_message_text: Optional[str] = None
    offline_message: Optional[str] = None
    quick_replies: Optional[List[str]] = None


class WidgetBrandingIn(BaseModel):
    theme_color: Optional[str] = None
    position: Optional[WidgetPosition] = None
    header_title: Optional[str] = None
    header_subtitle: Optional[str] = None
    header_logo_url: Optional[str] = None
    header_text_color: Optional[str] = None
    header_bg_color: Optional[str] = None
    greeting_message: Optional[str] = None
    dark_mode: Optional[bool] = None
    font_family: Optional[str] = None
    font_size_base: Optional[int] = Field(default=None, ge=10, le=24)
    font_weight: Optional[WidgetFontWeight] = None
    secondary_color: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    border_color: Optional[str] = None
    assistant_avatar_url: Optional[str] = None
    user_avatar_url: Optional[str] = None
    show_avatars_in_messages: Optional[bool] = None
    user_bubble_color: Optional[str] = None
    assistant_bubble_color: Optional[str] = None
    show_timestamps: Optional[bool] = None
    input_placeholder: Optional[str] = None
    send_button_color: Optional[str] = None
    loading_text: Optional[str] = None
    empty_state_text: Optional[str] = None
    error_message_text: Optional[str] = None
    quick_replies: Optional[List[str]] = None
    show_branding: Optional[bool] = None
    custom_css: Optional[str] = Field(default=None, max_length=20_000)
    text_direction: Optional[WidgetTextDirection] = None
    # Replaced wholesale when provided (locales aren't per-key merged --
    # the builder always sends the complete map).
    locales: Optional[Dict[str, WidgetLocaleCopyIn]] = None

    @field_validator("locales")
    @classmethod
    def _check_locale_tags(cls, value: Optional[Dict[str, "WidgetLocaleCopyIn"]]):
        if value is None:
            return value
        if len(value) > 30:
            raise ValueError("at most 30 locales are supported")
        for tag in value:
            if not _LOCALE_TAG_RE.match(tag):
                raise ValueError(f"'{tag}' is not a valid locale tag (expected e.g. 'es' or 'fr-CA')")
        return value

    @field_validator(
        "theme_color",
        "secondary_color",
        "background_color",
        "text_color",
        "border_color",
        "header_bg_color",
        "header_text_color",
        "user_bubble_color",
        "assistant_bubble_color",
        "send_button_color",
    )
    @classmethod
    def _check_colors(cls, value: Optional[str]) -> Optional[str]:
        return hex_color_or_none(value)

    @field_validator("header_logo_url", "assistant_avatar_url", "user_avatar_url")
    @classmethod
    def _check_urls(cls, value: Optional[str]) -> Optional[str]:
        return url_or_relative_path(value)


class WidgetBrandingPublic(BaseModel):
    theme_color: str
    position: WidgetPosition
    header_title: str
    header_subtitle: Optional[str] = None
    header_logo_url: Optional[str] = None
    header_text_color: str
    header_bg_color: Optional[str] = None
    greeting_message: str
    dark_mode: bool
    font_family: str
    font_size_base: int
    font_weight: WidgetFontWeight
    secondary_color: str
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    border_color: Optional[str] = None
    assistant_avatar_url: Optional[str] = None
    user_avatar_url: Optional[str] = None
    show_avatars_in_messages: bool
    user_bubble_color: Optional[str] = None
    assistant_bubble_color: Optional[str] = None
    show_timestamps: bool
    input_placeholder: str
    send_button_color: Optional[str] = None
    loading_text: str
    empty_state_text: str
    error_message_text: str
    quick_replies: List[str]
    show_branding: bool
    custom_css: Optional[str] = None
    text_direction: WidgetTextDirection
    locales: Dict[str, WidgetLocaleCopyPublic] = Field(default_factory=dict)


class WidgetLayoutIn(BaseModel):
    widget_width: Optional[int] = Field(default=None, ge=240, le=800)
    widget_height: Optional[int] = Field(default=None, ge=300, le=900)
    widget_min_width: Optional[int] = Field(default=None, ge=200, le=800)
    widget_min_height: Optional[int] = Field(default=None, ge=200, le=900)
    widget_max_width: Optional[int] = Field(default=None, ge=240, le=1200)
    widget_max_height: Optional[int] = Field(default=None, ge=300, le=1400)
    launcher_size: Optional[int] = Field(default=None, ge=36, le=96)
    launcher_shape: Optional[WidgetLauncherShape] = None
    launcher_icon: Optional[WidgetLauncherIcon] = None
    launcher_icon_url: Optional[str] = None
    launcher_hover_effect: Optional[WidgetLauncherHoverEffect] = None
    offset_x: Optional[int] = Field(default=None, ge=0, le=200)
    offset_y: Optional[int] = Field(default=None, ge=0, le=200)
    border_radius: Optional[int] = Field(default=None, ge=0, le=32)
    shadow_style: Optional[WidgetShadowStyle] = None
    bubble_style: Optional[WidgetBubbleStyle] = None
    send_button_shape: Optional[WidgetSendButtonShape] = None
    spacing_density: Optional[WidgetSpacingDensity] = None
    animation_style: Optional[WidgetAnimationStyle] = None
    mobile_full_screen: Optional[bool] = None
    mobile_breakpoint_px: Optional[int] = Field(default=None, ge=320, le=1280)

    @field_validator("launcher_icon_url")
    @classmethod
    def _check_urls(cls, value: Optional[str]) -> Optional[str]:
        return url_or_relative_path(value)


class WidgetLayoutPublic(BaseModel):
    widget_width: int
    widget_height: int
    widget_min_width: int
    widget_min_height: int
    widget_max_width: int
    widget_max_height: int
    launcher_size: int
    launcher_shape: WidgetLauncherShape
    launcher_icon: WidgetLauncherIcon
    launcher_icon_url: Optional[str] = None
    launcher_hover_effect: WidgetLauncherHoverEffect
    offset_x: int
    offset_y: int
    border_radius: int
    shadow_style: WidgetShadowStyle
    bubble_style: WidgetBubbleStyle
    send_button_shape: WidgetSendButtonShape
    spacing_density: WidgetSpacingDensity
    animation_style: WidgetAnimationStyle
    mobile_full_screen: bool
    mobile_breakpoint_px: int


class TargetedGreetingIn(BaseModel):
    path_pattern: str
    greeting: str


class WidgetTriggersIn(BaseModel):
    auto_open: Optional[bool] = None
    auto_open_delay_ms: Optional[int] = Field(default=None, ge=0, le=120_000)
    open_on_scroll_percent: Optional[int] = Field(default=None, ge=0, le=100)
    targeted_greetings: Optional[List[TargetedGreetingIn]] = None


class WidgetTriggersPublic(BaseModel):
    auto_open: bool
    auto_open_delay_ms: int
    open_on_scroll_percent: Optional[int] = None
    targeted_greetings: List[TargetedGreetingIn]


class WidgetBehaviorIn(BaseModel):
    response_language: Optional[str] = None
    tone_instructions: Optional[str] = None
    welcome_sound: Optional[bool] = None
    allow_attachments: Optional[bool] = None
    rich_messages: Optional[bool] = None


class WidgetBehaviorPublic(BaseModel):
    response_language: str
    tone_instructions: Optional[str] = None
    welcome_sound: bool
    allow_attachments: bool
    rich_messages: bool


class DayScheduleIn(BaseModel):
    enabled: Optional[bool] = None
    start: Optional[str] = None
    end: Optional[str] = None

    @field_validator("start", "end")
    @classmethod
    def _check_times(cls, value: Optional[str]) -> Optional[str]:
        return hhmm_time(value)


class DaySchedulePublic(BaseModel):
    enabled: bool
    start: str
    end: str


class WidgetAvailabilityIn(BaseModel):
    enabled: Optional[bool] = None
    timezone: Optional[str] = None
    schedule: Optional[Dict[str, DayScheduleIn]] = None
    offline_message: Optional[str] = None


class WidgetAvailabilityPublic(BaseModel):
    enabled: bool
    timezone: str
    schedule: Dict[str, DaySchedulePublic]
    offline_message: str


class WidgetAccessibilityIn(BaseModel):
    reduced_motion: Optional[bool] = None
    high_contrast: Optional[bool] = None
    large_text: Optional[bool] = None


class WidgetAccessibilityPublic(BaseModel):
    reduced_motion: bool
    high_contrast: bool
    large_text: bool


class LeadFieldIn(BaseModel):
    field_name: str
    label: str
    field_type: LeadFieldType = "text"
    required: bool = True


class LeadFieldPublic(BaseModel):
    field_name: str
    label: str
    field_type: LeadFieldType
    required: bool


class WidgetWebhookTargetIn(BaseModel):
    """`secret`: omit to leave the existing stored secret untouched, empty
    string to clear it, or a new value to replace it. Never round-tripped
    back to the client, so this is the only way to signal "keep as-is"."""

    url: Optional[str] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: Optional[str]) -> Optional[str]:
        return url_or_relative_path(value)


class WidgetWebhooksIn(BaseModel):
    conversation_started: Optional[WidgetWebhookTargetIn] = None
    lead_captured: Optional[WidgetWebhookTargetIn] = None
    message_sent: Optional[WidgetWebhookTargetIn] = None
    feedback_submitted: Optional[WidgetWebhookTargetIn] = None


class WidgetWebhookTargetPublic(BaseModel):
    url: Optional[str] = None
    has_secret: bool
    is_active: bool


class WidgetWebhooksPublic(BaseModel):
    conversation_started: WidgetWebhookTargetPublic
    lead_captured: WidgetWebhookTargetPublic
    message_sent: WidgetWebhookTargetPublic
    feedback_submitted: WidgetWebhookTargetPublic


class WidgetWebhookDeliveryItem(BaseModel):
    """One row of the outbound-delivery log shown in the builder's Webhooks tab."""

    id: str
    # "event" (real traffic), "test" (builder test-fire), or "replay".
    kind: str = "event"
    # Whether this row stored its payload and can be replayed.
    can_replay: bool = False
    event: str
    url: str
    ok: bool
    attempts: int
    status_code: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime


class WidgetWebhookDeliveryResult(BaseModel):
    """Outcome of a synchronous test-fire or replay delivery."""

    ok: bool
    status_code: Optional[int] = None
    error: Optional[str] = None


class WidgetWebhookDeliveriesResponse(BaseModel):
    items: List[WidgetWebhookDeliveryItem]
    total: int
    page: int
    page_size: int


class WidgetSecurityIn(BaseModel):
    allowed_origins: Optional[List[str]] = None
    require_api_key: Optional[bool] = None
    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1, le=10_000)
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)


class WidgetSecurityPublic(BaseModel):
    allowed_origins: List[str]
    require_api_key: bool
    # Whether a key has been generated — the plaintext/hash is never exposed
    # back to the client after creation, only this boolean.
    has_api_key: bool
    rate_limit_per_minute: Optional[int] = None
    retention_days: Optional[int] = None


class WidgetConfigCreate(BaseModel):
    """Payload for creating a widget config."""

    organization_id: str
    name: str = Field(min_length=2, max_length=120)
    source_type: WidgetSourceType = "single_agent"
    agent_id: Optional[str] = None
    branding: Optional[WidgetBrandingIn] = None
    layout: Optional[WidgetLayoutIn] = None
    triggers: Optional[WidgetTriggersIn] = None
    behavior: Optional[WidgetBehaviorIn] = None
    availability: Optional[WidgetAvailabilityIn] = None
    accessibility: Optional[WidgetAccessibilityIn] = None
    lead_fields: Optional[List[LeadFieldIn]] = None
    webhooks: Optional[WidgetWebhooksIn] = None
    security: Optional[WidgetSecurityIn] = None


class WidgetConfigUpdate(BaseModel):
    """Payload for updating a widget config (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    source_type: Optional[WidgetSourceType] = None
    agent_id: Optional[str] = None
    branding: Optional[WidgetBrandingIn] = None
    layout: Optional[WidgetLayoutIn] = None
    triggers: Optional[WidgetTriggersIn] = None
    behavior: Optional[WidgetBehaviorIn] = None
    availability: Optional[WidgetAvailabilityIn] = None
    accessibility: Optional[WidgetAccessibilityIn] = None
    lead_fields: Optional[List[LeadFieldIn]] = None
    webhooks: Optional[WidgetWebhooksIn] = None
    security: Optional[WidgetSecurityIn] = None
    is_enabled: Optional[bool] = None


class WidgetConfigPublic(BaseModel):
    """Widget config data returned to clients."""

    id: Optional[str] = None
    organization_id: str
    name: str
    source_type: WidgetSourceType
    agent_id: Optional[str] = None
    is_enabled: bool
    branding: WidgetBrandingPublic
    layout: WidgetLayoutPublic
    triggers: WidgetTriggersPublic
    behavior: WidgetBehaviorPublic
    availability: WidgetAvailabilityPublic
    accessibility: WidgetAccessibilityPublic
    lead_fields: List[LeadFieldPublic]
    webhooks: WidgetWebhooksPublic
    security: WidgetSecurityPublic
    created_by: str
    created_at: datetime
    updated_at: datetime
    # Draft/publish state -- branding/layout/triggers/behavior/availability/
    # accessibility/lead_fields above always reflect the DRAFT (what's shown
    # in the builder); visitors instead see whatever was last published.
    published_version: Optional[int] = None
    published_at: Optional[datetime] = None
    has_unpublished_changes: bool = False


class WidgetVersionListItem(BaseModel):
    """One entry in a widget's publish history."""

    version: int
    published_by: str
    # Display name of the publisher, resolved at list time (falls back to the
    # raw id if the user was since deleted).
    published_by_name: Optional[str] = None
    published_at: datetime
    # Set only when this version was created via rollback, not a direct publish.
    restored_from_version: Optional[int] = None
    # Which sections differ from the previous version (e.g. ["branding",
    # "layout"]). Empty for v1 and republished-identical versions.
    changed_sections: List[str] = Field(default_factory=list)


class WidgetImageUploadResponse(BaseModel):
    url: str


class WidgetPreviewTokenResponse(BaseModel):
    """Short-lived, stateless token letting the dashboard's preview iframe
    fetch the DRAFT config via the public GET /widget/{id}/config endpoint."""

    preview_token: str
    expires_at: datetime


class WidgetApiKeyResponse(BaseModel):
    """Returned exactly once — at creation or regeneration — since only the
    hash is persisted afterward."""

    widget_id: str
    api_key: str = Field(description="Plaintext key. Store it now — it cannot be retrieved again.")


class WidgetSessionListItem(BaseModel):
    visitor_session_id: str
    created_at: datetime
    last_active_at: datetime
    status: str
    origin: Optional[str] = None
    has_lead: bool = False
    lead_values: Optional[Dict[str, str]] = None


class WidgetDayCount(BaseModel):
    date: str
    count: int


class WidgetAnalytics(BaseModel):
    total_sessions: int
    sessions_today: int
    leads_captured: int
    feedback_up: int
    feedback_down: int
    sessions_by_day: List[WidgetDayCount]
