"""
One-time migration: upgrade the existing `schema_tables` Qdrant collection to the
recommended multi-tenant layout.

The collection was originally created with a global HNSW graph and only a
`db_conn_id` payload index. This script:

  1. adds a tenant payload index on `org_id` (is_tenant=True, on_disk=True), and
  2. switches the collection HNSW to per-tenant (m=0, payload_m=16).

No re-embedding is needed — every point already carries `org_id` in its payload,
so creating the tenant index simply indexes the existing values. Qdrant
re-optimizes segments in the background; queries keep working throughout.

Usage:
    python -m backend.scripts.migrate_schema_multitenancy
"""

import asyncio
import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    HnswConfigDiff,
    KeywordIndexParams,
    KeywordIndexType,
)

from ai.rag.schema_indexer import COLLECTION
from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_schema_multitenancy")


async def main() -> None:
    if not settings.QDRANT_URL:
        logger.error("QDRANT_URL is not set — nothing to migrate.")
        return

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        check_compatibility=False,
    )

    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION not in existing:
        logger.info("Collection '%s' does not exist yet — nothing to migrate "
                    "(it will be created with the new layout on first index).", COLLECTION)
        return

    logger.info("Adding tenant payload index on org_id ...")
    try:
        await client.create_payload_index(
            collection_name=COLLECTION,
            field_name="org_id",
            field_schema=KeywordIndexParams(
                type=KeywordIndexType.KEYWORD, is_tenant=True, on_disk=True
            ),
        )
        logger.info("  org_id tenant index created.")
    except Exception as exc:  # noqa: BLE001 - index may already exist; that's fine
        logger.info("  org_id index not created (likely already exists): %s", exc)

    logger.info("Switching HNSW to per-tenant (m=0, payload_m=16) ...")
    await client.update_collection(
        collection_name=COLLECTION,
        hnsw_config=HnswConfigDiff(m=0, payload_m=16),
    )
    logger.info("  HNSW updated. Qdrant will re-optimize segments in the background.")

    logger.info("Migration complete.")


if __name__ == "__main__":
    asyncio.run(main())
