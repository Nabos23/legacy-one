"""Execute user queries against an external database.

All functions are SYNCHRONOUS — call from async code via run_in_threadpool.
Supports PostgreSQL, MySQL, SQLite (via SQLAlchemy) and MongoDB.
"""

import hashlib
import json
import logging
import re
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from backend.core.firebase_connection import (
    FirebaseConnectionError,
    is_firebase_connection,
    parse_firestore_connection_string,
)

logger = logging.getLogger(__name__)

MAX_ROWS = 100
MAX_CELL_CHARS = 300      # truncate individual oversized cell values
MAX_OUTPUT_CHARS = 6000   # hard cap on the text returned to the agent (protects context)


def _fmt(v) -> str:
    """Render a single cell value safely for the agent."""
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray, memoryview)):
        return f"<{len(bytes(v))} bytes>"
    s = str(v)
    if len(s) > MAX_CELL_CHARS:
        s = s[:MAX_CELL_CHARS] + "…"
    return s


def _cap(text: str) -> str:
    """Cap total output so a wide/large result can't blow up the agent's context."""
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + f"\n… (output truncated at {MAX_OUTPUT_CHARS} characters — narrow your query)"
    return text

# Reject any statement that mutates data or schema. Agents are read-only by
# design, so this is enforced before the query ever reaches the database.
_WRITE_PATTERN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|MERGE|GRANT|"
    r"REVOKE|EXEC|EXECUTE|CALL)\b",
    re.IGNORECASE,
)

# Engines are expensive to build and own their own connection pool, so we cache
# one per distinct connection string instead of creating one per query.
_engine_pool: dict[str, Engine] = {}


class QueryExecutionError(Exception):
    pass


def run_query(connection_string: str, query: str) -> str:
    """Execute a query against the given database and return formatted results."""
    scheme = urlparse(connection_string).scheme.lower()
    if is_firebase_connection(connection_string):
        db_type = "firebase"
    else:
        db_type = "mongo" if scheme.startswith("mongodb") else "sql"
    logger.info("[query-runner] executing %s query: %.200s", db_type, query.strip() if isinstance(query, str) else str(query))
    if is_firebase_connection(connection_string):
        return run_firestore_query(connection_string, query)
    if scheme.startswith("mongodb"):
        return run_mongo_query(connection_string, query)
    return run_sql_query(connection_string, query)


def _normalize_url(connection_string: str):
    url = make_url(connection_string)
    backend = url.get_backend_name()
    if backend in ("postgresql", "postgres"):
        url = url.set(drivername="postgresql+psycopg2")
    elif backend == "mysql":
        url = url.set(drivername="mysql+pymysql")
    return url


def _get_engine(connection_string: str) -> Engine:
    """Return a pooled SQLAlchemy engine for the connection string, creating one lazily."""
    key = hashlib.sha256(connection_string.encode("utf-8")).hexdigest()
    engine = _engine_pool.get(key)
    if engine is None:
        url = _normalize_url(connection_string)
        backend = url.get_backend_name()
        logger.info("[query-runner] creating new engine pool for backend=%s", backend)
        if backend == "sqlite":
            engine = create_engine(url, pool_pre_ping=True)
        else:
            engine = create_engine(url, pool_size=5, max_overflow=10, pool_pre_ping=True)
        _engine_pool[key] = engine
    return engine


def _assert_readonly(query: str) -> None:
    """Raise if the SQL statement would mutate data or schema."""
    if _WRITE_PATTERN.match(query.strip()):
        raise QueryExecutionError(
            "Only SELECT queries are allowed. Write operations are disabled for agents."
        )


