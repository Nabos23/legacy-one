import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import List

import litellm

from ai.models import Model

logger = logging.getLogger(__name__)


DESCRIBE_BATCH_SIZE = 10    # tables per LLM call
_describe_semaphore: asyncio.Semaphore | None = None  # lazy-init (event loop safe)

_DESCRIBE_SYSTEM_PROMPT = (
    "You are a database documentation expert. "
    "For each table or collection provided, write a concise 1–2 sentence description "
    "of what it stores and its role in the application. "
    "Return ONLY valid JSON where every key is the exact table/collection name given "
    "and every value is its description string. "
    'Example: {"users": "Stores registered user accounts and credentials.", '
    '"orders": "Tracks customer purchase orders linked to users."}'
)


def _get_semaphore() -> asyncio.Semaphore:
    global _describe_semaphore
    if _describe_semaphore is None:
        _describe_semaphore = asyncio.Semaphore(3)
    return _describe_semaphore


async def _generate_descriptions_batch(tables: list[tuple[str, dict]]) -> dict[str, str]:
    """Call the LLM to generate descriptions for a batch of tables/collections.

    Returns a dict mapping table name → description. Returns {} on any failure
    so callers never surface a partial-batch error to the user.
    """
    lines: list[str] = []
    for name, info in tables:
        if "columns" in info:
            cols = ", ".join(
                f"{c['name']} ({c.get('type', 'unknown')})"
                for c in info["columns"][:20]
            )
            lines.append(f"Table: {name}\nColumns: {cols}")
        elif "fields" in info:
            fields = ", ".join(
                f"{f} ({'/'.join(v.get('types', ['unknown']))})"
                for f, v in list(info["fields"].items())[:20]
            )
            lines.append(f"Collection: {name}\nFields: {fields}")
        else:
            lines.append(f"Table/Collection: {name}")

    user_message = "\n\n".join(lines)

    try:
        async with _get_semaphore():
            resp = await litellm.acompletion(
                model=Model.GPT_5_4_NANO.value,
                messages=[
                    {"role": "system", "content": _DESCRIBE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=DESCRIBE_BATCH_SIZE * 80,
                response_format={"type": "json_object"},
            )
        return json.loads(resp.choices[0].message.content.strip())
    except Exception:
        logger.exception("[describe] batch LLM call failed for tables: %s", [n for n, _ in tables])
        return {}


async def _enrich_schema_with_descriptions(schema: dict) -> tuple[dict, int, int, bool]:
    """Add LLM-generated descriptions to each table/collection in the schema.

    Describes every discovered table in bounded LLM batches. Mutates and
    returns the schema dict.
    Returns: (schema, total_count, described_count, truncated)
    """
    kind = schema.get("kind", "")

    if kind == "sql":
        all_tables: list[tuple[str, dict]] = list(schema.get("tables", {}).items())
    elif kind == "mongo":
        all_tables = [
            (f"{db}.{coll}", info)
            for db, colls in schema.get("databases", {}).items()
            for coll, info in colls.items()
        ]
    elif kind == "firebase":
        all_tables = list(schema.get("collections", {}).items())
    else:
        return schema, 0, 0, False

    total = len(all_tables)
    batches = [
        all_tables[i : i + DESCRIBE_BATCH_SIZE]
        for i in range(0, len(all_tables), DESCRIBE_BATCH_SIZE)
    ]

    results = await asyncio.gather(
        *[_generate_descriptions_batch(batch) for batch in batches],
        return_exceptions=True,
    )

    descriptions: dict[str, str] = {}
    for r in results:
        if isinstance(r, dict):
            descriptions.update(r)

    # Merge descriptions in place
    if kind == "sql":
        for name, table_info in schema.get("tables", {}).items():
            table_info["description"] = descriptions.get(name)
    elif kind == "mongo":
        for db_name, colls in schema.get("databases", {}).items():
            for coll_name, coll_info in colls.items():
                coll_info["description"] = descriptions.get(f"{db_name}.{coll_name}")
    elif kind == "firebase":
        for coll_name, coll_info in schema.get("collections", {}).items():
            coll_info["description"] = descriptions.get(coll_name)

    return schema, total, len(descriptions), False


def _merge_descriptions_into_schema(schema: dict, descriptions: dict[str, str]) -> None:
    """Merge table_descriptions into schema dict in place."""
    if schema.get("kind") == "sql":
        tables = schema.get("tables", {})
        for name, desc in descriptions.items():
            if name in tables:
                tables[name]["description"] = desc
    elif schema.get("kind") == "mongo":
        databases = schema.get("databases", {})
        for db_name, colls in databases.items():
            for coll_name in colls:
                key = f"{db_name}.{coll_name}"
                if key in descriptions:
                    colls[coll_name]["description"] = descriptions[key]
    elif schema.get("kind") == "firebase":
        collections = schema.get("collections", {})
        for name, desc in descriptions.items():
            if name in collections:
                collections[name]["description"] = desc

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from starlette.concurrency import run_in_threadpool

from backend.core.db_introspect import SchemaFetchError, fetch_schema
from backend.core.encryption import decrypt, encrypt, mask_connection_string
from backend.core.firebase_connection import (
    FirebaseConnectionError,
    build_firestore_connection_string,
)
from backend.core.query_runner import QueryExecutionError, run_query
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.db.database import db, db_connections_collection, organizations_collection
from backend.dbconnection.constants import (
    SCHEMA_GRIDFS_BUCKET,
    SCHEMA_INLINE_MAX_BYTES,
)
from backend.dbconnection.schemas import (
    DbConnectionCreate,
    DbConnectionFormatRequest,
    DbConnectionFormatResponse,
    DbConnectionPreviewRequest,
    DbConnectionPublic,
    DbConnectionUpdate,
)

def _bucket() -> AsyncIOMotorGridFSBucket:
    """GridFS bucket for oversized schemas (created lazily, bound to the live loop)."""
    return AsyncIOMotorGridFSBucket(db, bucket_name=SCHEMA_GRIDFS_BUCKET)


async def _schema_storage_fields(schema: dict) -> dict:
    """Return the doc fields for persisting a schema.

    Stores it inline when small enough; otherwise offloads the full JSON to
    GridFS and keeps only a reference — so arbitrarily large schemas never
    exceed the document size limit.
    """
    raw = json.dumps(schema, default=str).encode("utf-8")
    if len(raw) <= SCHEMA_INLINE_MAX_BYTES:
        return {"schema": schema, "schema_gridfs_id": None}
    file_id = await _bucket().upload_from_stream("schema.json", raw)
    return {"schema": None, "schema_gridfs_id": str(file_id)}


async def _delete_gridfs_schema(gridfs_id) -> None:
    """Best-effort cleanup of a previously stored GridFS schema."""
    if not gridfs_id:
        return
    try:
        await _bucket().delete(ObjectId(str(gridfs_id)))
    except Exception:  # noqa: BLE001 - orphan cleanup must never fail the request
        pass


def _to_public(doc: dict) -> DbConnectionPublic:
    """Map a MongoDB document to the public schema, masking the secret.

    Note: the fetched `schema` is intentionally NOT exposed here.
    """
    try:
        plaintext = decrypt(doc["connection_string"])
    except Exception:
        logger.exception(
            "[db-connections] decrypt failed for conn_id=%s org_id=%s db=%s -- "
            "likely ENCRYPTION_KEY/JWT_SECRET_KEY mismatch between environments "
            "sharing this MongoDB (value was encrypted under a different key than this env is using)",
            doc.get("_id"), doc.get("organization_id"), db_connections_collection.database.name,
        )
        raise
    return DbConnectionPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc.get("name"),
        connection_type=doc.get("connection_type"),
        connection_string=mask_connection_string(plaintext),
        created_at=doc["created_at"],
    )


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _infer_connection_type(connection_string: str, schema: dict | None = None) -> str:
    """Infer a stable display type when the client did not provide one."""
    schema_kind = (schema or {}).get("kind")
    dialect = (schema or {}).get("dialect")
    if schema_kind == "firebase":
        return "firebase"
    if schema_kind == "mongo":
        return "mongodb"
    if dialect:
        return str(dialect).lower()

    prefix = connection_string.split(":", 1)[0].lower()
    aliases = {
        "postgres": "postgresql",
        "postgresql": "postgresql",
        "mysql": "mysql",
        "mariadb": "mariadb",
        "sqlite": "sqlite",
        "mssql": "mssql",
        "sqlserver": "mssql",
        "mongodb": "mongodb",
        "mongodb+srv": "mongodb",
        "firebase": "firebase",
    }
    return aliases.get(prefix, prefix or "database")


async def _validate_org_exists(org_id: str) -> None:
    """Raise 404 if org_id is not a valid ObjectId or the org doesn't exist."""
    if not ObjectId.is_valid(org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    doc = await organizations_collection.find_one(
        {"_id": ObjectId(org_id), "is_deleted": {"$ne": True}}
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )


async def _fetch_schema_or_400(connection_string: str) -> dict:
    """Introspect the external DB (off the event loop); 400 if unreachable."""
    try:
        return await run_in_threadpool(fetch_schema, connection_string)
    except SchemaFetchError as e:
        logger.exception("[_fetch_schema_or_400] Introspection failed for URL: %s", connection_string)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not fetch database schema from the connection: {e}",
        )


def _resolve_connection_string(
    payload: DbConnectionCreate | DbConnectionPreviewRequest | DbConnectionUpdate,
) -> str | None:
    """Return the plain connection string from raw or structured payloads."""
    if payload.connection_string:
        return payload.connection_string
    if payload.firebase:
        try:
            return build_firestore_connection_string(
                payload.firebase.service_account,
                payload.firebase.database_id,
            )
        except FirebaseConnectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    return None


_VALID_URI_REGEX = re.compile(
    r"^(mssql\+pyodbc|postgresql(\+psycopg2)?|postgres|mysql(\+pymysql)?|mariadb|sqlite|mongodb(\+srv)?|firebase):\/\/.+",
    re.IGNORECASE,
)


async def format_connection_string(
    connection_string: str,
    connection_type: str | None = None,
    name: str | None = None,
) -> str:
    """Format and normalize a database connection string into a valid DB connection URI.
    Uses regex to check if the string is in standard URI format.
    """
    if not connection_string or not connection_string.strip():
        return connection_string

    conn_str = connection_string.strip()
    context_info = []
    if not _VALID_URI_REGEX.match(conn_str):
        logger.info("[format_connection_string] Non-standard connection string detected. Calling LLM to convert...")
        context_parts = []
        if connection_type:
            context_info.append(f"Database Type / Driver: {connection_type}")
        if name:
            context_info.append(f"Database Name: {name}")

        context_str = "\n".join(context_info) if context_info else "None"

        system_prompt = (
            "You are a database connection string converter.\n"
            "Your task is to convert any input database connection string (ADO.NET, OLEDB, key-value pairs, or raw URIs) "
            "into a standard, fully-qualified database connection URI.\n\n"
            "Rules:\n"
            "1. Extract host, port, user, password, and database name from the input string or context hints.\n"
            "2. Format according to database type:\n"
            "   - MSSQL: mssql+pyodbc://<user>:<password>@<host>:<port>/<database_name>?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes\n"
            "   - PostgreSQL: postgresql://<user>:<password>@<host>:<port>/<database_name>\n"
            "   - MySQL: mysql+pymysql://<user>:<password>@<host>:<port>/<database_name>\n"
            "   - MongoDB: mongodb://<user>:<password>@<host>:<port>/<database_name>\n"
            "3. CRITICAL - DATABASE NAME EXTRACTION:\n"
            "   - Search input string for keys like Initial Catalog, Database, Catalog, DB, or InitialCatalog.\n"
            "   - If found, extract that exact database name and put it in the URI path (e.g. /NucleusOneDev).\n"
            "   - If no database key is in the string, check Connection Name from context and use it as the URI path.\n"
            "   - Only default to '/master' if no database name or connection name is provided anywhere.\n"
            "4. NEVER insert placeholder words like 'unknown' or 'database_name' into the URI path.\n"
            "5. For MSSQL, always ensure driver=ODBC+Driver+17+for+SQL+Server and TrustServerCertificate=yes are present.\n"
            "6. Return ONLY the final formatted URI string as raw text. Do not include markdown code blocks, quotes, or explanations."
        )

        try:
            resp = await litellm.acompletion(
                model=Model.GPT_5_4_NANO.value,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context:\n{context_str}\n\nInput Connection String:\n{conn_str}"},
                ],
                temperature=0.0,
                max_tokens=250,
            )
            converted = resp.choices[0].message.content.strip()
            if converted.startswith("```"):
                converted = re.sub(r"^```[a-zA-Z]*\n?", "", converted)
                converted = re.sub(r"\n?```$", "", converted).strip()
            if converted:
                logger.info("[format_connection_string] 5.4 nano formatting succeeded: %s", converted)
                return converted
        except Exception as e:
            logger.exception("[format_connection_string] 5.4 nano formatting failed: %s", e)

    return conn_str


