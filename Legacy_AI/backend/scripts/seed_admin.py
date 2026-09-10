"""Seed an admin user (needed to log into /admin).

Usage (from project root):
    uv run python -m backend.scripts.seed_admin <email> <password> [org_id] [name]

Example:
    uv run python -m backend.scripts.seed_admin admin@example.com "StrongPass123" org1 "Site Admin"
"""

import sys
from datetime import datetime, timezone

from backend.core.security import hash_password
from backend.db.database import DATABASE_NAME, MONGO_URL
from pymongo import MongoClient


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    org_id = sys.argv[3] if len(sys.argv) > 3 else "default-org"
    name = sys.argv[4] if len(sys.argv) > 4 else "Admin"

    users = MongoClient(MONGO_URL)[DATABASE_NAME]["users"]
    if users.find_one({"email": email}):
        print(f"A user with email {email} already exists. Aborting.")
        sys.exit(1)

    users.insert_one({
        "organization_id": org_id,
        "name": name,
        "email": email,
        "role": "admin",
        "password": hash_password(password),
        "created_at": datetime.now(timezone.utc),
    })
    print(f"Created admin: {email} (org={org_id}). Log in at /admin/login.")


if __name__ == "__main__":
    main()
