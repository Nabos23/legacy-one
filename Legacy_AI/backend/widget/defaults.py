"""Single source of truth for widget-config section defaults.

Shared by services.py (merging a create/update payload on top of existing +
defaults) and dependencies.py (backfilling sections that simply don't exist
yet on widgets created before a given section existed -- e.g. every widget
created in Phase 1-3 has no `triggers`/`behavior`/`availability`/
`accessibility`/`webhooks` key at all, and building the strict Pydantic
public schemas straight from `{}` would fail validation on required fields).
"""

DEFAULT_BRANDING = {
    "theme_color": "#4F46E5",
    "position": "bottom-right",
    "header_title": "Chat with us",
    "header_subtitle": None,
    "header_logo_url": None,
    "header_text_color": "#111827",
    "header_bg_color": None,
    "greeting_message": "Hi! How can I help you today?",
    "dark_mode": False,
    "font_family": "system-ui",
    "font_size_base": 14,
    "font_weight": "normal",
    "secondary_color": "#818CF8",
    "background_color": None,
    "text_color": None,
    "border_color": None,
    "assistant_avatar_url": None,
    "user_avatar_url": None,
    "show_avatars_in_messages": False,
    "user_bubble_color": None,
    "assistant_bubble_color": None,
    "show_timestamps": False,
    "input_placeholder": "Type a message…",
    "send_button_color": None,
    "loading_text": "Thinking…",
    "empty_state_text": "No messages yet. Say hello!",
    "error_message_text": "Something went wrong. Please try again.",
    "quick_replies": [],
    "show_branding": True,
    "custom_css": None,
    "text_direction": "auto",
    "locales": {},
}

DEFAULT_LAYOUT = {
    "widget_width": 380,
    "widget_height": 600,
    "widget_min_width": 300,
    "widget_min_height": 400,
    "widget_max_width": 480,
    "widget_max_height": 760,
    "launcher_size": 56,
    "launcher_shape": "circle",
    "launcher_icon": "chat",
    "launcher_icon_url": None,
    "launcher_hover_effect": "scale",
    "offset_x": 20,
    "offset_y": 20,
    "border_radius": 16,
    "shadow_style": "medium",
    "bubble_style": "rounded",
    "send_button_shape": "square",
    "spacing_density": "comfortable",
    "animation_style": "fade",
    "mobile_full_screen": True,
    "mobile_breakpoint_px": 640,
}

DEFAULT_TRIGGERS = {
    "auto_open": False,
    "auto_open_delay_ms": 4000,
    "open_on_scroll_percent": None,
    "targeted_greetings": [],
}

DEFAULT_BEHAVIOR = {
    "response_language": "auto",
    "tone_instructions": None,
    "welcome_sound": False,
    "allow_attachments": False,
    "rich_messages": False,
}

DEFAULT_DAY_SCHEDULE = {"enabled": False, "start": "09:00", "end": "17:00"}

DEFAULT_AVAILABILITY = {
    "enabled": False,
    "timezone": "UTC",
    "schedule": {day: dict(DEFAULT_DAY_SCHEDULE) for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
    "offline_message": "We're offline right now. Leave a message and we'll get back to you.",
}

DEFAULT_ACCESSIBILITY = {
    "reduced_motion": False,
    "high_contrast": False,
    "large_text": False,
}

DEFAULT_WEBHOOK_TARGET = {"url": None, "secret_encrypted": None, "is_active": True}
WEBHOOK_EVENTS = ("conversation_started", "lead_captured", "message_sent", "feedback_submitted")
DEFAULT_WEBHOOKS = {event: dict(DEFAULT_WEBHOOK_TARGET) for event in WEBHOOK_EVENTS}

DEFAULT_SECURITY = {
    "allowed_origins": [],
    "widget_api_key_hash": None,
    "require_api_key": False,
    # None = no widget-specific cap (the global per-IP RateLimitMiddleware
    # still applies). Set to enforce a tighter, per-widget requests/minute cap.
    "rate_limit_per_minute": None,
    # None = keep visitor sessions/leads/feedback forever; N = TTL-purge after N days.
    "retention_days": None,
}


def with_defaults(default: dict, stored: dict | None) -> dict:
    """Shallow merge for the simple (non-nested) sections."""
    return {**default, **(stored or {})}


def availability_with_defaults(stored: dict | None) -> dict:
    stored = stored or {}
    merged = {**DEFAULT_AVAILABILITY, **stored}
    schedule = {**DEFAULT_AVAILABILITY["schedule"]}
    for day, day_val in (stored.get("schedule") or {}).items():
        schedule[day] = {**DEFAULT_DAY_SCHEDULE, **day_val}
    merged["schedule"] = schedule
    return merged


def webhooks_with_defaults(stored: dict | None) -> dict:
    stored = stored or {}
    return {event: {**DEFAULT_WEBHOOK_TARGET, **(stored.get(event) or {})} for event in WEBHOOK_EVENTS}