async def _index_schema_background(org_id: str, db_conn_id: str, schema: dict) -> None:
    """Fire-and-forget background task: embed schema tables and upsert to Qdrant."""
    try:
        from ai.rag.schema_indexer import index_schema
        logger.info("[schema-index] background task started for conn=%s", db_conn_id)
        count = await index_schema(org_id=org_id, db_conn_id=db_conn_id, schema=schema)
        await db_connections_collection.update_one(
            {"_id": ObjectId(db_conn_id)},
            {"$set": {"schema_indexed": True, "schema_table_count": count}},
        )
        logger.info("[schema-index] background task complete — %d tables indexed for conn=%s", count, db_conn_id)
    except Exception:
        logger.exception("[schema-index] background task failed for conn=%s", db_conn_id)


def _validate_object_id(conn_id: str) -> ObjectId:
    """Convert a string id to ObjectId or raise 404 if malformed."""
    if not ObjectId.is_valid(conn_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DB connection not found.",
        )
    return ObjectId(conn_id)


async def create_db_connection(
    payload: DbConnectionCreate,
) -> DbConnectionPublic:
    await _validate_org_exists(payload.organization_id)
    connection_string = _resolve_connection_string(payload)
    if not connection_string:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A connection string or Firebase configuration is required.",
        )
    if connection_string and not connection_string.startswith("firebase://"):
        connection_string = await format_connection_string(
            connection_string,
            connection_type=payload.connection_type,
            name=payload.name,
        )
    schema = await _fetch_schema_or_400(connection_string)
    if payload.table_descriptions:
        _merge_descriptions_into_schema(schema, payload.table_descriptions)

    doc = {
        "organization_id": payload.organization_id,
        "name": _clean_optional_text(payload.name),
        "connection_type": _clean_optional_text(payload.connection_type)
        or _infer_connection_type(connection_string, schema),
        "connection_string": encrypt(connection_string),
        "created_at": datetime.now(timezone.utc),
        "is_deleted": False,
        **(await _schema_storage_fields(schema)),
    }
    result = await db_connections_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    conn_id = str(result.inserted_id)
    logger.info(
        "[db-connections] created conn_id=%s org_id=%s type=%s db=%s coll=%s",
        conn_id, payload.organization_id, doc["connection_type"],
        db_connections_collection.database.name, db_connections_collection.name,
    )

    asyncio.create_task(
        _index_schema_background(org_id=payload.organization_id, db_conn_id=conn_id, schema=schema)
    )

    return _to_public(doc)


