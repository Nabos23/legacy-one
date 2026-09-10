"""Helpers for soft deletion.

Soft-deleted documents keep `is_deleted=True` and a `deleted_at` timestamp
instead of being removed. All reads/updates filter them out via NOT_DELETED.
"""

from datetime import datetime, timezone

from backend.core.constants import NOT_DELETED  # re-exported for callers

__all__ = ["NOT_DELETED", "soft_delete_update"]


def soft_delete_update() -> dict:
    """The `$set` update that marks a document as soft-deleted."""
    return {
        "$set": {
            "is_deleted": True,
            "deleted_at": datetime.now(timezone.utc),
        }
    }
