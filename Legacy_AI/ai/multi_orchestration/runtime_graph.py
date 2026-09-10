"""Immutable, pre-loaded graph used throughout one orchestration run."""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from ai.multi_orchestration.supervisor.agent import (
    DEFAULT_MAX_CONSECUTIVE_HANDBACKS,
    DEFAULT_MAX_HOPS,
)


@dataclass
class RuntimeAgentNode:
    agent_id: str
    name: str
    prompt: str
    guardrails: List[str]
    tools: List[dict]                        # LiteLLM tool specs
    tool_callables: Dict[str, Callable]      # tool_name -> callable
    description: str = ""
    # Composed-at-creation prompt blocks (from the agent doc). These already
    # contain tool guidance — including the ask_human / human-in-the-loop block.
    tool_prompt: str = ""
    mcp_prompt: str = ""
    connector_prompt: str = ""
    next_agents: List[dict] = field(default_factory=list)  # [{"name": ..., "description": ...}]
    # tool_name -> {"connector_id", "provider_id", "display_name"} for connector
    # tools only — lets the invoker identify which connector needs reconnecting
    # when a tool call fails on auth (see ai.connectors.errors.is_connector_auth_error).
    connector_tool_owner: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # ---- supervisor mode ------------------------------------------------
    # tool_name -> MCP server display name. Counterpart of connector_tool_owner:
    # lets the Supervisor see "this agent can reach Notion" instead of a list of
    # opaque tool names.
    mcp_tool_owner: Dict[str, str] = field(default_factory=dict)
    # Prompt block appended in supervisor mode (team context + handback rules).
    # Empty in sequential mode, so sequential system prompts are unchanged.
    handback_prompt: str = ""
    # Operator-written short summary, when the agent has one — often the clearest
    # statement of intent, and therefore a strong routing signal.
    user_description: str = ""
    # Capabilities configured on the agent that failed to load for this run
    # (e.g. "Gmail (no valid token)"). Surfaced to the Supervisor so a degraded
    # agent is still routable but the outcome stays explicable.
    capability_load_errors: List[str] = field(default_factory=list)


@dataclass
class RuntimeGraph:
    orchestration_id: str
    # None in supervisor mode: the Supervisor is the entry point, and it is not
    # an agent document, so there is no id to store.
    main_agent_id: Optional[str]
    nodes: Dict[str, RuntimeAgentNode]       # agent_id -> node

    # Graph structure (derived from orchestration.connections)
    adjacency: Dict[str, List[str]]          # agent_id -> [outbound agent_ids]
    reverse_adjacency: Dict[str, List[str]]  # agent_id -> [inbound agent_ids]
    edge_types: Dict[tuple, str]             # (from_id, to_id) -> EdgeType value
    edge_labels: Dict[tuple, str]            # (from_id, to_id) -> label string

    # Pre-computed topology facts
    join_points: Set[str]                    # nodes with >1 inbound edge
    hub_nodes: Set[str]                      # nodes that appear as both source AND target
    has_parallel_branches: bool

    max_depth: int
    max_visits_per_agent: int = 3

    # "sequential" (edge-driven, the original behaviour) or "supervisor"
    # (dynamic routing; adjacency is empty and every node is a candidate).
    mode: str = "sequential"
    # Bounds on one supervisor-mode turn — both fail the run gracefully rather
    # than looping. Ignored in sequential mode.
    supervisor_max_hops: int = DEFAULT_MAX_HOPS
    supervisor_max_consecutive_handbacks: int = DEFAULT_MAX_CONSECUTIVE_HANDBACKS
    # Operator guidance appended to the Supervisor's routing prompt.
    supervisor_instructions: str = ""
    # False = routing only: the Supervisor must not answer questions itself.
    supervisor_allow_direct_answer: bool = True

    @property
    def is_supervised(self) -> bool:
        return self.mode == "supervisor"
