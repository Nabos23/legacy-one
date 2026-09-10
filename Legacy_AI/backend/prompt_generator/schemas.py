from typing import Optional

from pydantic import BaseModel, model_validator


class PromptGeneratorRequest(BaseModel):
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_description: Optional[str] = None

    @model_validator(mode="after")
    def _agent_id_or_identity(self) -> "PromptGeneratorRequest":
        if self.agent_id:
            return self
        if self.agent_name and self.agent_description:
            return self
        raise ValueError(
            "Provide agent_id, or both agent_name and agent_description."
        )


class PromptGeneratorResponse(BaseModel):
    prompt: str
    guardrails: str = ""
    model: str