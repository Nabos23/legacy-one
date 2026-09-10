import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.agent import services as agent_services
from backend.agent.routes import AgentListFilters
from backend.agent.schemas import AgentPublic
from backend.auth import services as auth_services
from backend.auth.permissions import (
    assert_org_access,
    assert_organization_access,
    is_super_admin,
)
from backend.auth.schemas import OrgRolePermissionPublic, OrgRolePermissionUpdate, UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dbconnection import services as dbconnection_services
from backend.dbconnection.schemas import DbConnectionPublic
from backend.dependencies import get_current_user, require_permission
from backend.organization import services
from backend.org_settings import services as org_settings_services
from backend.org_settings.schemas import OrgSettingsPublic, OrgSettingsUpdate
from backend.user import services as user_services
from backend.organization.schemas import (
    OrganizationCreate,
    OrganizationPublic,
    OrganizationUpdate,
)
from backend.tool import services as tool_services
from backend.tool.schemas import ToolPublic

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    current_user: UserPublic = Depends(require_permission("create_org")),
) -> OrganizationPublic:
    """Create a new organization (subject to the daily per-user quota)."""
    return await services.create_organization(payload, created_by=current_user.id)


@router.get("", response_model=Page[OrganizationPublic])
async def list_organizations(
    pg: Pagination = Depends(pagination_params),
    search: str | None = Query(default=None, description="Filter organizations by name or description (case-insensitive)"),
    sort_by: Literal["name", "created_at"] | None = Query(default=None),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    current_user: UserPublic = Depends(require_permission("view_org")),
) -> Page[OrganizationPublic]:
    """List organizations (paginated). Optionally filter by name/description with ?search=, and sort."""
    if is_super_admin(current_user.role):
        items, total = await services.list_organizations(
            skip=pg.skip, limit=pg.limit, search=search, sort_by=sort_by, sort_order=sort_order
        )
    else:
        try:
            org = await services.get_organization(current_user.organization_id)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise
            items, total = [], 0
        else:
            items, total = [org], 1
    return build_page(items, total, pg)


@router.get("/{org_id}", response_model=OrganizationPublic)
async def get_organization(
    org_id: str,
    current_user: UserPublic = Depends(require_permission("view_org")),
) -> OrganizationPublic:
    """Retrieve a single organization by id."""
    await assert_organization_access(current_user, org_id)
    return await services.get_organization(org_id)


@router.get("/{org_id}/agents", response_model=Page[AgentPublic])
async def list_organization_agents(
    org_id: str,
    pg: Pagination = Depends(pagination_params),
    filters: AgentListFilters = Depends(),
    current_user: UserPublic = Depends(require_permission("view_org")),
) -> Page[AgentPublic]:
    """List agents belonging to a specific organization (paginated), with
    optional search/status/capability filters and sorting."""
    assert_org_access(current_user, org_id)
    items, total = await agent_services.list_agents_by_org(
        org_id, skip=pg.skip, limit=pg.limit,
        requesting_user_id=current_user.id, **filters.as_kwargs()
    )
    return build_page(items, total, pg)


@router.get("/{org_id}/tools", response_model=Page[ToolPublic])
async def list_organization_tools(
    org_id: str,
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_org")),
) -> Page[ToolPublic]:
    """List tools belonging to a specific organization (paginated)."""
    logger.info(
        "[tools] GET /organizations/%s/tools by user=%s role=%s",
        org_id, current_user.id, current_user.role,
    )
    assert_org_access(current_user, org_id)
    items, total = await tool_services.list_tools_by_org(
        org_id, skip=pg.skip, limit=pg.limit
    )
    logger.info("[tools] GET /organizations/%s/tools -> returning %s of %s items", org_id, len(items), total)
    return build_page(items, total, pg)


@router.get("/{org_id}/db-connections", response_model=Page[DbConnectionPublic])
async def list_organization_db_connections(
    org_id: str,
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_org")),
) -> Page[DbConnectionPublic]:
    """List DB connections belonging to a specific organization (paginated)."""
    logger.info(
        "[db-connections] GET /organizations/%s/db-connections by user=%s role=%s",
        org_id, current_user.id, current_user.role,
    )
    assert_org_access(current_user, org_id)
    items, total = await dbconnection_services.list_db_connections_by_org(
        org_id, skip=pg.skip, limit=pg.limit
    )
    logger.info(
        "[db-connections] GET /organizations/%s/db-connections -> returning %s of %s items",
        org_id, len(items), total,
    )
    return build_page(items, total, pg)


