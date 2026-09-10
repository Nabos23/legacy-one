import logging
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import HTTPException, status

from backend.core.quota import enforce_tools_per_org
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.db.database import agents_collection, db_connections_collection, organizations_collection, tool_registry_collection, tools_collection
from backend.tool.schemas import ToolCreate, ToolPublic, ToolUpdate

from backend.agent.services import _invalidate_org_graph_cache, _merge_tool_into_prompt
from backend.notifications import services as notification_services
from backend.core.encryption import encrypt, decrypt_or_none

logger = logging.getLogger(__name__)


def _to_public(doc: dict, agent_info: dict | None = None) -> ToolPublic:
    """Map a MongoDB tool document to the public schema."""
    info = agent_info or {}
    return ToolPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        agent_id=doc.get("agent_id") or None,
        agent_name=info.get("name"),
        agent_avatar_type=info.get("avatar_type"),
        agent_avatar_value=info.get("avatar_value"),
        agent_avatar_url=info.get("avatar_url"),
        name=doc.get("name"),
        user_description=doc.get("user_description"),
        tool_id=doc["tool_id"],
        db_conn_id=doc.get("db_conn_id"),
        has_custom_credentials=bool(doc.get("encrypted_api_key")),
        created_at=doc["created_at"],
    )


async def _fetch_agent_info(agent_ids: list[str]) -> dict[str, dict]:
    """Batch-resolve agent ids to their display names and avatar information."""
    valid_ids = {ObjectId(a) for a in set(agent_ids) if a and ObjectId.is_valid(a)}
    if not valid_ids:
        return {}
    cursor = agents_collection.find(
        {"_id": {"$in": list(valid_ids)}},
        {"name": 1, "avatar_type": 1, "avatar_value": 1, "avatar_url": 1}
    )
    return {
        str(doc["_id"]): {
            "name": doc.get("name"),
            "avatar_type": doc.get("avatar_type"),
            "avatar_value": doc.get("avatar_value"),
            "avatar_url": doc.get("avatar_url"),
        }
        async for doc in cursor
    }


def _validate_object_id(tool_id: str) -> ObjectId:
    """Convert a string id to ObjectId or raise 404 if malformed."""
    if not ObjectId.is_valid(tool_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found.",
        )
    return ObjectId(tool_id)


async def _validate_tool_id_exists(tool_id: str) -> dict:
    """Return the registry entry, or raise if tool_id is invalid/inactive."""
    if not ObjectId.is_valid(tool_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid tool_id: must be a valid ObjectId.",
        )
    doc = await tool_registry_collection.find_one(
        {"_id": ObjectId(tool_id), "is_active": True, "is_deleted": {"$ne": True}}
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="tool_id does not reference an active tool registry entry.",
        )
    return doc


async def validate_org_exists(org_id: str) -> None:
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


async def _validate_db_connection_in_org(db_conn_id: str | None, org_id: str) -> None:
    if not db_conn_id:
        return
    if not ObjectId.is_valid(db_conn_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid db_conn_id: must be a valid ObjectId.",
        )
    doc = await db_connections_collection.find_one(
        {"_id": ObjectId(db_conn_id), "organization_id": org_id, "is_deleted": {"$ne": True}},
        {"_id": 1},
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="db_conn_id does not reference a database connection in this organization.",
        )


async def create_tool(payload: ToolCreate) -> ToolPublic:
    await validate_org_exists(payload.organization_id)
    registry_entry = await _validate_tool_id_exists(payload.tool_id)
    await _validate_db_connection_in_org(payload.db_conn_id, payload.organization_id)
    await enforce_tools_per_org(payload.organization_id)
    doc = {
        "organization_id": payload.organization_id,
        "agent_id": payload.agent_id,
        "user_description": payload.user_description,
        "tool_id": payload.tool_id,
        "name": payload.name or registry_entry["name"],
        # Copy the registry's handler + schema so the runtime can resolve the
        # callable and tool spec without re-reading the registry.
        "handler": registry_entry.get("handler") or registry_entry["name"],
        "input_schema": registry_entry.get("tool_schema", {}),
        "created_at": datetime.now(timezone.utc),
        "is_deleted": False,
    }
    if payload.db_conn_id:
        doc["db_conn_id"] = payload.db_conn_id

    if payload.credentials:
        if payload.credentials.api_key:
            doc["encrypted_api_key"] = encrypt(payload.credentials.api_key)
        if payload.credentials.base_url:
            doc["custom_base_url"] = payload.credentials.base_url
        if payload.credentials.model:
            doc["custom_model"] = payload.credentials.model
    
    result = await tools_collection.insert_one(doc)
    doc["_id"] = result.inserted_id

    # Register the new tool on its agent's record.
    if ObjectId.is_valid(payload.agent_id):
        await agents_collection.update_one(
            {"_id": ObjectId(payload.agent_id), **NOT_DELETED},
            {"$addToSet": {"tool_ids": str(result.inserted_id)}},
        )

        await _merge_tool_into_prompt(payload.agent_id, doc, registry_entry)
        _invalidate_org_graph_cache(payload.organization_id, payload.agent_id)

    await notification_services.create_notification(
        organization_id=payload.organization_id,
        type="tool",
        title="Tool registered",
        message=f"{registry_entry['name']} was connected to an agent.",
    )
    agent_info = await _fetch_agent_info([payload.agent_id])
    return _to_public(doc, agent_info=agent_info.get(payload.agent_id))


