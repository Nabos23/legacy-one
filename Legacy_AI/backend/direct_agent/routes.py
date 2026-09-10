from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.auth.schemas import UserPublic
from backend.dependencies import get_current_user
from backend.direct_agent import services
from backend.direct_agent.schemas import DirectChatRequest, DirectChatResponse

router = APIRouter(
    prefix="/chat",
    tags=["direct-chat"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=DirectChatResponse,
    summary="Send a message directly to a single agent (no supervisor)",
)
async def direct_chat(
    payload: DirectChatRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> DirectChatResponse:
    return await services.direct_chat(
        agent_id=payload.agent_id,
        message=payload.message,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        session_id=payload.session_id,
    )


@router.post(
    "/stream",
    summary="Send a message directly to a single agent, streaming live tool-call events (SSE)",
)
async def direct_chat_stream(
    payload: DirectChatRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> StreamingResponse:
    """Same as POST /chat, but streams `tool_call` progress events as
    Server-Sent Events while the turn runs, ending in a `done` event with the
    same payload shape as the blocking endpoint's response."""
    # Runs everything that can 404 (agent/session not found) BEFORE the
    # streaming response starts, since its status code is committed as soon
    # as the first chunk is sent.
    ctx = await services.prepare_direct_chat_stream(
        agent_id=payload.agent_id,
        message=payload.message,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        session_id=payload.session_id,
    )
    return StreamingResponse(
        services.direct_chat_stream(ctx),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
