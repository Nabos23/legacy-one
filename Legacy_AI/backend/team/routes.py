from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from backend.auth.permissions import assert_org_access, is_super_admin
from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission
from backend.team import services
from backend.team.schemas import TeamCreate, TeamMembersUpdate, TeamPermissionsUpdate, TeamPublic, TeamUpdate

router = APIRouter(
    prefix="/teams",
    tags=["teams"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=TeamPublic, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    current_user: UserPublic = Depends(require_permission("create_team")),
) -> TeamPublic:
    """Create a new team. organization_id must be provided and must be a valid org."""
    assert_org_access(current_user, payload.organization_id)
    return await services.create_team(payload, created_by=current_user.id)


@router.get("", response_model=Page[TeamPublic])
async def list_teams(
    pg: Pagination = Depends(pagination_params),
    search: Optional[str] = Query(default=None, description="Filter teams by name or description (case-insensitive)"),
    current_user: UserPublic = Depends(require_permission("view_team")),
) -> Page[TeamPublic]:
    """List teams (paginated)."""
    if is_super_admin(current_user.role):
        items, total = await services.list_teams(skip=pg.skip, limit=pg.limit, search=search)
    else:
        items, total = await services.list_teams_by_org(
            current_user.organization_id, skip=pg.skip, limit=pg.limit, search=search
        )
    return build_page(items, total, pg)


@router.get("/org/{org_id}", response_model=Page[TeamPublic])
async def get_teams_by_org(
    org_id: str,
    pg: Pagination = Depends(pagination_params),
    search: Optional[str] = Query(default=None, description="Filter teams by name or description (case-insensitive)"),
    current_user: UserPublic = Depends(require_permission("view_team")),
) -> Page[TeamPublic]:
    """List all teams belonging to a specific organization (paginated)."""
    assert_org_access(current_user, org_id)
    items, total = await services.list_teams_by_org(org_id, skip=pg.skip, limit=pg.limit, search=search)
    return build_page(items, total, pg)


@router.get("/{team_id}", response_model=TeamPublic)
async def get_team(
    team_id: str,
    current_user: UserPublic = Depends(require_permission("view_team")),
) -> TeamPublic:
    """Retrieve a single team by id."""
    team = await services.get_team(team_id)
    assert_org_access(current_user, team.organization_id)
    return team


@router.put("/{team_id}", response_model=TeamPublic)
async def update_team(
    team_id: str,
    payload: TeamUpdate,
    current_user: UserPublic = Depends(require_permission("edit_team")),
) -> TeamPublic:
    """Update a team's name/description/permissions."""
    team = await services.get_team(team_id)
    assert_org_access(current_user, team.organization_id)
    return await services.update_team(team_id, payload)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: str,
    current_user: UserPublic = Depends(require_permission("delete_team")),
) -> None:
    """Delete a team. Any agent assigned to it reverts to organization-wide visibility."""
    team = await services.get_team(team_id)
    assert_org_access(current_user, team.organization_id)
    await services.delete_team(team_id)


@router.post("/{team_id}/members", response_model=TeamPublic)
async def add_team_members(
    team_id: str,
    payload: TeamMembersUpdate,
    current_user: UserPublic = Depends(require_permission("edit_team")),
) -> TeamPublic:
    """Add one or more users (from the team's own organization) to a team."""
    team = await services.get_team(team_id)
    assert_org_access(current_user, team.organization_id)
    return await services.add_members(team_id, payload.user_ids)


@router.delete("/{team_id}/members/{user_id}", response_model=TeamPublic)
async def remove_team_member(
    team_id: str,
    user_id: str,
    current_user: UserPublic = Depends(require_permission("edit_team")),
) -> TeamPublic:
    """Remove a single user from a team."""
    team = await services.get_team(team_id)
    assert_org_access(current_user, team.organization_id)
    return await services.remove_member(team_id, user_id)


@router.get("/{team_id}/permissions", response_model=list[str])
async def get_team_permissions(
    team_id: str,
    current_user: UserPublic = Depends(require_permission("view_team")),
) -> list[str]:
    """Retrieve the permissions granted to a team."""
    team = await services.get_team(team_id)
    assert_org_access(current_user, team.organization_id)
    return await services.get_team_permissions(team_id)


@router.put("/{team_id}/permissions", response_model=TeamPublic)
async def update_team_permissions(
    team_id: str,
    payload: TeamPermissionsUpdate,
    current_user: UserPublic = Depends(require_permission("edit_team")),
) -> TeamPublic:
    """Update permissions granted to a team."""
    team = await services.get_team(team_id)
    assert_org_access(current_user, team.organization_id)
    return await services.update_team_permissions(team_id, payload.permissions)