def run_sql_query(connection_string: str, query: str) -> str:
    """Execute a read-only SQL query against the given connection string."""
    import time
    logger.info("[query-runner:sql] executing SQL query: %.200s", query.strip() if isinstance(query, str) else str(query))
    _assert_readonly(query)
    engine = _get_engine(connection_string)
    t0 = time.monotonic()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchmany(MAX_ROWS)
            columns = list(result.keys())
            elapsed = time.monotonic() - t0

            if not rows:
                logger.info("[query-runner:sql] done in %.3fs — 0 rows", elapsed)
                return "Query executed successfully. No rows returned."

            col_header = " | ".join(columns)
            separator = "-" * len(col_header)
            data_lines = [" | ".join(_fmt(v) for v in row) for row in rows]
            lines = [col_header, separator] + data_lines

            truncated = len(rows) == MAX_ROWS
            logger.info(
                "[query-runner:sql] done in %.3fs — %d row(s) returned%s, %d col(s)",
                elapsed, len(rows), " (capped)" if truncated else "", len(columns),
            )
            if truncated:
                lines.append(f"\n(Showing first {MAX_ROWS} rows — add filters or aggregate to see the rest)")

            output = _cap("\n".join(lines))
            if len(output) >= MAX_OUTPUT_CHARS:
                logger.warning("[query-runner:sql] output truncated to %d chars", MAX_OUTPUT_CHARS)
            return output

    except QueryExecutionError:
        raise
    except Exception as e:
        logger.error("[query-runner:sql] failed after %.3fs: %s", time.monotonic() - t0, e)
        raise QueryExecutionError(str(e)) from e


def _run_sql(connection_string: str, query: str) -> str:
    return run_sql_query(connection_string, query)


def run_mongo_query(connection_string: str, query: str) -> str:
    """Execute a MongoDB query against the given connection string."""
    from pymongo import MongoClient
    from pymongo.uri_parser import parse_uri

    logger.info("[query-runner:mongo] executing MongoDB query: %.200s", query.strip() if isinstance(query, str) else str(query))

    try:
        query_dict = json.loads(query) if isinstance(query, str) else query
    except json.JSONDecodeError as e:
        raise QueryExecutionError(
            f"MongoDB query must be valid JSON. Example: "
            '{"collection": "users", "filter": {"status": "active"}}. '
            f"Parse error: {e}"
        ) from e

    collection_name = query_dict.get("collection")
    if not collection_name:
        raise QueryExecutionError(
            "MongoDB query must include a 'collection' key. "
            'Example: {"collection": "users", "filter": {}}'
        )

    filter_dict = query_dict.get("filter", {})
    projection = query_dict.get("projection") or None
    sort = query_dict.get("sort") or None
    limit = min(int(query_dict.get("limit", MAX_ROWS)), MAX_ROWS)

    try:
        parsed = parse_uri(connection_string)
    except Exception as e:
        raise QueryExecutionError(f"Invalid MongoDB URI: {e}") from e

    db_name = parsed.get("database")
    if not db_name:
        raise QueryExecutionError(
            "MongoDB connection string must include a database name, "
            "e.g. mongodb://host:27017/mydb"
        )

    if "." in collection_name:
        parts = collection_name.split(".", 1)
        if parts[0] == db_name:
            collection_name = parts[1]

    import time
    logger.info(
        "[query-runner:mongo] db=%s collection=%s filter=%s limit=%d",
        db_name, collection_name, filter_dict, limit,
    )
    client = MongoClient(connection_string, serverSelectionTimeoutMS=10_000)
    t0 = time.monotonic()
    try:
        mongo_db = client[db_name]
        cursor = mongo_db[collection_name].find(filter_dict, projection)
        if sort:
            cursor = cursor.sort(list(sort.items()))
        cursor = cursor.limit(limit)
        docs = list(cursor)
        elapsed = time.monotonic() - t0

        if not docs:
            logger.info("[query-runner:mongo] done in %.3fs — 0 documents matched", elapsed)
            return "Query executed successfully. No documents matched."

        truncated = len(docs) == limit
        logger.info(
            "[query-runner:mongo] done in %.3fs — %d doc(s) returned%s",
            elapsed, len(docs), " (capped)" if truncated else "",
        )
        output = json.dumps(docs, default=str, indent=2)
        if truncated:
            output += f"\n\n(Showing up to {limit} documents — increase 'limit' to see more)"
        result = _cap(output)
        if len(result) >= MAX_OUTPUT_CHARS:
            logger.warning("[query-runner:mongo] output truncated to %d chars", MAX_OUTPUT_CHARS)
        return result

    except QueryExecutionError:
        raise
    except Exception as e:
        logger.error("[query-runner:mongo] failed after %.3fs: %s", time.monotonic() - t0, e)
        raise QueryExecutionError(str(e)) from e
    finally:
        client.close()


