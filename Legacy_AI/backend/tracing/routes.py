from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.permissions import is_org_manager_or_above
from backend.auth.schemas import UserPublic
from backend.dependencies import get_current_user, require_permission
from backend.tracing import services
from backend.tracing.schemas import (
    SessionsResponse,
    TraceDetail,
    TraceStats,
    TracesResponse,
)

router = APIRouter(tags=["tracing"], dependencies=[Depends(get_current_user)])

@router.get("/traces", response_model=TracesResponse, summary="List traces for the authenticated org")
async def list_traces(
    agent_id: Optional[str] = Query(None, description="Filter by MongoDB agent ObjectId"),
    session_id: Optional[str] = Query(None, description="Filter by Langfuse session id"),
    user_id: Optional[str] = Query(None, description="Filter by user id. org_admin/org_manager/super_admin only — plain users are always scoped to themselves"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: Optional[str] = Query(None, description="Super-admin only: scope to a specific org"),
    current_user: UserPublic = Depends(require_permission("view_trace")),
) -> TracesResponse:
    data = await services.list_traces(
        org_id=services.effective_org_id(current_user, organization_id),
        page=page,
        limit=page_size,
        agent_id=agent_id,
        session_id=session_id,
        user_id=services.effective_user_id(current_user, user_id),
    )
    return TracesResponse(**data)


@router.get("/traces/stats", response_model=TraceStats, summary="Aggregate cost and token stats")
async def get_trace_stats(
    agent_id: Optional[str] = Query(None, description="Scope stats to a single agent"),
    user_id: Optional[str] = Query(None, description="Scope stats to a single user. org_admin/org_manager/super_admin only — plain users are always scoped to themselves"),
    organization_id: Optional[str] = Query(None, description="Super-admin only: scope to a specific org"),
    current_user: UserPublic = Depends(require_permission("view_trace")),
) -> TraceStats:
    data = await services.get_trace_stats(
        org_id=services.effective_org_id(current_user, organization_id),
        agent_id=agent_id,
        user_id=services.effective_user_id(current_user, user_id),
    )
    return TraceStats(**data)


@router.get("/traces/{trace_id}", response_model=TraceDetail, summary="Trace detail with observation waterfall")
async def get_trace(
    trace_id: str,
    organization_id: Optional[str] = Query(None, description="Super-admin only: scope to a specific org"),
    current_user: UserPublic = Depends(require_permission("view_trace")),
) -> TraceDetail:
    data = await services.get_trace_detail(
        trace_id=trace_id,
        org_id=services.effective_org_id(current_user, organization_id),
        user_id=services.effective_user_id(current_user, None),
    )
    return TraceDetail(**data)


@router.get("/sessions", response_model=SessionsResponse, summary="List conversation sessions for the org")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserPublic = Depends(require_permission("view_trace")),
) -> SessionsResponse:
    if not is_org_manager_or_above(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sessions are only visible to org admins and managers.",
        )
    data = await services.list_sessions(
        page=page,
        limit=page_size,
    )
    return SessionsResponse(**data)


# ---------------------------------------------------------------------------
# Per-agent shortcuts  (convenience wrappers over the filtered trace endpoints)
# ---------------------------------------------------------------------------

@router.get("/agents/{agent_id}/traces", response_model=TracesResponse, summary="Traces for a specific agent")
async def list_agent_traces(
    agent_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None, description="Filter by user id. org_admin/org_manager/super_admin only — plain users are always scoped to themselves"),
    organization_id: Optional[str] = Query(None, description="Super-admin only: scope to a specific org"),
    current_user: UserPublic = Depends(require_permission("view_trace")),
) -> TracesResponse:
    data = await services.list_traces(
        org_id=services.effective_org_id(current_user, organization_id),
        page=page,
        limit=page_size,
        agent_id=agent_id,
        user_id=services.effective_user_id(current_user, user_id),
    )
    return TracesResponse(**data)


@router.get("/agents/{agent_id}/stats", response_model=TraceStats, summary="Cost and token stats for a specific agent")
async def get_agent_stats(
    agent_id: str,
    user_id: Optional[str] = Query(None, description="Filter by user id. org_admin/org_manager/super_admin only — plain users are always scoped to themselves"),
    organization_id: Optional[str] = Query(None, description="Super-admin only: scope to a specific org"),
    current_user: UserPublic = Depends(require_permission("view_trace")),
) -> TraceStats:
    data = await services.get_trace_stats(
        org_id=services.effective_org_id(current_user, organization_id),
        agent_id=agent_id,
        user_id=services.effective_user_id(current_user, user_id),
    )
    return TraceStats(**data)
