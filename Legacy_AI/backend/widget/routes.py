from fastapi import APIRouter, Body, Depends, File, Query, UploadFile, status

from backend.auth.permissions import assert_org_access, is_super_admin
from backend.auth.schemas import UserPublic
from backend.chat.schemas import SessionHistoryResponse
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission
from backend.widget import analytics_services, services
from backend.widget.schemas import (
    WidgetAnalytics,
    WidgetWebhookDeliveriesResponse,
    WidgetWebhookDeliveryResult,
    WidgetApiKeyResponse,
    WidgetConfigCreate,
    WidgetConfigPublic,
    WidgetConfigUpdate,
    WidgetImageUploadResponse,
    WidgetPreviewTokenResponse,
    WidgetSessionListItem,
    WidgetVersionListItem,
)
from typing import Optional

router = APIRouter(
    prefix="/widget-configs",
    tags=["widget-configs"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=WidgetConfigPublic, status_code=status.HTTP_201_CREATED)
async def create_widget_config(
    payload: WidgetConfigCreate,
    current_user: UserPublic = Depends(require_permission("create_widget")),
) -> WidgetConfigPublic:
    """Create a new embeddable chatbot widget, bound to either a single agent
    or the org's full supervisor (every active agent, auto-routed)."""
    assert_org_access(current_user, payload.organization_id)
    return await services.create_widget_config(payload, created_by=current_user.id)


@router.get("", response_model=Page[WidgetConfigPublic])
async def list_widget_configs(
    pg: Pagination = Depends(pagination_params),
    organization_id: Optional[str] = Query(default=None, description="Super-admin only: narrow to one organization"),
    current_user: UserPublic = Depends(require_permission("view_widget")),
) -> Page[WidgetConfigPublic]:
    """List widget configs (paginated). Super admins see every organization's
    widgets by default, or one org's via `organization_id`; everyone else is
    always scoped to their own organization."""
    if is_super_admin(current_user.role):
        if organization_id:
            items, total = await services.list_widget_configs_by_org(organization_id, skip=pg.skip, limit=pg.limit)
        else:
            items, total = await services.list_all_widget_configs(skip=pg.skip, limit=pg.limit)
    else:
        items, total = await services.list_widget_configs_by_org(
            current_user.organization_id, skip=pg.skip, limit=pg.limit
        )
    return build_page(items, total, pg)


@router.get("/{widget_id}", response_model=WidgetConfigPublic)
async def get_widget_config(
    widget_id: str,
    current_user: UserPublic = Depends(require_permission("view_widget")),
) -> WidgetConfigPublic:
    """Retrieve a single widget config by id."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return widget


@router.put("/{widget_id}", response_model=WidgetConfigPublic)
async def update_widget_config(
    widget_id: str,
    payload: WidgetConfigUpdate,
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetConfigPublic:
    """Update a widget config (branding, security, source agent, etc)."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.update_widget_config(widget_id, payload, requesting_user_id=current_user.id)


@router.post("/{widget_id}/duplicate", response_model=WidgetConfigPublic, status_code=status.HTTP_201_CREATED)
async def duplicate_widget_config(
    widget_id: str,
    current_user: UserPublic = Depends(require_permission("create_widget")),
) -> WidgetConfigPublic:
    """Duplicate a widget: copies the full draft config, allowed origins, and
    rate limit -- but never webhook secrets or the API key hash. The copy is
    named "{name} (copy)" and auto-publishes v1, same as create."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.duplicate_widget_config(widget_id, created_by=current_user.id)


@router.post("/{widget_id}/preview-token", response_model=WidgetPreviewTokenResponse)
async def create_widget_preview_token(
    widget_id: str,
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetPreviewTokenResponse:
    """Mint a short-lived (15 min), stateless token that lets the dashboard's
    preview iframe fetch this widget's DRAFT config through the public
    GET /widget/{id}/config endpoint (via its `preview_token` query param)."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.create_widget_preview_token(widget_id)


@router.patch("/{widget_id}/status", response_model=WidgetConfigPublic)
async def toggle_widget_status(
    widget_id: str,
    is_enabled: bool = Body(..., embed=True),
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetConfigPublic:
    """Enable or disable a widget (a disabled widget's public endpoints -- once
    built -- will refuse all traffic)."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.toggle_widget_status(widget_id, is_enabled)


@router.post("/{widget_id}/regenerate-key", response_model=WidgetApiKeyResponse)
async def regenerate_widget_api_key(
    widget_id: str,
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetApiKeyResponse:
    """Generate a new widget API key. Only the hash is persisted -- the
    plaintext is returned exactly once, in this response."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.regenerate_widget_api_key(widget_id)


@router.post("/{widget_id}/publish", response_model=WidgetConfigPublic)
async def publish_widget_config(
    widget_id: str,
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetConfigPublic:
    """Publish the current draft -- makes branding/layout/triggers/behavior/
    availability/accessibility/lead-capture changes visible to visitors."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.publish_widget_config(widget_id, published_by=current_user.id)


@router.post("/{widget_id}/discard-draft", response_model=WidgetConfigPublic)
async def discard_widget_draft(
    widget_id: str,
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetConfigPublic:
    """Discard unpublished draft edits, resetting to the last published version."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.discard_widget_draft(widget_id)


@router.get("/{widget_id}/versions", response_model=Page[WidgetVersionListItem])
async def list_widget_versions(
    widget_id: str,
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_widget")),
) -> Page[WidgetVersionListItem]:
    """Publish history for this widget, newest first."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    items, total = await services.list_widget_versions(widget_id, skip=pg.skip, limit=pg.limit)
    return build_page(items, total, pg)


@router.post("/{widget_id}/versions/{version}/rollback", response_model=WidgetConfigPublic)
async def rollback_widget_config(
    widget_id: str,
    version: int,
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetConfigPublic:
    """Restore a past published version as the new draft + a fresh published version."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.rollback_widget_config(widget_id, version, restored_by=current_user.id)


@router.post("/{widget_id}/upload-image", response_model=WidgetImageUploadResponse)
async def upload_widget_image(
    widget_id: str,
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetImageUploadResponse:
    """Upload a branding image (header logo, avatar, or launcher icon) for this
    widget. Accepts PNG, JPEG, GIF, or WEBP. Returns the URL only -- the
    caller (a subsequent PUT) decides which branding/layout field it fills."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    url = await services.upload_widget_image(widget_id, file)
    return WidgetImageUploadResponse(url=url)


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget_config(
    widget_id: str,
    current_user: UserPublic = Depends(require_permission("delete_widget")),
) -> None:
    """Delete a widget config."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    await services.delete_widget_config(widget_id)


@router.get("/{widget_id}/sessions", response_model=Page[WidgetSessionListItem])
async def list_widget_sessions(
    widget_id: str,
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_widget")),
) -> Page[WidgetSessionListItem]:
    """List anonymous visitor sessions for this widget (paginated, newest first)."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    items, total = await analytics_services.list_widget_sessions(widget_id, skip=pg.skip, limit=pg.limit)
    return build_page(items, total, pg)


@router.get("/{widget_id}/sessions/{visitor_session_id}/history", response_model=SessionHistoryResponse)
async def get_widget_session_history(
    widget_id: str,
    visitor_session_id: str,
    current_user: UserPublic = Depends(require_permission("view_widget")),
) -> SessionHistoryResponse:
    """Full conversation transcript for one visitor session."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await analytics_services.get_widget_session_history(widget_id, visitor_session_id)


@router.get("/{widget_id}/analytics", response_model=WidgetAnalytics)
async def get_widget_analytics(
    widget_id: str,
    current_user: UserPublic = Depends(require_permission("view_widget")),
) -> WidgetAnalytics:
    """Session/lead counts for this widget, plus a 14-day sessions trend."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await analytics_services.get_widget_analytics(widget_id)


@router.post("/{widget_id}/webhooks/{event}/test", response_model=WidgetWebhookDeliveryResult)
async def test_widget_webhook(
    widget_id: str,
    event: str,
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetWebhookDeliveryResult:
    """Synchronously deliver a sample payload (marked "test": true) to this
    event's configured URL and return the outcome."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.test_widget_webhook(widget_id, event)


@router.post("/{widget_id}/webhook-deliveries/{delivery_id}/replay", response_model=WidgetWebhookDeliveryResult)
async def replay_widget_webhook_delivery(
    widget_id: str,
    delivery_id: str,
    current_user: UserPublic = Depends(require_permission("edit_widget")),
) -> WidgetWebhookDeliveryResult:
    """Re-deliver a logged payload to the event's current URL/secret."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await services.replay_widget_webhook_delivery(widget_id, delivery_id)


@router.get("/{widget_id}/webhook-deliveries", response_model=WidgetWebhookDeliveriesResponse)
async def list_widget_webhook_deliveries(
    widget_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserPublic = Depends(require_permission("view_widget")),
) -> WidgetWebhookDeliveriesResponse:
    """Outcome log of outbound webhook deliveries (newest first, 30-day TTL)."""
    widget = await services.get_widget_config(widget_id)
    assert_org_access(current_user, widget.organization_id)
    return await analytics_services.list_widget_webhook_deliveries(widget_id, page, page_size)
