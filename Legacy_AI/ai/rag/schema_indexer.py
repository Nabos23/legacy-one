"""
Embed and index a db_connection's schema into Qdrant.

One vector point per table/collection. Points are filtered by db_conn_id at
query time, giving clean per-connection (and implicitly per-org) isolation.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

import litellm
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    KeywordIndexParams,
    KeywordIndexType,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from backend.core.config import settings

COLLECTION = "schema_tables"
VECTOR_DIM = 1536  # text-embedding-3-small output size

_qdrant: Optional[AsyncQdrantClient] = None
_qdrant_sync: Optional[QdrantClient] = None


def _get_client() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        logger.info("[schema-index] connecting to Qdrant at %s", settings.QDRANT_URL)
        _qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            check_compatibility=False,
        )
    return _qdrant


def set_client(client: AsyncQdrantClient) -> None:
    """Override the singleton client — used in tests to inject in-memory Qdrant."""
    global _qdrant
    _qdrant = client


def _get_sync_client() -> QdrantClient:
    """Separate sync client for callers that run outside asyncio (e.g. the
    ai/multi_orchestration engine, which drives its scheduler from a plain
    worker thread with no running event loop). Deliberately NOT the same
    singleton as `_get_client()` — the async client's connection pool is bound
    to whichever event loop first used it, so reusing it from a different
    loop/thread would break."""
    global _qdrant_sync
    if _qdrant_sync is None:
        logger.info("[schema-index] connecting to Qdrant (sync) at %s", settings.QDRANT_URL)
        _qdrant_sync = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            check_compatibility=False,
        )
    return _qdrant_sync


def set_sync_client(client: QdrantClient) -> None:
    """Override the sync singleton client — used in tests to inject in-memory Qdrant."""
    global _qdrant_sync
    _qdrant_sync = client


async def _ensure_collection() -> None:
    client = _get_client()
    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION not in existing:
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
            # Multi-tenant tuning (Qdrant's recommended pattern): skip the global
            # HNSW graph (m=0) and instead build a per-tenant subgraph (payload_m)
            # keyed on the org_id tenant index — so a per-org filtered search stays
            # fast as the number of orgs grows.
            hnsw_config=HnswConfigDiff(m=0, payload_m=16),
        )
        # Tenant index on org_id. is_tenant=True co-locates each org's points on
        # disk so per-org queries read sequentially; on_disk keeps the index off
        # the (paid) RAM budget on Qdrant Cloud.
        await client.create_payload_index(
            collection_name=COLLECTION,
            field_name="org_id",
            field_schema=KeywordIndexParams(
                type=KeywordIndexType.KEYWORD, is_tenant=True, on_disk=True
            ),
        )
        # Secondary filter: an org may have several DB connections and an agent is
        # scoped to a subset.
        await client.create_payload_index(
            collection_name=COLLECTION,
            field_name="db_conn_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )


def _stable_id(db_conn_id: str, table_name: str) -> str:
    """Deterministic UUID so re-indexing upserts rather than duplicates."""
    raw = f"{db_conn_id}:{table_name}".encode()
    return str(uuid.UUID(hashlib.md5(raw).hexdigest()))


def _sql_embedding_text(table_name: str, columns: list, foreign_keys: list | None = None) -> str:
    cols = ", ".join(f"{c['name']} ({c.get('type', 'unknown')})" for c in columns)
    text = f"Table: {table_name}\nColumns: {cols}"
    if foreign_keys:
        refs = ", ".join(fk.get("references_table", "") for fk in foreign_keys if fk.get("references_table"))
        if refs:
            text += f"\nReferences: {refs}"
    return text


def _mongo_embedding_text(db_name: str, coll_name: str, fields: dict) -> str:
    flds = ", ".join(f"{k} ({v})" for k, v in fields.items())
    return f"Database: {db_name}\nCollection: {coll_name}\nFields: {flds}"


def _firebase_embedding_text(project_id: str, coll_name: str, fields: dict) -> str:
    flds = ", ".join(f"{k} ({v})" for k, v in fields.items())
    return f"Firebase project: {project_id}\nFirestore collection: {coll_name}\nFields: {flds}"


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    logger.debug("[schema-index] embedding %d text(s) with model=%s", len(texts), settings.EMBEDDING_MODEL)
    resp = await litellm.aembedding(model=settings.EMBEDDING_MODEL, input=texts)
    return [
        item["embedding"] if isinstance(item, dict) else item.embedding
        for item in resp.data
    ]


async def _llm_describe_batch(tables: list[dict]) -> dict[str, str]:
    """
    Ask LLM to describe each table's business purpose in one sentence.
    Returns {table_name: description}. Silently returns {} on failure so
    indexing always completes even if the LLM call errors.
    """
    lines = "\n".join(
        f"- {t['name']}: {', '.join(c['name'] for c in t['columns'][:12])}"
        for t in tables
    )
    prompt = (
        "You are a database expert. Given these database tables and their columns, "
        "write a single-sentence description of each table's business purpose.\n\n"
        f"Tables:\n{lines}\n\n"
        'Return ONLY valid JSON like: {"TableName": "description", ...}'
    )
    logger.info("[schema-index] llm describe batch — %d tables, model=%s", len(tables), settings.DEFAULT_MODEL)
    try:
        resp = await litellm.acompletion(
            model=settings.DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())
        logger.info("[schema-index] llm describe batch — got %d description(s)", len(result))
        return result
    except Exception as e:
        logger.warning("[schema-index] llm describe batch failed — %s: %s, skipping descriptions", type(e).__name__, e)
        return {}


def _extract_tables(schema: dict) -> list[dict]:
    """
    Normalize any supported schema format into a flat list of table dicts.

    Handles three formats:
    - db_introspect SQL:  {"kind": "sql", "tables": {name: [col, ...]}}
    - db_introspect Mongo: {"kind": "mongo", "databases": {...}}
    - Firestore:          {"kind": "firebase", "collections": {...}}
    - db_schema_reader:   {name: {"columns": [...], "foreign_keys": [...], "primary_key": [...]}}
    """
    kind = schema.get("kind")
    tables = []

    if kind == "sql":
        for table_name, table_def in schema.get("tables", {}).items():
            # table_def is either a list of columns (old format) or {columns, foreign_keys}
            if isinstance(table_def, list):
                columns, fks, pk, existing_desc = table_def, [], [], None
            else:
                columns = table_def.get("columns", [])
                fks = table_def.get("foreign_keys", [])
                pk = table_def.get("primary_key", [])
                existing_desc = table_def.get("description") or None
            tables.append({"name": table_name, "columns": columns, "foreign_keys": fks, "primary_key": pk, "db_name": None, "kind": "sql", "description": existing_desc})

    elif kind == "mongo":
        for db_name, colls in schema.get("databases", {}).items():
            for coll_name, coll_info in colls.items():
                if isinstance(coll_info, dict) and "fields" in coll_info:
                    raw_fields = coll_info["fields"]
                    existing_desc = coll_info.get("description") or None
                else:
                    raw_fields = coll_info
                    existing_desc = None
                cols = [{"name": k, "type": v} for k, v in raw_fields.items()]
                tables.append({"name": coll_name, "columns": cols, "foreign_keys": [], "primary_key": [], "db_name": db_name, "kind": "mongo", "description": existing_desc})

    elif kind == "firebase":
        project_id = schema.get("project_id", "")
        for coll_name, coll_info in schema.get("collections", {}).items():
            if isinstance(coll_info, dict):
                raw_fields = coll_info.get("fields", {})
                existing_desc = coll_info.get("description") or None
            else:
                raw_fields = {}
                existing_desc = None
            cols = [{"name": k, "type": v} for k, v in raw_fields.items()]
            tables.append({
                "name": coll_name,
                "columns": cols,
                "foreign_keys": [],
                "primary_key": [],
                "db_name": project_id,
                "kind": "firebase",
                "description": existing_desc,
            })

    else:
        # db_schema_reader format: top-level keys are table names
        for table_name, table_def in schema.items():
            if not isinstance(table_def, dict):
                continue
            tables.append({
                "name": table_name,
                "columns": table_def.get("columns", []),
                "foreign_keys": table_def.get("foreign_keys", []),
                "primary_key": table_def.get("primary_key", []),
                "db_name": None,
                "kind": "sql",
            })

    return tables


async def index_schema(org_id: str, db_conn_id: str, schema: dict) -> int:
    """
    Embed and upsert all tables from a schema into Qdrant.

    Deletes all existing points for this db_conn_id first so re-indexing
    is always a clean slate. Returns the number of tables indexed.
    """
    if not settings.QDRANT_URL:
        logger.warning("[schema-index] QDRANT_URL is not set — skipping indexing for conn %s", db_conn_id)
        return 0

    logger.info("[schema-index] starting for conn=%s org=%s", db_conn_id, org_id)

    await _ensure_collection()
    client = _get_client()

    logger.info("[schema-index] wiping old index for conn=%s", db_conn_id)
    await client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(key="org_id", match=MatchValue(value=org_id)),
                FieldCondition(key="db_conn_id", match=MatchValue(value=db_conn_id)),
            ]
        ),
    )

    tables = _extract_tables(schema)
    if not tables:
        logger.warning("[schema-index] no tables extracted from schema for conn=%s", db_conn_id)
        return 0

    logger.info("[schema-index] extracted %d tables for conn=%s", len(tables), db_conn_id)

    # Seed descriptions from the schema (populated when user has already reviewed them
    # via POST /db-connections/{conn_id}/descriptions). Only call the LLM for tables
    # that don't already have a stored description.
    descriptions: dict[str, str] = {
        t["name"]: t["description"] for t in tables if t.get("description")
    }
    tables_needing_desc = [t for t in tables if not t.get("description")]
    LLM_BATCH = 15
    if tables_needing_desc:
        for i in range(0, len(tables_needing_desc), LLM_BATCH):
            batch = tables_needing_desc[i : i + LLM_BATCH]
            logger.info("[schema-index] generating LLM descriptions for tables %d-%d", i, i + len(batch) - 1)
            batch_desc = await _llm_describe_batch(batch)
            descriptions.update(batch_desc)
    n_preexisting = len(tables) - len(tables_needing_desc)
    logger.info("[schema-index] descriptions — %d pre-existing, %d from LLM, %d total", n_preexisting, len(descriptions) - n_preexisting, len(descriptions))

    # Build embedding texts (raw schema + LLM description)
    def _make_text(t: dict) -> str:
        if t["kind"] == "sql":
            base = _sql_embedding_text(t["name"], t["columns"], t.get("foreign_keys"))
        elif t["kind"] == "mongo":
            base = _mongo_embedding_text(t["db_name"], t["name"], {c["name"]: c["type"] for c in t["columns"]})
        else:
            base = _firebase_embedding_text(t["db_name"], t["name"], {c["name"]: c["type"] for c in t["columns"]})
        desc = descriptions.get(t["name"], "")
        return f"{base}\nDescription: {desc}" if desc else base

    texts = [_make_text(t) for t in tables]

    # Embed in batches of 50
    EMBED_BATCH = 50
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        logger.info("[schema-index] embedding batch %d-%d", i, min(i + EMBED_BATCH, len(texts)) - 1)
        vecs = await _embed_batch(texts[i : i + EMBED_BATCH])
        all_vectors.extend(vecs)
    logger.info("[schema-index] embedding complete — %d vectors", len(all_vectors))

    # Build Qdrant points
    points = [
        PointStruct(
            id=_stable_id(db_conn_id, t["name"]),
            vector=all_vectors[i],
            payload={
                "org_id": org_id,
                "db_conn_id": db_conn_id,
                "table_name": t["name"],
                "db_name": t.get("db_name"),
                "kind": t["kind"],
                "columns": t["columns"],
                "foreign_keys": t.get("foreign_keys", []),
                "primary_key": t.get("primary_key", []),
                "description": descriptions.get(t["name"], ""),
            },
        )
        for i, t in enumerate(tables)
    ]

    # Upsert in batches of 100
    UPSERT_BATCH = 100
    for i in range(0, len(points), UPSERT_BATCH):
        batch_end = min(i + UPSERT_BATCH, len(points))
        logger.info("[schema-index] upserting points %d-%d into Qdrant", i, batch_end - 1)
        await client.upsert(collection_name=COLLECTION, points=points[i : i + UPSERT_BATCH])

    logger.info("[schema-index] done — %d points upserted for conn=%s", len(points), db_conn_id)
    return len(points)


async def delete_schema_index(org_id: str, db_conn_id: str) -> None:
    """Remove all indexed tables for a connection (called on soft delete)."""
    if not settings.QDRANT_URL:
        return
    await _ensure_collection()
    client = _get_client()
    await client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(key="org_id", match=MatchValue(value=org_id)),
                FieldCondition(key="db_conn_id", match=MatchValue(value=db_conn_id)),
            ]
        ),
    )
