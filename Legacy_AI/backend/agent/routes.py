from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile, status

from backend.agent import services
from backend.agent.schemas import AgentCreate, AgentPermissionsDoc, AgentPermissionsPatch, AgentPublic, AgentUpdate
from backend.auth.permissions import assert_org_access, is_privileged_agent_creator, is_super_admin
from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    dependencies=[Depends(get_current_user)],
)

AgentSortBy = Literal["name", "created_at", "is_active"]
AgentSortOrder = Literal["asc", "desc"]


class AgentListFilters:
    """FastAPI dependency bundling the optional list-agents filters, so every
    route that lists agents declares (and documents) the same query params."""

    def __init__(
        self,
        search: Optional[str] = Query(default=None, description="Filter agents by name (case-insensitive)"),
        is_active: Optional[bool] = Query(default=None, description="Filter by active/inactive status"),
        has_tools: Optional[bool] = Query(default=None, description="Filter by whether the agent has any tools attached"),
        has_connectors: Optional[bool] = Query(default=None, description="Filter by whether the agent has any connectors attached"),
        has_mcp: Optional[bool] = Query(default=None, description="Filter by whether the agent has any MCP servers attached"),
        sort_by: Optional[AgentSortBy] = Query(default=None, description="Field to sort by (default: created_at)"),
        sort_order: AgentSortOrder = Query(default="desc", description="Sort direction"),
    ) -> None:
        self.search = search
        self.is_active = is_active
        self.has_tools = has_tools
        self.has_connectors = has_connectors
        self.has_mcp = has_mcp
        self.sort_by = sort_by
        self.sort_order = sort_order

    def as_kwargs(self) -> dict:
        return {
            "search": self.search,
            "is_active": self.is_active,
            "has_tools": self.has_tools,
            "has_connectors": self.has_connectors,
            "has_mcp": self.has_mcp,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
        }


@router.post("", response_model=AgentPublic, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    current_user: UserPublic = Depends(require_permission("create_agent")),
) -> AgentPublic:
    """Create a new agent. organization_id must be provided and must be a valid org.

    Plain "user" role callers always get a personal agent, regardless of what
    they send in `owner_scope`. Only org_admin/org_manager/super_admin may
    choose between "personal", "organization", "selected_users", and "team"
    visibility; for "selected_users" they also provide `allowed_user_ids`, and
    for "team" they provide `team_id`.
    """
    assert_org_access(current_user, payload.organization_id)
    if is_privileged_agent_creator(current_user.role):
        owner_scope = payload.owner_scope or "organization"
        allowed_user_ids = payload.allowed_user_ids if owner_scope == "selected_users" else []
        team_id = payload.team_id if owner_scope == "team" else None
    else:
        owner_scope = "user"
        allowed_user_ids = []
        team_id = None
    return await services.create_agent(
        payload, created_by=current_user.id, owner_scope=owner_scope,
        allowed_user_ids=allowed_user_ids, team_id=team_id,
    )


