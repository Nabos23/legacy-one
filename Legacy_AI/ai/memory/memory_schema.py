from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class MemorySchema(BaseModel):
    user_id: str
    organization_id: str
    agent_id: str
    agent_name: str
    user_query: str
    agents_output: str
    tool_called: bool = False
    tool_name: Optional[str] = None
    tool_output: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
