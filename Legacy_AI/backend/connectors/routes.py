"""Connector routes — thin handlers delegating all logic to services.py.

Two routers:
  router               JWT-protected, all /api/connectors/** endpoints
  callback_router      Public, /api/auth/connector/callback (browser OAuth redirect)
"""

import asyncio
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from backend.auth.schemas import UserPublic
from backend.connectors import services
from backend.connectors.schemas import (
    AuthUrlResponse,
    ConnectorActiveUpdate,
    ConnectorCredentialsSave,
    ConnectorRegistryItem,
    ConnectorRegistryPage,
    ConnectorSetupInfo,
    ConnectorStatus,
    ConnectorStatusBatchRequest,
    ConnectorStatusBatchResponse,
    ConnectorStatusEntry,
    ConnectorTestConnectionResult,
    ConnectorVisibilityUpdate,
    MessageResponse,
)
from backend.core.config import settings
from backend.dependencies import get_current_user, require_super_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/connectors",
    tags=["connectors"],
    dependencies=[Depends(get_current_user)],
)

callback_router = APIRouter(tags=["connectors"])


# ─── Registry ─────────────────────────────────────────────────────────────────

@router.get("/registry", response_model=list[ConnectorRegistryItem])
async def list_registry(
    current_user: UserPublic = Depends(get_current_user),
) -> list[ConnectorRegistryItem]:
    """Return visible connector definitions (client-facing)."""
    return await services.get_registry()


@router.get("/registry/admin", response_model=ConnectorRegistryPage)
async def list_registry_admin(
    _: UserPublic = Depends(require_super_admin),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=200, description="Items per page"),
    q: str = Query("", description="Search term (name, description, category)"),
    category: str = Query("", description="Filter by exact category name"),
    sort_by: Optional[Literal["name", "category"]] = Query(default=None),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
) -> ConnectorRegistryPage:
    """Return all connectors including hidden ones, paginated (super admin only)."""
    return await services.get_registry_admin(
        page=page, page_size=page_size, search=q, category=category, sort_by=sort_by, sort_order=sort_order
    )


@router.patch("/registry/{connector_id}/visibility", response_model=ConnectorRegistryItem)
async def set_visibility(
    connector_id: str,
    payload: ConnectorVisibilityUpdate,
    _: UserPublic = Depends(require_super_admin),
) -> ConnectorRegistryItem:
    """Show or hide a connector in the catalog (super admin only)."""
    return await services.set_connector_visibility(connector_id, payload.is_visible)


@router.patch("/registry/{connector_id}/active", response_model=ConnectorRegistryItem)
async def set_active(
    connector_id: str,
    payload: ConnectorActiveUpdate,
    _: UserPublic = Depends(require_super_admin),
) -> ConnectorRegistryItem:
    """Enable or disable a connector in the catalog (super admin only)."""
    return await services.set_connector_active(connector_id, payload.is_active)


# ─── Setup & Credentials ──────────────────────────────────────────────────────

