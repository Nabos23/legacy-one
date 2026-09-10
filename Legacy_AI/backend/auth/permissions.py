"""Role-based permissions resolved live from the `permissions` and
`role_permissions` collections. Fully DB-driven -- no code-side defaults.
"""

import time

from bson import ObjectId
from fastapi import HTTPException, status

from backend.auth.schemas import UserPublic
from backend.core.softdelete import NOT_DELETED
from backend.db.database import (
    org_role_permissions_collection,
    organizations_collection,
    permissions_collection,
    role_permissions_collection,
)

Permission = str

ROLE_SUPER_ADMIN = "super_admin"
ROLE_ORG_ADMIN = "org_admin"
ROLE_ORG_MANAGER = "org_manager"
ROLE_USER = "user"

ROLE_ADMIN = "admin"    # legacy alias -> org_admin
ROLE_MEMBER = "member"  # legacy alias -> user

LEGACY_ROLE_ALIASES: dict[str, str] = {
    ROLE_ADMIN: ROLE_ORG_ADMIN,
    ROLE_MEMBER: ROLE_USER,
    "super admin": ROLE_SUPER_ADMIN,
    "org admin": ROLE_ORG_ADMIN,
    "org manager": ROLE_ORG_MANAGER,
}

EDITABLE_OVERRIDE_ROLES = {ROLE_ORG_MANAGER, ROLE_USER}

ROLES_CACHE_TTL_SECONDS = 5.0

_cache: dict = {"permission_names": None, "roles": None, "ts": 0.0}
_ORG_OVERRIDE_CACHE_TTL_SECONDS = 5.0
_org_override_cache: dict[tuple[str, str], dict] = {}


def normalize_role(role: str) -> str:
    """Map legacy/human-readable role names to the canonical RBAC role slug."""
    canonical = role.lower().replace(" ", "_")
    return LEGACY_ROLE_ALIASES.get(role, LEGACY_ROLE_ALIASES.get(canonical, canonical))


def is_super_admin(role: str) -> bool:
    return normalize_role(role) == ROLE_SUPER_ADMIN


def is_org_admin(role: str) -> bool:
    return normalize_role(role) in (ROLE_ORG_ADMIN, ROLE_SUPER_ADMIN)


def is_privileged_agent_creator(role: str) -> bool:
    """org_admin / org_manager / super_admin may choose an agent's visibility
    (personal vs organization); plain 'user' always gets a forced-personal
    agent -- see agent.routes.create_agent."""
    return normalize_role(role) in (ROLE_ORG_ADMIN, ROLE_ORG_MANAGER, ROLE_SUPER_ADMIN)


def is_org_manager_or_above(role: str) -> bool:
    """org_admin / org_manager / super_admin may view tracing/usage data for
    every member of their organization (broken down user-by-user); a plain
    'user' may only ever see their own -- see tracing.services."""
    return normalize_role(role) in (ROLE_ORG_ADMIN, ROLE_ORG_MANAGER, ROLE_SUPER_ADMIN)


def _permission_names_to_bool_dict(
    perm_names: list[str], all_permission_names: frozenset[str]
) -> dict[str, bool]:
    """Convert a list of granted permission slugs to a full bool dict."""
    granted = frozenset(perm_names)
    result = {p: (p in granted) for p in all_permission_names}
    for p in granted - all_permission_names:
        result[p] = True
    return result


async def _load_roles() -> dict[str, dict]:
    """Load every role's config (permission flags + assign_permission) live
    from the `role_permissions` collection. That collection is self-sufficient
    per role (role, label, permission_names, assign_permission), so no
    code-side fallback/seed step is needed.
    """
    now = time.time()
    if (
        _cache["roles"] is not None
        and now - _cache["ts"] <= ROLES_CACHE_TTL_SECONDS
    ):
        return _cache["roles"]

    permission_names: set[str] = set()
    cursor = permissions_collection.find(NOT_DELETED)
    async for doc in cursor:
        name = doc.get("name")
        if name:
            permission_names.add(name)
    all_permission_names = frozenset(permission_names)

    roles: dict[str, dict] = {}
    cursor = role_permissions_collection.find(NOT_DELETED)
    async for doc in cursor:
        role_name = doc.get("role")
        perm_names = doc.get("permission_names")
        if not role_name or not isinstance(perm_names, list):
            continue
        roles[role_name] = {
            "label": doc.get("label", role_name),
            "permissions": _permission_names_to_bool_dict(perm_names, all_permission_names),
            "assign_permission": doc.get("assign_permission"),
        }

    _cache["permission_names"] = all_permission_names
    _cache["roles"] = roles
    _cache["ts"] = now
    return roles


