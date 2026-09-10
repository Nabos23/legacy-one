from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status

from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission, require_super_admin
from backend.toolregistry import services
from backend.toolregistry.schemas import (
    ToolRegistryCreate,
    ToolRegistryPublic,
    ToolRegistryUpdate,
)

router = APIRouter(
    prefix="/tool-registry",
    tags=["tool-registry"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=ToolRegistryPublic, status_code=status.HTTP_201_CREATED)
async def create_tool_registry(
    payload: ToolRegistryCreate,
    _: UserPublic = Depends(require_super_admin),
) -> ToolRegistryPublic:
    """Create a tool registry (catalog) entry. Super admin only."""
    return await services.create_tool_registry(payload)


@router.get("", response_model=Page[ToolRegistryPublic])
async def list_tool_registry(
    pg: Pagination = Depends(pagination_params),
    search: Optional[str] = Query(default=None, description="Filter by name (case-insensitive)"),
    type: Optional[str] = Query(default=None, description="Filter by tool type (db/http/rag/custom)"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active/inactive status"),
    sort_by: Optional[Literal["name", "created_at"]] = Query(default=None),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    _: UserPublic = Depends(require_permission("view_tool_registry")),
) -> Page[ToolRegistryPublic]:
    """List tool registry entries (paginated), with optional search/type/status filters and sorting."""
    items, total = await services.list_tool_registry(
        skip=pg.skip,
        limit=pg.limit,
        search=search,
        type=type,
        is_active=is_active,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return build_page(items, total, pg)


@router.get("/{registry_id}", response_model=ToolRegistryPublic)
async def get_tool_registry(
    registry_id: str,
    _: UserPublic = Depends(require_permission("view_tool_registry")),
) -> ToolRegistryPublic:
    """Retrieve a single tool registry entry by id."""
    return await services.get_tool_registry(registry_id)


@router.put("/{registry_id}", response_model=ToolRegistryPublic)
async def update_tool_registry(
    registry_id: str,
    payload: ToolRegistryUpdate,
    _: UserPublic = Depends(require_super_admin),
) -> ToolRegistryPublic:
    """Update a tool registry entry. Super admin only."""
    return await services.update_tool_registry(registry_id, payload)


@router.delete("/{registry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool_registry(
    registry_id: str,
    _: UserPublic = Depends(require_super_admin),
) -> None:
    """Soft-delete a tool registry entry. Super admin only."""
    await services.delete_tool_registry(registry_id)