async def list_db_connections(
    skip: int = 0, limit: int = 20
) -> tuple[List[DbConnectionPublic], int]:
    total = await db_connections_collection.count_documents(NOT_DELETED)
    logger.info(
        "[db-connections] list_db_connections (super_admin path) db=%s coll=%s skip=%s limit=%s -> total=%s",
        db_connections_collection.database.name, db_connections_collection.name, skip, limit, total,
    )
    cursor = db_connections_collection.find(NOT_DELETED).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def list_db_connections_by_org(
    org_id: str, skip: int = 0, limit: int = 20
) -> tuple[List[DbConnectionPublic], int]:
    """List DB connections that belong to a specific organization (paginated)."""
    query = {"organization_id": org_id, **NOT_DELETED}
    total = await db_connections_collection.count_documents(query)
    logger.info(
        "[db-connections] list_db_connections_by_org db=%s coll=%s org_id=%s skip=%s limit=%s -> total=%s",
        db_connections_collection.database.name, db_connections_collection.name, org_id, skip, limit, total,
    )
    if total == 0:
        overall_count = await db_connections_collection.count_documents(NOT_DELETED)
        logger.warning(
            "[db-connections] list_db_connections_by_org returned 0 for org_id=%s -- "
            "db_connections_collection has %s non-deleted docs total (db=%s)",
            org_id, overall_count, db_connections_collection.database.name,
        )
    cursor = db_connections_collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def get_db_connection(conn_id: str) -> DbConnectionPublic:
    oid = _validate_object_id(conn_id)
    doc = await db_connections_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        logger.warning(
            "[db-connections] get_db_connection: no doc for conn_id=%s in db=%s",
            conn_id, db_connections_collection.database.name,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DB connection not found.",
        )
    return _to_public(doc)


