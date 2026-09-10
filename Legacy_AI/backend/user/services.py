import re

from bson import ObjectId
from backend.auth.cache import invalidate_team_permissions, invalidate_user
from fastapi import HTTPException, UploadFile, status

from backend.auth.permissions import assert_can_assign_role, assert_org_access
from backend.auth.schemas import UpdateUserRequest, UserPublic
from backend.core.config import settings
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.core.uploads import save_image_upload
from backend.db.database import users_collection


def _search_query(search: str | None) -> dict:
    """Case-insensitive match on name or email; empty when no search given."""
    if not search or not search.strip():
        return {}
    pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
    return {"$or": [{"name": pattern}, {"email": pattern}]}


def _to_public(doc: dict) -> UserPublic:
    return UserPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc["name"],
        email=doc["email"],
        role=doc["role"],
        created_at=doc["created_at"],
        avatar_url=doc.get("avatar_url"),
    )


async def _require_user_doc(user_id: str) -> dict:
    """Return the user document for `user_id`, or raise 404."""
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    doc = await users_collection.find_one({"_id": ObjectId(user_id)})
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return doc


async def update_own_profile(user_id: str, name: str | None) -> UserPublic:
    """Update the caller's own profile. Currently supports the display name only."""
    await _require_user_doc(user_id)

    update: dict = {}
    if name is not None:
        name = name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Name cannot be empty."
            )
        update["name"] = name

    if not update:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update."
        )

    await users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update})
    invalidate_user(user_id)
    doc = await users_collection.find_one({"_id": ObjectId(user_id)})
    return _to_public(doc)


async def update_own_avatar(user_id: str, file: UploadFile) -> UserPublic:
    """Upload and set the caller's profile picture, replacing any existing one."""
    await _require_user_doc(user_id)

    url_path = await save_image_upload(file, subdir="avatars")
    avatar_url = f"{settings.BACKEND_BASE_URL}{url_path}"

    await users_collection.update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"avatar_url": avatar_url}}
    )
    invalidate_user(user_id)
    doc = await users_collection.find_one({"_id": ObjectId(user_id)})
    return _to_public(doc)


USER_SORTABLE_FIELDS = {"name", "email", "created_at"}


def _resolve_user_sort(sort_by: str | None, sort_order: str) -> tuple[str, int]:
    field = sort_by if sort_by in USER_SORTABLE_FIELDS else "created_at"
    direction = 1 if sort_order == "asc" else -1
    return field, direction


async def list_users(
    skip: int,
    limit: int,
    search: str | None = None,
    role: str | None = None,
    organization_id: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[list[UserPublic], int]:
    query = {**NOT_DELETED, "waiting_approval": {"$ne": "disapproved"}, **_search_query(search)}
    if role:
        query["role"] = role
    if organization_id:
        query["organization_id"] = organization_id
    field, direction = _resolve_user_sort(sort_by, sort_order)
    cursor = users_collection.find(query).sort(field, direction).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    total = await users_collection.count_documents(query)
    items = [_to_public(doc) for doc in docs]
    return items, total


async def list_users_by_org(
    org_id: str,
    skip: int,
    limit: int,
    search: str | None = None,
    role: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[list[UserPublic], int]:
    query = {"organization_id": org_id, "waiting_approval": {"$ne": "disapproved"}, **NOT_DELETED, **_search_query(search)}
    if role:
        query["role"] = role
    field, direction = _resolve_user_sort(sort_by, sort_order)
    cursor = users_collection.find(query).sort(field, direction).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    total = await users_collection.count_documents(query)
    items = [_to_public(doc) for doc in docs]
    return items, total


async def update_user_as_admin(
    user_id: str, payload: UpdateUserRequest, admin: UserPublic
) -> UserPublic:
    """Admin-driven update of another user's name and/or role.

    Requires the caller to have org access to the target (super_admin bypasses
    org scoping) and, via `assert_can_assign_role`, permission to manage the
    target's current role and the role being assigned — both DB-driven, not
    hardcoded.
    """
    target = await _require_user_doc(user_id)
    assert_org_access(admin, target["organization_id"])
    await assert_can_assign_role(admin, target["role"])

    update: dict = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name cannot be empty.")
        update["name"] = name
    if payload.role is not None:
        await assert_can_assign_role(admin, payload.role)
        update["role"] = payload.role

    if not update:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update.")

    await users_collection.update_one({"_id": target["_id"]}, {"$set": update})
    invalidate_user(str(target["_id"]))
    doc = await users_collection.find_one({"_id": target["_id"]})
    return _to_public(doc)


async def delete_user_as_admin(user_id: str, admin: UserPublic) -> None:
    """Admin-driven soft-delete of another user.

    Same DB-driven org-access and role-management checks as `update_user_as_admin`.
    """
    target = await _require_user_doc(user_id)
    if str(target["_id"]) == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )
    assert_org_access(admin, target["organization_id"])
    await assert_can_assign_role(admin, target["role"])

    await users_collection.update_one({"_id": target["_id"]}, soft_delete_update())
    invalidate_user(str(target["_id"]))
    invalidate_team_permissions(str(target["_id"]))
