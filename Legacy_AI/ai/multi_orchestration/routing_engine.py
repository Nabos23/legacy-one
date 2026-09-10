"""RoutingEngine — decides the next agent(s) after each node completes.

Three routing modes, evaluated in order:
  Mode C (agent-declared) — agent embeds {"next_agent": "<id>"} in its output
  Mode A (deterministic)  — exactly one outbound edge; no LLM needed
  Mode F (fan-out)        — multiple outbound edges; ALL successors are returned
                            so the scheduler runs them all (BFS fan-out)

Mode B (LLM-mediated single pick) has been removed: having edges to multiple
agents means "run all of them", not "let the LLM pick one". Use Mode C
(agent-declared) if you need conditional single-branch routing.
"""
import json
import logging
from typing import Dict, List

from ai.multi_orchestration.runtime_graph import RuntimeGraph

logger = logging.getLogger(__name__)


class RoutingEngine:
    def __init__(self, model: str):
        self._model = model  # kept for future use / Mode C LLM validation

    def decide_next(
        self,
        graph: RuntimeGraph,
        current_agent_id: str,
        agent_output: str,
        shared_context: str,
        original_task: str,
        loop_counters: Dict[str, int],
        max_visits: int = 3,
    ) -> List[str]:
        """
        Return the list of next agent_ids to run.
        Empty list means the orchestration is complete from this branch.

        - Single item  → advance to that agent (Modes A and C)
        - Multiple items → fan-out: the scheduler queues all of them (Mode F)
        """
        raw_candidates = graph.adjacency.get(current_agent_id, [])

        # Filter out agents that have hit their visit ceiling
        candidates = [
            c for c in raw_candidates
            if loop_counters.get(c, 0) < max_visits and c in graph.nodes
        ]

        if not candidates:
            logger.info("[routing] no eligible next agents from %s — complete", current_agent_id)
            return []

        # Mode C: agent-declared routing — pick the one the agent requested
        declared = self._extract_declared(agent_output, candidates)
        if declared:
            logger.info("[routing] agent-declared → %s", declared)
            return [declared]

        # Mode A: deterministic (single outbound edge)
        if len(candidates) == 1:
            logger.info("[routing] deterministic → %s", candidates[0])
            return candidates[0:1]

        # Mode F: fan-out — multiple outbound edges, run them all
        names = [graph.nodes[c].name for c in candidates if c in graph.nodes]
        logger.info("[routing] fan-out → %s (%s)", candidates, names)
        return candidates

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_declared(self, output: str, candidates: List[str]) -> str:
        """Look for a routing signal embedded by the agent in its output."""
        try:
            idx = output.rfind('{"next_agent"')
            if idx == -1:
                return ""
            data = json.loads(output[idx:idx + 300])
            declared_id = data.get("next_agent", "")
            if declared_id in candidates:
                return declared_id
        except Exception:
            pass
        return ""
