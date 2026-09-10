from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from backend.widget import public_services
from backend.widget.dependencies import WidgetContext, get_widget_context
from backend.widget.public_schemas import (
    WidgetHistoryResponse,
    WidgetAttachmentUploadResponse,
    WidgetFeedbackRequest,
    WidgetLeadRequest,
    WidgetMessageRequest,
    WidgetMessageResponse,
    WidgetPublicConfig,
    WidgetSessionResponse,
)
from backend.widget.services import verify_preview_token

# No Depends(get_current_user) at the router level -- this is the ONE
# authenticated-JWT exception in the codebase, by design. Every route below
# instead depends on get_widget_context, which enforces the Origin allowlist
# (or widget API key) as its own, independent access-control boundary.
router = APIRouter(prefix="/widget", tags=["widget-public"])


@router.get("/{widget_id}/config", response_model=WidgetPublicConfig)
async def get_public_widget_config(
    preview_token: Optional[str] = Query(
        default=None,
        description="Short-lived draft-preview token minted via POST /widget-configs/{id}/preview-token.",
    ),
    ctx: WidgetContext = Depends(get_widget_context),
) -> WidgetPublicConfig:
    """Public branding/behavior/trigger/availability/accessibility config for
    rendering the widget shell. Never includes security settings, webhook
    URLs/secrets, agent_id, or organization_id.

    With a valid `preview_token`, serves the DRAFT config instead of the
    published snapshot -- how the dashboard's builder previews unpublished
    edits. Origin/API-key checks apply unchanged (get_widget_context above)."""
    if preview_token is not None:
        if not verify_preview_token(ctx.widget_id, preview_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired preview token.",
            )
        return await public_services.get_widget_draft_public_config(ctx)
    return WidgetPublicConfig(
        widget_id=ctx.widget_id,
        branding=ctx.branding,
        layout=ctx.layout,
        triggers=ctx.triggers,
        behavior={
            "response_language": ctx.behavior.get("response_language", "auto"),
            "welcome_sound": ctx.behavior.get("welcome_sound", False),
            "allow_attachments": ctx.behavior.get("allow_attachments", False),
        },
        availability=ctx.availability,
        accessibility=ctx.accessibility,
        lead_fields=ctx.lead_fields,
    )


@router.post("/{widget_id}/session", response_model=WidgetSessionResponse)
async def create_widget_session(
    request: Request,
    ctx: WidgetContext = Depends(get_widget_context),
) -> WidgetSessionResponse:
    """Start an anonymous visitor session. The client stores the returned
    visitor_session_id (e.g. in localStorage) and sends it back on every
    subsequent /message call."""
    request_meta = {
        "origin": request.headers.get("origin"),
        "user_agent": request.headers.get("user-agent"),
    }
    return await public_services.create_widget_session(ctx, request_meta)


@router.get("/{widget_id}/session/{visitor_session_id}/messages", response_model=WidgetHistoryResponse)
async def get_widget_session_messages(
    visitor_session_id: str,
    ctx: WidgetContext = Depends(get_widget_context),
) -> WidgetHistoryResponse:
    """Returning visitor's transcript (last 50 turns, flattened to role/content
    pairs) so the embed can restore the conversation on open. Guarded by the
    same origin/API-key context as every other public route, plus possession
    of the opaque visitor_session_id."""
    return await public_services.get_widget_session_messages(ctx, visitor_session_id)


@router.post("/{widget_id}/lead", status_code=204)
async def submit_widget_lead(
    payload: WidgetLeadRequest,
    ctx: WidgetContext = Depends(get_widget_context),
) -> None:
    """Store the pre-chat lead-capture form values against this visitor's
    session and fire the `lead_captured` webhook (if configured)."""
    await public_services.submit_widget_lead(ctx, payload.visitor_session_id, payload.values)


@router.post("/{widget_id}/feedback", status_code=204)
async def submit_widget_feedback(
    payload: WidgetFeedbackRequest,
    ctx: WidgetContext = Depends(get_widget_context),
) -> None:
    """Thumbs up/down on one assistant message. Upserts, so a visitor can
    change their mind without creating duplicate rows."""
    await public_services.submit_widget_feedback(
        ctx, payload.visitor_session_id, payload.message_id, payload.rating, payload.message_excerpt
    )


@router.post("/{widget_id}/upload", response_model=WidgetAttachmentUploadResponse)
async def upload_widget_attachment(
    visitor_session_id: str = Form(...),
    file: UploadFile = File(...),
    ctx: WidgetContext = Depends(get_widget_context),
) -> WidgetAttachmentUploadResponse:
    """Upload a file attachment for a visitor message. Only available when the
    widget's published behavior.allow_attachments is on. Accepts PNG, JPEG,
    GIF, WEBP, PDF, or plain text (max 10MB). The returned `attachment` is
    what the client sends back inside the /message `attachments` list."""
    return await public_services.upload_widget_attachment(ctx, visitor_session_id, file)


@router.post("/{widget_id}/message", response_model=WidgetMessageResponse)
async def send_widget_message(
    payload: WidgetMessageRequest,
    ctx: WidgetContext = Depends(get_widget_context),
) -> WidgetMessageResponse:
    return await public_services.send_widget_message(
        ctx, payload.visitor_session_id, payload.message, attachments=payload.attachments
    )


@router.post("/{widget_id}/message/stream")
async def send_widget_message_stream(
    payload: WidgetMessageRequest,
    ctx: WidgetContext = Depends(get_widget_context),
) -> StreamingResponse:
    # Everything that can 404 (bad session) runs BEFORE the StreamingResponse
    # starts, since its status code is committed as soon as the first chunk
    # is sent -- same reasoning as chat/direct_agent's own stream routes.
    kind, inner_ctx = await public_services.prepare_widget_message_stream(
        ctx, payload.visitor_session_id, payload.message, attachments=payload.attachments
    )
    return StreamingResponse(
        public_services.widget_message_stream(kind, inner_ctx),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