@router.get("/{connector_id}/setup", response_model=ConnectorSetupInfo)
async def get_setup_info(
    connector_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> ConnectorSetupInfo:
    connector = await services.get_connector(connector_id)
    owner_id = services.resolve_owner_id(
        connector, current_user.id or "", current_user.organization_id
    )
    return await services.get_setup_info(connector_id, owner_id)


@router.post("/{connector_id}/configure", response_model=MessageResponse)
async def save_credentials(
    connector_id: str,
    payload: ConnectorCredentialsSave,
    current_user: UserPublic = Depends(get_current_user),
) -> MessageResponse:
    connector = await services.get_connector(connector_id)
    owner_id = services.resolve_owner_id(
        connector, current_user.id or "", current_user.organization_id
    )
    await services.save_credentials(connector_id, owner_id, payload)
    return MessageResponse(message="Credentials saved successfully.")


@router.delete("/{connector_id}/configure", response_model=MessageResponse)
async def delete_credentials(
    connector_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> MessageResponse:
    connector = await services.get_connector(connector_id)
    owner_id = services.resolve_owner_id(
        connector, current_user.id or "", current_user.organization_id
    )
    await services.delete_credentials(connector_id, owner_id)
    return MessageResponse(message="Credentials removed.")


# ─── OAuth ────────────────────────────────────────────────────────────────────

@router.get("/{connector_id}/auth-url", response_model=AuthUrlResponse)
async def get_auth_url(
    connector_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> AuthUrlResponse:
    connector = await services.get_connector(connector_id)
    owner_id = services.resolve_owner_id(
        connector, current_user.id or "", current_user.organization_id
    )

    status = await services.get_connection_status(connector_id, owner_id)
    if status.connected:
        return AuthUrlResponse(url="", already_connected=True)

    url = await services.build_auth_url(connector_id, owner_id)
    return AuthUrlResponse(url=url)


@callback_router.get("/api/auth/connector/callback")
async def oauth_callback(
    state: str = Query(...),
    code: str = Query(None),
    error: str = Query(None),
) -> RedirectResponse:
    """Universal OAuth callback. The `state` param links back to the connector + owner."""
    frontend_base = settings.FRONTEND_URL.rstrip("/")

    if error:
        logger.warning("Connector OAuth error from provider: %s", error)
        return RedirectResponse(
            url=f"{frontend_base}/client/connectors?connector=error&reason={error}"
        )

    if not code:
        logger.warning("Connector OAuth callback missing code param")
        return RedirectResponse(
            url=f"{frontend_base}/client/connectors?connector=error&reason=missing_code"
        )

    try:
        provider_id = await services.exchange_code(state, code)
    except Exception as exc:
        logger.exception("Connector OAuth exchange failed: %s", exc)
        return RedirectResponse(
            url=f"{frontend_base}/client/connectors?connector=error&reason=exchange_failed"
        )

    return RedirectResponse(
        url=f"{frontend_base}/client/connectors?connector=connected&provider={provider_id}"
    )


# ─── Status & Disconnect ──────────────────────────────────────────────────────

@router.post("/status", response_model=ConnectorStatusBatchResponse)
async def get_status_batch(
    payload: ConnectorStatusBatchRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> ConnectorStatusBatchResponse:
    ids = list(dict.fromkeys(i for i in payload.connector_ids if i))
    if not ids:
        return ConnectorStatusBatchResponse(statuses={})

    async def resolve(connector_id: str) -> tuple[str, ConnectorStatusEntry]:
        try:
            connector = await services.get_connector(connector_id)
            owner_id = services.resolve_owner_id(
                connector, current_user.id or "", current_user.organization_id
            )
            status = await services.get_connection_status(connector_id, owner_id)
            return connector_id, ConnectorStatusEntry(**status.model_dump())
        except Exception as exc:
            logger.warning("[connectors] status check failed for %s: %s", connector_id, exc)
            return connector_id, ConnectorStatusEntry(connected=False, check_failed=True)

    results = await asyncio.gather(*(resolve(i) for i in ids))
    return ConnectorStatusBatchResponse(statuses=dict(results))


@router.get("/{connector_id}/status", response_model=ConnectorStatus)
async def get_status(
    connector_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> ConnectorStatus:
    connector = await services.get_connector(connector_id)
    owner_id = services.resolve_owner_id(
        connector, current_user.id or "", current_user.organization_id
    )
    return await services.get_connection_status(connector_id, owner_id)


@router.post("/{connector_id}/disconnect", response_model=MessageResponse)
async def disconnect(
    connector_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> MessageResponse:
    connector = await services.get_connector(connector_id)
    owner_id = services.resolve_owner_id(
        connector, current_user.id or "", current_user.organization_id
    )
    await services.disconnect(connector_id, owner_id)
    return MessageResponse(message="Connector disconnected.")


@router.post("/{connector_id}/test-connection", response_model=ConnectorTestConnectionResult)
async def test_connection(
    connector_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> ConnectorTestConnectionResult:
    """On-demand probe (the UI 'Test connection' button). Read-only — unlike
    `/status`, this never mutates the connector's persisted status."""
    connector = await services.get_connector(connector_id)
    owner_id = services.resolve_owner_id(
        connector, current_user.id or "", current_user.organization_id
    )
    return await services.test_connection(connector_id, owner_id)


# ─── Actions ──────────────────────────────────────────────────────────────────

@router.post("/{connector_id}/actions/{action}")
async def run_action(
    connector_id: str,
    action: str,
    params: dict[str, Any] | None = None,
    current_user: UserPublic = Depends(get_current_user),
) -> Any:
    connector = await services.get_connector(connector_id)
    owner_id = services.resolve_owner_id(
        connector, current_user.id or "", current_user.organization_id
    )
    return await services.perform_action(connector_id, owner_id, action, params)


# ─── Slack Webhook ────────────────────────────────────────────────────────────

@callback_router.post("/api/connectors/slack/webhook")
async def slack_webhook(
    request: Request,
    connector_id: str = Query(..., description="connector_id for the Slack installation"),
    owner_id: str = Query(..., description="organization_id that owns this installation"),
) -> dict:
    """Slack Events API ingress. Verifies HMAC-SHA256 signature before processing."""
    raw_body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    valid = await services.verify_slack_signature(
        raw_body, timestamp, signature, connector_id, owner_id
    )
    if not valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Invalid Slack signature.")

    payload = await request.json()

    # URL verification challenge (required when first registering the endpoint).
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    event_type = payload.get("event", {}).get("type")
    logger.info(
        "Slack event [connector=%s owner=%s type=%s]",
        connector_id,
        owner_id,
        event_type,
    )

    if event_type in ("tokens_revoked", "app_uninstalled"):
        logger.warning(
            "Slack revoked access [connector=%s owner=%s type=%s] — disconnecting.",
            connector_id, owner_id, event_type,
        )
        await services.disconnect(connector_id, owner_id, reason="slack_revoked")

    return {"ok": True}
