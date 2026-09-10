"""RuntimeScheduler — BFS driver for one orchestration run.

Owns every state transition:
    LOADING → RUNNING → ROUTING → RUNNING → ... → COMPLETE / FAILED / TIMEOUT

Fan-out: when a node has multiple outbound edges, ALL successors are run in
parallel using a ThreadPoolExecutor. Each branch gets the same fork-point
context snapshot and writes are protected by a lock on the MemoryBus.

HITL: any agent can call the ask_human tool to pause execution. The BFS queue
is serialized to MongoDB, status is set to WAITING_FOR_HUMAN, and the run
resumes via the /resume endpoint.

All state lives in MongoDB (orchestration_runs collection).
"""
import json
import logging
import threading
from collections import deque
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.db.constants import ORCHESTRATION_RUNS_COLLECTION
from ai.connectors.reauth_interrupt import ConnectorReauthException
from ai.multi_orchestration.agent_invoker import AgentInvoker
from ai.multi_orchestration.memory_bus import MemoryBus
from ai.multi_orchestration.models import HumanInterruptException, RunStatus, ToolInvocationRecord, TERMINAL_STATUSES
from ai.multi_orchestration.routing_engine import RoutingEngine
from ai.multi_orchestration.run_context import RunContext
from ai.multi_orchestration.supervisor import (
    FINISH,
    FORCED_ASSIGNMENT_NOTE,
    KIND_BLOCKED,
    SUPERVISOR_AGENT_ID,
    SUPERVISOR_AGENT_NAME,
    Handback,
    RouteDecision,
    SupervisorAgent,
    SupervisorHandbackException,
    extract_handback,
)

logger = logging.getLogger(__name__)

_MAX_AGENT_RETRIES = 2
_MAX_PARALLEL_BRANCHES = 8


