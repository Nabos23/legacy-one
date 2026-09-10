"""One-off: re-index a single db_connection so Qdrant payloads pick up the
newly-added foreign_keys / primary_key fields. Run inside the app container:

    docker exec -w /app fastapi_app uv run --no-sync python backend/scripts/reindex_conn.py <conn_id>
"""
import asyncio
import sys

from bson import ObjectId

from backend.db.database import db_connections_collection
from backend.dbconnection.services import get_schema
from ai.rag.schema_indexer import index_schema


async def main(conn_id: str) -> None:
    doc = await db_connections_collection.find_one({"_id": ObjectId(conn_id)})
    if not doc:
        print(f"connection {conn_id} not found")
        return
    schema = await get_schema(conn_id)
    n = await index_schema(
        org_id=doc["organization_id"], db_conn_id=conn_id, schema=schema
    )
    print(f"re-indexed {n} tables for conn={conn_id}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
