"""Optional per-widget requests/minute cap, layered on top of (not instead of)
the app-wide per-IP RateLimitMiddleware in backend/main.py.

Same in-process, fixed-window pattern as backend/core/ratelimit.py -- a
single-instance assumption that's fine today (see backend/widget/origins.py's
identical note); swap for Redis if this backend ever runs multiple replicas.
"""

import time
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, status

_hits: Dict[str, Tuple[int, float]] = {}
_WINDOW_SECONDS = 60.0


def check_widget_rate_limit(widget_id: str, limit_per_minute: Optional[int]) -> None:
    if not limit_per_minute:
        return

    now = time.time()
    count, start = _hits.get(widget_id, (0, now))
    if now - start >= _WINDOW_SECONDS:
        count, start = 0, now

    count += 1
    _hits[widget_id] = (count, start)

    if count > limit_per_minute:
        retry_after = max(1, int(_WINDOW_SECONDS - (now - start)))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="This widget has exceeded its configured rate limit. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )
