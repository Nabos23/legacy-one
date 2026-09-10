from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from backend.auth.schemas import UserPublic
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission
from backend.schedule import services
from backend.schedule.schemas import (
    PreviewQuestionsRequest,
    PreviewQuestionsResponse,
    ScheduleCreate,
    SchedulePublic,
    ScheduleRunPublic,
    ScheduleUpdate,
)

router = APIRouter(
    prefix="/schedules",
    tags=["schedules"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/preview-questions",
    response_model=PreviewQuestionsResponse,
    summary="Generate clarifying questions for a schedule before creating it",
)
async def preview_questions(
    payload: PreviewQuestionsRequest,
    current_user: UserPublic = Depends(require_permission("create_schedule")),
) -> PreviewQuestionsResponse:
    return await services.generate_scheduling_questions(payload, current_user)


@router.post(
    "",
    response_model=SchedulePublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new schedule for an agent",
)
async def create_schedule(
    payload: ScheduleCreate,
    current_user: UserPublic = Depends(require_permission("create_schedule")),
) -> SchedulePublic:
    return await services.create_schedule(payload, current_user.organization_id, current_user)


@router.get(
    "",
    response_model=Page[SchedulePublic],
    summary="List schedules for the current organization",
)
async def list_schedules(
    needs_attention: Optional[bool] = Query(default=None),
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_schedule")),
) -> Page[SchedulePublic]:
    items, total = await services.list_schedules(
        current_user.organization_id, current_user, needs_attention=needs_attention, skip=pg.skip, limit=pg.limit
    )
    return build_page(items, total, pg)


@router.get(
    "/{schedule_id}",
    response_model=SchedulePublic,
    summary="Get a single schedule",
)
async def get_schedule(
    schedule_id: str,
    current_user: UserPublic = Depends(require_permission("view_schedule")),
) -> SchedulePublic:
    return await services.get_schedule(schedule_id, current_user.organization_id, current_user)


@router.patch(
    "/{schedule_id}",
    response_model=SchedulePublic,
    summary="Update a schedule",
)
async def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    current_user: UserPublic = Depends(require_permission("edit_schedule")),
) -> SchedulePublic:
    return await services.update_schedule(schedule_id, payload, current_user.organization_id, current_user)


@router.post(
    "/{schedule_id}/pause",
    response_model=SchedulePublic,
    summary="Pause a schedule",
)
async def pause_schedule(
    schedule_id: str,
    current_user: UserPublic = Depends(require_permission("edit_schedule")),
) -> SchedulePublic:
    return await services.pause_schedule(schedule_id, current_user.organization_id, current_user)


@router.post(
    "/{schedule_id}/resume",
    response_model=SchedulePublic,
    summary="Resume a paused schedule",
)
async def resume_schedule(
    schedule_id: str,
    current_user: UserPublic = Depends(require_permission("edit_schedule")),
) -> SchedulePublic:
    return await services.resume_schedule(schedule_id, current_user.organization_id, current_user)


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a schedule",
)
async def delete_schedule(
    schedule_id: str,
    current_user: UserPublic = Depends(require_permission("delete_schedule")),
) -> None:
    await services.delete_schedule(schedule_id, current_user.organization_id, current_user)


@router.get(
    "/{schedule_id}/runs",
    response_model=List[ScheduleRunPublic],
    summary="List a schedule's run history",
)
async def list_schedule_runs(
    schedule_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: UserPublic = Depends(require_permission("view_schedule")),
) -> List[ScheduleRunPublic]:
    return await services.list_schedule_runs(schedule_id, current_user.organization_id, current_user, skip=skip, limit=limit)
