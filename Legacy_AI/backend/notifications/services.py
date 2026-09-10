import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument

from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.db.database import notifications_collection
from backend.notifications.schemas import NotificationPublic

logger = logging.getLogger("notifications.services")

ALLOWED_NOTIFICATION_TYPES = {"agent", "tool", "alert", "success", "system"}


def _to_public(doc: dict) -> NotificationPublic:
    raw_type = str(doc.get("type", "system"))
    safe_type = raw_type if raw_type in ALLOWED_NOTIFICATION_TYPES else "system"
    return NotificationPublic(
        id=str(doc["_id"]),
        organization_id=str(doc.get("organization_id", "")),
        user_id=str(doc["user_id"]) if doc.get("user_id") else None,
        type=safe_type,
        title=str(doc.get("title", "")),
        message=str(doc.get("message", "")),
        read=bool(doc.get("read", False)),
        created_at=doc["created_at"],
    )


def _scope(organization_id: str, user_id: str) -> dict:
    """Match notifications a user may see: their own + org-wide (user_id=None)."""
    return {
        "organization_id": organization_id,
        "$or": [{"user_id": user_id}, {"user_id": None}],
        **NOT_DELETED,
    }


async def create_notification(
    *,
    organization_id: str,
    type: str,
    title: str,
    message: str,
    user_id: Optional[str] = None,
) -> None:
    """Insert a notification. ``user_id=None`` makes it visible to the whole org.

    Best-effort: a failure here must never break the caller's main operation,
    so all errors are swallowed (and logged) rather than raised.
    """
    try:
        await notifications_collection.insert_one(
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "type": type,
                "title": title,
                "message": message,
                "read": False,
                "created_at": datetime.now(timezone.utc),
                "is_deleted": False,
            }
        )
    except Exception:
        logger.exception(
            "Failed to create notification %r for org=%s", title, organization_id
        )


async def list_notifications(
    organization_id: str, user_id: str, skip: int, limit: int
) -> tuple[list[NotificationPublic], int]:
    query = _scope(organization_id, user_id)
    cursor = (
        notifications_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    total = await notifications_collection.count_documents(query)
    return [_to_public(doc) for doc in docs], total


async def count_unread(organization_id: str, user_id: str) -> int:
    return await notifications_collection.count_documents(
        {**_scope(organization_id, user_id), "read": {"$ne": True}}
    )


async def mark_read(
    notification_id: str, organization_id: str, user_id: str
) -> NotificationPublic:
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found."
        )
    doc = await notifications_collection.find_one_and_update(
        {"_id": ObjectId(notification_id), **_scope(organization_id, user_id)},
        {"$set": {"read": True}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found."
        )
    return _to_public(doc)


async def mark_all_read(organization_id: str, user_id: str) -> int:
    result = await notifications_collection.update_many(
        {**_scope(organization_id, user_id), "read": {"$ne": True}},
        {"$set": {"read": True}},
    )
    return result.modified_count


async def dismiss(notification_id: str, organization_id: str, user_id: str) -> None:
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found."
        )
    result = await notifications_collection.update_one(
        {"_id": ObjectId(notification_id), **_scope(organization_id, user_id)},
        soft_delete_update(),
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found."
        )
