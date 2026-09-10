from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class TracingContext:
    """
    Lightweight DTO created at the request boundary (FastAPI route, decoded from JWT).
    Pass this into MainAgent so it constructs an AgentTracer with the right identifiers.

    When the FastAPI backend is ready:
        ctx = TracingContext(
            org_id=jwt_payload["org_id"],
            user_id=jwt_payload["sub"],
            session_id=request.headers.get("X-Session-Id", str(uuid.uuid4())),
        )
        agent = MainAgent(..., tracing_context=ctx)
    """
    org_id: str
    user_id: str
    session_id: Optional[str] = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if not self.session_id:
            self.session_id = self.user_id
