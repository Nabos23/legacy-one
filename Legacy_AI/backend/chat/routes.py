from typing import List, Optional
import os
import mimetypes
from fastapi import APIRouter, Depends, Query, Response, status, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi import HTTPException
from backend.auth.permissions import is_super_admin
from backend.auth.schemas import UserPublic
from backend.chat import services
from backend.core.attachments import process_attachment
from starlette.background import BackgroundTask
from backend.core.uploads import delete_report_file
from backend.chat.schemas import (
    ChatRequest,
    ChatResponse,
    SessionHistoryResponse,
    SessionListItem,
    SessionPublic,
    SessionRenameRequest,
)
from backend.dependencies import get_current_user, require_permission

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/session",
    response_model=SessionPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize a LangGraph session for the user's organization",
)
async def create_session(
    organization_id: Optional[str] = Query(None),
    current_user: UserPublic = Depends(require_permission("create_chat_session")),
) -> SessionPublic:
    """Load org agents/tools, build the LangGraph, create a thread and return thread_id."""
    target_org = (
        organization_id
        if organization_id and is_super_admin(current_user.role)
        else current_user.organization_id
    )
    return await services.create_session(
        organization_id=target_org,
        user_id=current_user.id,
    )


@router.get(
    "/sessions",
    response_model=List[SessionListItem],
    summary="List all chat sessions for the current user",
)
async def list_sessions(
    organization_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    current_user: UserPublic = Depends(require_permission("view_chat_session")),
) -> List[SessionListItem]:
    if is_super_admin(current_user.role):
        return await services.get_sessions_for_admin(organization_id, agent_id=agent_id)
    return await services.get_user_sessions(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        agent_id=agent_id,
    )


@router.patch(
    "/sessions/{thread_id}",
    response_model=SessionListItem,
    summary="Rename a chat session",
)
async def rename_session(
    thread_id: str,
    payload: SessionRenameRequest,
    current_user: UserPublic = Depends(require_permission("edit_chat_session")),
) -> SessionListItem:
    """Manually set the session's title (overrides the auto-generated one)."""
    return await services.rename_session(
        thread_id=thread_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        name=payload.name,
    )


@router.delete(
    "/sessions/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session (soft-delete)",
)
async def delete_session(
    thread_id: str,
    current_user: UserPublic = Depends(require_permission("delete_chat_session")),
) -> Response:
    """Soft-delete a session and its conversation history."""
    await services.delete_session(
        thread_id=thread_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/sessions/{thread_id}/history",
    response_model=SessionHistoryResponse,
    summary="Get full conversation history for a session",
)
async def get_session_history(
    thread_id: str,
    organization_id: Optional[str] = Query(None),
    current_user: UserPublic = Depends(require_permission("view_chat_session")),
) -> SessionHistoryResponse:
    if is_super_admin(current_user.role):
        return await services.get_session_history_for_admin(thread_id)
    return await services.get_session_history(
        thread_id=thread_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )


@router.post(
    "/message",
    response_model=ChatResponse,
    summary="Send a message into an existing LangGraph session",
)
async def send_message(
    payload: ChatRequest,
    current_user: UserPublic = Depends(require_permission("create_chat")),
) -> ChatResponse:
    """Route the message through the supervisor → sub-agent graph and return the response."""
    target_org = (
        payload.organization_id
        if payload.organization_id and is_super_admin(current_user.role)
        else current_user.organization_id
    )
    return await services.send_message(
        thread_id=payload.thread_id,
        message=payload.message,
        user_id=current_user.id,
        organization_id=target_org,
        attachments=payload.attachments,
    )


@router.post(
    "/message/stream",
    summary="Send a message into an existing LangGraph session, streaming live routing/tool-call events (SSE)",
)
async def send_message_stream(
    payload: ChatRequest,
    current_user: UserPublic = Depends(require_permission("create_chat")),
) -> StreamingResponse:
    """Same as /chat/message, but streams `routing`/`tool_call` progress events
    as Server-Sent Events while the turn runs, ending in a `done` event with
    the same payload shape as the blocking endpoint's response."""
    target_org = (
        payload.organization_id
        if payload.organization_id and is_super_admin(current_user.role)
        else current_user.organization_id
    )
    # Runs everything that can 404 (session/agents not found) BEFORE the
    # streaming response starts, since its status code is committed as soon
    # as the first chunk is sent.
    ctx = await services.send_message_stream_prepare(
        thread_id=payload.thread_id,
        message=payload.message,
        user_id=current_user.id,
        organization_id=target_org,
        attachments=payload.attachments,
    )
    return StreamingResponse(
        services.send_message_stream(ctx),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/attachments",
    summary="Process a chat attachment (document → text, or image → data URL + OCR)",
)
async def process_chat_attachment(
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(require_permission("create_chat")),
) -> dict:
    """Turn an uploaded file into something the agent can consume so the client
    can attach it to a chat message. Documents (PDF/Word/Excel/PowerPoint/text/
    code) come back as extracted text; images come back as a base64 data URL
    (for vision) plus best-effort OCR text. Unsupported types are rejected.
    The file is never stored."""
    return await process_attachment(file)


@router.get(
    "/reports/{filename}",
    summary="Download a generated PDF report",
)
async def download_report(
    filename: str,
    current_user: UserPublic = Depends(get_current_user),
):
    """Serve a generated report PDF.  Requires a valid session — reports are
    never publicly accessible.  The filename is sanitized against path traversal."""
    filepath = await services.get_report_for_download(filename)
    safe_name = os.path.basename(filename)

    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=safe_name,
        background=BackgroundTask(delete_report_file, safe_name),
    )


@router.get(
    "/reports/{filename}/preview",
    summary="Preview a generated report/image inline (does not delete the file)",
)
async def preview_report(
    filename: str,
    current_user: UserPublic = Depends(get_current_user),
):
    """Serve a generated report/image for inline rendering (e.g. chat thumbnails,
    lightbox). Unlike /reports/{filename}, this is side-effect free and can be
    hit repeatedly (renders, reloads) without consuming the file. Still requires
    a valid session and sanitizes the filename against path traversal."""
    filepath, media_type = await services.get_report_for_preview(filename)
    safe_name = os.path.basename(filename)

    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=safe_name,
        # Deliberately no `background=BackgroundTask(delete_report_file, ...)` —
        # this route is read-only and must be safe to hit repeatedly.
    )