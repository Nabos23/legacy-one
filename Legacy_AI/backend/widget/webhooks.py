"""Outbound webhook delivery for widget lifecycle events.

Delivery is still scheduled fire-and-forget from the caller's perspective
(a broken customer endpoint must never slow a visitor's chat turn), but each
scheduled delivery now retries transient failures with a short backoff and
records its outcome in `widget_webhook_deliveries` so admins can see what
was sent, when, and whether it landed. There is still no cross-restart queue
-- a delivery scheduled moments before a process restart can be lost; the
delivery log makes that visible rather than silent.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx

from backend.core.encryption import decrypt_or_none
from backend.db.database import widget_webhook_deliveries_collection

logger = logging.getLogger("widget.webhooks")

WebhookEvent = Literal["conversation_started", "lead_captured", "message_sent", "feedback_submitted"]

_TIMEOUT_SECONDS = 5.0
# 3 attempts total: immediate, then after 2s, then after 8s.
_RETRY_DELAYS_SECONDS = (0.0, 2.0, 8.0)


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _record_delivery(
    widget_id: str,
    event: str,
    url: str,
    ok: bool,
    attempts: int,
    status_code: Optional[int],
    error: Optional[str],
    payload: Optional[dict] = None,
    kind: str = "event",
) -> None:
    try:
        await widget_webhook_deliveries_collection.insert_one(
            {
                "widget_id": widget_id,
                "event": event,
                "url": url,
                "ok": ok,
                "attempts": attempts,
                "status_code": status_code,
                "error": error,
                # Stored so failed deliveries can be replayed verbatim from the
                # builder; rows TTL out after 30 days along with the log itself.
                "payload": payload,
                # "event" (real traffic), "test" (builder test-fire), or
                # "replay" (builder replay of a failed row).
                "kind": kind,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception as exc:  # noqa: BLE001 - logging must never take down delivery
        logger.warning("[WIDGET WEBHOOK] failed to record delivery log: %s", exc)


async def _deliver(
    widget_id: str,
    event: str,
    url: str,
    secret_encrypted: Optional[str],
    payload: dict,
    kind: str = "event",
) -> None:
    body = json.dumps(payload, default=str).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret_encrypted:
        secret = decrypt_or_none(secret_encrypted)
        if secret:
            headers["X-OneAI-Signature"] = _sign(secret, body)

    status_code: Optional[int] = None
    error: Optional[str] = None
    attempts = 0
    for delay in _RETRY_DELAYS_SECONDS:
        if delay:
            await asyncio.sleep(delay)
        attempts += 1
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                resp = await client.post(url, content=body, headers=headers)
            status_code = resp.status_code
            error = None
            if resp.status_code < 400:
                await _record_delivery(widget_id, event, url, True, attempts, status_code, None, payload=payload, kind=kind)
                return
            # 4xx (except 408/429) means the endpoint understood us and said
            # no -- retrying the identical request won't change its mind.
            if 400 <= resp.status_code < 500 and resp.status_code not in (408, 429):
                break
            logger.warning("[WIDGET WEBHOOK] %s -> HTTP %s (attempt %s)", url, resp.status_code, attempts)
        except Exception as exc:  # noqa: BLE001 - a broken customer endpoint must never break the chat turn
            status_code = None
            error = str(exc)
            logger.warning("[WIDGET WEBHOOK] delivery to %s failed (attempt %s): %s", url, attempts, exc)

    await _record_delivery(widget_id, event, url, False, attempts, status_code, error, payload=payload, kind=kind)


def fire_webhook(widget_config_doc: dict, event: WebhookEvent, data: dict) -> None:
    """Schedules delivery on the event loop without awaiting it -- callers
    (session/lead/message/feedback paths) must never block the visitor-facing
    response on a third-party endpoint's latency or availability."""
    target = (widget_config_doc.get("webhooks") or {}).get(event) or {}
    if not target.get("is_active") or not target.get("url"):
        return

    payload = {
        "event": event,
        "widget_id": str(widget_config_doc["_id"]),
        "organization_id": widget_config_doc.get("organization_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    asyncio.create_task(
        _deliver(str(widget_config_doc["_id"]), event, target["url"], target.get("secret_encrypted"), payload)
    )


async def deliver_once(
    widget_id: str,
    event: str,
    url: str,
    secret_encrypted: Optional[str],
    payload: dict,
    kind: str,
) -> dict:
    """One synchronous delivery attempt (no retries), recorded in the log.
    Used by the builder's test-fire and replay endpoints, where the admin is
    watching and wants the outcome now."""
    body = json.dumps(payload, default=str).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret_encrypted:
        secret = decrypt_or_none(secret_encrypted)
        if secret:
            headers["X-OneAI-Signature"] = _sign(secret, body)
    status_code: Optional[int] = None
    error: Optional[str] = None
    ok = False
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, content=body, headers=headers)
        status_code = resp.status_code
        ok = resp.status_code < 400
    except Exception as exc:  # noqa: BLE001 - surfaced to the admin, never raised
        error = str(exc)
    await _record_delivery(widget_id, event, url, ok, 1, status_code, error, payload=payload, kind=kind)
    return {"ok": ok, "status_code": status_code, "error": error}
