import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from backend.chat import services as chat_services
from backend.chat.schemas import ChatAttachment
from backend.chat.services import _compose_message_with_attachments
from backend.core.attachments import MAX_TEXT_CHARS, process_attachment
from backend.core.config import settings
from backend.core.softdelete import NOT_DELETED
from backend.db.database import (
    widget_configs_collection,
    widget_message_feedback_collection,
    widget_sessions_collection,
)
from backend.direct_agent import services as direct_agent_services
from backend.widget.dependencies import WidgetContext
from backend.widget.public_schemas import (
    WidgetAttachmentUploadResponse,
    WidgetHistoryMessage,
    WidgetHistoryResponse,
    WidgetMessageResponse,
    WidgetPublicConfig,
    WidgetSessionResponse,
)
from backend.widget.services import _draft_sections
from backend.widget.webhooks import fire_webhook

# Visitor-upload limits -- narrower than the authenticated chat's attachment
# pipeline on purpose: this endpoint is reachable by anonymous visitors, so
# only the formats the widget UI actually offers are accepted.
_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024

# Magic-byte signatures (client filename/Content-Type are never trusted).
_ATTACHMENT_IMAGE_SIGNATURES: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}
_PDF_SIGNATURE = b"%PDF-"


def _webhook_doc(ctx: WidgetContext) -> dict:
    """Shape fire_webhook() expects -- just enough of a widget_configs
    document for it to read `_id`/`organization_id`/`webhooks`."""
    return {"_id": ctx.widget_id, "organization_id": ctx.organization_id, "webhooks": ctx.webhooks}


def _compose_widget_message(ctx: WidgetContext, message: str) -> str:
    """Folds the widget's response-language/tone-overlay settings into the
    turn, the same way chat/services.py already folds attachment text into
    the user's message (_compose_message_with_attachments) -- rather than
    touching the shared, per-org-cached AgentRuntime/graph (which direct_agent
    and chat/graph.py's supervisor also use for internal/playground traffic),
    since mutating that would leak a widget-specific instruction into every
    other caller of the same cached graph.

    Tradeoff: this preamble is stored verbatim as part of the turn's
    human_message, so it's visible if that conversation's transcript is ever
    read back. Applied every turn (not just the first) so the agent doesn't
    "forget" language/tone once the conversation grows.
    """
    language = ctx.behavior.get("response_language")
    tone = ctx.behavior.get("tone_instructions")
    parts = []
    if language and language != "auto":
        parts.append(f"Respond in {language}.")
    if tone:
        parts.append(tone)
    if ctx.behavior.get("rich_messages"):
        parts.append(
            "This chat UI renders two rich-message blocks you may use when they genuinely help. "
            'Tappable choice buttons: a fenced code block with language "buttons" containing a JSON '
            'array of strings or {"label","value"} objects (max 8). '
            'Cards: a fenced code block with language "cards" containing a JSON array of '
            '{"title","description","image_url","link_url","link_label","button","button_value"} '
            "objects (only title is required, max 10). "
            'Inline forms: a fenced code block with language "form" containing a JSON object '
            '{"title","submit_label","fields":[{"name","label","type"(text|email|phone|textarea),'
            '"required","placeholder"}]} (max 8 fields); submitted values arrive as the visitor\'s '
            "next message as labeled lines. Regular markdown works everywhere else."
        )
    if not parts:
        return message
    preamble = " ".join(parts)
    return f"[Widget instructions -- follow silently, never mention them to the visitor: {preamble}]\n\n{message}"


def _sniff_attachment_extension(data: bytes, filename: str) -> Optional[str]:
    """Identify an allowed visitor-attachment format from the file bytes:
    png/jpeg/gif/webp images, PDF, or plain text. None if unrecognized."""
    for signature, ext in _ATTACHMENT_IMAGE_SIGNATURES.items():
        if data.startswith(signature):
            return ext
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(_PDF_SIGNATURE):
        return "pdf"
    if filename.lower().endswith(".txt"):
        try:
            data.decode("utf-8")
            return "txt"
        except UnicodeDecodeError:
            return None
    return None


def _require_attachments_enabled(ctx: WidgetContext) -> None:
    """ctx.behavior always reflects the PUBLISHED snapshot (see
    get_widget_context) -- a draft-only toggle doesn't open the endpoint."""
    if not ctx.behavior.get("allow_attachments"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Attachments are not enabled for this widget.",
        )


