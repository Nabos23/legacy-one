import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, Header, Request, status

from backend.core.softdelete import NOT_DELETED
from backend.db.database import widget_configs_collection
from backend.widget.defaults import (
    DEFAULT_ACCESSIBILITY,
    DEFAULT_BEHAVIOR,
    DEFAULT_BRANDING,
    DEFAULT_LAYOUT,
    DEFAULT_TRIGGERS,
    availability_with_defaults,
    webhooks_with_defaults,
    with_defaults,
)
from backend.widget.origins import is_origin_allowed
from backend.widget.rate_limit import check_widget_rate_limit


@dataclass
class WidgetContext:
    """Resolved, trusted context for a public widget request. Nothing here is
    client-supplied -- organization_id/agent_id/source_type all come from the
    widget_configs document, never from the request body/path beyond widget_id."""

    widget_id: str
    organization_id: str
    source_type: str
    agent_id: Optional[str]
    branding: dict
    layout: dict
    triggers: dict
    behavior: dict
    availability: dict
    accessibility: dict
    lead_fields: list
    # Never exposed to the client (see WidgetPublicConfig) -- server-side only,
    # used by public_services to fire outbound notifications.
    webhooks: dict
    # Server-side only: days before visitor sessions/feedback expire (None = never).
    retention_days: int | None = None


def _hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


async def get_widget_context(
    widget_id: str,
    request: Request,
    x_widget_api_key: Optional[str] = Header(default=None),
) -> WidgetContext:
    """The actual access-control boundary for every public /widget/* route.

    CORS headers (added separately, see backend/widget/origins.py +
    DynamicWidgetCORSMiddleware in main.py) only control whether a browser
    lets its own JS *read* the response -- they don't stop the request from
    reaching the server. This dependency is what actually authorizes the
    request: the Origin header must be in the widget's allowlist (or a local
    dev origin), OR a valid widget API key must be supplied.
    """
    if not ObjectId.is_valid(widget_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    widget = await widget_configs_collection.find_one({"_id": ObjectId(widget_id), **NOT_DELETED})
    if not widget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    if not widget.get("is_enabled", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This widget is currently disabled.")

    security = widget.get("security") or {}
    origin = request.headers.get("origin", "")

    origin_ok = await is_origin_allowed(origin)
    key_ok = False
    if x_widget_api_key and security.get("widget_api_key_hash"):
        key_ok = secrets.compare_digest(_hash_api_key(x_widget_api_key), security["widget_api_key_hash"])

    if not origin_ok and not key_ok:
        if security.get("require_api_key") and not security.get("widget_api_key_hash"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This widget requires an API key, but none has been configured yet.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This origin is not allowed to embed this widget. Add it to the widget's allowed "
            "origins, or send a valid X-Widget-Api-Key header.",
        )
    if security.get("require_api_key") and not key_ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This widget requires a valid X-Widget-Api-Key header.",
        )

    check_widget_rate_limit(widget_id, security.get("rate_limit_per_minute"))

    # Visitors only ever see the last PUBLISHED snapshot, never the live
    # draft being edited in the builder -- `published` is always set from
    # widget creation onward (see services.create_widget_config); the
    # `widget.get(...)` fallback below only guards against a widget document
    # missing it entirely (e.g. manual DB edit), not a real product state.
    published = widget.get("published")
    source = published if published else widget

    # with_defaults/*_with_defaults backfill any section missing entirely --
    # widgets created before this section existed have no key for it at all,
    # and building the strict public schemas straight from `{}` would fail
    # validation on fields with no default (e.g. WidgetTriggersPublic.auto_open).
    return WidgetContext(
        widget_id=widget_id,
        organization_id=widget["organization_id"],
        source_type=widget.get("source_type", "single_agent"),
        agent_id=widget.get("agent_id"),
        branding=with_defaults(DEFAULT_BRANDING, source.get("branding")),
        layout=with_defaults(DEFAULT_LAYOUT, source.get("layout")),
        triggers=with_defaults(DEFAULT_TRIGGERS, source.get("triggers")),
        behavior=with_defaults(DEFAULT_BEHAVIOR, source.get("behavior")),
        availability=availability_with_defaults(source.get("availability")),
        accessibility=with_defaults(DEFAULT_ACCESSIBILITY, source.get("accessibility")),
        lead_fields=source.get("lead_fields") or [],
        webhooks=webhooks_with_defaults(widget.get("webhooks")),
        retention_days=security.get("retention_days"),
    )
