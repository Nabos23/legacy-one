from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.permissions import is_privileged_agent_creator
from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission
from backend.orchestration import services
from backend.orchestration.executor import resume_orchestration, run_orchestration, resume_branch
from backend.orchestration.schemas import (
    OrchestrationChatRequest,
    OrchestrationChatResponse,
    OrchestrationCreate,
    OrchestrationPublic,
    OrchestrationResumeRequest,
    OrchestrationRunStatus,
    OrchestrationSessionHistoryResponse,
    OrchestrationUpdate,
    OrchestrationSessionListResponse,
    OrchestrationSessionBrief
)

router = APIRouter(
    prefix="/orchestrations",
    tags=["orchestrations"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=OrchestrationPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new agent orchestration",
)
async def create_orchestration(
    payload: OrchestrationCreate,
    current_user: UserPublic = Depends(require_permission("create_agent")),
) -> OrchestrationPublic:
    """Create a new orchestration. Plain "user" role callers always get a
    personal orchestration, regardless of what they send in `owner_scope`.
    Only org_admin/org_manager/super_admin may choose between "personal",
    "organization", "selected_users", and "team" visibility -- mirrors
    backend.agent.routes.create_agent.
    """
    if is_privileged_agent_creator(current_user.role):
        owner_scope = payload.owner_scope or "organization"
        allowed_user_ids = payload.allowed_user_ids if owner_scope == "selected_users" else []
        team_id = payload.team_id if owner_scope == "team" else None
    else:
        owner_scope = "user"
        allowed_user_ids = []
        team_id = None
    return await services.create_orchestration(
        payload, current_user.organization_id, current_user.id,
        owner_scope=owner_scope, allowed_user_ids=allowed_user_ids, team_id=team_id,
    )


@router.get(
    "",
    response_model=Page[OrchestrationPublic],
    summary="List orchestrations for the current organization",
)
async def list_orchestrations(
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> Page[OrchestrationPublic]:
    items, total = await services.list_orchestrations(
        current_user.organization_id, requesting_user_id=current_user.id, skip=pg.skip, limit=pg.limit
    )
    return build_page(items, total, pg)


@router.get(
    "/{orchestration_id}",
    response_model=OrchestrationPublic,
    summary="Get a single orchestration",
)
async def get_orchestration(
    orchestration_id: str,
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> OrchestrationPublic:
    orch = await services.get_orchestration(orchestration_id, current_user.organization_id)
    await services.assert_orchestration_visible(current_user.id, orch)
    return orch


@router.patch(
    "/{orchestration_id}",
    response_model=OrchestrationPublic,
    summary="Update an orchestration",
)
async def update_orchestration(
    orchestration_id: str,
    payload: OrchestrationUpdate,
    current_user: UserPublic = Depends(require_permission("create_agent")),
) -> OrchestrationPublic:
    orch = await services.get_orchestration(orchestration_id, current_user.organization_id)
    await services.assert_orchestration_visible(current_user.id, orch)
    if (
        (payload.allowed_user_ids is not None or payload.team_id is not None)
        and not is_privileged_agent_creator(current_user.role)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only org_admin/org_manager/super_admin may change who an orchestration is shared with.",
        )
    return await services.update_orchestration(orchestration_id, payload, current_user.organization_id)


@router.delete(
    "/{orchestration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an orchestration",
)
async def delete_orchestration(
    orchestration_id: str,
    current_user: UserPublic = Depends(require_permission("create_agent")),
) -> None:
    orch = await services.get_orchestration(orchestration_id, current_user.organization_id)
    await services.assert_orchestration_visible(current_user.id, orch)
    await services.delete_orchestration(orchestration_id, current_user.organization_id)





@router.post(
    "/{orchestration_id}/chat",
    response_model=OrchestrationChatResponse,
    summary="Run an orchestration with a message",
)
async def orchestration_chat(
    orchestration_id: str,
    payload: OrchestrationChatRequest,
    current_user: UserPublic = Depends(require_permission("create_chat")),
) -> OrchestrationChatResponse:
    result = await run_orchestration(
        orchestration_id=orchestration_id,
        message=payload.message,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        session_id=payload.session_id,
        attachments=payload.attachments,
    )
    return OrchestrationChatResponse(**result)


@router.post(
    "/{orchestration_id}/runs/{run_id}/resume",
    response_model=OrchestrationChatResponse,
    summary="Resume a paused orchestration run after providing a human answer",
)
async def resume_run(
    orchestration_id: str,
    run_id: str,
    payload: OrchestrationResumeRequest,
    current_user: UserPublic = Depends(require_permission("create_chat")),
) -> OrchestrationChatResponse:
    if payload.branch_id:
        result = await resume_branch(
            orchestration_id=orchestration_id,
            run_id=run_id,
            branch_id=payload.branch_id,
            answer=payload.answer,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
        )
    else:
        result = await resume_orchestration(
            orchestration_id=orchestration_id,
            run_id=run_id,
            answer=payload.answer,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
        )
    return OrchestrationChatResponse(**result)


@router.get(
    "/{orchestration_id}/runs/{run_id}/status",
    response_model=OrchestrationRunStatus,
    summary="Get the current status of an orchestration run",
)
async def get_run_status(
    orchestration_id: str,
    run_id: str,
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> OrchestrationRunStatus:
    return await services.get_run_status(run_id, orchestration_id, current_user.organization_id)

#Routing to handle getting session history
@router.get(
    "/{orchestration_id}/sessions/{session_id}/history",
    response_model=OrchestrationSessionHistoryResponse,
    summary="Get conversation history for an orchestration session",
)
async def get_session_history(
    orchestration_id: str,
    session_id: str,
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> OrchestrationSessionHistoryResponse:
    return await services.get_orchestration_session_history(
        session_id=session_id,
        orchestration_id=orchestration_id,
        org_id=current_user.organization_id,
    )


#Routing to handle list of sessions
@router.get(
    "/{orchestration_id}/sessions",
    response_model=OrchestrationSessionListResponse,
    summary="List chat sessions for an orchestration",
)
async def list_sessions(
    orchestration_id: str,
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> OrchestrationSessionListResponse:
    return await services.list_orchestration_sessions(
        orchestration_id=orchestration_id,
        org_id=current_user.organization_id,
        user_id=current_user.id,
    )


@router.delete(
    "/{orchestration_id}/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an orchestration chat session (soft-delete)",
)
async def delete_session(
    orchestration_id: str,
    session_id: str,
    current_user: UserPublic = Depends(require_permission("delete_chat_session")),
) -> None:
    await services.delete_orchestration_session(
        session_id=session_id,
        orchestration_id=orchestration_id,
        org_id=current_user.organization_id,
        user_id=current_user.id,
    )


# New endpoint to get branch-specific messages
@router.get(
    "/{orchestration_id}/sessions/{session_id}/branches/{branch_id}/messages",
    response_model=OrchestrationSessionHistoryResponse,
    summary="Get messages for a specific branch within a session",
)
async def get_branch_messages(
    orchestration_id: str,
    session_id: str,
    branch_id: str,
    current_user: UserPublic = Depends(require_permission("view_agent")),
) -> OrchestrationSessionHistoryResponse:
    return await services.get_branch_messages(
        session_id=session_id,
        orchestration_id=orchestration_id,
        org_id=current_user.organization_id,
        branch_id=branch_id,
    )