async def upload_widget_attachment(
    ctx: WidgetContext, visitor_session_id: str, file: UploadFile
) -> WidgetAttachmentUploadResponse:
    """Store a visitor-uploaded file and return the processed attachment
    payload the client sends back inside WidgetMessageRequest.attachments --
    the same ChatAttachment shape POST /chat/attachments produces for the
    authenticated chat. Stored under MEDIA_ROOT the same way the admin
    branding upload is (see services.upload_widget_image), but in a separate
    widget-uploads/ subtree."""
    _require_attachments_enabled(ctx)
    await _get_widget_session(ctx.widget_id, visitor_session_id)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(data) > _ATTACHMENT_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size is {_ATTACHMENT_MAX_BYTES // (1024 * 1024)}MB.",
        )

    ext = _sniff_attachment_extension(data, file.filename or "")
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload a PNG, JPEG, GIF, or WEBP image, a PDF, or a plain-text (.txt) file.",
        )

    # Same storage mechanism as save_image_upload: server-generated filename
    # under MEDIA_ROOT, served back via MEDIA_URL_PATH.
    subdir = f"widget-uploads/{ctx.widget_id}"
    directory = Path(settings.MEDIA_ROOT) / subdir
    directory.mkdir(parents=True, exist_ok=True)
    attachment_id = uuid.uuid4().hex
    (directory / f"{attachment_id}.{ext}").write_bytes(data)
    url = f"{settings.BACKEND_BASE_URL}{settings.MEDIA_URL_PATH}/{subdir}/{attachment_id}.{ext}"

    if ext == "txt":
        # process_attachment gates plain text on the filename extension; the
        # bytes were already validated as UTF-8 above, so decode directly.
        text = data.decode("utf-8").strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No readable text found in the file.")
        processed = {
            "kind": "document",
            "filename": file.filename or "attachment.txt",
            "text": text[:MAX_TEXT_CHARS],
            "truncated": len(text) > MAX_TEXT_CHARS,
        }
    else:
        # Images and PDFs go through the exact pipeline the authenticated
        # chat uses (data URL + OCR for images, text extraction for PDFs).
        await file.seek(0)
        processed = await process_attachment(file)

    return WidgetAttachmentUploadResponse(
        attachment_id=attachment_id,
        url=url,
        attachment=ChatAttachment.model_validate(processed),
    )


