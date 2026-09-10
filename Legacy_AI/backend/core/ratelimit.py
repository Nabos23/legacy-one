"""Admin-configurable rate limiting.

Limits are stored in the `rate_limit_config` collection (a single doc named
"global") so they can be edited live from the admin dashboard — no restart
needed. A fixed-window counter (per client IP) enforces them in-process.

Note: the counter is in-memory, so it is per-process. For multiple workers /
instances you'd back it with Redis; for a single instance this is sufficient.
"""

import logging
import time
from typing import Dict, Tuple
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import Headers

from backend.core.config import settings
from backend.core.constants import (
    DEFAULT_RATE_LIMIT_CONFIG,
    GLOBAL_CONFIG_NAME,
    RATE_LIMIT_CONFIG_TTL_SECONDS,
    RATE_LIMIT_EXCLUDED_PREFIXES,
)
from backend.db.database import rate_limit_config_collection

logger = logging.getLogger(__name__)

_config_cache: dict = {"cfg": None, "ts": 0.0}
_hits: Dict[str, Tuple[int, float]] = {}

# Hard cap on the number of tracked IPs so a flood of unique source IPs cannot
# grow the in-memory map unbounded. When exceeded, expired entries are pruned.
_MAX_TRACKED_KEYS = 50_000


def _prune_expired(now: float, window: int) -> None:
    """Drop windows that have fully elapsed so the hit map stays bounded."""
    stale = [k for k, (_, start) in _hits.items() if now - start >= window]
    for k in stale:
        _hits.pop(k, None)


async def ensure_default_config() -> None:
    """Create the default config document if none exists (called at startup)."""
    existing = await rate_limit_config_collection.find_one({"name": GLOBAL_CONFIG_NAME})
    if not existing:
        await rate_limit_config_collection.insert_one(dict(DEFAULT_RATE_LIMIT_CONFIG))


async def _get_config() -> dict:
    now = time.time()

    if _config_cache["cfg"] is None or now - _config_cache["ts"] > RATE_LIMIT_CONFIG_TTL_SECONDS:
        doc = await rate_limit_config_collection.find_one({"name": GLOBAL_CONFIG_NAME})

        if doc:
            doc.pop("_id", None)

        _config_cache["cfg"] = doc or dict(DEFAULT_RATE_LIMIT_CONFIG)
        _config_cache["ts"] = now

    return _config_cache["cfg"]


def _get_client_ip(scope: Scope) -> str:
    # Only honor X-Forwarded-For when explicitly configured to trust an upstream
    # proxy. Otherwise an attacker could spoof the header to evade per-IP limits.
    if settings.RATE_LIMIT_TRUST_FORWARDED:
        headers = Headers(scope=scope)
        fwd = headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


class RateLimitMiddleware:
    """Fixed-window, per-IP rate limiting."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        response_started = False

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if any(path.startswith(p) for p in RATE_LIMIT_EXCLUDED_PREFIXES):
            await self.app(scope, receive, send)
            return

        # Rate-limit decision — wrapped in try/except so a limiter bug never
        # takes the API down.  The downstream app call is intentionally
        # *outside* this guard so application errors propagate normally.
        send_fn = send
        try:
            cfg = await _get_config()
            if not cfg.get("enabled", True):
                await self.app(scope, receive, send)
                return

            max_requests = int(cfg.get("max_requests", 100))
            window = int(cfg.get("window_seconds", 60))

            now = time.time()
            key = _get_client_ip(scope)

            # Keep the in-memory map bounded under high IP churn.
            if len(_hits) > _MAX_TRACKED_KEYS:
                _prune_expired(now, window)

            count, start = _hits.get(key, (0, now))

            if now - start >= window:
                count, start = 0, now

            count += 1
            _hits[key] = (count, start)

            if count > max_requests:
                retry_after = max(1, int(window - (now - start)))
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return

            remaining = max(0, max_requests - count)

            async def send_wrapper(message):
                nonlocal response_started
                if message["type"] == "http.response.start":
                    response_started = True
                    message["headers"] = list(message["headers"]) + [
                        (b"x-ratelimit-limit", str(max_requests).encode()),
                        (b"x-ratelimit-remaining", str(remaining).encode()),
                    ]
                await send(message)

            send_fn = send_wrapper

        except Exception:
            logger.exception("Rate limiter error — passing request through")

        await self.app(scope, receive, send_fn)