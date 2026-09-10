"""Admin-configurable business quotas.

Limits are stored in the `quota_config` collection (a single doc named "global")
so they can be edited live from the admin dashboard. Quota checks read the config
fresh on each create (creates are infrequent), so admin changes take effect
immediately.

Current quotas:
- max_orgs_per_day:  how many organizations a single user may create per day.
- max_tools_per_org: how many tools an organization may have at once.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from backend.core.constants import DEFAULT_QUOTA, GLOBAL_CONFIG_NAME
from backend.core.softdelete import NOT_DELETED
from backend.db.database import (
    organizations_collection,
    quota_config_collection,
    tools_collection,
)


async def ensure_default_quota() -> None:
    """Create the default quota document if none exists (called at startup)."""
    existing = await quota_config_collection.find_one({"name": GLOBAL_CONFIG_NAME})
    if not existing:
        await quota_config_collection.insert_one(dict(DEFAULT_QUOTA))


async def _get_quota() -> dict:
    return await quota_config_collection.find_one(
        {"name": GLOBAL_CONFIG_NAME}
    ) or dict(DEFAULT_QUOTA)


def _start_of_today_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def enforce_orgs_per_day(created_by: str) -> None:
    """Raise 429 if the user has hit the daily organization-creation limit."""
    quota = await _get_quota()
    if not quota.get("enabled", True):
        return
    limit = int(quota.get("max_orgs_per_day", DEFAULT_QUOTA["max_orgs_per_day"]))
    count = await organizations_collection.count_documents(
        {
            "created_by": created_by,
            "created_at": {"$gte": _start_of_today_utc()},
            **NOT_DELETED,
        }
    )
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit reached: you can create at most {limit} "
            f"organizations per day.",
        )


async def enforce_tools_per_org(organization_id: str) -> None:
    """Raise 403 if the organization has reached its tool limit."""
    quota = await _get_quota()
    if not quota.get("enabled", True):
        return
    limit = int(quota.get("max_tools_per_org", DEFAULT_QUOTA["max_tools_per_org"]))
    count = await tools_collection.count_documents(
        {"organization_id": organization_id, **NOT_DELETED}
    )
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tool limit reached: an organization can have at most "
            f"{limit} tools.",
        )
