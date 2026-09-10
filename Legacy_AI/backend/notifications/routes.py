from fastapi import APIRouter, Depends, status

from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user
from backend.notifications import services
from backend.notifications.schemas import NotificationPublic, UnreadCountResponse

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=Page[NotificationPublic])
async def list_notifications(
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(get_current_user),
) -> Page[NotificationPublic]:
    """List the caller's notifications (own + org-wide), newest first."""
    items, total = await services.list_notifications(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        skip=pg.skip,
        limit=pg.limit,
    )
    return build_page(items, total, pg)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: UserPublic = Depends(get_current_user),
) -> UnreadCountResponse:
    """Number of unread notifications for the caller."""
    unread = await services.count_unread(
        current_user.organization_id, current_user.id
    )
    return UnreadCountResponse(unread=unread)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    current_user: UserPublic = Depends(get_current_user),
) -> None:
    """Mark every notification visible to the caller as read."""
    await services.mark_all_read(current_user.organization_id, current_user.id)


@router.patch("/{notification_id}/read", response_model=NotificationPublic)
async def mark_read(
    notification_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> NotificationPublic:
    """Mark a single notification as read."""
    return await services.mark_read(
        notification_id, current_user.organization_id, current_user.id
    )


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss(
    notification_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> None:
    """Dismiss (soft-delete) a notification."""
    await services.dismiss(
        notification_id, current_user.organization_id, current_user.id
    )
