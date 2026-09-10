from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from backend.auth.schemas import UpdateProfileRequest, UpdateUserRequest, UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission, require_super_admin
from backend.user import services

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=Page[UserPublic])
async def list_users(
    pg: Pagination = Depends(pagination_params),
    search: str | None = Query(default=None, description="Filter users by name or email (case-insensitive)"),
    role: str | None = Query(default=None, description="Filter users by exact role"),
    organization_id: Optional[str] = Query(default=None, description="Filter by organization"),
    sort_by: Optional[Literal["name", "email", "created_at"]] = Query(default=None),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    _: UserPublic = Depends(require_super_admin),
) -> Page[UserPublic]:
    """List all users (paginated). Optionally filter by name/email/role/organization and sort. Super admin only."""
    items, total = await services.list_users(
        skip=pg.skip,
        limit=pg.limit,
        search=search,
        role=role,
        organization_id=organization_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return build_page(items, total, pg)


@router.patch("/me", response_model=UserPublic)
async def update_my_profile(
    payload: UpdateProfileRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """Update the caller's own profile (currently: display name)."""
    return await services.update_own_profile(current_user.id, name=payload.name)


@router.post("/me/avatar", response_model=UserPublic)
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """Upload/replace the caller's profile picture. Accepts PNG, JPEG, GIF, or WEBP."""
    return await services.update_own_avatar(current_user.id, file)


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    admin: UserPublic = Depends(require_permission("edit_user")),
) -> UserPublic:
    """Admin-only: update another user's name and/or role.

    Requires org access to the target user and, for role changes, permission
    to manage both the target's current role and the new role — resolved
    dynamically from the role_permissions collection.
    """
    return await services.update_user_as_admin(user_id, payload, admin)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin: UserPublic = Depends(require_permission("delete_user")),
) -> None:
    """Admin-only: soft-delete another user. Same org/role checks as PATCH."""
    await services.delete_user_as_admin(user_id, admin)
