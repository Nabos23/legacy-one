from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BuilderRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=4000)
    answers: Dict[str, str] = {}


class BuilderOption(BaseModel):
    value: str
    label: str
    description: Optional[str] = None


class BuilderQuestion(BaseModel):
    id: str
    text: str
    options: List[BuilderOption]


class AgentBlueprint(BaseModel):
    name: str
    description: str
    system_prompt: str
    guardrails: str
    connector_ids: List[str] = []
    connector_names: List[str] = []
    mcp_registry_keys: List[str] = []
    mcp_names: List[str] = []
    tool_ids: List[str] = []
    tool_names: List[str] = []
    db_tool_ids: List[str] = []
    requires_db_connection: bool = False
    questions: List[BuilderQuestion] = []
    ready: bool = False
    # Capabilities the prompt named that had no plausible match anywhere in
    # the registry (connectors/tools/mcp). Empty when everything requested
    # was covered.
    unmatched_capabilities: List[str] = []
    # The full active catalog (not just the top candidates sent to the LLM),
    # so the client can offer a substitute when something is unmatched.
    available_options: List[BuilderOption] = []
