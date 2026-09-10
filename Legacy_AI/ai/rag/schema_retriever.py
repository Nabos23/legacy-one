"""
Retrieve relevant schema tables from Qdrant given a natural language query.
"""

import logging

import litellm
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from backend.core.config import settings
from ai.rag.schema_indexer import COLLECTION, _get_sync_client

logger = logging.getLogger(__name__)


def _build_schema_filter(db_conn_ids: list[str], org_id: str) -> Filter:
    must_conditions = [FieldCondition(key="db_conn_id", match=MatchAny(any=db_conn_ids))]
    if org_id:
        must_conditions.insert(0, FieldCondition(key="org_id", match=MatchValue(value=org_id)))
    return Filter(must=must_conditions)


def _format_schema_hits(hits, query: str) -> str:
    if not hits:
        logger.info("[schema-retriever] no relevant tables found for query=%.100s", query)
        return "No relevant tables found for this query."

    logger.info("[schema-retriever] found %d relevant table(s)", len(hits))

    lines = ["Relevant database schema for your query:\n"]
    for hit in hits:
        p = hit.payload
        table = p["table_name"]
        kind = p.get("kind", "sql")
        description = p.get("description", "")
        columns = p.get("columns", [])
        primary_key = p.get("primary_key", [])
        foreign_keys = p.get("foreign_keys", [])

        col_str = ", ".join(
            f"{c['name']} ({c.get('type', 'unknown')})" for c in columns[:30]
        )

        if kind == "firebase":
            lines.append(f"Firestore collection: {table}")
        elif kind == "mongo":
            db_name = p.get("db_name")
            prefix = f"{db_name}." if db_name else ""
            lines.append(f"MongoDB collection: {prefix}{table}")
        else:
            lines.append(f"SQL table: {table}")
        if description:
            lines.append(f"  Purpose: {description}")
        lines.append(f"  Columns: {col_str}")
        if primary_key:
            lines.append(f"  Primary key: {', '.join(primary_key)}")
        if foreign_keys:
            def _cols(v) -> str:
                return ", ".join(v) if isinstance(v, list) else str(v)
            fk_str = "; ".join(
                f"{_cols(fk.get('column', '?'))} → {fk.get('references_table', '?')}"
                f".{_cols(fk.get('references_column', '?'))}"
                for fk in foreign_keys
            )
            lines.append(f"  Foreign keys: {fk_str}")
        lines.append("")

    return "\n".join(lines)


async def get_relevant_schema(
    query: str,
    db_conn_ids: list[str],
    org_id: str = "",
    top_k: int = 20,
) -> str:
    """
    Embed the query, search Qdrant filtered by db_conn_ids, and return
    a formatted schema slice ready to inject into an agent's context.

    Thin async wrapper — the actual embedding + search work is
    `get_relevant_schema_sync` below, the exact same code the
    ai/multi_orchestration engine calls directly. Running it here via
    `run_in_threadpool` (instead of keeping a second async-Qdrant-client
    implementation) means there is only ever one schema retriever, whichever
    engine is asking.
    """
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(get_relevant_schema_sync, query, db_conn_ids, org_id, top_k)


def get_relevant_schema_sync(
    query: str,
    db_conn_ids: list[str],
    org_id: str = "",
    top_k: int = 20,
) -> str:
    """Synchronous counterpart of `get_relevant_schema`, for callers that run
    outside asyncio (the ai/multi_orchestration engine drives its scheduler
    from a plain worker thread — bridging into the async client/event loop
    from there is not safe, so this uses its own sync Qdrant client + a sync
    embedding call instead)."""
    if not settings.QDRANT_URL or not db_conn_ids:
        logger.warning("[schema-retriever] skipping — QDRANT_URL not set or no db_conn_ids")
        return "Schema search is not available."

    logger.info(
        "[schema-retriever] retrieving schema (sync) — query=%.100s conn_ids=%s top_k=%d",
        query, db_conn_ids, top_k,
    )
    client = _get_sync_client()

    try:
        logger.debug("[schema-retriever] embedding query with model=%s", settings.EMBEDDING_MODEL)
        resp = litellm.embedding(
            model=settings.EMBEDDING_MODEL,
            input=[query],
            timeout=15,
            num_retries=1,
        )
        item = resp.data[0]
        query_vector = item["embedding"] if isinstance(item, dict) else item.embedding

        result = client.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            query_filter=_build_schema_filter(db_conn_ids, org_id),
            limit=top_k,
            with_payload=True,
        )
        hits = result.points
    except Exception as e:
        logger.warning("[schema-retriever] sync failed — %s: %s, skipping schema injection", type(e).__name__, e)
        return "Schema search is temporarily unavailable."

    return _format_schema_hits(hits, query)