@router.get("", response_model=Page[AgentPublic])
async def list_agents(
    pg: Pagination = Depends(pagination_params),
    filters: AgentListFilters = Depends(),
    organization_id: Optional[str] = Query(default=None, description="Super-admin only: narrow to one organization"),
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> Page[AgentPublic]:
    """List agents (paginated), with optional search/status/capability filters and sorting."""
    if is_super_admin(current_user.role):
        if organization_id:
            items, total = await services.list_agents_by_org(
                organization_id, skip=pg.skip, limit=pg.limit,
                requesting_user_id=current_user.id, **filters.as_kwargs()
            )
        else:
            items, total = await services.list_agents(
                skip=pg.skip, limit=pg.limit,
                requesting_user_id=current_user.id, **filters.as_kwargs()
            )
    else:
        items, total = await services.list_agents_by_org(
            current_user.organization_id, skip=pg.skip, limit=pg.limit,
            requesting_user_id=current_user.id, **filters.as_kwargs()
        )
    return build_page(items, total, pg)


@router.get("/org/{org_id}", response_model=Page[AgentPublic])
async def get_agents_by_org(
    org_id: str,
    pg: Pagination = Depends(pagination_params),
    filters: AgentListFilters = Depends(),
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> Page[AgentPublic]:
    """List all agents belonging to a specific organization (paginated)."""
    assert_org_access(current_user, org_id)
    items, total = await services.list_agents_by_org(
        org_id, skip=pg.skip, limit=pg.limit,
        requesting_user_id=current_user.id, **filters.as_kwargs()
    )
    return build_page(items, total, pg)


@router.get("/{agent_id}", response_model=AgentPublic)
async def get_agent(
    agent_id: str,
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> AgentPublic:
    """Retrieve a single agent by id."""
    agent = await services.get_agent(agent_id)
    assert_org_access(current_user, agent.organization_id)
    await services.assert_agent_visible(current_user.id, agent)
    return agent


@router.put("/{agent_id}", response_model=AgentPublic)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    current_user: UserPublic = Depends(require_permission("edit_agent")),
) -> AgentPublic:
    """Update an agent."""
    agent = await services.get_agent(agent_id)
    assert_org_access(current_user, agent.organization_id)
    await services.assert_agent_visible(current_user.id, agent)
    if (
        (payload.allowed_user_ids is not None or payload.team_id is not None)
        and not is_privileged_agent_creator(current_user.role)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only org_admin/org_manager/super_admin may change who an agent is shared with.",
        )
    return await services.update_agent(agent_id, payload)


@router.post("/{agent_id}/avatar", response_model=AgentPublic)
async def upload_agent_avatar(
    agent_id: str,
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(require_permission("edit_agent")),
) -> AgentPublic:
    """Upload or replace an agent's avatar image. Accepts PNG, JPEG, GIF, or WEBP."""
    agent = await services.get_agent(agent_id)
    assert_org_access(current_user, agent.organization_id)
    await services.assert_agent_visible(current_user.id, agent)
    return await services.update_agent_avatar(agent_id, file)


@router.patch("/{agent_id}/status", response_model=AgentPublic)
async def toggle_agent_status(
    agent_id: str,
    is_active: bool = Body(..., embed=True),
    current_user: UserPublic = Depends(require_permission("edit_agent")),
) -> AgentPublic:
    """Activate or deactivate an agent."""
    agent = await services.get_agent(agent_id)
    assert_org_access(current_user, agent.organization_id)
    await services.assert_agent_visible(current_user.id, agent)
    return await services.toggle_agent_status(agent_id, is_active)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: UserPublic = Depends(require_permission("delete_agent")),
) -> None:
    """Delete an agent."""
    agent = await services.get_agent(agent_id)
    assert_org_access(current_user, agent.organization_id)
    await services.assert_agent_visible(current_user.id, agent)
    await services.delete_agent(agent_id)


@router.get("/{agent_id}/permissions", response_model=AgentPermissionsDoc)
async def get_agent_permissions(
    agent_id: str,
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> AgentPermissionsDoc:
    """Return the agent's permissions document."""
    agent = await services.get_agent(agent_id)
    assert_org_access(current_user, agent.organization_id)
    await services.assert_agent_visible(current_user.id, agent)
    return await services.get_agent_permissions(agent_id)

#Same Routes one is used in GET, the other is used in POST

@router.patch("/{agent_id}/permissions", response_model=AgentPermissionsDoc)
async def patch_agent_permissions(
    agent_id: str,
    payload: AgentPermissionsPatch,
    current_user: UserPublic = Depends(require_permission("edit_agent")),
) -> AgentPermissionsDoc:
    """Partially update the agent's permissions."""
    agent = await services.get_agent(agent_id)
    assert_org_access(current_user, agent.organization_id)
    await services.assert_agent_visible(current_user.id, agent)
    return await services.patch_agent_permissions(agent_id, payload)
