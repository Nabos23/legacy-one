import logging

from fastapi import APIRouter, Depends, status

from backend.auth.permissions import assert_org_access, is_super_admin
from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dbconnection import services
from backend.dbconnection.schemas import (
    DbConnectionCreate,
    DbConnectionFormatRequest,
    DbConnectionFormatResponse,
    DbConnectionPreviewRequest,
    DbConnectionPublic,
    DbConnectionQueryRequest,
    DbConnectionUpdate,
    SaveDescriptionsRequest,
)
from backend.dependencies import get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/db-connections",
    tags=["db-connections"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/format", response_model=DbConnectionFormatResponse)
async def format_db_connection(
    payload: DbConnectionFormatRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> DbConnectionFormatResponse:
    """Format and normalize a raw database connection string.

    Accepts connection_string, optional connection_type, and optional name.
    Returns the normalized connection_string, connection_type, and name.
    """
    formatted = await services.format_connection_string(
        connection_string=payload.connection_string,
        connection_type=payload.connection_type,
        name=payload.name,
    )
    conn_type = payload.connection_type or services._infer_connection_type(formatted)
    return DbConnectionFormatResponse(
        connection_string=formatted,
        connection_type=conn_type,
        name=payload.name,
    )


@router.post("/preview")
async def preview_db_connection(
    payload: DbConnectionPreviewRequest,
    current_user: UserPublic = Depends(require_permission("create_db_connection")),
) -> dict:
    """Fetch the database schema and generate LLM descriptions for every table.

    Nothing is persisted. Returns the full schema with a ``description`` field
    on each table/collection, plus metadata:
    - ``table_count``: total tables found in the DB
    - ``described_count``: how many received LLM descriptions
    - ``truncated``: retained for API compatibility; always false because all
      discovered tables are sent for description generation
    """
    assert_org_access(current_user, payload.organization_id)
    return await services.preview_schema_with_descriptions(payload)


@router.post("", response_model=DbConnectionPublic, status_code=status.HTTP_201_CREATED)
async def create_db_connection(
    payload: DbConnectionCreate,
    current_user: UserPublic = Depends(require_permission("create_db_connection")),
) -> DbConnectionPublic:
    """Create a DB connection. organization_id must be provided and must be a valid org.
    The connection string is encrypted before storage."""
    assert_org_access(current_user, payload.organization_id)
    return await services.create_db_connection(payload)


@router.get("", response_model=Page[DbConnectionPublic])
async def list_db_connections(
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_db_connection")),
) -> Page[DbConnectionPublic]:
    """List DB connections (paginated; connection strings are masked)."""
    logger.info(
        "[db-connections] GET /db-connections by user=%s role=%s org_id=%s skip=%s limit=%s",
        current_user.id, current_user.role, current_user.organization_id, pg.skip, pg.limit,
    )
    if is_super_admin(current_user.role):
        items, total = await services.list_db_connections(skip=pg.skip, limit=pg.limit)
    else:
        items, total = await services.list_db_connections_by_org(
            current_user.organization_id, skip=pg.skip, limit=pg.limit
        )
    logger.info("[db-connections] GET /db-connections -> returning %s of %s items", len(items), total)
    return build_page(items, total, pg)


@router.get("/{conn_id}", response_model=DbConnectionPublic)
async def get_db_connection(
    conn_id: str,
    current_user: UserPublic = Depends(require_permission("view_db_connection")),
) -> DbConnectionPublic:
    """Retrieve a single DB connection by id (connection string masked)."""
    logger.info(
        "[db-connections] GET /db-connections/%s by user=%s role=%s",
        conn_id, current_user.id, current_user.role,
    )
    conn = await services.get_db_connection(conn_id)
    assert_org_access(current_user, conn.organization_id)
    return conn


@router.get("/{conn_id}/schema")
async def get_db_connection_schema(
    conn_id: str,
    current_user: UserPublic = Depends(require_permission("view_db_connection")),
) -> dict:
    """Return the fetched database schema for this connection."""
    conn = await services.get_db_connection(conn_id)
    assert_org_access(current_user, conn.organization_id)
    return await services.get_schema(conn_id)


@router.put("/{conn_id}", response_model=DbConnectionPublic)
async def update_db_connection(
    conn_id: str,
    payload: DbConnectionUpdate,
    current_user: UserPublic = Depends(require_permission("edit_db_connection")),
) -> DbConnectionPublic:
    """Update a DB connection (re-encrypts the connection string if provided)."""
    conn = await services.get_db_connection(conn_id)
    assert_org_access(current_user, conn.organization_id)
    return await services.update_db_connection(conn_id, payload)


@router.delete("/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_db_connection(
    conn_id: str,
    current_user: UserPublic = Depends(require_permission("delete_db_connection")),
) -> None:
    """Delete a DB connection."""
    conn = await services.get_db_connection(conn_id)
    assert_org_access(current_user, conn.organization_id)
    await services.delete_db_connection(conn_id)


@router.post("/{conn_id}/descriptions", status_code=status.HTTP_204_NO_CONTENT)
async def save_table_descriptions(
    conn_id: str,
    payload: SaveDescriptionsRequest,
    current_user: UserPublic = Depends(require_permission("edit_db_connection")),
) -> None:
    """Save LLM-generated table descriptions into the connection's stored schema.

    Merges the supplied ``table_descriptions`` dict (table_name → description)
    into the connection's stored schema and persists it. Unknown table names are
    silently ignored. Requires **edit_db_connection** permission.
    """
    conn = await services.get_db_connection(conn_id)
    assert_org_access(current_user, conn.organization_id)
    await services.save_descriptions(conn_id, payload.table_descriptions)


@router.post("/{conn_id}/query")
async def query_db_connection(
    conn_id: str,
    payload: DbConnectionQueryRequest,
    current_user: UserPublic = Depends(require_permission("view_db_connection")),
) -> dict:
    """Run a read-only test query against a saved DB connection."""
    conn = await services.get_db_connection(conn_id)
    assert_org_access(current_user, conn.organization_id)
    return {"result": await services.run_readonly_query(conn_id, payload.query)}
