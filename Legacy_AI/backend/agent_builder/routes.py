from fastapi import APIRouter, Depends

from backend.agent_builder.schemas import AgentBlueprint, BuilderRequest
from backend.agent_builder.services import build_blueprint
from backend.auth.schemas import UserPublic
from backend.dependencies import require_permission

router = APIRouter(prefix="/agent-builder", tags=["agent-builder"])


@router.post("/blueprint", response_model=AgentBlueprint)
async def blueprint(
    payload: BuilderRequest,
    _current_user: UserPublic = Depends(require_permission("create_agent")),
) -> AgentBlueprint:
    return await build_blueprint(payload)
