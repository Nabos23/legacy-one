"""Fetch the schema of an external database from its connection string.

Supports SQL (PostgreSQL, MySQL, SQLite via SQLAlchemy), MongoDB (via pymongo),
and Supabase (PostgreSQL hosted on supabase.co — detected automatically).
All functions here are SYNCHRONOUS and may block on network I/O — call them from
async code via `starlette.concurrency.run_in_threadpool`.
"""

from urllib.parse import urlparse

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from backend.core.constants import (
    DB_INTROSPECT_TIMEOUT_SECONDS as _TIMEOUT_SECONDS,
    MONGO_SAMPLE_SIZE as _MONGO_SAMPLE,
)
from backend.core.firebase_connection import (
    FirebaseConnectionError,
    is_firebase_connection,
    parse_firestore_connection_string,
)


class SchemaFetchError(Exception):
    """Raised when the external database's schema cannot be fetched."""


def _is_supabase(connection_string: str) -> bool:
    """Detect Supabase PostgreSQL connections by checking the host."""
    host = urlparse(connection_string).hostname or ""
    return "supabase.co" in host


def fetch_schema(connection_string: str) -> dict:
    """Connect to the database and return a JSON-serializable schema description.

    Raises SchemaFetchError if the database is unreachable or introspection fails.
    """
    scheme = urlparse(connection_string).scheme.lower()
    try:
        if is_firebase_connection(connection_string):
            return _fetch_firestore(connection_string)
        if scheme.startswith("mongodb"):
            return _fetch_mongo(connection_string)
        result = _fetch_sql(connection_string)
        if _is_supabase(connection_string):
            result["supabase"] = True
        return result
    except SchemaFetchError:
        raise
    except Exception as e:
        raise SchemaFetchError(f"{type(e).__name__}: {e}") from e


def _normalize_sql_url(connection_string: str):
    """Pick a driver we actually have installed for the given scheme."""
    url = make_url(connection_string)
    backend = url.get_backend_name()
    if backend in ("postgresql", "postgres"):
        url = url.set(drivername="postgresql+psycopg2")
    elif backend == "mysql":
        url = url.set(drivername="mysql+pymysql")
    elif backend == "mssql":
        url = url.set(drivername="mssql+pyodbc")
        if not url.database:
            url = url.set(database="master")
        query = dict(url.query)
        driver = query.get("driver", "")
        if not driver or driver.upper() in ("DRIVER", ""):
            query["driver"] = "ODBC Driver 17 for SQL Server"
        query.setdefault("TrustServerCertificate", "yes")
        url = url.set(query=query)
    return url


def _fetch_sql(connection_string: str) -> dict:
    url = _normalize_sql_url(connection_string)
    dialect = url.get_backend_name()
    connect_args = {}
    if dialect in ("postgresql", "mysql"):
        connect_args["connect_timeout"] = _TIMEOUT_SECONDS

    SKIP_SCHEMAS = {"information_schema", "sys", "guest", "INFORMATION_SCHEMA", "SYS"}

    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    try:
        insp = inspect(engine)

        all_schemas = insp.get_schema_names()
        schemas_to_scan = [s for s in all_schemas if s not in SKIP_SCHEMAS]

        tables: dict = {}
        for db_schema in schemas_to_scan:
            for table in insp.get_table_names(schema=db_schema):
                full_name = table if db_schema == "dbo" else f"{db_schema}.{table}"
                columns = [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": bool(col.get("nullable", True)),
                        "default": str(col.get("default", "")),
                    }
                    for col in insp.get_columns(table, schema=db_schema)
                ]

                indexes = [
                    {
                        "name": idx.get("name"),
                        "columns": idx.get("column_names", idx.get("columns", [])),
                        "unique": idx.get("unique", False),
                    }
                    for idx in insp.get_indexes(table, schema=db_schema)
                ]

                foreign_keys = [
                    {
                        "column": fk["constrained_columns"],
                        "references_table": fk["referred_table"],
                        "references_column": fk["referred_columns"],
                    }
                    for fk in insp.get_foreign_keys(table, schema=db_schema)
                ]

                tables[full_name] = {
                    "columns": columns,
                    "indexes": indexes,
                    "foreign_keys": foreign_keys,
                }

        views: dict = {}
        try:
            for db_schema in schemas_to_scan:
                for view in insp.get_view_names(schema=db_schema):
                    full_view_name = view if db_schema == "dbo" else f"{db_schema}.{view}"
                    view_columns = [
                        {"name": col["name"], "type": str(col["type"])}
                        for col in insp.get_columns(view, schema=db_schema)
                    ]
                    views[full_view_name] = {"columns": view_columns}
        except Exception:
            pass

        result = {
            "kind": "sql",
            "dialect": dialect,
            "tables": tables,
        }
        if views:
            result["views"] = views

        enums = _get_enums(engine, dialect)
        if enums:
            result["enums"] = enums

        return result
    finally:
        engine.dispose()


