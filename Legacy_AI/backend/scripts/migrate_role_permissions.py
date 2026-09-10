"""Sync the `permissions` and `role_permissions` collections from the
PERMISSION_DEFINITIONS / ROLE_DEFINITIONS constants in backend/auth/constants.py.

Auth is fully DB-driven at request time (see backend/auth/permissions.py) --
nothing reads those constants directly outside of this script. Whenever a
permission or role's permission_names list changes in constants.py (e.g. a
new feature adds view_X/create_X/edit_X/delete_X), re-run this so the change
actually reaches the running system:

Usage:
    uv run python -m backend.scripts.migrate_role_permissions

Safe to re-run any time -- every write is an idempotent upsert.
"""

import asyncio
from datetime import datetime, timezone

from backend.auth.constants import PERMISSION_DEFINITIONS, ROLE_DEFINITIONS
from backend.db.database import permissions_collection, role_permissions_collection


async def _sync_permissions(now) -> None:
    for name, definition in PERMISSION_DEFINITIONS.items():
        result = await permissions_collection.update_one(
            {"name": name},
            {
                "$set": {
                    "label": definition["label"],
                    "description": definition["description"],
                    "resource": definition["resource"],
                    "is_deleted": False,
                    "updated_at": now,
                },
                "$setOnInsert": {"name": name, "created_at": now},
            },
            upsert=True,
        )
        if result.upserted_id:
            print(f"Created permission '{name}'.")
        elif result.modified_count:
            print(f"Updated permission '{name}'.")


async def _sync_roles(now) -> None:
    for name, definition in ROLE_DEFINITIONS.items():
        result = await role_permissions_collection.update_one(
            {"role": name},
            {
                "$set": {
                    "label": definition["label"],
                    "description": definition["description"],
                    "permission_names": definition["permission_names"],
                    "is_deleted": False,
                    "updated_at": now,
                },
                "$setOnInsert": {"role": name, "created_at": now},
            },
            upsert=True,
        )
        if result.upserted_id:
            print(f"Created role '{name}'.")
        elif result.modified_count:
            print(f"Updated role '{name}'.")
        else:
            print(f"Role '{name}' already correct.")


async def main() -> None:
    now = datetime.now(timezone.utc)
    await _sync_permissions(now)
    await _sync_roles(now)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
