"""Supervisor-mode orchestration: dynamic routing across connected agents.

Public surface for the rest of the codebase — import from here, not from the
submodules, so internal layout stays free to change.

  agent.py     the Supervisor: identity, candidate selection, routing, synthesis
  prompt.py    the prompt text it and its routed agents run on
  handback.py  the control signal a routed agent raises to give control back
"""
from ai.multi_orchestration.supervisor.agent import (
    DEFAULT_MAX_CONSECUTIVE_HANDBACKS,
    DEFAULT_MAX_HOPS,
    DEFAULT_MAX_VISITS_PER_AGENT,
    FINISH,
    MAX_INLINE_CANDIDATES,
    ROUTE,
    SHORTLIST_SIZE,
    SUPERVISOR_AGENT_ID,
    SUPERVISOR_AGENT_NAME,
    RouteDecision,
    SupervisorAgent,
)
from ai.multi_orchestration.supervisor.handback import (
    KIND_BLOCKED,
    KIND_WRONG_DOMAIN,
    Handback,
    SupervisorHandbackException,
    extract_handback,
)
from ai.multi_orchestration.supervisor.prompt import (
    FORCED_ASSIGNMENT_NOTE,
    SUPERVISOR_MODE_PROMPT,
    render_agent_mode_prompt,
)

__all__ = [
    "DEFAULT_MAX_CONSECUTIVE_HANDBACKS",
    "DEFAULT_MAX_HOPS",
    "DEFAULT_MAX_VISITS_PER_AGENT",
    "FINISH",
    "FORCED_ASSIGNMENT_NOTE",
    "Handback",
    "KIND_BLOCKED",
    "KIND_WRONG_DOMAIN",
    "MAX_INLINE_CANDIDATES",
    "ROUTE",
    "RouteDecision",
    "SHORTLIST_SIZE",
    "SUPERVISOR_AGENT_ID",
    "SUPERVISOR_AGENT_NAME",
    "SUPERVISOR_MODE_PROMPT",
    "SupervisorAgent",
    "SupervisorHandbackException",
    "extract_handback",
    "render_agent_mode_prompt",
]