async def update_db_connection(
    conn_id: str, payload: DbConnectionUpdate
) -> DbConnectionPublic:
    oid = _validate_object_id(conn_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )
    # If the connection string changed, re-fetch the schema and re-encrypt.
    old_gridfs_id = None
    new_schema: dict | None = None
    new_conn = _resolve_connection_string(payload)
    if new_conn is not None:
        new_conn = await format_connection_string(new_conn, payload.connection_type)
        new_schema = await _fetch_schema_or_400(new_conn)
        existing = await db_connections_collection.find_one({"_id": oid, **NOT_DELETED})
        old_gridfs_id = existing.get("schema_gridfs_id") if existing else None
        updates["connection_string"] = encrypt(new_conn)
        if not _clean_optional_text(payload.connection_type):
            updates["connection_type"] = _infer_connection_type(new_conn, new_schema)
        updates.update(await _schema_storage_fields(new_schema))
    if "name" in updates:
        updates["name"] = _clean_optional_text(payload.name)
    if "connection_type" in updates and payload.connection_type is not None:
        updates["connection_type"] = _clean_optional_text(payload.connection_type)
    updates.pop("firebase", None)

    doc = await db_connections_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DB connection not found.",
        )
    await _delete_gridfs_schema(old_gridfs_id)

    if new_schema is not None:
        asyncio.create_task(
            _index_schema_background(
                org_id=doc["organization_id"],
                db_conn_id=conn_id,
                schema=new_schema,
            )
        )

    return _to_public(doc)