def _run_mongo(connection_string: str, query: str) -> str:
    return run_mongo_query(connection_string, query)


def _serialize_firestore_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "path"):
        return value.path
    if isinstance(value, dict):
        return {k: _serialize_firestore_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_firestore_value(v) for v in value]
    return value


def _run_firestore(connection_string: str, query: str) -> str:
    """Execute a read-only Firestore query.

    The agent should provide JSON like:
        {
          "collection": "users",
          "filters": [["status", "==", "active"]],
          "order_by": [["created_at", "DESCENDING"]],
          "limit": 20
        }

    Supported keys: collection (required), filters, order_by, limit.
    """
    try:
        from google.cloud import firestore
        from google.oauth2 import service_account
    except ImportError as exc:
        raise QueryExecutionError(
            "Firestore support requires the google-cloud-firestore package."
        ) from exc

    try:
        query_dict = json.loads(query)
    except json.JSONDecodeError as exc:
        raise QueryExecutionError(
            "Firestore query must be valid JSON. Example: "
            '{"collection": "users", "filters": [["status", "==", "active"]]}. '
            f"Parse error: {exc}"
        ) from exc

    collection_name = query_dict.get("collection")
    if not collection_name:
        raise QueryExecutionError(
            "Firestore query must include a 'collection' key. "
            'Example: {"collection": "users", "filters": []}'
        )

    filters = query_dict.get("filters") or []
    order_by = query_dict.get("order_by") or []
    limit = min(int(query_dict.get("limit", MAX_ROWS)), MAX_ROWS)

    try:
        service_account_info, project_id, database_id = parse_firestore_connection_string(
            connection_string
        )
    except FirebaseConnectionError as exc:
        raise QueryExecutionError(str(exc)) from exc

    import time

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/datastore"],
    )
    client = firestore.Client(
        project=project_id,
        credentials=credentials,
        database=database_id,
    )

    logger.info(
        "[query-runner] firestore query - project=%s database=%s collection=%s limit=%d",
        project_id,
        database_id,
        collection_name,
        limit,
    )
    t0 = time.monotonic()
    try:
        fs_query = client.collection(collection_name)
        for item in filters:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise QueryExecutionError(
                    "Each Firestore filter must be [field, operator, value]."
                )
            field, operator, value = item
            fs_query = fs_query.where(field, operator, value)

        for item in order_by:
            if isinstance(item, str):
                field, direction = item, "ASCENDING"
            elif isinstance(item, (list, tuple)) and len(item) in (1, 2):
                field = item[0]
                direction = item[1] if len(item) == 2 else "ASCENDING"
            else:
                raise QueryExecutionError(
                    "Each Firestore order_by item must be a field string or [field, direction]."
                )
            direction_attr = str(direction).upper()
            if direction_attr not in ("ASCENDING", "DESCENDING"):
                raise QueryExecutionError("Firestore order_by direction must be ASCENDING or DESCENDING.")
            fs_query = fs_query.order_by(field, direction=getattr(firestore.Query, direction_attr))

        docs = list(fs_query.limit(limit).stream())
        elapsed = time.monotonic() - t0
        if not docs:
            logger.info("[query-runner] firestore done in %.3fs - 0 documents matched", elapsed)
            return "Query executed successfully. No documents matched."

        rows = [
            {
                "id": doc.id,
                **{
                    key: _serialize_firestore_value(value)
                    for key, value in doc.to_dict().items()
                },
            }
            for doc in docs
        ]
        output = json.dumps(rows, default=str, indent=2)
        if len(rows) == limit:
            output += f"\n\n(Showing up to {limit} documents - increase 'limit' to see more)"
        result = _cap(output)
        if len(result) >= MAX_OUTPUT_CHARS:
            logger.warning("[query-runner] firestore output truncated to %d chars", MAX_OUTPUT_CHARS)
        logger.info(
            "[query-runner] firestore done in %.3fs - %d doc(s) returned",
            elapsed,
            len(rows),
        )
        return result
    except QueryExecutionError:
        raise
    except Exception as exc:
        logger.error(
            "[query-runner] firestore failed after %.3fs: %s",
            time.monotonic() - t0,
            exc,
        )
        raise QueryExecutionError(str(exc)) from exc
