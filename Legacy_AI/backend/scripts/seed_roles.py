"""Seed the `roles` collection with the four default roles and their permissions.

Each role carries a `permissions` flag map (view / create / edit / delete) that
can be tuned afterwards directly from the DB or the /admin panel.

Usage (from project root):
    uv run python -m backend.scripts.seed_roles

Re-running is safe: existing roles are upserted by `name` (permissions are
refreshed to the defaults), and no documents are duplicated.
"""

from datetime import datetime, timezone

from pymongo import MongoClient

from backend.auth.constants import ROLE_DEFINITIONS
from backend.db import constants as c
from backend.db.database import DATABASE_NAME, MONGO_URL


def main() -> None:
    roles = MongoClient(MONGO_URL)[DATABASE_NAME][c.ROLES_COLLECTION]
    now = datetime.now(timezone.utc)

    for name, definition in ROLE_DEFINITIONS.items():
        roles.update_one(
            {"name": name},
            {
                "$set": {
                    "label": definition["label"],
                    "description": definition["description"],
                    "permissions": definition["permissions"],
                    "is_deleted": False,
                },
                "$setOnInsert": {"name": name, "created_at": now},
            },
            upsert=True,
        )
        perms = ", ".join(k for k, v in definition["permissions"].items() if v) or "none"
        print(f"Seeded role '{name}' (allowed: {perms}).")

    print(f"Done. {len(ROLE_DEFINITIONS)} roles in '{c.ROLES_COLLECTION}'.")


if __name__ == "__main__":
    main()