@router.get("/{org_id}/users", response_model=Page[UserPublic])
async def list_organization_users(
    org_id: str,
    pg: Pagination = Depends(pagination_params),
    search: str | None = Query(default=None, description="Filter users by name or email (case-insensitive)"),
    role: str | None = Query(default=None, description="Filter users by exact role"),
    sort_by: Literal["name", "email", "created_at"] | None = Query(default=None),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    current_user: UserPublic = Depends(require_permission("view_org")),
) -> Page[UserPublic]:
    """List users belonging to a specific organization (paginated). Optionally filter with ?search= and/or ?role=, and sort."""
    assert_org_access(current_user, org_id)
    items, total = await user_services.list_users_by_org(
        org_id, skip=pg.skip, limit=pg.limit, search=search, role=role, sort_by=sort_by, sort_order=sort_order
    )
    return build_page(items, total, pg)


@router.get("/{org_id}/settings", response_model=OrgSettingsPublic)
async def get_organization_settings(
    org_id: str,
    current_user: UserPublic = Depends(require_permission("view_org")),
) -> OrgSettingsPublic:
    """Retrieve an organization's settings (defaults applied when unset)."""
    assert_org_access(current_user, org_id)
    return await org_settings_services.get_settings(org_id)


@router.put("/{org_id}/settings", response_model=OrgSettingsPublic)
async def update_organization_settings(
    org_id: str,
    payload: OrgSettingsUpdate,
    current_user: UserPublic = Depends(require_permission("edit_org")),
) -> OrgSettingsPublic:
    """Update (upsert) an organization's settings."""
    assert_org_access(current_user, org_id)
    return await org_settings_services.update_settings(org_id, payload)


@router.get("/{org_id}/roles/{role}/permissions", response_model=OrgRolePermissionPublic)
async def get_org_role_permissions(
    org_id: str,
    role: Literal["org_manager", "user"],
    current_user: UserPublic = Depends(require_permission("view_role_permissions")),
) -> OrgRolePermissionPublic:
    """Retrieve a role's effective permissions for this org (override if
    customized, otherwise the global default). Only org_manager/user are
    valid here -- org_admin and super_admin are never per-org customizable."""
    assert_org_access(current_user, org_id)
    return await auth_services.get_org_role_permissions(org_id, role)


@router.put("/{org_id}/roles/{role}/permissions", response_model=OrgRolePermissionPublic)
async def update_org_role_permissions(
    org_id: str,
    role: Literal["org_manager", "user"],
    payload: OrgRolePermissionUpdate,
    current_user: UserPublic = Depends(require_permission("edit_role_permissions")),
) -> OrgRolePermissionPublic:
    """Customize a role's permissions for THIS org only -- never mutates the
    global role_permissions default that every other org falls back to."""
    assert_org_access(current_user, org_id)
    return await auth_services.update_org_role_permissions(org_id, role, payload.permission_names)


@router.delete("/{org_id}/roles/{role}/permissions", response_model=OrgRolePermissionPublic)
async def reset_org_role_permissions(
    org_id: str,
    role: Literal["org_manager", "user"],
    current_user: UserPublic = Depends(require_permission("edit_role_permissions")),
) -> OrgRolePermissionPublic:
    """Remove this org's override for `role`, reverting it to the global default."""
    assert_org_access(current_user, org_id)
    return await auth_services.reset_org_role_permissions(org_id, role)


@router.put("/{org_id}", response_model=OrganizationPublic)
async def update_organization(
    org_id: str,
    payload: OrganizationUpdate,
    current_user: UserPublic = Depends(require_permission("edit_org")),
) -> OrganizationPublic:
    """Update an organization."""
    await assert_organization_access(current_user, org_id)
    return await services.update_organization(org_id, payload)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: str,
    current_user: UserPublic = Depends(require_permission("delete_org")),
) -> None:
    """Delete an organization."""
    await assert_organization_access(current_user, org_id)
    await services.delete_organization(org_id)