class RuntimeScheduler:
    def __init__(self, ctx: RunContext, model: str):
        self._ctx = ctx
        self._invoker = AgentInvoker(model)
        self._router = RoutingEngine(model)  # sequential mode: edge-driven
        self._join_lock = threading.Lock()
        # Supervisor mode: dynamic routing. Built lazily via `_supervisor` so a
        # sequential run never constructs one.
        self._model = model
        self._supervisor_agent: Optional[SupervisorAgent] = None

    @property
    def _supervisor(self) -> SupervisorAgent:
        if self._supervisor_agent is None:
            self._supervisor_agent = SupervisorAgent(
                self._model,
                instructions=self._ctx.runtime_graph.supervisor_instructions,
                allow_direct_answer=self._ctx.runtime_graph.supervisor_allow_direct_answer,
            )
        return self._supervisor_agent

    def run(
        self,
        entry_message: str,
        initial_queue: Optional[List[str]] = None,
        resumed: bool = False,
    ) -> str:
        """
        Drive the orchestration from start (or resume point) to finish.

        initial_queue: when provided (HITL resume), start BFS from these agent IDs
                       instead of the graph's main_agent_id. In supervisor mode it
                       is the sticky candidate — the agent that handled the last
                       turn, tried first so an on-topic follow-up costs no routing
                       call.
        """
        if self._ctx.runtime_graph.is_supervised:
            return self._run_supervised(entry_message, initial_queue, resumed=resumed)

        db = self._ctx.sync_db
        run_col = db[ORCHESTRATION_RUNS_COLLECTION]
        graph = self._ctx.runtime_graph
        memory_bus: MemoryBus = self._ctx.memory_bus

        self._set_status(run_col, RunStatus.RUNNING)

        # Append the new user message on a fresh start (initial_queue is None).
        # On HITL resume the message is already in the log and the human answer
        # has been injected, so we must not append it again. The log may already
        # be non-empty on a fresh start too, when it was seeded with prior-run
        # context from the same session (see executor session-scoped seeding).
        if initial_queue is None:
            memory_bus.append_user(entry_message) #writing to the new conversation collection
            memory_bus.write_user_input(entry_message) #writing to the memory bus
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {"$set": memory_bus.flush_to_run_doc()},
            )

        start_ids = initial_queue if initial_queue else [graph.main_agent_id]
        pending: deque[str] = deque(start_ids)
        retry_counts: dict = {}
        # Each entry is (output_text, tools_called_count) so trivial branches can be filtered
        terminal_outputs: list = []
        failed = False
        step_num: int = 0  # monotonically increasing node execution counter

        while pending and not failed:

            logger.info(
                "[scheduler] pending=%s",
                list(pending),
            )

            if not pending:
                break
                
            current_agent_id = pending.popleft()

            run_doc = run_col.find_one({"run_id": self._ctx.run_id}) or {}
            loop_counters: dict = run_doc.get("loop_counters", {})

            # ── Guard: per-agent visit cap ──────────────────────────────
            # This is the real runaway guard. The graph is acyclic (validated at
            # creation) so BFS terminates on its own; this only bounds repeat
            # visits to a single agent (e.g. from diamond re-convergence). The
            # whole run is also bounded by timeout_sec. There is no global depth
            # guard: it conflated total invocations (incl. parallel branches and
            # HITL resumes) with graph depth and killed legitimate runs.
            if loop_counters.get(current_agent_id, 0) >= graph.max_visits_per_agent:
                logger.warning("[scheduler] visit cap hit for agent %s", current_agent_id)
                self._fail(run_col, current_agent_id, "LoopLimitExceeded",
                           f"Agent {current_agent_id} reached max visits ({graph.max_visits_per_agent})", 0)
                failed = True
                terminal_outputs.append(("Orchestration stopped: an agent was called too many times in a loop.", 0))
                break

            node = graph.nodes.get(current_agent_id)
            if not node:
                logger.error("[scheduler] agent %s not in graph", current_agent_id)
                self._fail(run_col, current_agent_id, "NodeNotFound",
                           f"Agent {current_agent_id} missing from graph", 0)
                failed = True
                break

            # Memory is the single source of context: the entire log, verbatim.
            agent_input = memory_bus.get_context()

            step_start = datetime.now(timezone.utc)
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {
                    "$inc": {
                        f"loop_counters.{current_agent_id}": 1,
                    },
                    # Live position for the UI: which agent is executing right now.
                    "$set": {
                        "current_agent_id": current_agent_id,
                        "current_agent_name": node.name,
                    },
                },
            )

            # ── Invoke ──────────────────────────────────────────────────
            try:
                output, tool_records = self._invoker.invoke(node, agent_input, unattended=getattr(self._ctx, 'unattended', False))
                retry_counts.pop(current_agent_id, None)

            except HumanInterruptException as hitl:
                if getattr(self._ctx, "unattended", False):
                    logger.info("[scheduler] unattended run ignoring HITL interrupt for %s — proceeding", current_agent_id)
                    output = f"Unattended execution note: {hitl.question}"
                    tool_records = []
                else:
                    # Agent called ask_human — pause the run and save BFS state.
                    # Undo the loop counter increment: HITL pauses are not BFS cycles
                    # and should not count against max_visits_per_agent.
                    remaining = [current_agent_id] + list(pending)
                    memory_bus.write_hitl_question(node.name, hitl.question)
                    mem_flush = memory_bus.flush_to_run_doc()
                    run_col.update_one(
                        {"run_id": self._ctx.run_id},
                        {
                            "$set": {
                                "status": RunStatus.WAITING_FOR_HUMAN.value,
                                "human_question": hitl.question,
                                "human_asked_by_agent": current_agent_id,
                                "pending_agents": remaining,
                                **mem_flush,
                            },
                            "$inc": {
                                f"loop_counters.{current_agent_id}": -1,
                            },
                        },
                    )
                    logger.info(
                        "[scheduler] HITL pause — run_id=%s agent=%s question=%.100s",
                        self._ctx.run_id, current_agent_id, hitl.question,
                    )
                    return f"__HITL__:{hitl.question}"

            except ConnectorReauthException as reauth:
                # Tool call failed on expired/invalid connector auth — pause the
                # run exactly like a HITL question, but store connector identity
                # instead of a question so the frontend can render a reconnect
                # action. Resume works the same way once the connector is fixed.
                remaining = [current_agent_id] + list(pending)
                run_col.update_one(
                    {"run_id": self._ctx.run_id},
                    {
                        "$set": {
                            "status": RunStatus.WAITING_FOR_REAUTH.value,
                            "pending_reauth": reauth.to_dict(),
                            "pending_agents": remaining,
                        },
                        "$inc": {
                            f"loop_counters.{current_agent_id}": -1,
                        },
                    },
                )
                logger.info(
                    "[scheduler] reauth pause — run_id=%s agent=%s connector=%s",
                    self._ctx.run_id, current_agent_id, reauth.display_name,
                )
                return f"__REAUTH__:{reauth.display_name}"

            except Exception as exc:
                retries = retry_counts.get(current_agent_id, 0)
                if retries < _MAX_AGENT_RETRIES:
                    retry_counts[current_agent_id] = retries + 1
                    logger.warning(
                        "[scheduler] agent %s failed (attempt %d/%d): %s",
                        current_agent_id, retries + 1, _MAX_AGENT_RETRIES, exc,
                    )
                    pending.appendleft(current_agent_id)
                    continue
                logger.error("[scheduler] agent %s failed after %d retries: %s", current_agent_id, retries, exc)
                self._fail(run_col, current_agent_id, type(exc).__name__, str(exc), retries)
                terminal_outputs.append((f"Agent '{node.name}' failed after {retries} retries: {exc}", 0))
                failed = True
                break

            # ── Deterministic HITL net ──────────────────────────────────
            # An agent that finished WITHOUT calling any tool neither performed
            # its action nor asked for input — it just emitted prose (or empty
            # text). Never pass that silently downstream: convert it into a HITL
            # pause so the run stops and asks the human. Generic — applies to any
            # agent in any graph, no hardcoded roles.
            if not tool_records:
                question = self._no_tool_hitl_question(node, output)
                memory_bus.write_hitl_question(node.name, question)
                remaining = [current_agent_id] + list(pending)
                mem_flush = memory_bus.flush_to_run_doc()
                run_col.update_one(
                    {"run_id": self._ctx.run_id},
                    {
                        "$set": {
                            "status": RunStatus.WAITING_FOR_HUMAN.value,
                            "human_question": question,
                            "human_asked_by_agent": current_agent_id,
                            "pending_agents": remaining,
                            **mem_flush,
                        },
                        "$inc": {f"loop_counters.{current_agent_id}": -1},
                    },
                )
                logger.info(
                    "[scheduler] no-tool turn by %s → auto HITL — question=%.100s",
                    current_agent_id, question,
                )
                return f"__HITL__:{question}"

            # ── Persist turn ────────────────────────────────────────────
            step_num += 1
            tools_called = [r.tool_name for r in tool_records]  #saving tools used in a conversation turn by agent
            memory_bus.write_orchestration_turn(node.name, step_num, tools_called, output)
            memory_bus.append_agent(node.name, output)

            path_entry = {
                "agent_id": current_agent_id,
                "agent_name": node.name,
                "input_summary": agent_input[:300],
                "output_summary": output[:300],
                "output": output,  # full output, surfaced per-step to the UI
                "tool_invocations": [_serialize_tool(t) for t in tool_records],
                "started_at": step_start,
                "ended_at": datetime.now(timezone.utc),
                "status": "complete",
                "branch_id": "main",
            }
            mem_flush = memory_bus.flush_to_run_doc()
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {
                    "$push": {"execution_path": path_entry},
                    "$set": {"status": RunStatus.ROUTING.value, **mem_flush},
                },
            )

            # ── Route ───────────────────────────────────────────────────
            next_ids = self._router.decide_next(
                graph=graph,
                current_agent_id=current_agent_id,
                agent_output=output,
                shared_context="",
                original_task=entry_message,
                loop_counters={**loop_counters, current_agent_id: loop_counters.get(current_agent_id, 0) + 1},
                max_visits=graph.max_visits_per_agent,
            )

            routing_entry = {
                "from_agent_id": current_agent_id,
                "to_agent_ids": next_ids,
                "fan_out": len(next_ids) > 1,
                "reason": "no_next" if not next_ids else ("fan-out" if len(next_ids) > 1 else "routed"),
                "timestamp": datetime.now(timezone.utc),
            }
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {"$push": {"routing_history": routing_entry}},
            )

            if not next_ids:
                terminal_outputs.append((output, len(tool_records)))
                logger.info("[scheduler] terminal node %s — %d still pending", current_agent_id, len(pending))

            elif len(next_ids) == 1:
                nid = next_ids[0]

                if nid in graph.join_points:
                    join_ready = self._record_join_arrival(run_col, graph, nid, current_agent_id)
                    if join_ready:
                        pending.append(nid)
                    else:
                        logger.info("[scheduler] %s reached join point %s — waiting on sibling(s)", current_agent_id, nid)

                else:
                    pending.append(nid)
            else:
                # Fan-out: run all branches in parallel
                logger.info("[scheduler] fan-out — spawning %d parallel branches", len(next_ids))
                branch_terminals = self._run_parallel_branches(next_ids, entry_message, run_col, arriving_from=current_agent_id)

                # Check if any branch triggered HITL or a connector reauth pause
                hitl_questions = [t for t in branch_terminals if isinstance(t, str) and t.startswith("__HITL__:")]
                if hitl_questions:
                    # A branch hit HITL — status already set, return the question
                    return hitl_questions[0]
                reauth_signals = [t for t in branch_terminals if isinstance(t, str) and t.startswith("__REAUTH__:")]
                if reauth_signals:
                    # A branch hit a connector reauth pause — status already set
                    return reauth_signals[0]

                self._set_status(run_col, RunStatus.RUNNING)

        # ── Build final response ─────────────────────────────────────────
        if terminal_outputs:
            # Filter out trivial branches: no tools called AND short output (e.g. "connector not active")
            _TRIVIAL_THRESHOLD = 300
            meaningful = [(out, tc) for out, tc in terminal_outputs if tc > 0 or len(out) > _TRIVIAL_THRESHOLD]
            if not meaningful:
                meaningful = terminal_outputs  # all were trivial — show something

            if len(meaningful) == 1:
                final_response = meaningful[0][0]
            else:
                parts = [f"[{i+1}] {out}" for i, (out, _) in enumerate(meaningful)]
                final_response = "\n\n---\n\n".join(parts)
        else:
            final_response = self._aggregate_branch_outputs(run_col) if hasattr(self, '_aggregate_branch_outputs') else "The orchestration completed without a final response."

        if not failed:
            self._set_status(run_col, RunStatus.COMPLETE, final_response=final_response)
            logger.info(
                "[scheduler] complete — run_id=%s  terminal_nodes=%d",
                self._ctx.run_id, len(terminal_outputs),
            )

        return final_response

    # ------------------------------------------------------------------
    # Supervisor mode
    # ------------------------------------------------------------------

    def _run_supervised(
        self,
        entry_message: str,
        initial_queue: Optional[List[str]] = None,
        resumed: bool = False,
    ) -> str:
        """Drive one supervisor-mode turn: route → run an agent → return to the
        Supervisor → repeat until it finishes.

        `initial_queue` is a soft sticky preference (the agent that handled the
        last turn). It is passed to the Supervisor as a continuity hint on the
        first routing call — not hard-invoked — so a domain shift (time → HR)
        is re-routed instead of answered by the wrong specialist. Nothing here
        consults `adjacency` — supervisor-mode graphs have no edges.
        """
        graph = self._ctx.runtime_graph
        memory_bus: MemoryBus = self._ctx.memory_bus
        run_col = self._ctx.sync_db[ORCHESTRATION_RUNS_COLLECTION]

        self._set_status(run_col, RunStatus.RUNNING)

        if not resumed:
            memory_bus.append_user(entry_message)
            memory_bus.write_user_input(entry_message)
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {"$set": memory_bus.flush_to_run_doc()},
            )

        # Soft sticky: remember who handled the last turn as a *hint* for the
        # first routing call, but do NOT skip the Supervisor. Hard-invoking the
        # sticky agent made Time Trace answer HR follow-ups (shared query_db)
        # instead of handing back — the Supervisor must pick the domain.
        sticky_agent_id: Optional[str] = next(
            (a for a in (initial_queue or []) if a in graph.nodes), None,
        )
        if sticky_agent_id:
            logger.info(
                "[scheduler:supervisor] sticky preference (soft) — agent=%s",
                sticky_agent_id,
            )
        pending: List[str] = []
        assignment = ""
        handed_back: List[str] = []
        # Why each agent declined. Passing only the ids left the Supervisor
        # blind: two agents can each insist the request is the other's, and
        # without the reasons it cannot see the contradiction.
        declined: List[dict] = []
        # The deadlock escape may be used once per turn.
        forced_agent_id: Optional[str] = None
        forced_used = False
        completed: List[dict] = []
        last_output = ""
        consecutive_handbacks = 0
        step_num = 0
        # Agents that already produced a successful answer this turn. Re-routing
        # the *same* agent for micro-refinements is almost always churn — that
        # agent already ran a full tool loop. Same-agent revisit is still allowed
        # once more (e.g. "email Alice, then Bob") but a third hit finishes.
        completed_agent_ids: List[str] = []

        for hop in range(graph.supervisor_max_hops):
            if not pending:
                # Surface the Supervisor as the live position so the UI's
                # existing "<agent> is working" indicator reads "Supervisor"
                # while it routes — no frontend special-casing needed.
                run_col.update_one(
                    {"run_id": self._ctx.run_id},
                    {"$set": {
                        "status": RunStatus.ROUTING.value,
                        "current_agent_id": SUPERVISOR_AGENT_ID,
                        "current_agent_name": SUPERVISOR_AGENT_NAME,
                    }},
                )
                decision = self._supervisor.decide(
                    nodes=graph.nodes.values(),
                    message=entry_message,
                    excluded_agent_ids=handed_back,
                    completed_steps=completed,
                    routing_history=(run_col.find_one({"run_id": self._ctx.run_id}) or {}).get(
                        "routing_history", []
                    ),
                    sticky_agent_id=sticky_agent_id,
                    declined_agents=declined,
                )
                # Continuity hint applies only to the first decide of the turn.
                sticky_agent_id = None
                self._record_routing(run_col, decision, len(graph.nodes), handed_back)

                if not decision.is_route:
                    # Guard against the Supervisor answering a specialist
                    # question itself. It has no tools and no data, so such an
                    # answer is a guess in an authoritative voice. Only worth
                    # re-asking when nothing has run yet and the request
                    # actually overlaps someone's domain — greetings and small
                    # talk score zero and pass straight through.
                    if (
                        not completed
                        and not forced_used
                        and self._supervisor.covers_a_specialist_domain(
                            graph.nodes.values(), entry_message
                        )
                    ):
                        forced_used = True
                        decision = self._commit_route(
                            run_col, graph, entry_message, completed, declined, handed_back,
                            "answered a request matching an agent's domain itself",
                        )
                    if not decision.is_route:
                        return self._finish_supervised(
                            run_col, decision, completed, last_output, step_num
                        )
                if decision.target_agent_id not in graph.nodes:
                    # Stale or deleted agent id.
                    return self._report_supervised(
                        run_col,
                        "I tried to hand this to an agent that is no longer part of this "
                        "orchestration. Please re-open it and try again.",
                        completed, last_output, step_num,
                        agent_id=decision.target_agent_id, error_type="NodeNotFound",
                        detail=f"Agent {decision.target_agent_id} is not in the graph",
                    )
                # Same agent already answered twice this turn → finish. One
                # revisit covers legitimate multi-action cases (two emails);
                # further hops are the churn pattern that floods the chat.
                same_hits = completed_agent_ids.count(decision.target_agent_id)
                if same_hits >= 2 and completed:
                    logger.warning(
                        "[scheduler:supervisor] refusing third visit to %s this turn — finishing",
                        decision.target_agent_id,
                    )
                    return self._finish_supervised(
                        run_col,
                        RouteDecision(action=FINISH, reason="same-agent revisit limit"),
                        completed, last_output, step_num,
                    )
                pending = [decision.target_agent_id]
                assignment = decision.agent_input

            current_agent_id = pending.pop(0)
            node = graph.nodes[current_agent_id]

            run_doc = run_col.find_one({"run_id": self._ctx.run_id}) or {}
            if run_doc.get("loop_counters", {}).get(current_agent_id, 0) >= graph.max_visits_per_agent:
                # Hitting a bound is not a reason to throw away work already
                # done — answer with what we have and only fail when there is
                # nothing to report.
                if completed:
                    logger.warning(
                        "[scheduler:supervisor] visit cap reached for %s — finishing with %d completed step(s)",
                        node.name, len(completed),
                    )
                    return self._finish_supervised(
                        run_col, RouteDecision(action=FINISH, reason="visit limit reached"),
                        completed, last_output, step_num,
                    )
                return self._report_supervised(
                    run_col,
                    f"I kept coming back to {node.name} without making progress on this, "
                    "so I've stopped. Could you rephrase what you need?",
                    completed, last_output, step_num,
                    agent_id=current_agent_id, error_type="SupervisorVisitLimitExceeded",
                    detail=f"{node.name} hit the per-turn visit cap",
                )

            # Prior turns go in as real chat history, and only this hop's job
            # goes in as the task. Passing the rendered "[name]: content" log as
            # the task instead made agents treat it as a document — a Gmail agent
            # asked to send "this" pasted the internal [user]/[Supervisor] tags
            # into a real email.
            history = memory_bus.get_messages()
            agent_input = assignment or entry_message
            is_forced = current_agent_id == forced_agent_id
            if is_forced:
                agent_input += FORCED_ASSIGNMENT_NOTE
                # Applies to this one invocation only — a later, legitimate
                # visit to the same agent must be free to decline again.
                forced_agent_id = None
            assignment = ""

            step_start = datetime.now(timezone.utc)
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {
                    "$inc": {f"loop_counters.{current_agent_id}": 1},
                    "$set": {"current_agent_id": current_agent_id, "current_agent_name": node.name},
                },
            )

            handback: Optional[Handback] = None
            try:
                output, tool_records = self._invoker.invoke(node, agent_input, history=history)
            except SupervisorHandbackException as raised:
                handback, output, tool_records = raised.to_handback(), "", []
            except HumanInterruptException as hitl:
                return self._pause_supervised(
                    run_col, current_agent_id, node,
                    status=RunStatus.WAITING_FOR_HUMAN,
                    question=hitl.question,
                )
            except ConnectorReauthException as reauth:
                return self._pause_supervised(
                    run_col, current_agent_id, node,
                    status=RunStatus.WAITING_FOR_REAUTH,
                    reauth=reauth.to_dict(),
                )
            except Exception as exc:  # noqa: BLE001 — one agent must not kill the run silently
                return self._report_supervised(
                    run_col,
                    f"{node.name} ran into an error and couldn't finish this: {exc}",
                    completed, last_output, step_num,
                    agent_id=current_agent_id, error_type=type(exc).__name__, detail=str(exc),
                )

            if handback is None:
                handback = extract_handback(output)

            if handback and is_forced:
                # It was told not to decline and did anyway. Re-routing would
                # restart the deadlock, so report it as a blocked step: the user
                # gets a real explanation instead of silence.
                logger.warning(
                    "[scheduler:supervisor] forced agent %s still declined — reporting",
                    node.name,
                )
                handback = Handback(reason=handback.reason, kind=KIND_BLOCKED)

            if handback and handback.is_blocked:
                # The right agent, blocked by its own tools. Excluding it would
                # disqualify the only owner of this data and let the Supervisor
                # hand the request to an unrelated agent, which then answers
                # from the wrong source. Record the failure as this agent's
                # result and let the Supervisor report it honestly.
                blocked_note = (
                    f"{node.name} could not complete this: {handback.reason}"
                )
                logger.warning(
                    "[scheduler:supervisor] hop %d — %s blocked: %s",
                    hop, node.name, handback.reason,
                )
                step_num += 1
                memory_bus.write_orchestration_turn(
                    node.name, step_num, [r.tool_name for r in tool_records], blocked_note
                )
                memory_bus.append_agent(node.name, blocked_note)
                self._record_blocked(run_col, node, blocked_note, step_start, tool_records, memory_bus)
                completed.append({"agent": node.name, "result": blocked_note[:200], "failed": True})
                completed_agent_ids.append(current_agent_id)
                last_output = blocked_note
                consecutive_handbacks = 0
                pending = []
                continue

            if handback:
                consecutive_handbacks += 1
                handed_back.append(current_agent_id)
                self._record_handback(run_col, node, handback.reason, step_start)
                logger.info(
                    "[scheduler:supervisor] hop %d — %s handed back: %s",
                    hop, node.name, handback.reason,
                )
                # `>=`, not `>`: max_consecutive_handbacks=2 means stop at the
                # second decline. Allowing a third attempt is what let a DB
                # question reach an email agent after two specialists declined.
                declined.append({"agent": node.name, "reason": handback.reason})

                if consecutive_handbacks >= graph.supervisor_max_consecutive_handbacks:
                    if completed:
                        return self._finish_supervised(
                            run_col, RouteDecision(action=FINISH, reason="no agent could take the rest"),
                            completed, last_output, step_num,
                        )
                    if not forced_used:
                        # Deadlock escape. Agents can decline in mirror image —
                        # "that's HR's", "that's time-tracking's" — over a
                        # request the system can actually answer. Failing here
                        # leaves the user with nothing, so make the Supervisor
                        # commit: exclusions are dropped, it sees every decline
                        # and its reason, and it must name the closest owner.
                        forced_used = True
                        forced = self._commit_route(
                            run_col, graph, entry_message, completed, declined, handed_back,
                            f"deadlock after {len(declined)} decline(s)",
                        )
                        if forced.is_route and forced.target_agent_id in graph.nodes:
                            forced_agent_id = forced.target_agent_id
                            pending = [forced_agent_id]
                            assignment = forced.agent_input
                            consecutive_handbacks = 0
                            continue
                        return self._finish_supervised(
                            run_col, forced, completed, last_output, step_num,
                        )
                    names = ", ".join(d["agent"] for d in declined) or "the connected agents"
                    return self._report_supervised(
                        run_col,
                        f"I couldn't find the right agent for this — {names} each said it "
                        "falls outside their area. Could you tell me a bit more about what "
                        "you're after, or which agent should handle it?",
                        completed, last_output, step_num,
                        agent_id=current_agent_id, error_type="SupervisorBounceLimitExceeded",
                        detail=f"{consecutive_handbacks} consecutive declines",
                    )
                pending = []
                continue

            # A repeat visit that called no tools produced no new work — it is
            # the churn pattern, not progress. Stop rather than burn another hop.
            if not tool_records and current_agent_id in completed_agent_ids:
                logger.warning(
                    "[scheduler:supervisor] hop %d — %s revisited with no tool calls — finishing",
                    hop, node.name,
                )
                return self._finish_supervised(
                    run_col, RouteDecision(action=FINISH, reason="no further progress"),
                    completed, last_output, step_num,
                )

            # Progress made: earlier refusals were recorded before this output
            # existed, so they are stale — an agent may be needed again now.
            consecutive_handbacks = 0
            handed_back.clear()
            declined.clear()

            step_num += 1
            memory_bus.write_orchestration_turn(
                node.name, step_num, [r.tool_name for r in tool_records], output
            )
            memory_bus.append_agent(node.name, output)
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {
                    "$push": {"execution_path": {
                        "agent_id": current_agent_id,
                        "agent_name": node.name,
                        "input_summary": agent_input[:300],
                        "output_summary": output[:300],
                        "output": output,
                        "tool_invocations": [_serialize_tool(t) for t in tool_records],
                        "started_at": step_start,
                        "ended_at": datetime.now(timezone.utc),
                        "status": "complete",
                        "branch_id": None,
                    }},
                    "$set": {"status": RunStatus.RUNNING.value, **memory_bus.flush_to_run_doc()},
                },
            )
            # Keep enough of the answer that the next routing call can tell the
            # request is already satisfied (200 chars often truncates mid-summary).
            completed.append({"agent": node.name, "result": output[:800]})
            completed_agent_ids.append(current_agent_id)
            last_output = output
            logger.info("[scheduler:supervisor] hop %d — %s completed", hop, node.name)
            pending = []

        if completed:
            logger.warning(
                "[scheduler:supervisor] hop limit (%d) reached — finishing with %d completed step(s)",
                graph.supervisor_max_hops, len(completed),
            )
            return self._finish_supervised(
                run_col, RouteDecision(action=FINISH, reason="hop limit reached"),
                completed, last_output, step_num,
            )
        return self._report_supervised(
            run_col,
            "This request took more steps than I'm allowed in one turn without reaching "
            "an answer. Could you break it into smaller parts?",
            completed, last_output, step_num,
            error_type="SupervisorHopLimitExceeded",
            detail=f"exceeded {graph.supervisor_max_hops} hops",
        )

    def _commit_route(
        self, run_col, graph, message: str, completed: List[dict],
        declined: List[dict], handed_back: List[str], why: str,
    ) -> RouteDecision:
        """Make the Supervisor commit to an agent rather than leave the user empty.

        Used for the two cases where finishing is not an acceptable answer: it
        tried to answer a specialist question itself, or every agent declined.
        Exclusions are dropped and the decline reasons go in, so it chooses
        with the full picture.
        """
        logger.warning("[scheduler:supervisor] %s — requiring a routing decision", why)
        decision = self._supervisor.decide(
            nodes=graph.nodes.values(), message=message, completed_steps=completed,
            declined_agents=declined or None, force_assignment=True,
        )
        self._record_routing(run_col, decision, len(graph.nodes), handed_back)
        return decision

    def _report_supervised(
        self, run_col, note: str, completed: List[dict], last_output: str, step_num: int,
        *, agent_id: Optional[str] = None, error_type: str = "", detail: str = "",
    ) -> str:
        """End the turn with an explanation instead of a failed run.

        The Supervisor's job is to manage the agents, so when management itself
        runs out of road — nobody will take the request, an agent errored, a
        bound was hit — the user should still get a sentence telling them what
        happened. A FAILED run with no message is the one outcome that helps
        nobody.

        `error_context` is still written when there was a real error, so logs
        and ops tooling keep the diagnostic; only the user-facing outcome
        changes.
        """
        if error_type:
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {"$set": {"error_context": {
                    "agent_id": agent_id,
                    "error_type": error_type,
                    "message": detail or note,
                    "retry_count": 0,
                    "timestamp": datetime.now(timezone.utc),
                }}},
            )
            logger.error(
                "[scheduler:supervisor] %s — reporting to the user: %s", error_type, note,
            )
        return self._finish_supervised(
            run_col, RouteDecision(action=FINISH, final_response=note),
            completed, last_output, step_num,
        )

    def _finish_supervised(
        self, run_col, decision, completed: List[dict], last_output: str, step_num: int
    ) -> str:
        """Close the turn. Several agents contributed → synthesize; one agent →
        return its answer verbatim (no cost, no paraphrase risk); none → the
        Supervisor's own reply."""
        memory_bus: MemoryBus = self._ctx.memory_bus

        # Synthesis is for combining *different* specialists. Counting steps
        # instead of agents made a single agent called twice trigger a synthesis
        # of its own two answers.
        distinct_agents = len({step["agent"] for step in completed})
        if distinct_agents > 1:
            # Prefer an explicit supervisor closing line when it already wrote one;
            # otherwise synthesize. Either way one Supervisor bubble is the
            # user-facing answer on top of the per-agent steps already logged.
            final = (decision.final_response
                     or self._supervisor.synthesize(memory_bus.get_context())
                     or last_output)
            by_supervisor = True
        elif last_output:
            # Single specialist already answered and that turn is in the
            # transcript — never publish a Supervisor paraphrase of the same
            # content (that was the "answered twice" bug).
            final = last_output
            by_supervisor = False
        elif decision.final_response:
            # No agent ran; Supervisor answered directly (or declined).
            final = decision.final_response
            by_supervisor = True
        else:
            final = decision.reason or "I couldn't determine which agent should handle that."
            by_supervisor = True

        if by_supervisor:
            # Persist the Supervisor's own words, otherwise a turn it answered
            # directly leaves the chat UI with nothing to render.
            memory_bus.append_agent(SUPERVISOR_AGENT_NAME, final)
            memory_bus.write_orchestration_turn(SUPERVISOR_AGENT_NAME, step_num + 1, [], final)
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {
                    "$push": {"execution_path": {
                        "agent_id": SUPERVISOR_AGENT_ID,
                        "agent_name": SUPERVISOR_AGENT_NAME,
                        "input_summary": "",
                        "output_summary": final[:300],
                        "output": final,
                        "tool_invocations": [],
                        "started_at": datetime.now(timezone.utc),
                        "ended_at": datetime.now(timezone.utc),
                        "status": "complete",
                        "branch_id": None,
                    }},
                    "$set": memory_bus.flush_to_run_doc(),
                },
            )

        self._set_status(run_col, RunStatus.COMPLETE, final_response=final)
        logger.info(
            "[scheduler:supervisor] complete — run_id=%s agents_used=%d synthesized=%s",
            self._ctx.run_id, len(completed), by_supervisor and len(completed) > 1,
        )
        return final

    def _pause_supervised(
        self, run_col, agent_id: str, node, *, status: RunStatus,
        question: str = "", reauth: Optional[dict] = None,
    ) -> str:
        """Suspend the turn for human input or a connector reconnect. The paused
        agent is stored as pending so the resume goes straight back to it —
        a human's answer must never be re-routed — and `pending_supervisor`
        marks that control returns to the Supervisor once it finishes."""
        memory_bus: MemoryBus = self._ctx.memory_bus
        update: dict = {
            "status": status.value,
            "pending_agents": [agent_id],
            "pending_supervisor": True,
        }
        if question:
            memory_bus.write_hitl_question(node.name, question)
            update.update({
                "human_question": question,
                "human_asked_by_agent": agent_id,
                **memory_bus.flush_to_run_doc(),
            })
        if reauth:
            update["pending_reauth"] = reauth

        run_col.update_one({"run_id": self._ctx.run_id}, {"$set": update})
        logger.info(
            "[scheduler:supervisor] pause (%s) — agent=%s run_id=%s",
            status.value, node.name, self._ctx.run_id,
        )
        return f"__HITL__:{question}" if question else f"__REAUTH__:{(reauth or {}).get('display_name', '')}"

    def _record_routing(self, run_col, decision, total_agents: int, excluded: List[str]) -> None:
        """Append the decision to routing_history — the queryable audit trail of
        why each agent was chosen."""
        run_col.update_one(
            {"run_id": self._ctx.run_id},
            {"$push": {"routing_history": {
                "from_agent_id": SUPERVISOR_AGENT_ID,
                "to_agent_ids": [decision.target_agent_id] if decision.is_route else [],
                "fan_out": False,
                "reason": decision.reason or decision.action,
                "action": decision.action,
                "total_agents": total_agents,
                "excluded_agent_ids": list(excluded),
                "timestamp": datetime.now(timezone.utc),
            }}},
        )

    def _record_blocked(
        self, run_col, node, note: str, step_start: datetime, tool_records, memory_bus,
    ) -> None:
        """Record a blocked agent as a real (failed) step.

        Unlike a handback this IS user-visible: the request was this agent's job
        and it could not complete it, so the honest outcome is to say so rather
        than silently shop the request around other agents.
        """
        run_col.update_one(
            {"run_id": self._ctx.run_id},
            {
                "$push": {"execution_path": {
                    "agent_id": node.agent_id,
                    "agent_name": node.name,
                    "input_summary": "",
                    "output_summary": note[:300],
                    "output": note,
                    "tool_invocations": [_serialize_tool(t) for t in tool_records],
                    "started_at": step_start,
                    "ended_at": datetime.now(timezone.utc),
                    "status": "complete",
                    "branch_id": None,
                }},
                "$set": {"status": RunStatus.RUNNING.value, **memory_bus.flush_to_run_doc()},
            },
        )

    def _record_handback(self, run_col, node, reason: str, step_start: datetime) -> None:
        """Record a handback in execution_path only.

        Deliberately does NOT call write_orchestration_turn: a handback is an
        internal control transfer, not a message, so it must never reach the
        conversation transcript the chat UI renders.
        """
        run_col.update_one(
            {"run_id": self._ctx.run_id},
            {
                "$push": {"execution_path": {
                    "agent_id": node.agent_id,
                    "agent_name": node.name,
                    "input_summary": "",
                    "output_summary": f"handback: {reason}",
                    "output": None,
                    "tool_invocations": [],
                    "started_at": step_start,
                    "ended_at": datetime.now(timezone.utc),
                    "status": "handback",
                    "branch_id": None,
                }},
                # A handback is not a real visit — don't spend the agent's budget.
                "$inc": {f"loop_counters.{node.agent_id}": -1},
            },
        )

    # ------------------------------------------------------------------
    # Parallel fan-out
    # ------------------------------------------------------------------

    def _run_parallel_branches(
        self,
        branch_ids: List[str],
        entry_message: str,
        run_col,
        arriving_from: str,
    ) -> List:
        """Run fan-out branches in parallel.
        Returns a mixed list: plain str for HITL signals, (str, int) tuples for terminal outputs.
        """
        memory_bus = self._ctx.memory_bus
        graph = self._ctx.runtime_graph

        # Snapshot the context BEFORE starting threads so every branch's first
        # agent sees the same fork-point log (no branch reads a sibling's
        # in-flight append). Downstream agents in a branch re-read the live log.
        fork_context = memory_bus.get_context()

        all_terminals: List = []

        def run_branch(bid: str) -> List:
            label = graph.edge_labels.get((arriving_from, bid), "")
            self._upsert_branch_state(
                run_col, branch_id=bid, status=RunStatus.RUNNING.value,
                pending_agents=[bid], label=label
            )
            return self._run_single_branch(bid, deque([bid]), entry_message, run_col, fork_context=fork_context)

        workers = min(len(branch_ids), _MAX_PARALLEL_BRANCHES)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run_branch, bid) for bid in branch_ids]
            for future in as_completed(futures):
                try:
                    all_terminals.extend(future.result())
                except Exception as exc:
                    logger.error("[scheduler:parallel] branch raised: %s", exc)

        return all_terminals
    
    def _run_single_branch(
        self,
        bid: str,
        branch_pending: "deque[str]",
        entry_message: str,
        run_col,
        fork_context: Optional[str] = None,
    ) -> List:
        """Run one branch's agent chain to completion or until it hits HITL.
        fork_context supplied → fresh fan-out spawn (first agent sees the
        fork-point snapshot). fork_context=None → resuming a paused branch
        (reads the live log, since the human's answer was just injected)."""
        memory_bus = self._ctx.memory_bus
        graph = self._ctx.runtime_graph
        branch_terminals: List = []
        first_agent = fork_context is not None

        effective_bid = bid

        while branch_pending:
            current_bid = branch_pending.popleft()
            current_node = graph.nodes.get(current_bid)
            if not current_node:
                continue

            if first_agent and current_bid == bid:
                agent_input = fork_context
                first_agent = False
            else:
                agent_input = memory_bus.get_context()

            step_start = datetime.now(timezone.utc)
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {
                    "$inc": {f"loop_counters.{current_bid}": 1},
                    "$set": {"current_agent_id": current_bid, "current_agent_name": current_node.name},
                },
            )

            try:
                output, tool_records = self._invoker.invoke(current_node, agent_input, unattended=getattr(self._ctx, 'unattended', False))
            except HumanInterruptException as hitl:
                if getattr(self._ctx, "unattended", False):
                    logger.info("[scheduler:branch] unattended run ignoring HITL interrupt for %s — proceeding", current_bid)
                    output = f"Unattended execution note: {hitl.question}"
                    tool_records = []
                elif effective_bid is None:
                    memory_bus.write_hitl_question(current_node.name, hitl.question,)
                    self._upsert_branch_state(
                        run_col, branch_id=bid, status=RunStatus.WAITING_FOR_HUMAN.value,
                        pending_agents=[current_bid], human_question=hitl.question,
                        human_asked_by_agent=current_bid,
                    )
                    run_col.update_one(
                        {"run_id": self._ctx.run_id},
                        {"$inc": {f"loop_counters.{current_bid}": -1}},
                    )
                    run_col.update_one(
                        {"run_id": self._ctx.run_id, "status": {"$nin": list(TERMINAL_STATUSES)}},
                        {"$set": {"status": RunStatus.WAITING_FOR_HUMAN.value}},
                    )
                    logger.info("[scheduler:branch] HITL — branch=%s agent=%s question=%.100s", bid, current_bid, hitl.question)
                    branch_terminals.append(f"__HITL__:{bid}:{hitl.question}")
                    return branch_terminals
                else:
                    memory_bus.write_hitl_question(current_node.name, hitl.question, branch_id=effective_bid)
                    self._upsert_branch_state(
                        run_col, branch_id=bid, status=RunStatus.WAITING_FOR_HUMAN.value,
                        pending_agents=[current_bid], human_question=hitl.question,
                        human_asked_by_agent=current_bid,
                    )
                    run_col.update_one(
                        {"run_id": self._ctx.run_id},
                        {"$inc": {f"loop_counters.{current_bid}": -1}},
                    )
                    run_col.update_one(
                        {"run_id": self._ctx.run_id, "status": {"$nin": list(TERMINAL_STATUSES)}},
                        {"$set": {"status": RunStatus.WAITING_FOR_HUMAN.value}},
                    )
                    logger.info("[scheduler:branch] HITL — branch=%s agent=%s question=%.100s", bid, current_bid, hitl.question)
                    branch_terminals.append(f"__HITL__:{bid}:{hitl.question}")
                    return branch_terminals
            except ConnectorReauthException as reauth:
                self._upsert_branch_state(
                    run_col, branch_id=bid, status=RunStatus.WAITING_FOR_REAUTH.value,
                    pending_agents=[current_bid], pending_reauth=reauth.to_dict(),
                )
                run_col.update_one(
                    {"run_id": self._ctx.run_id},
                    {"$inc": {f"loop_counters.{current_bid}": -1}},
                )
                run_col.update_one(
                    {"run_id": self._ctx.run_id, "status": {"$nin": list(TERMINAL_STATUSES)}},
                    {"$set": {"status": RunStatus.WAITING_FOR_REAUTH.value}},
                )
                logger.info(
                    "[scheduler:branch] reauth — branch=%s agent=%s connector=%s",
                    bid, current_bid, reauth.display_name,
                )
                branch_terminals.append(f"__REAUTH__:{bid}:{reauth.display_name}")
                return branch_terminals
            except Exception as exc:
                logger.error("[scheduler:branch] agent %s failed: %s", current_bid, exc)
                self._upsert_branch_state(run_col, branch_id=bid, status=RunStatus.FAILED.value)
                branch_terminals.append((f"Agent '{current_node.name}' failed: {exc}", 0))
                return branch_terminals

            if not tool_records and not getattr(self._ctx, "unattended", False):
                question = self._no_tool_hitl_question(current_node, output)

                if effective_bid is None:
                    memory_bus.write_hitl_question(current_node.name, question)
                    mem_flush = memory_bus.flush_to_run_doc()
                    run_col.update_one(
                        {"run_id": self._ctx.run_id},
                        {"$set": {
                            "status": RunStatus.WAITING_FOR_HUMAN.value,
                            "human_question": question,
                            "human_asked_by_agent": current_bid,
                            "pending_agents": [current_bid],
                            **mem_flush,
                        }},
                    )
                    logger.info("[scheduler:branch] post-join no-tool → HITL — question=%.100s", question)
                    branch_terminals.append(f"__HITL__:{bid}:{question}")
                    return branch_terminals
                else:
                    memory_bus.write_hitl_question(current_node.name, question, branch_id=effective_bid)
                    self._upsert_branch_state(
                        run_col, branch_id=bid, status=RunStatus.WAITING_FOR_HUMAN.value,
                        pending_agents=[current_bid], human_question=question,
                        human_asked_by_agent=current_bid,
                    )
                    run_col.update_one(
                        {"run_id": self._ctx.run_id},
                        {"$inc": {f"loop_counters.{current_bid}": -1}},
                    )
                    run_col.update_one(
                        {"run_id": self._ctx.run_id, "status": {"$nin": list(TERMINAL_STATUSES)}},
                        {"$set": {"status": RunStatus.WAITING_FOR_HUMAN.value}},
                    )
                    logger.info("[scheduler:branch] no-tool turn by %s → auto HITL (branch=%s)", current_bid, bid)
                    branch_terminals.append(f"__HITL__:{bid}:{question}")
                    return branch_terminals

            branch_tools = [r.tool_name for r in tool_records]
            branch_node_num = self._ctx.sync_db.orchestration_conversations.find_one(
                {"session_id": self._ctx.session_id}, {"total_messages": 1}
            )
            branch_node_num = (branch_node_num or {}).get("total_messages", 0) + 1
            memory_bus.write_orchestration_turn(current_node.name, branch_node_num, branch_tools, output, branch_id=effective_bid)
            memory_bus.append_agent(current_node.name, output)
            mem_flush = memory_bus.flush_to_run_doc()

            run_col.update_one(
                {"run_id": self._ctx.run_id, "status": {"$ne": RunStatus.WAITING_FOR_HUMAN.value}},
                {
                    "$push": {"execution_path": {
                        "agent_id": current_bid,
                        "agent_name": current_node.name,
                        "input_summary": agent_input[:300],
                        "output_summary": output[:300],
                        "output": output,
                        "tool_invocations": [_serialize_tool(t) for t in tool_records],
                        "started_at": step_start,
                        "ended_at": datetime.now(timezone.utc),
                        "status": "complete",
                        "branch_id": effective_bid,
                    }},
                    "$set": {"status": RunStatus.RUNNING.value, **mem_flush},
                },
            )

            run_doc = run_col.find_one({"run_id": self._ctx.run_id}) or {}
            loop_counters = run_doc.get("loop_counters", {})
            next_ids = self._router.decide_next(
                graph=graph, current_agent_id=current_bid, agent_output=output,
                shared_context="", original_task=entry_message,
                loop_counters={**loop_counters, current_bid: loop_counters.get(current_bid, 0) + 1},
                max_visits=graph.max_visits_per_agent,
            )

            if not next_ids:
                branch_terminals.append((output, len(tool_records)))
                if effective_bid is not None:
                    self._upsert_branch_state(
                        run_col,
                        branch_id=bid,
                        status=RunStatus.COMPLETE.value,
                    )
                logger.info("[scheduler:branch] terminal — agent=%s", current_bid)

            else:
                if effective_bid is None:
                    branch_pending.extend(next_ids)
                else:
                    if len(next_ids) > 1:
                        # Gate any join nodes BEFORE spawning threads for them.
                        to_spawn = []
                        for nid in next_ids:
                            if nid in graph.join_points:
                                join_ready = self._record_join_arrival(run_col, graph, nid, current_bid)
                                if join_ready:
                                    logger.info(
                                        "[scheduler:branch] %s is last arrival at join %s — merging into main",
                                        current_bid, nid,
                                    )
                                    required = set(graph.reverse_adjacency.get(nid, []))
                                    for sibling_id in required:
                                        if sibling_id != current_bid:
                                            self._upsert_branch_state(run_col, branch_id=sibling_id, status=RunStatus.COMPLETE.value)
                                    to_spawn.append(nid)
                                else:
                                    logger.info(
                                        "[scheduler:branch] %s arrived at join %s — waiting on sibling(s)",
                                        current_bid, nid,
                                    )
                            else:
                                to_spawn.append(nid)

                        if to_spawn:
                            nested_terminals = self._run_parallel_branches(to_spawn, entry_message, run_col, arriving_from=current_bid)
                            branch_terminals.extend(nested_terminals)
                            self._upsert_branch_state(run_col, branch_id=bid, status=RunStatus.COMPLETE.value)
                        else:
                            self._upsert_branch_state(run_col, branch_id=bid, status=RunStatus.RUNNING.value)
                            logger.info("[scheduler:branch] branch %s parked — waiting on join sibling(s)", bid)

                        return branch_terminals

                    for nid in next_ids:
                        if nid not in graph.join_points:
                            branch_pending.append(nid)
                            continue

                        join_ready = self._record_join_arrival(run_col, graph, nid, current_bid)
                        if join_ready:
                            logger.info("[scheduler:branch] %s is last arrival at join %s — merging into main", current_bid, nid)
                            # This branch now runs the join node itself. Sibling branches that
                            # fed this same join have their execution subsumed into this one —
                            # mark them COMPLETE so they stop being counted as "still active".
                            required = set(graph.reverse_adjacency.get(nid, []))
                            for sibling_id in required:
                                if sibling_id != current_bid:
                                    self._upsert_branch_state(run_col, branch_id=sibling_id, status=RunStatus.COMPLETE.value)
                            self._upsert_branch_state(run_col, branch_id=bid, status=RunStatus.COMPLETE.value)
                            branch_pending.append(nid)
                        else:
                            logger.info("[scheduler:branch] %s arrived at join %s — waiting on other branch(es)", current_bid, nid)

                    if not branch_pending:
                        self._upsert_branch_state(run_col, branch_id=bid, status=RunStatus.RUNNING.value)
                        logger.info("[scheduler:branch] branch %s parked — waiting on join sibling(s)", bid)
                        return branch_terminals

        return branch_terminals

        

    def resume_branch(self, branch_id: str, pending_agents: List[str], entry_message: str) -> List:
        """Resume ONE previously-paused branch..."""
        db = self._ctx.sync_db
        run_col = db[ORCHESTRATION_RUNS_COLLECTION]

        branch_terminals = self._run_single_branch(
            branch_id, deque(pending_agents), entry_message, run_col, fork_context=None, 
        )

        hitl = [t for t in branch_terminals if isinstance(t, str) and t.startswith("__HITL__:")]
        if hitl:
            return branch_terminals

        # Re-check if ALL branches are done
        run_doc = run_col.find_one({"run_id": self._ctx.run_id}) or {}
        branches = run_doc.get("branches", [])
        still_active = [
            b for b in branches 
            if b.get("status") not in (RunStatus.COMPLETE.value, RunStatus.FAILED.value, RunStatus.TIMEOUT.value)
        ]

        if not still_active:
            final_response = self._aggregate_branch_outputs(run_col)
            self._set_status(run_col, RunStatus.COMPLETE, final_response=final_response)
            logger.info("[scheduler] all branches complete after resume — run_id=%s", self._ctx.run_id)
        else:
            logger.info("[scheduler] resume done, but other branches still active")

        return branch_terminals

    def _aggregate_branch_outputs(self, run_col) -> str:
        """Build the run's final_response from each branch's last execution_path
        entry, once every branch has reached a terminal node."""
        run_doc = run_col.find_one({"run_id": self._ctx.run_id}) or {}
        path = run_doc.get("execution_path", [])

        merged_entries = [p for p in path if p.get("branch_id") is None]
        if merged_entries:
            # A join fired and execution converged — the main-thread tail is
            # the real final output, not each branch's pre-merge last step.
            return merged_entries[-1]["output"]

        branches = run_doc.get("branches", [])
        outputs = []
        for b in branches:
            bid = b.get("branch_id")
            entries = [p for p in path if p.get("branch_id") == bid]
            if entries:
                outputs.append(entries[-1]["output"])
        if not outputs and path:
            return path[-1].get("output") or "The orchestration completed without a final response."
        if not outputs:
            return "The orchestration completed without a final response."
        if len(outputs) == 1:
            return outputs[0]
        return "\n\n---\n\n".join(f"[{i+1}] {o}" for i, o in enumerate(outputs))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _no_tool_hitl_question(node, output: str) -> str:
        """Question to surface when an agent ends its turn without calling any
        tool. Prefer the agent's own text (it is often already a clarifying
        question); fall back to a generic role-scoped prompt if it is empty or
        the invoker's 'unable to complete' placeholder."""
        text = (output or "").strip()
        print(f"node name: {node.name}")
        print(f"agent output: {text}")
        if text:
            return text
        else:
            return (
                f"I'm the {node.name} and What would you like me to do?"
            )

    def _set_status(
        self,
        run_col,
        status: RunStatus,
        final_response: Optional[str] = None,
    ) -> None:
        update: dict = {"$set": {"status": status.value}}
        if status in (RunStatus.COMPLETE, RunStatus.FAILED, RunStatus.TIMEOUT):
            update["$set"]["completed_at"] = datetime.now(timezone.utc)
        if final_response is not None:
            update["$set"]["final_response"] = final_response
        run_col.update_one({"run_id": self._ctx.run_id}, update)

    def _fail(
        self,
        run_col,
        agent_id: str,
        error_type: str,
        message: str,
        retry_count: int,
    ) -> None:
        run_col.update_one(
            {"run_id": self._ctx.run_id},
            {"$set": {
                "status": RunStatus.FAILED.value,
                "completed_at": datetime.now(timezone.utc),
                "error_context": {
                    "agent_id": agent_id,
                    "error_type": error_type,
                    "message": message,
                    "retry_count": retry_count,
                    "timestamp": datetime.now(timezone.utc),
                },
            }},
        )
        logger.error("[scheduler] FAILED — agent=%s type=%s msg=%s", agent_id, error_type, message)

    ## Helper Functions for Parallization
    
    def _upsert_branch_state(
        self,
        run_col,
        branch_id: str,
        *,
        status: str,
        pending_agents: Optional[List[str]] = None,
        human_question: Optional[str] = None,
        human_asked_by_agent: Optional[str] = None,
        pending_reauth: Optional[dict] = None,
        label: Optional[str] = None,
    ) -> None:
        """Create or update this branch's entry in the run document's `branches`
        array. Uses arrayFilters so each branch's state is updated independently
        without clobbering sibling branches."""
        from ai.multi_orchestration.models import new_branch_state

        run_doc = run_col.find_one({"run_id": self._ctx.run_id}, {"branches": 1})
        existing = run_doc.get("branches", []) if run_doc else []
        exists = any(b.get("branch_id") == branch_id for b in existing)

        update_fields: dict = {"branches.$[b].status": status}
        if pending_agents is not None:
            update_fields["branches.$[b].pending_agents"] = pending_agents
        if human_question is not None:
            update_fields["branches.$[b].human_question"] = human_question
        if human_asked_by_agent is not None:
            update_fields["branches.$[b].human_asked_by_agent"] = human_asked_by_agent
        if pending_reauth is not None:
            update_fields["branches.$[b].pending_reauth"] = pending_reauth
        if label is not None:
            update_fields["branches.$[b].label"] = label
        if status in (RunStatus.COMPLETE.value, RunStatus.FAILED.value):
            update_fields["branches.$[b].completed_at"] = datetime.now(timezone.utc)

        if exists:
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {"$set": update_fields},
                array_filters=[{"b.branch_id": branch_id}],
            )
        else:
            new_state = new_branch_state(pending_agents or [], label=label or "")
            new_state["branch_id"] = branch_id  # use the caller's id, not a fresh one
            new_state["status"] = status
            if human_question is not None:
                new_state["human_question"] = human_question
            if human_asked_by_agent is not None:
                new_state["human_asked_by_agent"] = human_asked_by_agent
            if pending_reauth is not None:
                new_state["pending_reauth"] = pending_reauth
            run_col.update_one(
                {"run_id": self._ctx.run_id},
                {"$push": {"branches": new_state}},
            )


    def _record_join_arrival(self, run_col, graph, join_node_id: str, arriving_from: str) -> bool:
        """Atomically record that `arriving_from` reached `join_node_id`, using
        the run document itself — not in-memory state — since each resume spins
        up a brand-new RuntimeScheduler in its own thread with no shared memory
        to a prior resume. Returns True once every required predecessor has
        arrived (i.e., it's now safe to run the join node)."""
        required = set(graph.reverse_adjacency.get(join_node_id, []))

        run_col.update_one(
            {"run_id": self._ctx.run_id},
            {"$addToSet": {f"join_arrivals.{join_node_id}": arriving_from}},
        )
        run_doc = run_col.find_one(
            {"run_id": self._ctx.run_id}, {f"join_arrivals.{join_node_id}": 1}
        ) or {}
        arrived = set(run_doc.get("join_arrivals", {}).get(join_node_id, []))

        logger.info(
            "[join] node=%s arrived=%s required=%s missing=%s",
            join_node_id, sorted(arrived), sorted(required), sorted(required - arrived),
        )
        return required.issubset(arrived)


def _serialize_tool(t: ToolInvocationRecord) -> dict:
    return {
        "tool_name": t.tool_name,
        "arguments": t.arguments,
        "result": t.result[:500],
        "status": t.status,
        "started_at": t.started_at,
        "ended_at": t.ended_at,
        "error": t.error,
    }



