import logging

from fastapi import APIRouter, Depends, status

from backend.auth.permissions import assert_org_access, is_super_admin
from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission
from backend.tool import services
from backend.tool.schemas import ToolCreate, ToolPublic, ToolUpdate

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tools",
    tags=["tools"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=ToolPublic, status_code=status.HTTP_201_CREATED)
async def create_tool(
    payload: ToolCreate,
    current_user: UserPublic = Depends(require_permission("create_tool")),
) -> ToolPublic:
    """Create a new tool. organization_id must be provided and must be a valid org."""
    assert_org_access(current_user, payload.organization_id)
    return await services.create_tool(payload)


@router.get("", response_model=Page[ToolPublic])
async def list_tools(
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> Page[ToolPublic]:
    """List tools (paginated)."""
    logger.info(
        "[tools] GET /tools by user=%s role=%s org_id=%s skip=%s limit=%s",
        current_user.id, current_user.role, current_user.organization_id, pg.skip, pg.limit,
    )
    if is_super_admin(current_user.role):
        items, total = await services.list_tools(skip=pg.skip, limit=pg.limit)
    else:
        items, total = await services.list_tools_by_org(
            current_user.organization_id, skip=pg.skip, limit=pg.limit
        )
    logger.info("[tools] GET /tools -> returning %s of %s items", len(items), total)
    return build_page(items, total, pg)


@router.get("/org/{org_id}", response_model=Page[ToolPublic])
async def get_tools_by_org(
    org_id: str,
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> Page[ToolPublic]:
    """List all tools belonging to a specific organization (paginated)."""
    assert_org_access(current_user, org_id)
    items, total = await services.list_tools_by_org(org_id, skip=pg.skip, limit=pg.limit)
    return build_page(items, total, pg)


@router.get("/{tool_id}", response_model=ToolPublic)
async def get_tool(
    tool_id: str,
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> ToolPublic:
    """Retrieve a single tool by id."""
    tool = await services.get_tool(tool_id)
    assert_org_access(current_user, tool.organization_id)
    return tool


@router.put("/{tool_id}", response_model=ToolPublic)
async def update_tool(
    tool_id: str,
    payload: ToolUpdate,
    current_user: UserPublic = Depends(require_permission("edit_tool")),
) -> ToolPublic:
    """Update a tool."""
    tool = await services.get_tool(tool_id)
    assert_org_access(current_user, tool.organization_id)
    return await services.update_tool(tool_id, payload)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: str,
    current_user: UserPublic = Depends(require_permission("delete_tool")),
) -> None:
    """Delete a tool."""
    tool = await services.get_tool(tool_id)
    assert_org_access(current_user, tool.organization_id)
    await services.delete_tool(tool_id)
