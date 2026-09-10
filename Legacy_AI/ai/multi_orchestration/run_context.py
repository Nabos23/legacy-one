"""RunContext — single DTO threaded through every component of a run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ai.multi_orchestration.runtime_graph import RuntimeGraph
    from ai.multi_orchestration.memory_bus import MemoryBus


@dataclass
class RunContext:
    # Identity (immutable for the life of a run)
    run_id: str
    orchestration_id: str
    session_id: str
    org_id: str
    user_id: str
    unattended: bool = False

    # Execution position (mutated by RuntimeScheduler)
    current_depth: int = 0
    execution_path: List[str] = field(default_factory=list)  # agent_ids in order

    # Set after graph loading
    runtime_graph: Optional["RuntimeGraph"] = None
    memory_bus: Optional["MemoryBus"] = None
    sync_db: Optional[object] = None
    model: str = ""
