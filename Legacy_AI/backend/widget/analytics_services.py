from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import HTTPException, status

from backend.chat import services as chat_services
from backend.chat.schemas import SessionHistoryResponse
from backend.db.database import (
    widget_message_feedback_collection,
    widget_sessions_collection,
    widget_webhook_deliveries_collection,
)
from backend.widget.schemas import (
    WidgetAnalytics,
    WidgetDayCount,
    WidgetSessionListItem,
    WidgetWebhookDeliveriesResponse,
    WidgetWebhookDeliveryItem,
)


async def _get_session_doc(widget_id: str, visitor_session_id: str) -> dict:
    doc = await widget_sessions_collection.find_one(
        {"widget_id": widget_id, "visitor_session_id": visitor_session_id}
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return doc


def _to_list_item(doc: dict) -> WidgetSessionListItem:
    lead = (doc.get("metadata") or {}).get("lead")
    return WidgetSessionListItem(
        visitor_session_id=doc["visitor_session_id"],
        created_at=doc["created_at"],
        last_active_at=doc["last_active_at"],
        status=doc.get("status", "active"),
        origin=(doc.get("metadata") or {}).get("origin"),
        has_lead=bool(lead),
        lead_values=lead,
    )


async def list_widget_sessions(
    widget_id: str, skip: int = 0, limit: int = 20
) -> tuple[List[WidgetSessionListItem], int]:
    query = {"widget_id": widget_id}
    total = await widget_sessions_collection.count_documents(query)
    cursor = widget_sessions_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_list_item(doc) for doc in docs], total


async def get_widget_session_history(widget_id: str, visitor_session_id: str) -> SessionHistoryResponse:
    """Reuses chat's own admin-scoped transcript reader -- a widget visitor's
    conversation lives in the exact same conversation_logs collection as any
    other direct_agent/supervisor thread, keyed by the session's stored
    backend_thread_id, regardless of which of those two engines ran it."""
    doc = await _get_session_doc(widget_id, visitor_session_id)
    thread_id = doc.get("backend_thread_id")
    if not thread_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This visitor hasn't sent a message yet.",
        )
    return await chat_services.get_session_history_for_admin(thread_id)


async def get_widget_analytics(widget_id: str) -> WidgetAnalytics:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today_start - timedelta(days=13)

    total_sessions = await widget_sessions_collection.count_documents({"widget_id": widget_id})
    sessions_today = await widget_sessions_collection.count_documents(
        {"widget_id": widget_id, "created_at": {"$gte": today_start}}
    )
    leads_captured = await widget_sessions_collection.count_documents(
        {"widget_id": widget_id, "metadata.lead": {"$exists": True, "$ne": None}}
    )
    feedback_up = await widget_message_feedback_collection.count_documents({"widget_id": widget_id, "rating": "up"})
    feedback_down = await widget_message_feedback_collection.count_documents({"widget_id": widget_id, "rating": "down"})

    recent = await widget_sessions_collection.find(
        {"widget_id": widget_id, "created_at": {"$gte": window_start}}, {"created_at": 1}
    ).to_list(length=10_000)

    counts_by_day = {}
    for i in range(14):
        day = (window_start + timedelta(days=i)).strftime("%Y-%m-%d")
        counts_by_day[day] = 0
    for doc in recent:
        day = doc["created_at"].strftime("%Y-%m-%d")
        if day in counts_by_day:
            counts_by_day[day] += 1

    return WidgetAnalytics(
        total_sessions=total_sessions,
        sessions_today=sessions_today,
        leads_captured=leads_captured,
        feedback_up=feedback_up,
        feedback_down=feedback_down,
        sessions_by_day=[WidgetDayCount(date=d, count=c) for d, c in sorted(counts_by_day.items())],
    )


async def list_widget_webhook_deliveries(
    widget_id: str, page: int, page_size: int
) -> WidgetWebhookDeliveriesResponse:
    """Newest-first page of the outbound-delivery log for this widget."""
    query = {"widget_id": widget_id}
    total = await widget_webhook_deliveries_collection.count_documents(query)
    cursor = (
        widget_webhook_deliveries_collection.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        WidgetWebhookDeliveryItem(
            id=str(d["_id"]),
            kind=d.get("kind", "event"),
            can_replay=bool(d.get("payload")),
            event=d["event"],
            url=d["url"],
            ok=d["ok"],
            attempts=d["attempts"],
            status_code=d.get("status_code"),
            error=d.get("error"),
            created_at=d["created_at"],
        )
        async for d in cursor
    ]
    return WidgetWebhookDeliveriesResponse(items=items, total=total, page=page, page_size=page_size)