def _get_enums(engine, dialect: str) -> list:
    """Fetch enum types for PostgreSQL databases."""
    if dialect != "postgresql":
        return []
    try:
        with engine.connect() as conn:
            result = conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder) AS values "
                    "FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid "
                    "GROUP BY t.typname"
                )
            )
            return [
                {"name": row[0], "values": row[1]} for row in result
            ]
    except Exception:
        return []


def _infer_type(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _fetch_firestore(connection_string: str) -> dict:
    """Fetch top-level Firestore collections and infer fields from sample docs."""
    try:
        from google.cloud import firestore
        from google.oauth2 import service_account
    except ImportError as exc:
        raise SchemaFetchError(
            "Firestore support requires the google-cloud-firestore package."
        ) from exc

    try:
        service_account_info, project_id, database_id = parse_firestore_connection_string(
            connection_string
        )
    except FirebaseConnectionError as exc:
        raise SchemaFetchError(str(exc)) from exc

    try:
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/datastore"],
        )
        client = firestore.Client(
            project=project_id,
            credentials=credentials,
            database=database_id,
        )

        collections: dict = {}
        for collection_ref in client.collections():
            fields: dict[str, set[str]] = {}
            sample_count = 0
            for doc in collection_ref.limit(_MONGO_SAMPLE).stream(
                timeout=_TIMEOUT_SECONDS
            ):
                sample_count += 1
                for key, val in doc.to_dict().items():
                    fields.setdefault(key, set()).add(_infer_type(val))

            collections[collection_ref.id] = {
                "fields": {
                    name: {"types": sorted(types)}
                    for name, types in sorted(fields.items())
                },
                "sample_document_count": sample_count,
            }

        return {
            "kind": "firebase",
            "database": "firestore",
            "project_id": project_id,
            "database_id": database_id,
            "collections": collections,
        }
    except SchemaFetchError:
        raise
    except Exception as exc:
        raise SchemaFetchError(f"{type(exc).__name__}: {exc}") from exc


def _fetch_mongo(connection_string: str) -> dict:
    from pymongo import MongoClient
    from pymongo.uri_parser import parse_uri

    client = MongoClient(connection_string, serverSelectionTimeoutMS=_TIMEOUT_SECONDS * 1000)
    try:
        client.admin.command("ping")
        db_in_uri = parse_uri(connection_string).get("database")
        if db_in_uri:
            db_names = [db_in_uri]
        else:
            db_names = [
                n for n in client.list_database_names()
                if n not in ("admin", "local", "config")
            ]

        databases: dict = {}
        for db_name in db_names:
            mongo_db = client[db_name]
            collections: dict = {}
            for coll_name in mongo_db.list_collection_names():
                fields: dict = {}
                type_counts: dict = {}
                for doc in mongo_db[coll_name].find().limit(_MONGO_SAMPLE):
                    for key, val in doc.items():
                        t = _infer_type(val)
                        if key not in fields:
                            fields[key] = set()
                        fields[key].add(t)
                        type_counts.setdefault(key, {})
                        type_counts[key][t] = type_counts[key].get(t, 0) + 1

                sorted_fields = {}
                for fname in sorted(fields.keys()):
                    types = sorted(fields[fname])
                    sorted_fields[fname] = {
                        "types": types,
                    }

                doc_count = mongo_db[coll_name].estimated_document_count()
                indexes = list(mongo_db[coll_name].list_indexes())
                idx_info = [
                    {
                        "name": idx["name"],
                        "keys": [k for k in idx["key"]],
                        "unique": idx.get("unique", False),
                    }
                    for idx in indexes
                ]

                collections[coll_name] = {
                    "fields": sorted_fields,
                    "document_count": doc_count,
                    "indexes": idx_info,
                }
            databases[db_name] = collections
        return {"kind": "mongo", "databases": databases}
    finally:
        client.close()