async def _load_org_role_override(organization_id: str, role: str) -> list[str] | None:
    """The org-specific permission_names override for (organization_id, role),
    or None if the org hasn't customized this role (falls back to global)."""
    key = (organization_id, role)
    now = time.time()
    entry = _org_override_cache.get(key)
    if entry is not None and now - entry["ts"] <= _ORG_OVERRIDE_CACHE_TTL_SECONDS:
        return entry["permission_names"]

    doc = await org_role_permissions_collection.find_one(
        {"organization_id": organization_id, "role": role}
    )
    permission_names = doc["permission_names"] if doc else None
    _org_override_cache[key] = {"permission_names": permission_names, "ts": now}
    return permission_names


def invalidate_org_role_override_cache(organization_id: str, role: str) -> None:
    """Drop the cached override for (organization_id, role) so a save/reset
    takes effect immediately instead of waiting out the TTL."""
    _org_override_cache.pop((organization_id, role), None)


async def get_permissions_for_role(role: str, organization_id: str | None = None) -> dict[str, bool]:
    """Return the permission flags for a role, optionally merged with an
    org-specific override (only applies to EDITABLE_OVERRIDE_ROLES)."""
    roles = await _load_roles()
    canonical = normalize_role(role)
    config = roles.get(canonical) or roles.get(ROLE_USER)
    if not config:
        return {}
    if organization_id and canonical in EDITABLE_OVERRIDE_ROLES:
        override_names = await _load_org_role_override(organization_id, canonical)
        if override_names is not None:
            all_permission_names = _cache["permission_names"] or frozenset()
            return _permission_names_to_bool_dict(override_names, all_permission_names)
    return config["permissions"]


async def get_assign_permission_for_role(role: str) -> str | None:
    """Return the permission (if any) required to assign `role` to a user."""
    roles = await _load_roles()
    canonical = normalize_role(role)
    config = roles.get(canonical)
    return config["assign_permission"] if config else None


async def list_assignable_roles(user: UserPublic) -> list[dict]:
    """Return every DB-defined role the caller is permitted to assign to a new user.

    A role is assignable if it has no `assign_permission` requirement, or the
    caller holds that permission. Entirely DB-driven — new roles created via
    the /admin panel show up here (and in clients that consume this) with no
    code change.

    `is_admin` reflects the role's `access_admin_panel` permission, so clients
    can highlight admin-tier roles (e.g. a "primary" badge) without hardcoding
    role names — any new custom role granted that permission is picked up
    automatically.
    """
    roles = await _load_roles()
    result = []
    for name, config in roles.items():
        required_permission = config.get("assign_permission")
        if not required_permission or await user_has_permission(user, required_permission):
            result.append({
                "name": name,
                "label": config.get("label", name),
                "is_admin": bool(config.get("permissions", {}).get("access_admin_panel")),
            })
    return result


async def list_all_roles() -> list[dict]:
    """Return every DB-defined role's name/label/is_admin, unfiltered by assignability.

    Unlike `list_assignable_roles` (used for the create/edit-user role picker,
    which only shows roles the caller may grant), this is for display purposes —
    e.g. so any authenticated user's UI can correctly badge a role as admin-tier
    even if that role isn't one the current viewer could assign themselves.
    """
    roles = await _load_roles()
    return [
        {
            "name": name,
            "label": config.get("label", name),
            "is_admin": bool(config.get("permissions", {}).get("access_admin_panel")),
        }
        for name, config in roles.items()
    ]


