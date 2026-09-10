from fastapi import APIRouter, Depends

from backend.dependencies import get_current_user
from backend.auth.schemas import UserPublic
from backend.prompt_generator.schemas import PromptGeneratorRequest, PromptGeneratorResponse
from backend.prompt_generator.services import generate_prompt

router = APIRouter(
    prefix="/generate-prompt",
    tags=["prompt-generator"],
    # Authentication required: this endpoint triggers an LLM call, so it must
    # not be reachable anonymously (prevents unmetered token-burn / cost abuse).
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=PromptGeneratorResponse)
async def generate_agent_prompt(
    payload: PromptGeneratorRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> PromptGeneratorResponse:
    """Generate an optimized system prompt for an agent given its name and description.

    Requires an authenticated user — the LLM call is gated behind a valid
    Bearer token and metered by the global rate limiter.
    """
    prompt, guardrails = await generate_prompt(payload, current_user)
    return PromptGeneratorResponse(prompt=prompt, guardrails=guardrails, model="gpt-5.4-nano")