EXCLUDE_INTERNAL_TOOLS = {"name": {"$nin": ["ask_human", "ask human", "human_in_loop"]}}


async def list_tools(skip: int = 0, limit: int = 20) -> tuple[List[ToolPublic], int]:
    total = await tools_collection.count_documents(NOT_DELETED)
    logger.info(
        "[tools] list_tools (super_admin path) db=%s coll=%s skip=%s limit=%s -> total=%s",
        tools_collection.database.name, tools_collection.name, skip, limit, total,
    )
    cursor = tools_collection.find(NOT_DELETED).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    agent_info = await _fetch_agent_info([doc.get("agent_id") for doc in docs])
    return [_to_public(doc, agent_info=agent_info.get(doc.get("agent_id"))) for doc in docs], total


async def list_tools_by_org(
    org_id: str, skip: int = 0, limit: int = 20
) -> tuple[List[ToolPublic], int]:
    """List tools that belong to a specific organization (paginated)."""
    query = {"organization_id": org_id, **NOT_DELETED, **EXCLUDE_INTERNAL_TOOLS}
    total = await tools_collection.count_documents(query)
    logger.info(
        "[tools] list_tools_by_org db=%s coll=%s org_id=%s query=%s skip=%s limit=%s -> total=%s",
        tools_collection.database.name, tools_collection.name, org_id, query, skip, limit, total,
    )
    if total == 0:
        # Cheap extra signal: is this org_id even valid, and does the tools
        # collection have *any* docs at all (wrong DB / empty DB in this env)?
        overall_count = await tools_collection.count_documents(NOT_DELETED)
        logger.warning(
            "[tools] list_tools_by_org returned 0 for org_id=%s -- tools_collection has %s non-deleted docs total (db=%s)",
            org_id, overall_count, tools_collection.database.name,
        )
    cursor = tools_collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    agent_info = await _fetch_agent_info([doc.get("agent_id") for doc in docs])
    return [_to_public(doc, agent_info=agent_info.get(doc.get("agent_id"))) for doc in docs], total


async def get_tool(tool_id: str) -> ToolPublic:
    oid = _validate_object_id(tool_id)
    doc = await tools_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found.",
        )
    agent_info = await _fetch_agent_info([doc.get("agent_id")])
    return _to_public(doc, agent_info=agent_info.get(doc.get("agent_id")))


async def update_tool(tool_id: str, payload: ToolUpdate) -> ToolPublic:
    oid = _validate_object_id(tool_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )

    if "tool_id" in updates:
        registry_entry = await _validate_tool_id_exists(updates["tool_id"])
        updates["handler"] = registry_entry.get("handler") or registry_entry["name"]
        updates["input_schema"] = registry_entry.get("tool_schema", {})
    if "db_conn_id" in updates:
        current = await tools_collection.find_one(
            {"_id": oid, **NOT_DELETED},
            {"organization_id": 1},
        )
        if current:
            await _validate_db_connection_in_org(updates["db_conn_id"], current["organization_id"])

    if "credentials" in updates:
        creds = updates.pop("credentials")
        if creds:
            if creds.get("api_key"):
                updates["encrypted_api_key"] = encrypt(creds["api_key"])
            if creds.get("base_url"):
                updates["custom_base_url"] = creds["base_url"]
            if creds.get("model"):
                updates["custom_model"] = creds["model"]

    doc = await tools_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found.",
        )
    registry_entry = await _validate_tool_id_exists(doc["tool_id"])
    if doc.get("agent_id"):
        await _merge_tool_into_prompt(doc["agent_id"], doc, registry_entry)
        _invalidate_org_graph_cache(doc.get("organization_id"), doc["agent_id"])
    agent_info = await _fetch_agent_info([doc.get("agent_id")])
    return _to_public(doc, agent_info=agent_info.get(doc.get("agent_id")))


async def delete_tool(tool_id: str) -> None:
    """Soft delete: mark as deleted instead of removing the document."""
    oid = _validate_object_id(tool_id)
    tool_doc = await tools_collection.find_one(
        {"_id": oid, **NOT_DELETED},
        {"agent_id": 1, "organization_id": 1},
    )
    result = await tools_collection.update_one(
        {"_id": oid, **NOT_DELETED}, soft_delete_update()
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found.",
        )
    if tool_doc and tool_doc.get("agent_id"):
        _invalidate_org_graph_cache(tool_doc.get("organization_id"), tool_doc["agent_id"])