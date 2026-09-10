from typing import List, Literal, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from backend.auth.permissions import (
    assert_org_access,
    is_privileged_agent_creator,
    is_super_admin,
)
from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission
from backend.projects import services
from backend.projects.schemas import (
    ProjectChatMessagePublic,
    ProjectChatRequest,
    ProjectChatResponse,
    ProjectCreate,
    ProjectFilePublic,
    ProjectPublic,
    ProjectUpdate,
)

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)

ProjectSortBy = Literal["name", "created_at"]
ProjectSortOrder = Literal["asc", "desc"]


class ProjectListFilters:
    """FastAPI dependency bundling optional query filters for listing projects."""

    def __init__(
        self,
        search: Optional[str] = Query(default=None, description="Filter projects by name (case-insensitive)"),
        has_tools: Optional[bool] = Query(default=None, description="Filter by whether the project has tools attached"),
        has_connectors: Optional[bool] = Query(default=None, description="Filter by whether the project has connectors attached"),
        sort_by: Optional[ProjectSortBy] = Query(default=None, description="Field to sort by (default: created_at)"),
        sort_order: ProjectSortOrder = Query(default="desc", description="Sort direction"),
    ) -> None:
        self.search = search
        self.has_tools = has_tools
        self.has_connectors = has_connectors
        self.sort_by = sort_by
        self.sort_order = sort_order

    def as_kwargs(self) -> dict:
        return {
            "search": self.search,
            "has_tools": self.has_tools,
            "has_connectors": self.has_connectors,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
        }


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: UserPublic = Depends(require_permission("create_project")),
) -> ProjectPublic:
    """Create a new project."""
    assert_org_access(current_user, payload.organization_id)
    if is_privileged_agent_creator(current_user.role):
        owner_scope = payload.owner_scope or "organization"
        allowed_user_ids = payload.allowed_user_ids if owner_scope == "selected_users" else []
        team_id = payload.team_id if owner_scope == "team" else None
    else:
        owner_scope = "user"
        allowed_user_ids = []
        team_id = None

    return await services.create_project(
        payload,
        created_by=current_user.id,
        owner_scope=owner_scope,
        allowed_user_ids=allowed_user_ids,
        team_id=team_id,
    )


@router.get("", response_model=Page[ProjectPublic])
async def list_projects(
    pg: Pagination = Depends(pagination_params),
    filters: ProjectListFilters = Depends(),
    organization_id: Optional[str] = Query(default=None, description="Super-admin only: narrow to one organization"),
    current_user: UserPublic = Depends(require_permission("view_project")),
) -> Page[ProjectPublic]:
    """List projects (paginated) with optional filters."""
    if is_super_admin(current_user.role):
        if organization_id:
            items, total = await services.list_projects_by_org(
                organization_id,
                skip=pg.skip,
                limit=pg.limit,
                requesting_user_id=current_user.id,
                **filters.as_kwargs(),
            )
        else:
            items, total = await services.list_projects(
                skip=pg.skip,
                limit=pg.limit,
                requesting_user_id=current_user.id,
                **filters.as_kwargs(),
            )
    else:
        target_org = current_user.organization_id
        if not target_org:
            return build_page([], 0, pg)
        items, total = await services.list_projects_by_org(
            target_org,
            skip=pg.skip,
            limit=pg.limit,
            requesting_user_id=current_user.id,
            **filters.as_kwargs(),
        )

    return build_page(items, total, pg)


@router.get("/{project_id}", response_model=ProjectPublic)
async def get_project(
    project_id: str,
    current_user: UserPublic = Depends(require_permission("view_project")),
) -> ProjectPublic:
    """Get a project by ID."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    user_id = "" if is_super_admin(current_user.role) else current_user.id
    return await services.get_project(project_id, org_id=org_id, user_id=user_id)


@router.patch("/{project_id}", response_model=ProjectPublic)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    current_user: UserPublic = Depends(require_permission("edit_project")),
) -> ProjectPublic:
    """Update a project by ID."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    return await services.update_project(project_id, payload, org_id=org_id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: UserPublic = Depends(require_permission("delete_project")),
) -> None:
    """Soft delete a project."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    await services.delete_project(project_id, org_id=org_id)


# ---------------------------------------------------------------------------
# Skills & Files Endpoints
# ---------------------------------------------------------------------------

@router.post("/{project_id}/files", response_model=ProjectFilePublic, status_code=status.HTTP_201_CREATED)
async def upload_project_file(
    project_id: str,
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(require_permission("edit_project")),
) -> ProjectFilePublic:
    """Upload a skill (e.g. skills.md / SKILL.md) or project file saved directly in MongoDB."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    return await services.upload_project_file(
        project_id=project_id,
        file=file,
        uploaded_by=current_user.id,
        org_id=org_id,
    )


@router.get("/{project_id}/files", response_model=List[ProjectFilePublic])
async def list_project_files(
    project_id: str,
    current_user: UserPublic = Depends(require_permission("view_project")),
) -> List[ProjectFilePublic]:
    """List all files and skills attached to a project."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    return await services.list_project_files(project_id, org_id=org_id)


@router.get("/{project_id}/files/{file_id}", response_model=ProjectFilePublic)
async def get_project_file(
    project_id: str,
    file_id: str,
    current_user: UserPublic = Depends(require_permission("view_project")),
) -> ProjectFilePublic:
    """Get metadata and content of an uploaded file or skill in a project."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    return await services.get_project_file(project_id, file_id, org_id=org_id)


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_file(
    project_id: str,
    file_id: str,
    current_user: UserPublic = Depends(require_permission("edit_project")),
) -> None:
    """Delete an uploaded file or skill from a project."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    await services.delete_project_file(project_id, file_id, org_id=org_id)


# ---------------------------------------------------------------------------
# Project Chat Endpoints
# ---------------------------------------------------------------------------

@router.get("/{project_id}/messages", response_model=List[ProjectChatMessagePublic])
async def list_project_messages(
    project_id: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: UserPublic = Depends(get_current_user),
) -> List[ProjectChatMessagePublic]:
    """Retrieve chat message history for a project (no sessions, continuous project history)."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    return await services.list_project_messages(project_id, org_id=org_id, limit=limit)


@router.delete("/{project_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_project_messages(
    project_id: str,
    current_user: UserPublic = Depends(require_permission("delete_project")),
) -> None:
    """Clear continuous chat history for a project."""
    org_id = "" if is_super_admin(current_user.role) else (current_user.organization_id or "")
    await services.clear_project_messages(project_id, org_id=org_id)


@router.post("/{project_id}/chat", response_model=ProjectChatResponse)
async def project_chat(
    project_id: str,
    payload: ProjectChatRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> ProjectChatResponse:
    """Chat directly with a project (blocking)."""
    return await services.project_chat(
        project_id=project_id,
        message=payload.message,
        org_id=current_user.organization_id or "",
        user_id=current_user.id,
        session_id=payload.session_id,
    )


@router.post("/{project_id}/chat/stream")
async def project_chat_stream(
    project_id: str,
    payload: ProjectChatRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> StreamingResponse:
    """Chat directly with a project, streaming live tool calls and completion (SSE)."""
    ctx = await services.prepare_project_chat_stream(
        project_id=project_id,
        message=payload.message,
        org_id=current_user.organization_id or "",
        user_id=current_user.id,
        session_id=payload.session_id,
    )
    return StreamingResponse(
        services.project_chat_stream(ctx),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