async def _delete_schema_index_background(org_id: str, db_conn_id: str) -> None:
    """Fire-and-forget: drop this connection's vectors from its org's tenant index."""
    try:
        from ai.rag.schema_indexer import delete_schema_index
        await delete_schema_index(org_id=org_id, db_conn_id=db_conn_id)
        logger.info("[schema-index] removed vectors for deleted conn=%s", db_conn_id)
    except Exception:
        logger.exception("[schema-index] failed to remove vectors for conn=%s", db_conn_id)


async def delete_db_connection(conn_id: str) -> None:
    """Soft delete: mark as deleted instead of removing the document."""
    oid = _validate_object_id(conn_id)
    doc = await db_connections_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DB connection not found.",
        )
    await db_connections_collection.update_one(
        {"_id": oid, **NOT_DELETED}, soft_delete_update()
    )
    # Drop this connection's indexed schema vectors so they don't linger in Qdrant.
    asyncio.create_task(
        _delete_schema_index_background(org_id=doc["organization_id"], db_conn_id=conn_id)
    )


async def get_schema(conn_id: str) -> dict:
    """Return the stored database schema for a connection (dedicated endpoint).

    Reads from GridFS transparently if the schema was too large to store inline.
    """
    oid = _validate_object_id(conn_id)
    doc = await db_connections_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DB connection not found.",
        )
    gridfs_id = doc.get("schema_gridfs_id")
    if gridfs_id:
        stream = await _bucket().open_download_stream(ObjectId(str(gridfs_id)))
        raw = await stream.read()
        return json.loads(raw)
    return doc.get("schema") or {}


