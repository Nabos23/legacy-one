import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from ai.multi_orchestration.supervisor.prompt import (
    SYNTHESIS_PROMPT,
    render_system_prompt,
)

logger = logging.getLogger(__name__)

# The Supervisor is hardcoded: not a document in the `agents` collection, so it
# cannot be created, renamed, or given tools. The id is deliberately not a valid
# ObjectId, so any path that tries to load it from Mongo misses rather than
# silently resolving to a real agent. It is also a persisted value — it appears
# as `execution_path.agent_id` on turns the Supervisor answered itself.
SUPERVISOR_AGENT_ID = "__supervisor__"
SUPERVISOR_AGENT_NAME = "Supervisor"

# Bounds on one supervisor-mode turn, used when a run has no stored config.
# backend.orchestration.schemas.SupervisorConfig is the operator-facing source
# of truth and declares the same defaults.
DEFAULT_MAX_HOPS = 6
DEFAULT_MAX_CONSECUTIVE_HANDBACKS = 2
DEFAULT_MAX_VISITS_PER_AGENT = 3

ROUTE = "route"
FINISH = "finish"

# Prefix for the per-agent routing functions offered to the model.
ROUTE_TOOL_PREFIX = "route_to_"

# Roster rendering budget, per field.
MAX_DESC_CHARS = 200
MAX_TOOL_DESC_CHARS = 100

# Candidate selection. At or below MAX_INLINE_CANDIDATES every agent is offered
# — the common case. Beyond it, candidates are ranked by relevance and trimmed
# to SHORTLIST_SIZE so routing cost stays flat however many agents are attached.
MAX_INLINE_CANDIDATES = 25
SHORTLIST_SIZE = 12

_WORD = re.compile(r"[a-z0-9]{3,}")
# Very common words carry no routing signal but match everything.
_STOPWORDS = frozenset(
    "the and for you your are can with that this what how many much have has "
    "was were will would should could from about into out get got tell show "
    "give please need want they them their our its all any some more most".split()
)


def _completion_with_retry(**kwargs):
    """LiteLLM call with the project's shared transient-error retry policy.

    Imported lazily on purpose: `ai.agents.loop` imports SupervisorHandbackException
    from this package to re-raise it, so importing the loop at module scope here
    would close an import cycle. Kept as a module-level name (rather than an
    inline import at each call site) so tests can patch it.
    """
    from ai.agents.loop import _completion_with_retry as _litellm_completion

    return _litellm_completion(**kwargs)


@dataclass
class RouteDecision:
    """What the Supervisor decided for one hop.

    action == ROUTE  -> run `target_agent_id` with `agent_input`
    action == FINISH -> reply to the user; `final_response` may be empty, in
                        which case the caller synthesizes from the run context.
    """

    action: str
    reason: str = ""
    target_agent_id: Optional[str] = None
    agent_input: str = ""
    final_response: str = ""

    @property
    def is_route(self) -> bool:
        return self.action == ROUTE


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return slug or "agent"


