from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ai.tracing.context import TracingContext
from backend.auth.permissions import (
    Permission,
    assert_super_admin,
    user_has_permission,
)
from backend.auth.cache import user_cache
from backend.auth.schemas import UserPublic
from backend.auth.services import get_user_by_id
from backend.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserPublic:
    """Resolve the authenticated user from a Bearer JWT, or raise 401."""
    token = credentials.credentials
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    user = await user_cache.get_or_load(user_id, lambda: get_user_by_id(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )
    if getattr(user, "waiting_approval", "approved") != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending admin approval.",
        )
    return user


def require_permission(permission: Permission):
    """Dependency factory: authenticated user must have the given permission."""

    async def _dependency(
        current_user: UserPublic = Depends(get_current_user),
    ) -> UserPublic:
        if not await user_has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing '{permission}' permission for your role.",
            )
        return current_user

    return _dependency


async def get_current_admin(
    current_user: UserPublic = Depends(require_permission("create_user")),
) -> UserPublic:
    """Require create_user permission to provision users."""
    return current_user


async def require_super_admin(
    current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """Require the super_admin role for global operations."""
    assert_super_admin(current_user)
    return current_user


async def get_tracing_context(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> TracingContext:
    """Build a TracingContext from the authenticated user and request headers."""
    session_id = request.headers.get("X-Session-Id") or current_user.id
    return TracingContext(
        org_id=current_user.organization_id,
        user_id=current_user.id,
        session_id=session_id,
    )
