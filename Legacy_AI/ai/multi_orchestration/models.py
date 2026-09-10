"""Data classes and document factories for the multi-orchestration runtime."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from ai.tools.tools import HumanInterruptException
import uuid


class RunStatus(str, Enum):
    LOADING = "loading"
    RUNNING = "running"
    ROUTING = "routing"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_FOR_HUMAN = "waiting_for_human"
    WAITING_FOR_REAUTH = "waiting_for_reauth"
    SLEEPING = "sleeping"
    COMPLETE = "complete"
    FAILED = "failed"
    TIMEOUT = "timeout"

TERMINAL_STATUSES = (
    RunStatus.COMPLETE.value,
    RunStatus.FAILED.value,
    RunStatus.TIMEOUT.value,
    RunStatus.WAITING_FOR_HUMAN.value,
    RunStatus.WAITING_FOR_REAUTH.value,
)


class EdgeType(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class TriggerType(str, Enum):
    CRON = "cron"
    EVENT = "event"
    WEBHOOK = "webhook"
    AGENT_DECLARED = "agent_declared"
    USER_MESSAGE = "user_message"


@dataclass
class ToolInvocationRecord:
    tool_name: str
    arguments: dict
    result: str
    status: str          # "success" | "error"
    started_at: datetime
    ended_at: datetime
    error: Optional[str] = None

@dataclass
class BranchState:
    branch_id: str
    status: str                          # RunStatus value scoped to this branch
    pending_agents: List[str] = field(default_factory=list)
    human_question: Optional[str] = None
    human_asked_by_agent: Optional[str] = None
    pending_reauth: Optional[Dict[str, str]] = None  # {connector_id, provider_id, display_name, fn_name}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


def new_branch_state(pending_agents: List[str], label: str = "") -> dict:
    """Factory for one entry in a run document's `branches` array."""
    return {
        "branch_id": str(uuid.uuid4()),
        "status": RunStatus.RUNNING.value,
        "pending_agents": pending_agents,
        "label": label,
        "human_question": None,
        "human_asked_by_agent": None,
        "pending_reauth": None,
        "started_at": datetime.now(timezone.utc),
        "completed_at": None,
    }

def new_run_document(
    orchestration_id: str,
    session_id: str,
    user_id: str,
    organization_id: str,
    entry_message: str,
    main_agent_id: str,
    max_depth: int,
    timeout_sec: int,
    epoch: int = 1,
    instance_id: Optional[str] = None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "run_id": str(uuid.uuid4()),
        "orchestration_id": orchestration_id,
        "instance_id": instance_id,           # set for 24/7 (epoch-based) runs
        "session_id": session_id,
        "user_id": user_id,
        "organization_id": organization_id,
        "epoch": epoch,
        "status": RunStatus.LOADING.value,
        "current_agent_id": main_agent_id,
        "entry_message": entry_message,
        "final_response": None,
        "execution_path": [],                  # List[PathEntry dict]
        "routing_history": [],                 # List[RoutingEntry dict]
        "memory_log": [],                      # single append-only context log (verbatim, uncapped)
        "human_question": None,                # set when status=waiting_for_human
        "human_asked_by_agent": None,          # agent_id that triggered HITL
        "pending_reauth": None,                # set when status=waiting_for_reauth: {connector_id, provider_id, display_name, fn_name}
        "pending_agents": [],                  # BFS queue snapshot for HITL/reauth resume
        "branches": [],                        # List[BranchState dict] for fan-out branches
        "error_context": None,                 # ErrorRecord dict on failure
        "depth_counter": 0,
        "loop_counters": {},                   # {agent_id: visit_count}
        "max_depth": max_depth,
        "started_at": now,
        "completed_at": None,
        "timeout_sec": timeout_sec,
    }


def new_instance_document(
    orchestration_id: str,
    organization_id: str,
    user_id: str,
    trigger_type: str,
    trigger_config: dict,
) -> dict:
    """
    Factory for an OrchestrationInstance document — groups all epochs of a 24/7 run.
    """
    now = datetime.now(timezone.utc)
    return {
        "instance_id": str(uuid.uuid4()),
        "orchestration_id": orchestration_id,
        "organization_id": organization_id,
        "user_id": user_id,
        "trigger_type": trigger_type,
        "trigger_config": trigger_config,      # e.g. {"cron_expr": "0 9 * * *"}
        "status": "active",                    # active | paused | terminated
        "epoch_count": 0,
        "last_handoff": None,                  # context summary for next epoch
        "created_at": now,
        "updated_at": now,
    }