async def get_decrypted_connection_string(conn_id: str) -> str:
    """Internal helper: return the plaintext connection string for actual use."""
    oid = _validate_object_id(conn_id)
    doc = await db_connections_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DB connection not found.",
        )
    return decrypt(doc["connection_string"])


async def preview_schema_with_descriptions(
    payload: DbConnectionPreviewRequest | str,
) -> dict:
    """Fetch the database schema and generate LLM descriptions for every table.

    Nothing is persisted — this is a read-only preview.

    Every discovered table is described. LLM requests are split into bounded
    batches and concurrency is limited so large schemas do not create one
    oversized model request.
    """
    if isinstance(payload, str):
        connection_string = payload
        conn_type = None
        conn_name = None
    else:
        connection_string = _resolve_connection_string(payload)
        conn_type = payload.connection_type
        conn_name = payload.name
    if not connection_string:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A connection string or Firebase configuration is required.",
        )
    if connection_string and not connection_string.startswith("firebase://"):
        connection_string = await format_connection_string(
            connection_string,
            connection_type=conn_type,
            name=conn_name,
        )
    schema = await _fetch_schema_or_400(connection_string)
    enriched, table_count, described_count, truncated = await _enrich_schema_with_descriptions(schema)
    return {
        **enriched,
        "table_count": table_count,
        "described_count": described_count,
        "truncated": truncated,
        "formatted_connection_string": connection_string,
    }


async def run_readonly_query(conn_id: str, query: str) -> str:
    """Execute a read-only query against a saved connection for UI testing."""
    connection_string = await get_decrypted_connection_string(conn_id)
    try:
        return await run_in_threadpool(run_query, connection_string, query)
    except QueryExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query failed: {exc}",
        ) from exc


async def save_descriptions(conn_id: str, table_descriptions: dict[str, str]) -> None:
    """Merge LLM descriptions into the stored schema for an existing connection.

    Reads the current schema (from inline storage or GridFS), merges the
    supplied descriptions, then writes it back using the same
    inline-vs-GridFS logic as on create. The old GridFS file is deleted if
    the updated schema routes to a new one.

    Unknown table names in ``table_descriptions`` are silently ignored.
    """
    oid = _validate_object_id(conn_id)
    doc = await db_connections_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DB connection not found.",
        )

    old_gridfs_id = doc.get("schema_gridfs_id")

    # Load current schema from wherever it lives
    if old_gridfs_id:
        stream = await _bucket().open_download_stream(ObjectId(str(old_gridfs_id)))
        raw = await stream.read()
        schema = json.loads(raw)
    else:
        schema = doc.get("schema") or {}

    _merge_descriptions_into_schema(schema, table_descriptions)

    storage_fields = await _schema_storage_fields(schema)
    await db_connections_collection.update_one(
        {"_id": oid, **NOT_DELETED},
        {"$set": storage_fields},
    )

    # Clean up the old GridFS file if a new one was written (or schema shrank to inline)
    new_gridfs_id = storage_fields.get("schema_gridfs_id")
    if old_gridfs_id and str(old_gridfs_id) != str(new_gridfs_id or ""):
        await _delete_gridfs_schema(old_gridfs_id)

    # Re-index Qdrant with the updated schema so the user-reviewed descriptions
    # are reflected in vector search. The indexer will use existing descriptions
    # and only call the LLM for any tables still missing one.
    asyncio.create_task(
        _index_schema_background(
            org_id=doc["organization_id"],
            db_conn_id=conn_id,
            schema=schema,
        )
    )
