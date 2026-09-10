"""Inspect the MongoDB database: list every collection and its documents.

Usage (from project root):
    uv run python -m backend.scripts.show_data            # all collections
    uv run python -m backend.scripts.show_data users      # one collection
"""

import asyncio
import sys
from datetime import datetime

from bson import ObjectId

from backend.db.database import DATABASE_NAME, MONGO_URL, db


def _serialize(value):
    """Make ObjectId / datetime printable as JSON-ish text."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


async def show(collection_filter: str | None = None) -> None:
    print(f"MONGO_URL : {MONGO_URL}")
    print(f"DATABASE  : {DATABASE_NAME}\n")

    names = await db.list_collection_names()
    if not names:
        print("(no collections yet - the DB is empty)")
        return

    for name in sorted(names):
        if collection_filter and name != collection_filter:
            continue
        count = await db[name].count_documents({})
        print(f"[{name}]  ({count} document{'s' if count != 1 else ''})")
        async for doc in db[name].find().limit(20):
            print(f"   {_serialize(doc)}")
        print()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(show(target))