class SupervisorAgent:
    agent_id = SUPERVISOR_AGENT_ID
    name = SUPERVISOR_AGENT_NAME

    def __init__(
        self,
        model: str,
        instructions: str = "",
        allow_direct_answer: bool = True,
        max_inline: int = MAX_INLINE_CANDIDATES,
        shortlist_size: int = SHORTLIST_SIZE,
    ) -> None:
        self._model = model
        self._instructions = instructions or ""
        self._allow_direct_answer = allow_direct_answer
        self._max_inline = max_inline
        self._shortlist_size = shortlist_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(
        self,
        nodes: Iterable,
        message: str,
        excluded_agent_ids: Optional[List[str]] = None,
        completed_steps: Optional[List[dict]] = None,
        routing_history: Optional[List[dict]] = None,
        sticky_agent_id: Optional[str] = None,
        declined_agents: Optional[List[dict]] = None,
        force_assignment: bool = False,
    ) -> RouteDecision:
        """Pick the next agent for `message`, or finish the turn.

        `excluded_agent_ids` are agents that already handed this request back —
        they are not offered again, so a bounce cannot repeat. With nothing
        eligible left there is nothing to decide, so no LLM call is made.

        `declined_agents` carries *why* each of those declined. Passing only the
        ids meant re-routing was blind: two agents could each insist the request
        was the other's and the Supervisor had no way to see the contradiction.

        `force_assignment` is the deadlock escape: every agent has declined, so
        exclusions are dropped and the Supervisor must name the closest owner
        rather than leave the user with nothing.
        """
        if force_assignment:
            excluded_agent_ids = None
        candidates = self.build_candidates(nodes, message, excluded_agent_ids)
        if not candidates:
            logger.info(
                "[supervisor] no eligible candidates (%d excluded) — finishing",
                len(excluded_agent_ids or ()),
            )
            return RouteDecision(
                action=FINISH, reason="No connected agent can handle this request."
            )

        by_fn: Dict[str, object] = {}
        for node in candidates:
            fn = f"{ROUTE_TOOL_PREFIX}{_slugify(node.name)}"
            if fn in by_fn:  # display-name collision — disambiguate deterministically
                fn = f"{fn}_{node.agent_id[-6:]}"
            by_fn[fn] = node

        sticky_name = next(
            (n.name for n in candidates if n.agent_id == sticky_agent_id), ""
        ) if sticky_agent_id else ""

        user_content = message
        if completed_steps:
            # Make the finish-vs-continue choice explicit in the user turn —
            # relying only on the system progress block is too easy for the
            # model to ignore, which causes same-agent re-routing loops.
            user_content = (
                f"User request:\n{message}\n\n"
                "Work already completed this turn is listed in the system prompt. "
                "If it fully answers the request, do NOT call a function — "
                "reply with the final answer text (or empty). "
                "Only call a routing function for a distinct remaining part "
                "that has not been handled yet."
            )

        response = _completion_with_retry(
            model=self._model,
            messages=[
                {"role": "system", "content": render_system_prompt(
                    [self._agent_context(n) for n in candidates],
                    completed_steps,
                    self._instructions,
                    sticky_agent_name=sticky_name,
                    allow_direct_answer=self._allow_direct_answer,
                    declined_agents=declined_agents,
                    force_assignment=force_assignment,
                )},
                {"role": "user", "content": user_content},
            ],
            tools=[self._route_tool(fn, node) for fn, node in by_fn.items()],
            tool_choice="auto",
        )
        reply = response.choices[0].message

        for call in getattr(reply, "tool_calls", None) or []:
            node = by_fn.get(getattr(call.function, "name", ""))
            if node is None:
                logger.warning(
                    "[supervisor] model called unknown function %r — ignoring",
                    getattr(call.function, "name", ""),
                )
                continue
            args = self._parse_args(call.function.arguments)
            decision = RouteDecision(
                action=ROUTE,
                target_agent_id=node.agent_id,
                agent_input=(args.get("task") or "").strip() or message,
                reason=(args.get("reason") or "").strip(),
            )
            logger.info(
                "[supervisor] route -> %s (%s) of %d candidate(s): %s",
                node.name, node.agent_id, len(candidates),
                decision.reason or "no reason given",
            )
            return decision

        final = (getattr(reply, "content", "") or "").strip()
        logger.info(
            "[supervisor] finish after considering %d candidate(s) — %s",
            len(candidates), "direct answer" if final else "no answer text",
        )
        return RouteDecision(
            action=FINISH, final_response=final, reason="No agent matched the request."
        )

    def covers_a_specialist_domain(self, nodes: Iterable, message: str) -> bool:
        """True when `message` overlaps some agent's stated domain.

        Used to catch the Supervisor answering a specialist question itself. It
        has no tools and no data, so any such answer is a guess wearing an
        authoritative tone. The same term-overlap scoring that ranks candidates
        is a cheap, no-LLM signal: zero overlap across every agent means the
        message is small talk, anything above it deserves an agent.
        """
        tokens = self._tokenize(message)
        return any(self._score(node, tokens) > 0 for node in nodes)

    def synthesize(self, conversation_context: str) -> str:
        """Combine several agents' outputs into the single user-facing reply."""
        response = _completion_with_retry(
            model=self._model,
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {"role": "user", "content": conversation_context},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    def build_candidates(
        self,
        nodes: Iterable,
        message: str,
        excluded_agent_ids: Optional[List[str]] = None,
    ) -> List:
        """Which agents the Supervisor considers this hop.

        Small rosters go in whole, which is the common case. Past `max_inline`
        the prompt would bloat and the tool list would dilute, so candidates are
        ranked by lexical overlap with the request and trimmed — keeping routing
        cost flat regardless of how many agents are attached.

        Trimming is logged, never silent: a shortlist that drops the right agent
        must be diagnosable.
        """
        excluded = set(excluded_agent_ids or ())
        eligible = [n for n in nodes if n.agent_id not in excluded]
        if len(eligible) <= self._max_inline:
            return eligible

        tokens = self._tokenize(message)
        ranked = sorted(eligible, key=lambda n: (-self._score(n, tokens), n.name))
        shortlist = ranked[: self._shortlist_size]
        logger.warning(
            "[supervisor] %d eligible agents exceeds inline limit %d — "
            "routing over top %d by relevance: %s",
            len(eligible), self._max_inline, len(shortlist),
            [n.name for n in shortlist],
        )
        return shortlist

    # ------------------------------------------------------------------
    # Internal — agent context
    # ------------------------------------------------------------------

    def _agent_context(self, node) -> dict:
        """Everything the Supervisor knows about one agent, compactly.

        Connector and MCP tools collapse to their provider/server display names:
        an agent with 22 Gmail tools costs one entry ("Gmail") instead of 22,
        which is what keeps roster size independent of how many tools an agent
        owns. Plain tools are listed in full — truncating them hides the exact
        capability that should drive routing.
        """
        connector_owner = getattr(node, "connector_tool_owner", None) or {}
        mcp_owner = getattr(node, "mcp_tool_owner", None) or {}

        tools: List[dict] = []
        connectors: List[str] = []
        mcp_servers: List[str] = []

        for spec in node.tools or []:
            fn = spec.get("function") or {}
            name = fn.get("name") or ""
            if name in connector_owner:
                owner = connector_owner[name] or {}
                label = owner.get("display_name") or owner.get("provider_id")
                if label and label not in connectors:
                    connectors.append(label)
            elif name in mcp_owner:
                label = mcp_owner[name]
                if label and label not in mcp_servers:
                    mcp_servers.append(label)
            else:
                tools.append({
                    "name": name,
                    "description": (fn.get("description") or "")[:MAX_TOOL_DESC_CHARS],
                })

        context = {
            "id": node.agent_id,
            "name": node.name,
            "purpose": (getattr(node, "description", "") or "")[:MAX_DESC_CHARS],
            "instructions": (node.prompt or "")[:MAX_DESC_CHARS],
            "tools": tools,
            "connectors": connectors,
            "mcp_servers": mcp_servers,
        }
        # Optional enrichment — only included when the agent actually has it,
        # so the roster stays small for simple agents.
        extra = (getattr(node, "user_description", "") or "")[:MAX_DESC_CHARS]
        if extra:
            context["summary"] = extra
        guardrails = getattr(node, "guardrails", None) or []
        if guardrails:
            context["guardrails"] = [str(g)[:MAX_TOOL_DESC_CHARS] for g in guardrails]
        unavailable = getattr(node, "capability_load_errors", None) or []
        if unavailable:
            # Routing is still allowed: the reauth pause is the right handler for
            # an expired connector. The Supervisor just needs to know it is
            # degraded so the outcome is explicable.
            context["unavailable"] = unavailable
        return context

    @staticmethod
    def _route_tool(fn_name: str, node) -> dict:
        return {
            "type": "function",
            "function": {
                "name": fn_name,
                "description": f"Delegate this request to {node.name}.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The specific task this agent should carry out.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "One line on why this agent is the right choice.",
                        },
                    },
                    "required": ["task"],
                },
            },
        }

    @staticmethod
    def _parse_args(raw: Optional[str]) -> dict:
        try:
            parsed = json.loads(raw or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            logger.warning("[supervisor] unparseable tool arguments: %.200s", raw)
            return {}

    # ------------------------------------------------------------------
    # Internal — relevance scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> set:
        """Significant words, crudely singularised.

        The plural stripping matters more than it looks: without it "how many
        annual leaves" does not match an HR agent described in terms of "leave",
        and the shortlist silently drops the only correct agent. Full stemming
        is not worth a dependency here — a trailing "s" covers the common case.
        """
        words = set()
        for word in _WORD.findall((text or "").lower()):
            if word in _STOPWORDS:
                continue
            words.add(word[:-1] if len(word) > 3 and word.endswith("s") else word)
        return words

    @classmethod
    def _score(cls, node, tokens: set) -> int:
        """Weighted term overlap. Name and purpose describe what an agent is
        *for*, so they outrank a coincidental match on a tool description."""
        if not tokens:
            return 0
        strong = cls._tokenize(f"{node.name} {getattr(node, 'description', '')}")
        summary = cls._tokenize(getattr(node, "user_description", "") or "")
        weak = set()
        for spec in node.tools or []:
            fn = spec.get("function") or {}
            weak |= cls._tokenize(f"{fn.get('name', '')} {fn.get('description', '')}")
        for label in (getattr(node, "mcp_tool_owner", None) or {}).values():
            weak |= cls._tokenize(str(label))
        for owner in (getattr(node, "connector_tool_owner", None) or {}).values():
            weak |= cls._tokenize(str((owner or {}).get("display_name", "")))

        return (
            3 * len(tokens & strong)
            + 2 * len(tokens & summary)
            + 1 * len(tokens & weak)
        )