async def get_effective_permissions_for_user(user: UserPublic) -> dict[str, bool]:
    """Return the user's effective permissions, combining base role permissions
    (plus org overrides) and any permissions granted via team membership."""
    perms = await get_permissions_for_role(user.role, user.organization_id)
    if is_super_admin(user.role) or is_org_admin(user.role):
        return {k: True for k in perms}
    from backend.team import services as team_services
    team_perms = await team_services.get_user_team_permissions(user.id)
    if team_perms:
        perms = dict(perms)
        for p in team_perms:
            perms[p] = True
    return perms


async def user_has_permission(user: UserPublic, permission: Permission) -> bool:
    if is_super_admin(user.role) or is_org_admin(user.role):
        return True
    perms = await get_permissions_for_role(user.role, user.organization_id)
    if perms.get(permission):
        return True
    from backend.team import services as team_services
    team_perms = await team_services.get_user_team_permissions(user.id)
    return permission in team_perms



def assert_org_access(user: UserPublic, org_id: str) -> None:
    """Raise 403 when a non–super-admin accesses another organization's data."""
    if is_super_admin(user.role):
        return
    if user.organization_id == org_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this organization.",
    )


async def assert_organization_access(user: UserPublic, org_id: str) -> None:
    """Org access for organization documents (membership or creator).

    Raises 404 when the organization does not exist (or the id is malformed),
    and 403 when it exists but the caller is neither a member, its creator,
    nor a super admin. Existence is checked before access so callers get a
    truthful status code instead of a blanket 403.
    """
    if is_super_admin(user.role):
        return
    if user.organization_id == org_id:
        return
    doc = (
        await organizations_collection.find_one(
            {"_id": ObjectId(org_id), **NOT_DELETED}
        )
        if ObjectId.is_valid(org_id)
        else None
    )
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    if doc.get("created_by") == user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this organization.",
    )


async def assert_can_assign_role(user: UserPublic, target_role: str) -> None:
    """Raise 403 when the caller's role lacks permission to grant `target_role`.

    The permission required to assign a role is read from that role's own
    `assign_permission` field in the `role_permissions` collection (editable
    via the /admin panel) — not hardcoded here.
    """
    canonical = normalize_role(target_role)
    required_permission = await get_assign_permission_for_role(canonical)
    if required_permission and not await user_has_permission(user, required_permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to assign the {canonical} role.",
        )


def assert_super_admin(user: UserPublic) -> None:
    if not is_super_admin(user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required.",
        )


async def can_access_admin_panel(role: str) -> bool:
    """Whether the role may sign in to the /admin UI.

    DB-driven via the `access_admin_panel` permission (see role_permissions
    collection) rather than a hardcoded role set. super_admin always passes.
    """
    if is_super_admin(role):
        return True
    perms = await get_permissions_for_role(role)
    return bool(perms.get("access_admin_panel"))


async def ensure_default_roles() -> None:
    """Read-only startup sanity check.

    Roles and permissions are now fully DB-managed (no code-side defaults
    to seed from), so this no longer inserts or backfills anything. It just
    warns if any of the four expected roles are missing or soft-deleted in
    `role_permissions`, to fail loudly on a misconfigured DB rather than
    letting permission checks silently misbehave.
    """
    import logging

    logger = logging.getLogger("startup")
    expected_roles = {ROLE_SUPER_ADMIN, ROLE_ORG_ADMIN, ROLE_ORG_MANAGER, ROLE_USER}

    found_roles: set[str] = set()
    cursor = role_permissions_collection.find(NOT_DELETED)
    async for doc in cursor:
        role_name = doc.get("role")
        if role_name:
            found_roles.add(role_name)

    missing = expected_roles - found_roles
    for role_name in sorted(missing):
        logger.warning(
            "Expected role '%s' is missing or soft-deleted in the "
            "'role_permissions' collection. Permission checks for this "
            "role will fall back to the '%s' role's permissions until "
            "it is added.",
            role_name,
            ROLE_USER,
        )