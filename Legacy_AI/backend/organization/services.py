import re
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import HTTPException, status

from backend.core.quota import enforce_orgs_per_day
from backend.auth.cache import invalidate_all, invalidate_user
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.auth.permissions import is_super_admin
from backend.db.database import (
    agents_collection,
    chat_sessions_collection,
    connector_credentials_collection,
    connector_instances_collection,
    connector_tokens_collection,
    conversation_logs_collection,
    db_connections_collection,
    mcp_oauth_flows_collection,
    mcp_oauth_tokens_sync,
    mcp_servers_collection,
    notifications_collection,
    organization_settings_collection,
    organizations_collection,
    teams_collection,
    tools_collection,
    users_collection,
)
from backend.organization.schemas import (
    OrganizationCreate,
    OrganizationPublic,
    OrganizationUpdate,
)


def _to_public(doc: dict) -> OrganizationPublic:
    """Map a MongoDB organization document to the public schema."""
    return OrganizationPublic(
        id=str(doc["_id"]),
        name=doc["name"],
        description=doc.get("description"),
        created_by=doc.get("created_by"),
        created_at=doc.get("created_at") or datetime.now(timezone.utc),
        updated_at=doc.get("updated_at"),
    )


def _validate_object_id(org_id: str) -> ObjectId:
    """Convert a string id to ObjectId or raise 404 if malformed."""
    if not ObjectId.is_valid(org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    return ObjectId(org_id)


async def create_organization(
    payload: OrganizationCreate, created_by: str
) -> OrganizationPublic:
    await enforce_orgs_per_day(created_by)
    now = datetime.now(timezone.utc)
    doc = {
        "name": payload.name,
        "description": payload.description,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    result = await organizations_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    org_id = str(result.inserted_id)
    user = await users_collection.find_one({"_id": ObjectId(created_by)})
    if user:
        if not is_super_admin(user.get("role", "")):
            await users_collection.update_one(
                {"_id": ObjectId(created_by)},
                {"$set": {"organization_id": org_id}},
            )
            invalidate_user(created_by)
    return _to_public(doc)


def _search_query(search: str | None) -> dict:
    """Case-insensitive match on name or description; empty when no search given."""
    if not search or not search.strip():
        return {}
    pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
    return {"$or": [{"name": pattern}, {"description": pattern}]}


ORGANIZATION_SORTABLE_FIELDS = {"name", "created_at"}


async def list_organizations(
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[List[OrganizationPublic], int]:
    query = {**NOT_DELETED, **_search_query(search)}
    field = sort_by if sort_by in ORGANIZATION_SORTABLE_FIELDS else "created_at"
    direction = 1 if sort_order == "asc" else -1
    total = await organizations_collection.count_documents(query)
    cursor = organizations_collection.find(query).sort(field, direction).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def get_organization(org_id: str) -> OrganizationPublic:
    oid = _validate_object_id(org_id)
    doc = await organizations_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    return _to_public(doc)


async def update_organization(
    org_id: str, payload: OrganizationUpdate
) -> OrganizationPublic:
    oid = _validate_object_id(org_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )
    updates["updated_at"] = datetime.now(timezone.utc)

    doc = await organizations_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    return _to_public(doc)


async def delete_organization(org_id: str) -> None:
    """Soft-delete the organization AND everything scoped to it, so nothing is
    left orphaned under a now-invisible organization:

    - Records with an existing is_deleted/NOT_DELETED convention (users,
      agents, tools, teams, db connections, chat sessions, MCP servers,
      notifications) are soft-deleted the same way their own
      single-item delete already works.
    - Records with no soft-delete convention today (org settings, conversation
      logs, pending MCP OAuth flows, connector credentials/tokens/instances)
      are hard-deleted outright — they're either a single settings blob, an
      in-progress ephemeral flow, or live secrets, not history worth keeping.

    Deliberately NOT touched: query_audit_logs (compliance/audit trail — an
    org being deleted shouldn't erase the record that it existed), and the
    global catalogs (tool_registry, connector_registry, mcp_server_registry,
    roles/permissions) which aren't org-scoped at all.
    """
    oid = _validate_object_id(org_id)

    # Snapshot the org's user and MCP-server ids *before* anything is
    # soft-deleted — soft-delete doesn't remove the doc so this would still
    # work after too, but this keeps the intent obvious: these ids drive the
    # joins below (connector secrets keyed by owner_id, OAuth tokens keyed by
    # MCP server id).
    user_ids = [str(doc["_id"]) async for doc in users_collection.find({"organization_id": org_id}, {"_id": 1})]
    mcp_server_ids = [
        str(doc["_id"])
        async for doc in mcp_servers_collection.find({"organization_id": org_id, **NOT_DELETED}, {"_id": 1})
    ]

    result = await organizations_collection.update_one(
        {"_id": oid, **NOT_DELETED}, soft_delete_update()
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    cascade_filter = {"organization_id": org_id, **NOT_DELETED}
    update = soft_delete_update()
    await users_collection.update_many(cascade_filter, update)
    invalidate_all()
    await agents_collection.update_many(cascade_filter, update)
    await tools_collection.update_many(cascade_filter, update)
    await teams_collection.update_many(cascade_filter, update)
    await db_connections_collection.update_many(cascade_filter, update)
    await chat_sessions_collection.update_many(cascade_filter, update)
    await notifications_collection.update_many(cascade_filter, update)
    await mcp_servers_collection.update_many(cascade_filter, update)

    # No soft-delete convention for these — hard-delete the org-scoped records.
    await organization_settings_collection.delete_many({"organization_id": org_id})
    await conversation_logs_collection.delete_many({"organization_id": org_id})
    await mcp_oauth_flows_collection.delete_many({"organization_id": org_id})

    # Connector credentials/tokens/instances are keyed by owner_id, which is
    # either this org's id (org-scoped connectors) or one of its users' ids
    # (user-scoped connectors) — live secrets, not history, so hard-delete.
    owner_filter = {"owner_id": {"$in": [org_id, *user_ids]}}
    await connector_credentials_collection.delete_many(owner_filter)
    await connector_tokens_collection.delete_many(owner_filter)
    await connector_instances_collection.delete_many(owner_filter)

    # Pending OAuth tokens for this org's MCP servers live in a separate,
    # sync-only collection keyed by the server's own id.
    if mcp_server_ids:
        mcp_oauth_tokens_sync.delete_many({"storage_key": {"$in": mcp_server_ids}})
