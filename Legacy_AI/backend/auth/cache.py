import logging

from backend.core.config import settings
from backend.core.ttl_cache import AsyncTTLCache

logger = logging.getLogger(__name__)

_TTL = settings.AUTH_CACHE_TTL_SECONDS

user_cache: AsyncTTLCache = AsyncTTLCache(_TTL, name="auth.user")

team_permissions_cache: AsyncTTLCache = AsyncTTLCache(_TTL, name="auth.team_permissions")


def invalidate_user(user_id: str | None) -> None:
    if user_id:
        user_cache.invalidate(str(user_id))


def invalidate_team_permissions(user_ids: object = None) -> None:
    if user_ids is None:
        team_permissions_cache.clear()
        return
    if isinstance(user_ids, (str, bytes)):
        team_permissions_cache.invalidate(str(user_ids))
        return
    try:
        for uid in user_ids:  # type: ignore[union-attr]
            if uid:
                team_permissions_cache.invalidate(str(uid))
    except TypeError:
        team_permissions_cache.clear()


def invalidate_all() -> None:
    user_cache.clear()
    team_permissions_cache.clear()


def stats() -> dict:
    return {
        "user": user_cache.stats(),
        "team_permissions": team_permissions_cache.stats(),
    }
