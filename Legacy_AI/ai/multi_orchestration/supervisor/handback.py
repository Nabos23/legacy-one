"""Handback — how a routed agent returns control to the Supervisor.

An agent that has been routed a request it should not answer hands control back
instead, either by emitting a marker object in its output (mirroring the
`{"next_agent": ...}` convention RoutingEngine already uses for sequential mode)
or by raising SupervisorHandbackException from a tool call.

A handback is an internal control transfer, never a user-visible message.

Two kinds, and the difference matters a great deal:

  wrong_domain  the request belongs to another specialist. The Supervisor
                excludes this agent and routes elsewhere.
  blocked       this IS the right agent, but its tools failed (a query errored,
                a table was missing). Excluding it would disqualify the only
                agent that owns the data and push the request onto an unrelated
                one — which is how a database question ends up being answered
                from someone's mailbox. So a blocked handback is reported as a
                failed step instead: no exclusion, no re-route cascade.
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

HANDBACK_MARKER = '{"handback"'
DEFAULT_HANDBACK_REASON = "This request is outside my domain."

KIND_WRONG_DOMAIN = "wrong_domain"
KIND_BLOCKED = "blocked"


@dataclass(frozen=True)
class Handback:
    """A routed agent giving control back to the Supervisor."""

    reason: str
    kind: str = KIND_WRONG_DOMAIN

    @property
    def is_blocked(self) -> bool:
        """True when the agent was the right choice but could not complete."""
        return self.kind == KIND_BLOCKED


class SupervisorHandbackException(Exception):
    """Raised from a tool call to hand control back to the Supervisor.

    Parallels HumanInterruptException / ConnectorReauthException: the scheduler
    catches it, records the transfer, and re-routes — the agent's turn produces
    no user-visible output.
    """

    def __init__(self, reason: str = "", kind: str = KIND_WRONG_DOMAIN) -> None:
        self.reason = reason or DEFAULT_HANDBACK_REASON
        self.kind = kind
        super().__init__(self.reason)

    def to_handback(self) -> Handback:
        return Handback(reason=self.reason, kind=self.kind)


def extract_handback(output: Optional[str]) -> Optional[Handback]:
    """Return a Handback if `output` declares one, else None.

    Tolerant by design — a false negative just means the agent's text is treated
    as a real answer, so this must never raise. Uses raw_decode so a marker
    followed by trailing prose still parses.
    """
    if not output:
        return None
    idx = output.rfind(HANDBACK_MARKER)
    if idx == -1:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(output[idx:])
    except ValueError:
        logger.debug("[supervisor:handback] marker present but unparseable — treating as answer")
        return None
    if not isinstance(data, dict) or data.get("handback") is not True:
        return None
    reason = str(data.get("reason") or "").strip() or DEFAULT_HANDBACK_REASON
    # Unknown or absent kind reads as wrong_domain: that is the conservative
    # default, since it is what the marker meant before `kind` existed.
    kind = KIND_BLOCKED if str(data.get("kind") or "").strip() == KIND_BLOCKED else KIND_WRONG_DOMAIN
    return Handback(reason=reason, kind=kind)
