import re
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from backend.auth.cache import invalidate_team_permissions, team_permissions_cache
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.db.database import (
    agent_orchestrations_collection,
    agents_collection,
    organizations_collection,
    teams_collection,
    users_collection,
)
from backend.team.schemas import TeamCreate, TeamPublic, TeamUpdate


def _to_public(doc: dict) -> TeamPublic:
    """Map a MongoDB team document to the public schema."""
    return TeamPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc["name"],
        description=doc.get("description"),
        member_ids=doc.get("member_ids", []),
        permissions=doc.get("permissions", []),
        created_by=doc.get("created_by"),
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at"),
    )


def _validate_object_id(team_id: str) -> ObjectId:
    """Convert a string id to ObjectId or raise 404 if malformed."""
    if not ObjectId.is_valid(team_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
    return ObjectId(team_id)


async def _validate_org_exists(org_id: str) -> None:
    """Raise 404 if org_id is not a valid ObjectId or the org doesn't exist."""
    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    doc = await organizations_collection.find_one({"_id": ObjectId(org_id), **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")


async def _validate_member_ids(org_id: str, user_ids: List[str]) -> List[str]:
    """Validate that every id in `user_ids` is a real user belonging to `org_id`,
    dedupe, and return the cleaned list. Prevents an org_admin/org_manager from
    adding a user outside their own organization to a team."""
    unique_ids = list(dict.fromkeys(uid for uid in user_ids if uid))
    if not unique_ids:
        return []
    object_ids = [ObjectId(uid) for uid in unique_ids if ObjectId.is_valid(uid)]
    if len(object_ids) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more selected user ids are invalid.")
    count = await users_collection.count_documents({"_id": {"$in": object_ids}, "organization_id": org_id})
    if count != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected users do not belong to this organization.",
        )
    return unique_ids


async def create_team(payload: TeamCreate, created_by: str) -> TeamPublic:
    await _validate_org_exists(payload.organization_id)
    member_ids = await _validate_member_ids(payload.organization_id, payload.member_ids)
    now = datetime.now(timezone.utc)
    doc = {
        "organization_id": payload.organization_id,
        "name": payload.name,
        "description": payload.description,
        "member_ids": member_ids,
        "permissions": payload.permissions or [],
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    result = await teams_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_public(doc)


def _search_query(search: Optional[str]) -> dict:
    """Case-insensitive match on name or description; empty when no search given."""
    if not search or not search.strip():
        return {}
    pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
    return {"$or": [{"name": pattern}, {"description": pattern}]}


async def list_teams(skip: int = 0, limit: int = 20, search: Optional[str] = None) -> tuple[List[TeamPublic], int]:
    query = {**NOT_DELETED, **_search_query(search)}
    total = await teams_collection.count_documents(query)
    cursor = teams_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def list_teams_by_org(
    org_id: str, skip: int = 0, limit: int = 20, search: Optional[str] = None
) -> tuple[List[TeamPublic], int]:
    query = {"organization_id": org_id, **NOT_DELETED, **_search_query(search)}
    total = await teams_collection.count_documents(query)
    cursor = teams_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def get_team(team_id: str) -> TeamPublic:
    oid = _validate_object_id(team_id)
    doc = await teams_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
    return _to_public(doc)


async def update_team(team_id: str, payload: TeamUpdate) -> TeamPublic:
    oid = _validate_object_id(team_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update.")
    updates["updated_at"] = datetime.now(timezone.utc)

    doc = await teams_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED}, {"$set": updates}, return_document=True
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
    if "member_ids" in updates or "permissions" in updates:
        invalidate_team_permissions()
    return _to_public(doc)


async def delete_team(team_id: str) -> None:
    """Soft-delete the team, and reset any agent or orchestration pointed at it back to
    organization-wide visibility so they aren't silently left inaccessible."""
    oid = _validate_object_id(team_id)
    result = await teams_collection.update_one({"_id": oid, **NOT_DELETED}, soft_delete_update())
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
    invalidate_team_permissions()

    await agents_collection.update_many(
        {"team_id": team_id}, {"$set": {"owner_scope": "organization", "team_id": None}}
    )
    await agent_orchestrations_collection.update_many(
        {"team_id": team_id}, {"$set": {"owner_scope": "organization", "team_id": None}}
    )


async def add_members(team_id: str, user_ids: List[str]) -> TeamPublic:
    oid = _validate_object_id(team_id)
    team_doc = await teams_collection.find_one({"_id": oid, **NOT_DELETED})
    if not team_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

    cleaned = await _validate_member_ids(team_doc["organization_id"], user_ids)
    doc = await teams_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$addToSet": {"member_ids": {"$each": cleaned}}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )
    invalidate_team_permissions(cleaned)
    return _to_public(doc)


async def remove_member(team_id: str, user_id: str) -> TeamPublic:
    oid = _validate_object_id(team_id)
    doc = await teams_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$pull": {"member_ids": user_id}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
    invalidate_team_permissions(user_id)
    return _to_public(doc)


async def get_team_permissions(team_id: str) -> List[str]:
    """Fetch the permissions granted to a team."""
    oid = _validate_object_id(team_id)
    doc = await teams_collection.find_one({"_id": oid, **NOT_DELETED}, {"permissions": 1})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
    return doc.get("permissions", [])


async def update_team_permissions(team_id: str, permissions: List[str]) -> TeamPublic:
    """Update permissions granted to a team."""
    oid = _validate_object_id(team_id)
    cleaned_permissions = list(dict.fromkeys(p for p in permissions if p))
    doc = await teams_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": {"permissions": cleaned_permissions, "updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
    invalidate_team_permissions()
    return _to_public(doc)


async def is_member(team_id: str, user_id: str) -> bool:
    """Whether `user_id` belongs to (non-deleted) team `team_id`. Used by
    agent visibility checks; tolerant of a malformed/missing team id."""
    if not team_id or not ObjectId.is_valid(team_id):
        return False
    doc = await teams_collection.find_one({"_id": ObjectId(team_id), "member_ids": user_id, **NOT_DELETED}, {"_id": 1})
    return doc is not None


async def get_team_ids_for_user(user_id: str) -> List[str]:
    """All (non-deleted) team ids that `user_id` is a member of, across any
    organization. Used to build the agent-visibility query clause."""
    cursor = teams_collection.find({"member_ids": user_id, **NOT_DELETED}, {"_id": 1})
    return [str(doc["_id"]) async for doc in cursor]


async def _load_user_team_permissions(user_id: str) -> set[str]:
    cursor = teams_collection.find({"member_ids": user_id, **NOT_DELETED}, {"permissions": 1})
    granted: set[str] = set()
    async for doc in cursor:
        perms = doc.get("permissions", [])
        if perms:
            granted.update(perms)
    return granted


async def get_user_team_permissions(user_id: str) -> set[str]:
    """Fetch all unique permission slugs granted across all non-deleted teams
    `user_id` belongs to."""
    if not user_id:
        return set()
    return await team_permissions_cache.get_or_load(
        user_id, lambda: _load_user_team_permissions(user_id)
    )