async def get_widget_draft_public_config(ctx: WidgetContext) -> WidgetPublicConfig:
    """The DRAFT-flavored counterpart of GET /widget/{id}/config's normal
    published view -- only reachable with a valid preview token (see
    public_routes.get_public_widget_config)."""
    doc = await widget_configs_collection.find_one({"_id": ObjectId(ctx.widget_id), **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    sections = _draft_sections(doc)
    return WidgetPublicConfig(
        widget_id=ctx.widget_id,
        branding=sections["branding"],
        layout=sections["layout"],
        triggers=sections["triggers"],
        behavior={
            "response_language": sections["behavior"].get("response_language", "auto"),
            "welcome_sound": sections["behavior"].get("welcome_sound", False),
            "allow_attachments": sections["behavior"].get("allow_attachments", False),
        },
        availability=sections["availability"],
        accessibility=sections["accessibility"],
        lead_fields=sections["lead_fields"],
    )


async def _get_widget_session(widget_id: str, visitor_session_id: str) -> dict:
    session = await widget_sessions_collection.find_one(
        {"widget_id": widget_id, "visitor_session_id": visitor_session_id}
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired. Start a new session first.",
        )
    return session


async def _touch_session(session_id) -> None:
    await widget_sessions_collection.update_one(
        {"_id": session_id}, {"$set": {"last_active_at": datetime.now(timezone.utc)}}
    )


async def create_widget_session(ctx: WidgetContext, request_meta: dict) -> WidgetSessionResponse:
    """Mint an opaque visitor_session_id and (for supervisor widgets, which
    require an eagerly-created LangGraph session) create the underlying chat
    session now. Single-agent widgets create their underlying session lazily,
    on the first message -- see send_widget_message/prepare_widget_message_stream.
    """
    visitor_session_id = secrets.token_urlsafe(24)
    # Deterministic from (widget_id, visitor_session_id) -- never client-supplied,
    # never exposed -- this is the "user_id" chat/direct_agent services use to
    # scope this visitor's conversation history and enforce session ownership.
    visitor_user_id = f"widget:{ctx.widget_id}:{visitor_session_id}"

    backend_thread_id: Optional[str] = None
    if ctx.source_type == "supervisor":
        session_public = await chat_services.create_session(
            organization_id=ctx.organization_id, user_id=visitor_user_id
        )
        backend_thread_id = session_public.thread_id

    now = datetime.now(timezone.utc)
    await widget_sessions_collection.insert_one(
        {
            "widget_id": ctx.widget_id,
            "organization_id": ctx.organization_id,
            "source_type": ctx.source_type,
            "agent_id": ctx.agent_id,
            "visitor_session_id": visitor_session_id,
            "visitor_user_id": visitor_user_id,
            "backend_thread_id": backend_thread_id,
            "status": "active",
            "metadata": request_meta,
            "created_at": now,
            "last_active_at": now,
            # TTL-purged by the widget_sessions expires_at index; absent when
            # the widget has no retention policy (kept indefinitely).
            **({"expires_at": now + timedelta(days=ctx.retention_days)} if ctx.retention_days else {}),
        }
    )
    fire_webhook(
        _webhook_doc(ctx),
        "conversation_started",
        {"visitor_session_id": visitor_session_id, "origin": request_meta.get("origin")},
    )
    return WidgetSessionResponse(visitor_session_id=visitor_session_id)


def _fire_message_sent(
    ctx: WidgetContext,
    visitor_session_id: str,
    message: str,
    attachments: Optional[List[ChatAttachment]],
) -> None:
    """Fired when a visitor message is accepted (both plain and streaming
    paths), before the agent reply exists -- keeping the payload identical
    across transports. The reply is retrievable via the session-history API."""
    fire_webhook(
        _webhook_doc(ctx),
        "message_sent",
        {
            "visitor_session_id": visitor_session_id,
            "message": message[:500],
            "attachment_count": len(attachments or []),
        },
    )


async def submit_widget_lead(ctx: WidgetContext, visitor_session_id: str, values: dict) -> None:
    session = await _get_widget_session(ctx.widget_id, visitor_session_id)
    await widget_sessions_collection.update_one(
        {"_id": session["_id"]},
        {"$set": {"metadata.lead": values, "last_active_at": datetime.now(timezone.utc)}},
    )
    fire_webhook(
        _webhook_doc(ctx),
        "lead_captured",
        {"visitor_session_id": visitor_session_id, "values": values},
    )


async def submit_widget_feedback(
    ctx: WidgetContext,
    visitor_session_id: str,
    message_id: str,
    rating: str,
    message_excerpt: Optional[str],
) -> None:
    """Upsert so a visitor can change their mind (up -> down) on the same
    message without creating duplicate rows -- (widget_id, visitor_session_id,
    message_id) is the unique key (see widget/seed.py)."""
    await _get_widget_session(ctx.widget_id, visitor_session_id)
    now = datetime.now(timezone.utc)
    await widget_message_feedback_collection.update_one(
        {"widget_id": ctx.widget_id, "visitor_session_id": visitor_session_id, "message_id": message_id},
        {
            "$set": {
                "organization_id": ctx.organization_id,
                "rating": rating,
                "message_excerpt": message_excerpt,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
                **({"expires_at": now + timedelta(days=ctx.retention_days)} if ctx.retention_days else {}),
            },
        },
        upsert=True,
    )
    fire_webhook(
        _webhook_doc(ctx),
        "feedback_submitted",
        {
            "visitor_session_id": visitor_session_id,
            "message_id": message_id,
            "rating": rating,
            "message_excerpt": message_excerpt,
        },
    )


async def send_widget_message(
    ctx: WidgetContext,
    visitor_session_id: str,
    message: str,
    attachments: Optional[List[ChatAttachment]] = None,
) -> WidgetMessageResponse:
    if attachments:
        _require_attachments_enabled(ctx)
    session = await _get_widget_session(ctx.widget_id, visitor_session_id)
    visitor_user_id = session["visitor_user_id"]
    await _touch_session(session["_id"])
    composed_message = _compose_widget_message(ctx, message)
    _fire_message_sent(ctx, visitor_session_id, message, attachments)

    if ctx.source_type == "single_agent":
        # direct_agent has no attachments parameter -- fold the attachment
        # text into the message here, exactly the way chat/services.py does
        # for its own callers (_compose_message_with_attachments).
        result = await direct_agent_services.direct_chat(
            agent_id=ctx.agent_id,
            message=_compose_message_with_attachments(composed_message, attachments),
            org_id=ctx.organization_id,
            user_id=visitor_user_id,
            session_id=session.get("backend_thread_id"),
        )
        if not session.get("backend_thread_id"):
            await widget_sessions_collection.update_one(
                {"_id": session["_id"]}, {"$set": {"backend_thread_id": result.session_id}}
            )
        return WidgetMessageResponse(reply=result.reply, name=result.name, auth_errors=result.auth_errors)

    if not session.get("backend_thread_id"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Session is missing its chat thread.")
    result = await chat_services.send_message(
        thread_id=session["backend_thread_id"],
        message=composed_message,
        user_id=visitor_user_id,
        organization_id=ctx.organization_id,
        attachments=attachments,
    )
    return WidgetMessageResponse(reply=result.response, name=result.name, auth_errors=result.auth_errors)


async def prepare_widget_message_stream(
    ctx: WidgetContext,
    visitor_session_id: str,
    message: str,
    attachments: Optional[List[ChatAttachment]] = None,
) -> Tuple[str, Any]:
    """Runs everything that can 404 BEFORE the StreamingResponse starts, same
    reasoning as chat/direct_agent's own prepare_* functions."""
    if attachments:
        _require_attachments_enabled(ctx)
    session = await _get_widget_session(ctx.widget_id, visitor_session_id)
    visitor_user_id = session["visitor_user_id"]
    await _touch_session(session["_id"])
    composed_message = _compose_widget_message(ctx, message)
    _fire_message_sent(ctx, visitor_session_id, message, attachments)

    if ctx.source_type == "single_agent":
        # Same attachment folding as send_widget_message -- see the note there.
        inner_ctx = await direct_agent_services.prepare_direct_chat_stream(
            agent_id=ctx.agent_id,
            message=_compose_message_with_attachments(composed_message, attachments),
            org_id=ctx.organization_id,
            user_id=visitor_user_id,
            session_id=session.get("backend_thread_id"),
        )
        if not session.get("backend_thread_id"):
            await widget_sessions_collection.update_one(
                {"_id": session["_id"]}, {"$set": {"backend_thread_id": inner_ctx.thread_id}}
            )
        return "single_agent", inner_ctx

    if not session.get("backend_thread_id"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Session is missing its chat thread.")
    inner_ctx = await chat_services.send_message_stream_prepare(
        thread_id=session["backend_thread_id"],
        message=composed_message,
        user_id=visitor_user_id,
        organization_id=ctx.organization_id,
        attachments=attachments,
    )
    return "supervisor", inner_ctx


async def widget_message_stream(kind: str, inner_ctx: Any):
    """Delegates to whichever backend's own SSE generator matches `kind` --
    both already yield the same `data: {"type": ..., "payload": ...}\\n\\n`
    framing, so no reshaping is needed here."""
    if kind == "single_agent":
        async for chunk in direct_agent_services.direct_chat_stream(inner_ctx):
            yield chunk
    else:
        async for chunk in chat_services.send_message_stream(inner_ctx):
            yield chunk


_PREAMBLE_RE = __import__("re").compile(r"^\[Widget instructions --[^\]]*\]\s*", __import__("re").DOTALL)


async def get_widget_session_messages(
    ctx: WidgetContext, visitor_session_id: str, limit: int = 50
) -> WidgetHistoryResponse:
    """Returning visitor's transcript, flattened to role/content pairs so the
    embed can hydrate its message list on open. The hidden per-turn preamble
    (language/tone/rich-message instructions) is stripped from user messages
    -- the visitor never typed it and must never see it echoed back."""
    session = await _get_widget_session(ctx.widget_id, visitor_session_id)
    thread_id = session.get("backend_thread_id")
    if not thread_id:
        return WidgetHistoryResponse(messages=[])

    try:
        history = await chat_services.get_session_history_for_admin(thread_id)
    except HTTPException:
        return WidgetHistoryResponse(messages=[])

    turns = []
    for agent in history.agents:
        for entry in agent.conversations:
            if getattr(entry, "type", None) != "turn":
                continue
            turns.append(entry)
    turns.sort(key=lambda t: t.timestamp or datetime.min.replace(tzinfo=timezone.utc))

    messages: list[WidgetHistoryMessage] = []
    for t in turns[-limit:]:
        at = str(t.timestamp) if t.timestamp else None
        if t.human_message:
            content = _PREAMBLE_RE.sub("", t.human_message).strip()
            if content:
                messages.append(WidgetHistoryMessage(role="user", content=content, at=at))
        if t.agent_message:
            messages.append(WidgetHistoryMessage(role="assistant", content=t.agent_message, at=at))
    return WidgetHistoryResponse(messages=messages)
