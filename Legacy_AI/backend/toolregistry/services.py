import re
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import HTTPException, status

from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.db.database import tool_registry_collection
from backend.toolregistry.schemas import (
    ToolRegistryCreate,
    ToolRegistryPublic,
    ToolRegistryUpdate,
)


def _to_public(doc: dict) -> ToolRegistryPublic:
    """Map a MongoDB tool_registry document to the public schema."""
    return ToolRegistryPublic(
        id=str(doc["_id"]),
        name=doc["name"],
        type=doc["type"],
        description=doc.get("description"),
        is_active=doc.get("is_active", True),
        tool_schema=doc.get("tool_schema"),
        created_at=doc["created_at"],
    )


def _validate_object_id(registry_id: str) -> ObjectId:
    """Convert a string id to ObjectId or raise 404 if malformed."""
    if not ObjectId.is_valid(registry_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool registry entry not found.",
        )
    return ObjectId(registry_id)


async def create_tool_registry(payload: ToolRegistryCreate) -> ToolRegistryPublic:
    doc = {
        "name": payload.name,
        "type": payload.type,
        "description": payload.description,
        "is_active": payload.is_active,
        "tool_schema": payload.tool_schema,
        "created_at": datetime.now(timezone.utc),
        "is_deleted": False,
    }
    result = await tool_registry_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_public(doc)


TOOL_REGISTRY_SORTABLE_FIELDS = {"name", "created_at"}


async def list_tool_registry(
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
    type: str | None = None,
    is_active: bool | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[List[ToolRegistryPublic], int]:
    query: dict = {**NOT_DELETED}
    if search:
        query["name"] = {"$regex": re.escape(search), "$options": "i"}
    if type:
        query["type"] = type
    if is_active is not None:
        query["is_active"] = is_active

    field = sort_by if sort_by in TOOL_REGISTRY_SORTABLE_FIELDS else "created_at"
    direction = 1 if sort_order == "asc" else -1

    total = await tool_registry_collection.count_documents(query)
    cursor = tool_registry_collection.find(query).sort(field, direction).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def get_tool_registry(registry_id: str) -> ToolRegistryPublic:
    oid = _validate_object_id(registry_id)
    doc = await tool_registry_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool registry entry not found.",
        )
    return _to_public(doc)


async def update_tool_registry(
    registry_id: str, payload: ToolRegistryUpdate
) -> ToolRegistryPublic:
    oid = _validate_object_id(registry_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )

    doc = await tool_registry_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool registry entry not found.",
        )
    return _to_public(doc)


async def delete_tool_registry(registry_id: str) -> None:
    """Soft delete: mark as deleted instead of removing the document."""
    oid = _validate_object_id(registry_id)
    result = await tool_registry_collection.update_one(
        {"_id": oid, **NOT_DELETED}, soft_delete_update()
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool registry entry not found.",
        )
