"""Per-widget CORS origin allowlist, unioned across every widget config and
cached in-process. Mirrors the fixed, static `ALLOWED_ORIGINS` list in
`backend/main.py` used for the authenticated dashboard -- this one is dynamic
because the whole point of a widget is running on domains we don't control.

The cache is a plain module-level dict today because the backend runs as a
single uvicorn process (see backend/core/ratelimit.py's identical note on its
own in-memory hit-counter). If this ever runs as multiple replicas, swap
`_cache`/`invalidate_widget_origins_cache` for a Redis-backed equivalent --
every *caller* of `get_all_widget_origins()`/`invalidate_widget_origins_cache()`
stays unchanged, since both are already exposed as plain async functions
rather than inlined at call sites.
"""

import time
from typing import Set

from backend.core.config import settings
from backend.core.softdelete import NOT_DELETED
from backend.db.database import widget_configs_collection

_CACHE_TTL_SECONDS = 60.0
_cache: dict = {"origins": None, "ts": 0.0}

def _is_local_dev(origin: str) -> bool:
    """Any-port localhost is always allowed, so local widget testing never
    needs an explicit allowlist entry."""
    try:
        # origin looks like "http://localhost:3000" or "https://127.0.0.1:5173"
        after_scheme = origin.split("://", 1)[1]
        host = after_scheme.split(":", 1)[0].split("/", 1)[0]
        return host in ("localhost", "127.0.0.1", "::1")
    except (IndexError, AttributeError):
        return False


async def get_all_widget_origins() -> Set[str]:
    """Union of every enabled widget's `security.allowed_origins`, cached for
    `_CACHE_TTL_SECONDS`. Disabled/deleted widgets don't contribute origins --
    disabling a widget also revokes its embedding rights immediately(-ish)."""
    now = time.time()
    if _cache["origins"] is not None and now - _cache["ts"] < _CACHE_TTL_SECONDS:
        return _cache["origins"]

    origins: Set[str] = set()
    cursor = widget_configs_collection.find(
        {"is_enabled": True, **NOT_DELETED},
        {"security.allowed_origins": 1},
    )
    async for doc in cursor:
        for origin in (doc.get("security") or {}).get("allowed_origins") or []:
            origins.add(origin.rstrip("/"))

    _cache["origins"] = origins
    _cache["ts"] = now
    return origins


def invalidate_widget_origins_cache() -> None:
    """Called whenever a widget's allowed_origins or is_enabled flag changes,
    so new/removed origins take effect without waiting out the TTL."""
    _cache["origins"] = None
    _cache["ts"] = 0.0


async def is_origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    normalized = origin.rstrip("/")
    if _is_local_dev(normalized):
        return True
    # Our own dashboard's origin is always trusted -- it's not "any origin",
    # just specifically the app we control, and it's what the dashboard's own
    # "test this widget" preview page (served from this same origin) needs to
    # actually work without requiring an org to allowlist their own app first.
    if settings.FRONTEND_URL and normalized == settings.FRONTEND_URL.rstrip("/"):
        return True
    origins = await get_all_widget_origins()
    return normalized in origins
