"""Supervisor-mode orchestration: routing, handback, multi-hop, isolation.

Offline and deterministic — the LLM call and agent invocation are both patched,
so this exercises the scheduler's real control flow without network access.

    .venv/Scripts/python.exe -m pytest backend/tests/test_supervisor_mode.py -v
"""
import copy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

# ai.tools.tools must finish initialising before anything else in
# ai.multi_orchestration / ai.agents imports it — the repo has a pre-existing
# import cycle (ai.agents.loop -> ai.multi_orchestration.models ->
# ai.tools.tools -> ai.agents.loop) that only resolves in this order.
import ai.tools.tools  # noqa: F401

from ai.multi_orchestration.agent_invoker import AgentInvoker
from ai.multi_orchestration.memory_bus import MemoryBus
from ai.multi_orchestration.models import RunStatus, ToolInvocationRecord, new_run_document
from ai.multi_orchestration.run_context import RunContext
from ai.multi_orchestration.runtime_graph import RuntimeAgentNode, RuntimeGraph
from ai.multi_orchestration.scheduler import RuntimeScheduler
from ai.multi_orchestration.supervisor import (
    KIND_BLOCKED,
    SUPERVISOR_AGENT_ID,
    RouteDecision,
    SupervisorAgent,
    SupervisorHandbackException,
    extract_handback,
)
from backend.orchestration.schemas import AgentStepPublic, OrchestrationCreate, SupervisorConfig

TIME_TRACE = "aaaaaaaaaaaaaaaaaaaaaaaa"
HR = "bbbbbbbbbbbbbbbbbbbbbbbb"
SHEETS = "cccccccccccccccccccccccc"
GMAIL = "dddddddddddddddddddddddd"


# ---------------------------------------------------------------------------
# Fixtures / fakes
# ---------------------------------------------------------------------------

def _node(agent_id, name, description, tools=None, **kw):
    return RuntimeAgentNode(
        agent_id=agent_id,
        name=name,
        prompt=f"You are {name}.",
        guardrails=[],
        tools=tools if tools is not None else [{"function": {"name": "lookup", "description": "d"}}],
        tool_callables={},
        description=description,
        **kw,
    )


class _FakeRunCollection:
    """Single-document Mongo fake supporting only the operators this code issues."""

    def __init__(self, seed):
        self._docs = {seed["run_id"]: copy.deepcopy(seed)}

    def find_one(self, filt, projection=None, sort=None):
        doc = self._docs.get(filt.get("run_id"))
        return copy.deepcopy(doc) if doc else None

    def update_one(self, filt, update, array_filters=None):
        doc = self._docs.get(filt.get("run_id"))
        if doc is None:
            return
        for op, fields in update.items():
            for key, value in fields.items():
                if op == "$set":
                    self._set(doc, key, value)
                elif op == "$inc":
                    self._set(doc, key, (self._get(doc, key) or 0) + value)
                elif op == "$push":
                    lst = self._get(doc, key)
                    if lst is None:
                        lst = []
                        self._set(doc, key, lst)
                    lst.append(value)

    @staticmethod
    def _set(doc, dotted, value):
        parts = dotted.split(".")
        cur = doc
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value

    @staticmethod
    def _get(doc, dotted):
        cur = doc
        for p in dotted.split("."):
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur

    def latest(self, run_id="run1"):
        return copy.deepcopy(self._docs[run_id])


class _FakeSyncDb:
    def __init__(self, run_col):
        self._run_col = run_col
        self.orchestration_conversations = SimpleNamespace(
            update_one=lambda *a, **k: None,
            find_one=lambda *a, **k: {"total_messages": 0},
        )

    def __getitem__(self, _name):
        return self._run_col


def _tool_record(name="lookup"):
    now = datetime.now(timezone.utc)
    return ToolInvocationRecord(
        tool_name=name, arguments={}, result="ok", status="success",
        started_at=now, ended_at=now,
    )


def _graph(nodes, max_hops=6, max_bounces=2, visits=3):
    return RuntimeGraph(
        orchestration_id="orch1",
        main_agent_id=None,
        nodes={n.agent_id: n for n in nodes},
        adjacency={}, reverse_adjacency={}, edge_types={}, edge_labels={},
        join_points=set(), hub_nodes=set(), has_parallel_branches=False,
        max_depth=5, max_visits_per_agent=visits, mode="supervisor",
        supervisor_max_hops=max_hops,
        supervisor_max_consecutive_handbacks=max_bounces,
    )


def _scheduler(graph):
    run_doc = new_run_document(
        orchestration_id="orch1", session_id="sess1", user_id="user1",
        organization_id="org1", entry_message="q", main_agent_id=None,
        max_depth=5, timeout_sec=600,
    ) | {"run_id": "run1"}
    run_col = _FakeRunCollection(run_doc)
    sync_db = _FakeSyncDb(run_col)
    ctx = RunContext(
        run_id="run1", orchestration_id="orch1", session_id="sess1",
        org_id="org1", user_id="user1", runtime_graph=graph,
        memory_bus=MemoryBus(run_col.latest(), sync_db, "m"), sync_db=sync_db, model="m",
    )
    return RuntimeScheduler(ctx, model="m"), run_col


def _route_to(*agent_ids):
    """Router stub: route through `agent_ids` in order, then finish.

    Modelling the finish is essential — a stub that routes unconditionally would
    spin until a bound trips, which is a property of the stub, not the scheduler.
    A real router finishes once `completed_steps` shows the request is satisfied.

    `**_kw` absorbs routing inputs a given test doesn't care about, so adding a
    new hint to `decide()` doesn't break every stub.
    """
    def _decide(self, nodes, message, excluded_agent_ids=None, completed_steps=None, routing_history=None, **_kw):
        done = len(completed_steps or [])
        if done < len(agent_ids):
            return RouteDecision(action="route", target_agent_id=agent_ids[done], agent_input=message)
        return RouteDecision(action="finish", reason="request satisfied")
    return _decide


def _route_skipping_declined(*agent_ids):
    """Router stub that mirrors the real exclusion contract: an agent that handed
    back is never offered again, so routing falls through to the next candidate.

    Needed for handback tests because sticky is only a *hint* — the scheduler no
    longer invokes the previous turn's agent directly, so a test must route to it
    to get it into the turn at all.
    """
    def _decide(self, nodes, message, excluded_agent_ids=None, completed_steps=None, routing_history=None, **_kw):
        if completed_steps:
            return RouteDecision(action="finish", reason="request satisfied")
        excluded = set(excluded_agent_ids or ())
        for agent_id in agent_ids:
            if agent_id not in excluded:
                return RouteDecision(action="route", target_agent_id=agent_id, agent_input=message)
        return RouteDecision(action="finish", reason="every agent declined")
    return _decide


# ---------------------------------------------------------------------------
# extract_handback
# ---------------------------------------------------------------------------

class TestExtractHandback:
    @pytest.mark.parametrize("text,expected", [
        ('Let me check... {"handback": true, "reason": "salary is HR territory"}', "salary is HR territory"),
        ("You worked on 4 projects.", None),
        ("", None),
        (None, None),
        ('{"handback": true, "reason": ', None),          # malformed
        ('{"handback": false, "reason": "n/a"}', None),   # explicit false
    ])
    def test_parsing(self, text, expected):
        result = extract_handback(text)
        assert (result.reason if result else None) == expected

    def test_missing_reason_gets_a_default(self):
        assert extract_handback('{"handback": true}').reason

    def test_trailing_prose_after_marker_still_parses(self):
        assert extract_handback('{"handback": true, "reason": "not mine"} sorry!').reason == "not mine"

    def test_kind_defaults_to_wrong_domain(self):
        """Absent kind must read as wrong_domain — that is what the marker meant
        before `kind` existed, and it is the conservative reading."""
        assert not extract_handback('{"handback": true, "reason": "nope"}').is_blocked

    def test_blocked_kind_is_recognised(self):
        hb = extract_handback('{"handback": true, "kind": "blocked", "reason": "table missing"}')
        assert hb.is_blocked and hb.reason == "table missing"

    def test_unknown_kind_falls_back_to_wrong_domain(self):
        assert not extract_handback('{"handback": true, "kind": "weird"}').is_blocked


# ---------------------------------------------------------------------------
# Candidate selection — the "any number of agents" guarantee
# ---------------------------------------------------------------------------

class TestCandidateSelection:
    def test_small_roster_passes_through_whole(self):
        nodes = [_node(f"{i:024d}", f"Agent {i}", "d") for i in range(10)]
        assert len(SupervisorAgent("m").build_candidates(nodes, "anything")) == 10

    def test_large_roster_is_shortlisted_and_ranked_by_relevance(self):
        nodes = [_node(f"{i:024d}", f"Filler {i}", "unrelated domain") for i in range(200)]
        nodes.append(_node(HR, "HR Agent", "employee leave and salary information"))
        agent = SupervisorAgent("m")

        picked = agent.build_candidates(nodes, "how many annual leaves do I have left?")

        assert len(picked) == 12  # SHORTLIST_SIZE — cost stays flat at any roster size
        assert HR in [n.agent_id for n in picked]

    def test_excluded_agents_are_dropped_before_ranking(self):
        nodes = [_node(TIME_TRACE, "TimeTrace", "time"), _node(HR, "HR", "leave")]
        picked = SupervisorAgent("m").build_candidates(nodes, "leave", excluded_agent_ids=[HR])
        assert [n.agent_id for n in picked] == [TIME_TRACE]

    def test_connector_and_mcp_names_are_routing_signal(self):
        """An agent whose only clue is its Gmail connector must still be findable."""
        plain = [_node(f"{i:024d}", f"Filler {i}", "unrelated") for i in range(200)]
        mailer = _node(
            GMAIL, "Comms", "sends things",
            tools=[{"function": {"name": "gmail_send", "description": "send"}}],
            connector_tool_owner={"gmail_send": {"display_name": "Gmail", "provider_id": "gmail"}},
        )
        picked = SupervisorAgent("m").build_candidates(plain + [mailer], "send this over gmail")
        assert GMAIL in [n.agent_id for n in picked]


# ---------------------------------------------------------------------------
# Agent context — what the Supervisor actually sees
# ---------------------------------------------------------------------------

class TestAgentContext:
    def test_connector_tools_collapse_to_one_provider_name(self):
        """22 Gmail tools must cost one line, not 22, and must not bury the
        agent's own custom tool."""
        node = _node(
            GMAIL, "Gmail Assistant", "Sends and manages email",
            tools=([{"function": {"name": "custom_lookup", "description": "Look up"}}]
                   + [{"function": {"name": f"gmail_{i}", "description": "g"}} for i in range(22)]),
            connector_tool_owner={
                f"gmail_{i}": {"display_name": "Gmail", "provider_id": "gmail"} for i in range(22)
            },
        )
        ctx = SupervisorAgent("m")._agent_context(node)
        assert ctx["connectors"] == ["Gmail"]
        assert [t["name"] for t in ctx["tools"]] == ["custom_lookup"]

    def test_mcp_tools_collapse_to_server_names(self):
        node = _node(
            SHEETS, "Docs", "d",
            tools=[{"function": {"name": "search_docs", "description": "s"}}],
            mcp_tool_owner={"search_docs": "Notion MCP"},
        )
        ctx = SupervisorAgent("m")._agent_context(node)
        assert ctx["mcp_servers"] == ["Notion MCP"]
        assert ctx["tools"] == []

    def test_plain_tools_are_never_truncated(self):
        node = _node(TIME_TRACE, "Many", "d",
                     tools=[{"function": {"name": f"t{i}", "description": "d"}} for i in range(30)])
        assert len(SupervisorAgent("m")._agent_context(node)["tools"]) == 30

    def test_degraded_capabilities_are_surfaced_not_hidden(self):
        node = _node(GMAIL, "Mailer", "d", capability_load_errors=["Gmail (needs reconnecting)"])
        ctx = SupervisorAgent("m")._agent_context(node)
        assert ctx["unavailable"] == ["Gmail (needs reconnecting)"]


# ---------------------------------------------------------------------------
# Routing decision — the tool-calling contract, with the LLM patched
# ---------------------------------------------------------------------------

def _llm_reply(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=tool_calls)
    )])


def _tool_call(name, arguments="{}"):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


class TestRouterDecision:
    def test_routes_to_the_called_tool_and_extracts_the_task(self, monkeypatch):
        tt = _node(TIME_TRACE, "TimeTrace", "project and time tracking")
        hr = _node(HR, "HR", "employee leave")
        seen = {}

        def fake_completion(**kwargs):
            seen.update(kwargs)
            target = next(t["function"]["name"] for t in kwargs["tools"] if "timetrace" in t["function"]["name"])
            return _llm_reply(tool_calls=[_tool_call(target, '{"task": "count projects", "reason": "time domain"}')])

        monkeypatch.setattr("ai.multi_orchestration.supervisor.agent._completion_with_retry", fake_completion)

        decision = SupervisorAgent("m").decide([tt, hr], "how many projects?")

        assert decision.action == "route"
        assert decision.target_agent_id == TIME_TRACE
        assert decision.agent_input == "count projects"
        assert decision.reason == "time domain"
        assert seen["tool_choice"] == "auto" and len(seen["tools"]) == 2

    def test_no_tool_call_becomes_a_direct_answer(self, monkeypatch):
        monkeypatch.setattr("ai.multi_orchestration.supervisor.agent._completion_with_retry",
                            lambda **kw: _llm_reply(content="Hello! How can I help?"))
        decision = SupervisorAgent("m").decide([_node(HR, "HR", "leave")], "hi")
        assert decision.action == "finish"
        assert decision.final_response == "Hello! How can I help?"

    def test_excluded_agent_is_never_offered(self, monkeypatch):
        tt = _node(TIME_TRACE, "TimeTrace", "time")
        hr = _node(HR, "HR", "leave")
        offered = []

        def fake_completion(**kwargs):
            offered.extend(t["function"]["name"] for t in kwargs["tools"])
            return _llm_reply(tool_calls=[_tool_call(kwargs["tools"][0]["function"]["name"], "{}")])

        monkeypatch.setattr("ai.multi_orchestration.supervisor.agent._completion_with_retry", fake_completion)
        decision = SupervisorAgent("m").decide([tt, hr], "salary?", excluded_agent_ids=[TIME_TRACE])

        assert decision.target_agent_id == HR
        assert not any("timetrace" in name for name in offered)

    def test_everything_excluded_finishes_without_calling_the_llm(self, monkeypatch):
        def boom(**kwargs):
            raise AssertionError("no candidates means nothing to decide")
        monkeypatch.setattr("ai.multi_orchestration.supervisor.agent._completion_with_retry", boom)

        decision = SupervisorAgent("m").decide([_node(HR, "HR", "leave")], "x", excluded_agent_ids=[HR])
        assert decision.action == "finish"

    def test_unknown_tool_name_is_a_finish_not_a_crash(self, monkeypatch):
        monkeypatch.setattr("ai.multi_orchestration.supervisor.agent._completion_with_retry",
                            lambda **kw: _llm_reply(content="fallback", tool_calls=[_tool_call("route_to_ghost")]))
        assert SupervisorAgent("m").decide([_node(HR, "HR", "leave")], "x").action == "finish"

    def test_missing_task_argument_falls_back_to_the_user_message(self, monkeypatch):
        monkeypatch.setattr(
            "ai.multi_orchestration.supervisor.agent._completion_with_retry",
            lambda **kw: _llm_reply(tool_calls=[_tool_call(kw["tools"][0]["function"]["name"], "{}")]),
        )
        decision = SupervisorAgent("m").decide([_node(HR, "HR", "leave")], "how much leave?")
        assert decision.agent_input == "how much leave?"

    def test_agents_with_the_same_display_name_get_distinct_tools(self, monkeypatch):
        offered = []

        def fake_completion(**kwargs):
            offered.extend(t["function"]["name"] for t in kwargs["tools"])
            return _llm_reply(content="none")

        monkeypatch.setattr("ai.multi_orchestration.supervisor.agent._completion_with_retry", fake_completion)
        SupervisorAgent("m").decide([_node(TIME_TRACE, "Agent", "a"), _node(HR, "Agent", "b")], "x")

        assert len(set(offered)) == 2  # a collision would silently hide one agent

    def test_roster_carries_the_capability_metadata(self, monkeypatch):
        """Routing must be able to key on tools, connectors and MCP servers, not
        just the agent's name."""
        captured = {}

        def fake_completion(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _llm_reply(content="none")

        monkeypatch.setattr("ai.multi_orchestration.supervisor.agent._completion_with_retry", fake_completion)
        node = _node(
            GMAIL, "Comms", "sends reports",
            tools=[{"function": {"name": "draft", "description": "compose"}},
                   {"function": {"name": "gmail_send", "description": "send"}},
                   {"function": {"name": "sheet_write", "description": "write"}}],
            connector_tool_owner={"gmail_send": {"display_name": "Gmail", "provider_id": "gmail"}},
            mcp_tool_owner={"sheet_write": "Sheets MCP"},
        )
        SupervisorAgent("m").decide([node], "email the report")

        for expected in ("Comms", "sends reports", "draft", "Gmail", "Sheets MCP"):
            assert expected in captured["system"]


# ---------------------------------------------------------------------------
# Scheduler — supervisor turn behaviour
# ---------------------------------------------------------------------------

class TestSupervisorTurn:
    def test_routes_then_returns_the_agent_answer(self, monkeypatch):
        graph = _graph([_node(TIME_TRACE, "TimeTrace", "time"), _node(HR, "HR", "leave")])
        sched, run_col = _scheduler(graph)
        monkeypatch.setattr(SupervisorAgent, "decide", _route_to(TIME_TRACE))
        monkeypatch.setattr(AgentInvoker, "invoke",
                            lambda self, n, t, history=None, **_: ("4 projects.", [_tool_record()]))

        assert sched.run("how many projects?") == "4 projects."
        final = run_col.latest()
        assert final["status"] == RunStatus.COMPLETE.value
        assert final["execution_path"][-1]["agent_id"] == TIME_TRACE

    def test_sticky_is_a_preference_not_a_shortcut(self, monkeypatch):
        """The previous turn's agent is offered to the Supervisor as continuity
        context — never invoked behind its back.

        Hard-invoking it was wrong: agents share tools (several can reach
        query_db), so a time-tracking agent handed an HR question would happily
        answer it from the shared table instead of handing back. Only the
        Supervisor can judge domain ownership, so it always decides first. The
        hint also applies to the first decision only, or a stale preference
        would drag every later hop back to the same agent.
        """
        graph = _graph([_node(TIME_TRACE, "TimeTrace", "time"), _node(HR, "HR", "leave")])
        sched, _ = _scheduler(graph)
        events: list[str] = []
        hints: list[str | None] = []

        def decide(self, nodes, message, sticky_agent_id=None, **_kw):
            events.append("decide")
            hints.append(sticky_agent_id)
            if len(events) == 1:
                return RouteDecision(action="route", target_agent_id=HR, agent_input=message)
            return RouteDecision(action="finish", reason="satisfied")

        monkeypatch.setattr(SupervisorAgent, "decide", decide)
        monkeypatch.setattr(
            AgentInvoker, "invoke",
            lambda self, n, t, history=None, **_: (events.append("invoke"), ("12 days.", [_tool_record()]))[1],
        )

        assert sched.run("how many leave days?", initial_queue=[TIME_TRACE]) == "12 days."
        assert events == ["decide", "invoke", "decide"]
        assert hints == [TIME_TRACE, None]

    def test_off_topic_agent_hands_back_and_supervisor_reroutes(self, monkeypatch):
        """Example 3/4: an agent handed a request outside its domain declines,
        and the Supervisor routes to the right one. The user sees one answer."""
        graph = _graph([_node(TIME_TRACE, "TimeTrace", "time"), _node(HR, "HR", "leave")])
        sched, run_col = _scheduler(graph)
        seen = []

        def invoke(self, node, task, history=None, **_):
            seen.append(node.agent_id)
            if node.agent_id == TIME_TRACE:
                return '{"handback": true, "reason": "leave is HR territory"}', []
            return "You have 12 leave days.", [_tool_record()]

        monkeypatch.setattr(AgentInvoker, "invoke", invoke)
        monkeypatch.setattr(SupervisorAgent, "decide", _route_skipping_declined(TIME_TRACE, HR))

        result = sched.run("how many leave days?")

        assert result == "You have 12 leave days."
        assert seen == [TIME_TRACE, HR]
        path = run_col.latest()["execution_path"]
        handbacks = [e for e in path if e["status"] == "handback"]
        assert len(handbacks) == 1 and handbacks[0]["agent_id"] == TIME_TRACE

    def test_handback_is_invisible_to_the_user(self, monkeypatch):
        """The internal transfer must not reach the chat step list — it is not a
        message. It stays in execution_path for audit."""
        graph = _graph([_node(TIME_TRACE, "TimeTrace", "time"), _node(HR, "HR", "leave")])
        sched, run_col = _scheduler(graph)
        monkeypatch.setattr(
            AgentInvoker, "invoke",
            lambda self, n, t, history=None, **_: (
                ('{"handback": true, "reason": "not mine"}', [])
                if n.agent_id == TIME_TRACE else ("12 days.", [_tool_record()])
            ),
        )
        monkeypatch.setattr(SupervisorAgent, "decide", _route_skipping_declined(TIME_TRACE, HR))
        sched.run("leave?")

        path = run_col.latest()["execution_path"]
        assert any(e["status"] == "handback" for e in path)          # audited
        visible = _steps_as_endpoint_would(path)
        assert [s.agent_id for s in visible] == [HR]                 # not shown
        assert all("handback" not in (s.output or "") for s in visible)

    def test_handback_via_tool_call_is_also_handled(self, monkeypatch):
        graph = _graph([_node(TIME_TRACE, "TimeTrace", "time"), _node(HR, "HR", "leave")])
        sched, _ = _scheduler(graph)

        def invoke(self, node, task, history=None, **_):
            if node.agent_id == TIME_TRACE:
                raise SupervisorHandbackException("not my domain")
            return "12 days.", [_tool_record()]

        monkeypatch.setattr(AgentInvoker, "invoke", invoke)
        monkeypatch.setattr(SupervisorAgent, "decide", _route_skipping_declined(TIME_TRACE, HR))
        assert sched.run("leave?") == "12 days."

    def test_multi_hop_combines_two_agents(self, monkeypatch):
        """Example 2: control returns to the Supervisor after each agent, and a
        multi-agent turn is synthesized rather than returning only the last
        agent's half of the answer."""
        graph = _graph([_node(TIME_TRACE, "TimeTrace", "time"), _node(HR, "HR", "leave")])
        sched, run_col = _scheduler(graph)
        order = [TIME_TRACE, HR]

        def decide(self, nodes, message, excluded_agent_ids=None, completed_steps=None, routing_history=None, **_kw):
            done = {c["agent"] for c in (completed_steps or [])}
            for agent_id in order:
                name = graph.nodes[agent_id].name
                if name not in done:
                    return RouteDecision(action="route", target_agent_id=agent_id, agent_input=message)
            return RouteDecision(action="finish", reason="all parts answered")

        monkeypatch.setattr(SupervisorAgent, "decide", decide)
        monkeypatch.setattr(SupervisorAgent, "synthesize",
                            lambda self, ctx: "4 projects, 30 hours, and 12 leave days.")
        monkeypatch.setattr(
            AgentInvoker, "invoke",
            lambda self, n, t, history=None, **_: (
                ("4 projects, 30 hours.", [_tool_record()]) if n.agent_id == TIME_TRACE
                else ("12 leave days.", [_tool_record()])
            ),
        )

        result = sched.run("projects, hours, and leave balance?")

        assert result == "4 projects, 30 hours, and 12 leave days."
        path = run_col.latest()["execution_path"]
        assert [e["agent_id"] for e in path] == [TIME_TRACE, HR, SUPERVISOR_AGENT_ID]

    def test_same_agent_may_be_used_twice_in_one_turn(self, monkeypatch):
        """Excluding an agent after it succeeds would break "email Alice, then
        Bob". Only handbacks exclude."""
        graph = _graph([_node(GMAIL, "Gmail", "sends email")])
        sched, run_col = _scheduler(graph)
        calls = {"n": 0}

        def decide(self, nodes, message, excluded_agent_ids=None, completed_steps=None, routing_history=None, **_kw):
            if len(completed_steps or []) < 2:
                return RouteDecision(action="route", target_agent_id=GMAIL, agent_input=message)
            return RouteDecision(action="finish", reason="both sent")

        def invoke(self, node, task, history=None, **_):
            calls["n"] += 1
            return f"sent #{calls['n']}", [_tool_record("gmail_send")]

        monkeypatch.setattr(SupervisorAgent, "decide", decide)
        monkeypatch.setattr(AgentInvoker, "invoke", invoke)

        # Both hops run — and the reply is the last agent turn verbatim, not a
        # synthesis: one agent twice is not a multi-agent turn (see
        # TestChurnGuards.test_synthesis_keys_on_distinct_agents_not_step_count).
        assert sched.run("email Alice then Bob") == "sent #2"
        assert calls["n"] == 2
        assert run_col.latest()["status"] == RunStatus.COMPLETE.value

    def test_direct_supervisor_answer_is_persisted(self, monkeypatch):
        """A greeting matches no agent. The Supervisor answers, and that answer
        must land in execution_path or the chat UI renders an empty turn."""
        graph = _graph([_node(TIME_TRACE, "TimeTrace", "time")])
        sched, run_col = _scheduler(graph)
        monkeypatch.setattr(
            SupervisorAgent, "decide",
            lambda self, nodes, message, excluded_agent_ids=None, completed_steps=None, routing_history=None, **_kw:
                RouteDecision(action="finish", final_response="Hello! How can I help?"),
        )

        assert sched.run("hi") == "Hello! How can I help?"
        final = run_col.latest()
        assert final["final_response"] == "Hello! How can I help?"
        assert len(final["execution_path"]) == 1
        entry = final["execution_path"][0]
        assert entry["agent_id"] == SUPERVISOR_AGENT_ID
        assert entry["agent_name"] == "Supervisor"
        assert entry["status"] == "complete"

    def test_deadlock_forces_the_closest_agent_instead_of_failing(self, monkeypatch):
        """Two agents declining in mirror image ("that's HR's" / "that's
        time-tracking's") used to fail the run outright, even when the system
        could answer. The Supervisor now sees both reasons, drops the
        exclusions, and must commit to the closest owner."""
        graph = _graph([_node(TIME_TRACE, "TimeTrace", "time"), _node(HR, "HR", "hr")], max_bounces=2)
        sched, run_col = _scheduler(graph)
        seen_declines = []
        invoked = []

        def invoke(self, node, task, history=None, **_):
            invoked.append(node.agent_id)
            if "[Assignment note]" in task:      # forced: stop refusing, answer
                return "12 days of leave taken.", [_tool_record("query_db")]
            return '{"handback": true, "reason": "belongs to the other one"}', []

        def decide(self, nodes, message, excluded_agent_ids=None, declined_agents=None,
                   completed_steps=None, force_assignment=False, **_kw):
            if force_assignment:
                seen_declines.append(list(declined_agents or []))
                return RouteDecision(action="route", target_agent_id=HR, agent_input=message)
            if completed_steps:
                return RouteDecision(action="finish", reason="answered")
            excluded = set(excluded_agent_ids or ())
            for agent_id in (TIME_TRACE, HR):
                if agent_id not in excluded:
                    return RouteDecision(action="route", target_agent_id=agent_id, agent_input=message)
            return RouteDecision(action="finish", reason="nobody left")

        monkeypatch.setattr(AgentInvoker, "invoke", invoke)
        monkeypatch.setattr(SupervisorAgent, "decide", decide)

        result = sched.run("how many holidays have I taken?")

        assert result == "12 days of leave taken."
        assert run_col.latest()["status"] == RunStatus.COMPLETE.value
        assert invoked == [TIME_TRACE, HR, HR]     # both declined, then HR forced
        # The forced decision saw *why* each agent declined, not just their ids.
        assert [d["agent"] for d in seen_declines[0]] == ["TimeTrace", "HR"]
        assert all(d["reason"] for d in seen_declines[0])

    def test_a_forced_agent_that_still_declines_is_reported_not_rerouted(self, monkeypatch):
        """Re-routing after the forced attempt would restart the deadlock, so
        the refusal becomes a reported failure — a real answer, not silence."""
        graph = _graph([_node(TIME_TRACE, "A", "a"), _node(HR, "B", "b")], max_bounces=2)
        sched, run_col = _scheduler(graph)

        monkeypatch.setattr(AgentInvoker, "invoke",
                            lambda self, n, t, history=None, **_: ('{"handback": true, "reason": "still not mine"}', []))
        monkeypatch.setattr(
            SupervisorAgent, "decide",
            lambda self, nodes, message, excluded_agent_ids=None, force_assignment=False, **_kw:
                RouteDecision(
                    action="route",
                    target_agent_id=(HR if force_assignment
                                     else next((a for a in (TIME_TRACE, HR)
                                                if a not in set(excluded_agent_ids or ())), HR)),
                    agent_input=message,
                ),
        )

        result = sched.run("ambiguous")

        assert run_col.latest()["status"] == RunStatus.COMPLETE.value
        assert "still not mine" in result      # explained, not "orchestration stopped"

    def test_hop_limit_fails_gracefully(self, monkeypatch):
        graph = _graph([_node(TIME_TRACE, "A", "a")], max_hops=2, max_bounces=10)
        sched, run_col = _scheduler(graph)
        monkeypatch.setattr(AgentInvoker, "invoke",
                            lambda self, n, t, history=None, **_: ('{"handback": true, "reason": "no"}', []))
        monkeypatch.setattr(SupervisorAgent, "decide", _route_to(TIME_TRACE))

        sched.run("q")
        assert run_col.latest()["error_context"]["error_type"] == "SupervisorHopLimitExceeded"

    def test_stale_agent_id_fails_cleanly(self, monkeypatch):
        graph = _graph([_node(TIME_TRACE, "A", "a")])
        sched, run_col = _scheduler(graph)
        monkeypatch.setattr(SupervisorAgent, "decide", _route_to("deadbeefdeadbeefdeadbeef"))

        sched.run("q")
        assert run_col.latest()["error_context"]["error_type"] == "NodeNotFound"

    def test_agent_error_is_explained_to_the_user_not_left_as_a_dead_run(self, monkeypatch):
        """The Supervisor manages the agents, so an agent blowing up should end
        the turn with a sentence the user can act on — while still leaving the
        diagnostic in the run document for logs and ops."""
        graph = _graph([_node(TIME_TRACE, "A", "a")])
        sched, run_col = _scheduler(graph)
        monkeypatch.setattr(SupervisorAgent, "decide", _route_to(TIME_TRACE))

        def boom(self, node, task, history=None):
            raise RuntimeError("upstream 500")
        monkeypatch.setattr(AgentInvoker, "invoke", boom)

        result = sched.run("q")
        final = run_col.latest()
        assert "upstream 500" in result                      # the user is told
        assert final["status"] == RunStatus.COMPLETE.value   # not a dead run
        assert final["error_context"]["error_type"] == "RuntimeError"   # still diagnosable


def _steps_as_endpoint_would(execution_path):
    """Mirror of get_run_status's step construction, so a change to the endpoint's
    filtering shows up here rather than in production."""
    return [
        AgentStepPublic(
            agent_id=e.get("agent_id") or "",
            agent_name=e.get("agent_name", ""),
            status=e.get("status") or "complete",
            output=e.get("output") or e.get("output_summary"),
            branch_id=e.get("branch_id"),
        )
        for e in execution_path
        if e.get("status") != "handback"
    ]


# ---------------------------------------------------------------------------
# Sequential mode must be untouched
# ---------------------------------------------------------------------------

class TestSequentialModeUnaffected:
    def test_single_agent_run_still_completes(self, monkeypatch):
        node = _node(SHEETS, "Solo", "answers directly")
        graph = RuntimeGraph(
            orchestration_id="orch1", main_agent_id=SHEETS, nodes={SHEETS: node},
            adjacency={}, reverse_adjacency={}, edge_types={}, edge_labels={},
            join_points=set(), hub_nodes=set(), has_parallel_branches=False,
            max_depth=5, max_visits_per_agent=3,
        )
        sched, run_col = _scheduler(graph)
        monkeypatch.setattr(AgentInvoker, "invoke",
                            lambda self, n, t, history=None, **_: ("Hi there!", [_tool_record("greet")]))

        assert sched.run("hello") == "Hi there!"
        assert run_col.latest()["status"] == RunStatus.COMPLETE.value

    def test_mode_defaults_to_sequential_everywhere(self):
        graph = RuntimeGraph(
            orchestration_id="o", main_agent_id="a", nodes={},
            adjacency={}, reverse_adjacency={}, edge_types={}, edge_labels={},
            join_points=set(), hub_nodes=set(), has_parallel_branches=False, max_depth=5,
        )
        assert graph.mode == "sequential" and not graph.is_supervised

    def test_sequential_nodes_get_no_handback_prompt(self):
        assert _node(SHEETS, "A", "d").handback_prompt == ""


# ---------------------------------------------------------------------------
# Blocked handbacks — "my tools failed" must not be treated as "not my domain"
# ---------------------------------------------------------------------------

class TestBlockedHandback:
    def test_blocked_agent_is_not_excluded_and_the_failure_is_reported(self, monkeypatch):
        """Regression for the worst observed failure: HR's SQL errored, HR handed
        back, HR got excluded, and the Supervisor eventually handed a database
        question to the Gmail agent — which answered from the user's mailbox.

        A blocked agent keeps the work and its failure becomes the result.
        """
        graph = _graph([_node(HR, "HR", "employee records"), _node(GMAIL, "Gmail", "email")])
        sched, run_col = _scheduler(graph)
        offered = []

        def decide(self, nodes, message, excluded_agent_ids=None, completed_steps=None, **_kw):
            offered.append(list(excluded_agent_ids or ()))
            if completed_steps:
                return RouteDecision(action="finish", reason="reported the failure")
            return RouteDecision(action="route", target_agent_id=HR, agent_input=message)

        monkeypatch.setattr(SupervisorAgent, "decide", decide)
        monkeypatch.setattr(
            AgentInvoker, "invoke",
            lambda self, n, t, history=None, **_: (
                '{"handback": true, "kind": "blocked", "reason": "HR.DepartmentMaster is missing"}',
                [_tool_record("query_db")],
            ),
        )

        result = sched.run("list the AI engineers")

        # HR was never excluded, so Gmail was never offered the DB question.
        assert all(HR not in excluded for excluded in offered)
        assert "HR" in result and "missing" in result
        path = run_col.latest()["execution_path"]
        assert [e["agent_id"] for e in path] == [HR]
        assert path[0]["status"] == "complete"   # a reported failure, not a hidden transfer

    def test_blocked_via_exception_carries_the_kind(self, monkeypatch):
        graph = _graph([_node(HR, "HR", "employee records")])
        sched, _ = _scheduler(graph)

        def decide(self, nodes, message, completed_steps=None, **_kw):
            if completed_steps:
                return RouteDecision(action="finish", reason="done")
            return RouteDecision(action="route", target_agent_id=HR, agent_input=message)

        monkeypatch.setattr(SupervisorAgent, "decide", decide)

        def invoke(self, node, task, history=None, **_):
            raise SupervisorHandbackException("connection dropped", kind=KIND_BLOCKED)
        monkeypatch.setattr(AgentInvoker, "invoke", invoke)

        assert "connection dropped" in sched.run("list the AI engineers")

    def test_declines_never_cascade_onto_an_unrelated_agent(self, monkeypatch):
        """`max_consecutive_handbacks=2` stops the cascade at the second decline.
        The third attempt is what reached an unrelated agent in production."""
        graph = _graph(
            [_node(HR, "HR", "hr"), _node(TIME_TRACE, "TimeTrace", "time"), _node(GMAIL, "Gmail", "email")],
            max_bounces=2,
        )
        sched, _ = _scheduler(graph)
        invoked = []

        def invoke(self, node, task, history=None, **_):
            invoked.append(node.agent_id)
            return '{"handback": true, "reason": "not mine"}', []
        monkeypatch.setattr(AgentInvoker, "invoke", invoke)
        monkeypatch.setattr(
            SupervisorAgent, "decide", _route_skipping_declined(HR, TIME_TRACE, GMAIL),
        )

        sched.run("something nobody owns")

        # The email agent is never handed a request two data agents declined.
        assert GMAIL not in invoked


# ---------------------------------------------------------------------------
# The Supervisor routes; it does not answer, and it does not dead-end
# ---------------------------------------------------------------------------

class TestSupervisorStaysInItsLane:
    def test_a_specialist_question_answered_directly_is_sent_back_to_route(self, monkeypatch):
        """The Supervisor has no tools and no data, so answering a question that
        belongs to an agent produces a guess in an authoritative voice."""
        graph = _graph([_node(HR, "HR", "employee leave and holiday records")])
        sched, _ = _scheduler(graph)
        forced_calls = []

        def decide(self, nodes, message, force_assignment=False, completed_steps=None, **_kw):
            if completed_steps:
                return RouteDecision(action="finish", reason="answered")
            if force_assignment:
                forced_calls.append(message)
                return RouteDecision(action="route", target_agent_id=HR, agent_input=message)
            return RouteDecision(action="finish", final_response="You have 20 days.")

        monkeypatch.setattr(SupervisorAgent, "decide", decide)
        monkeypatch.setattr(AgentInvoker, "invoke",
                            lambda self, n, t, history=None, **_: ("12 days.", [_tool_record()]))

        assert sched.run("how much leave do I have?") == "12 days."
        assert forced_calls, "should have been told to route instead of answering"

    def test_small_talk_still_gets_a_direct_answer(self, monkeypatch):
        """The guard keys on domain overlap, so greetings pass straight through
        — otherwise every 'hi' would be forced onto some agent."""
        graph = _graph([_node(HR, "HR", "employee leave and holiday records")])
        sched, _ = _scheduler(graph)

        monkeypatch.setattr(
            SupervisorAgent, "decide",
            lambda self, nodes, message, force_assignment=False, **_kw: (
                pytest.fail("small talk must not be forced onto an agent")
                if force_assignment else
                RouteDecision(action="finish", final_response="Hello! How can I help?")
            ),
        )
        monkeypatch.setattr(AgentInvoker, "invoke",
                            lambda self, n, t, history=None, **_: pytest.fail("no agent should run"))

        assert sched.run("hi there") == "Hello! How can I help?"

    @pytest.mark.parametrize("scenario,is_error", [
        ("hop_limit", False),     # ran out of steps, but with work to report
        ("all_declined", False),  # forced agent still declined — reported as blocked
        ("stale_agent", True),    # genuine fault
    ])
    def test_no_path_leaves_the_user_with_a_dead_run(self, scenario, is_error, monkeypatch):
        """Every way a supervisor turn can run out of road ends COMPLETE with
        something to read. `error_context` is written only for real faults, so
        ops can still tell a fault from an orderly stop."""
        graph = _graph([_node(TIME_TRACE, "A", "a"), _node(HR, "B", "b")],
                       max_hops=2, max_bounces=1)
        sched, run_col = _scheduler(graph)

        if scenario == "stale_agent":
            monkeypatch.setattr(
                SupervisorAgent, "decide",
                lambda self, nodes, message, **_kw: RouteDecision(
                    action="route", target_agent_id="deadbeefdeadbeefdeadbeef", agent_input=message),
            )
        else:
            monkeypatch.setattr(
                SupervisorAgent, "decide",
                lambda self, nodes, message, **_kw: RouteDecision(
                    action="route", target_agent_id=TIME_TRACE, agent_input=message),
            )
            monkeypatch.setattr(
                AgentInvoker, "invoke",
                lambda self, n, t, history=None, **_: (
                    ('{"handback": true, "reason": "nope"}', [])
                    if scenario == "all_declined" else ("thinking...", [_tool_record()])
                ),
            )

        result = sched.run("something hard")
        final = run_col.latest()

        assert final["status"] == RunStatus.COMPLETE.value
        assert result.strip(), "the user must always get something to read"
        assert bool(final.get("error_context")) is is_error


# ---------------------------------------------------------------------------
# Agent input shape — history as turns, not a pasteable transcript
# ---------------------------------------------------------------------------

class TestAgentInput:
    def test_agent_gets_chat_history_and_a_clean_task(self, monkeypatch):
        """Passing the rendered "[user]: ..." log as the task made a Gmail agent
        paste internal role tags into a real email. History goes in as turns."""
        graph = _graph([_node(GMAIL, "Gmail", "email")])
        sched, _ = _scheduler(graph)
        seen = {}

        def decide(self, nodes, message, completed_steps=None, **_kw):
            if completed_steps:
                return RouteDecision(action="finish", reason="done")
            return RouteDecision(action="route", target_agent_id=GMAIL, agent_input="send the report")

        def invoke(self, node, task, history=None, **_):
            seen["task"] = task
            seen["history"] = history
            return "sent", [_tool_record("gmail_send")]

        monkeypatch.setattr(SupervisorAgent, "decide", decide)
        monkeypatch.setattr(AgentInvoker, "invoke", invoke)
        sched.run("email it to Bilal")

        assert seen["task"] == "send the report"
        assert "[user]:" not in seen["task"]
        assert seen["history"], "prior turns must reach the agent as history"
        assert all(m["role"] in ("user", "assistant") for m in seen["history"])
        assert all("[Supervisor]:" not in m["content"] for m in seen["history"])

    def test_memory_bus_renders_turns_without_role_tags(self):
        bus = MemoryBus({"run_id": "r", "session_id": "s", "user_id": "u",
                         "organization_id": "o", "memory_log": []}, _FakeSyncDb(None), "m")
        bus.append_user("how many employees?")
        bus.append_agent("HR ONE", "There are 30.")

        messages = bus.get_messages()
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "how many employees?"
        assert messages[1]["content"] == "HR ONE: There are 30."
        # The document form still exists for the Supervisor's own synthesis.
        assert "[user]:" in bus.get_context()


# ---------------------------------------------------------------------------
# Churn guards
# ---------------------------------------------------------------------------

class TestChurnGuards:
    def test_synthesis_keys_on_distinct_agents_not_step_count(self, monkeypatch):
        """One agent called twice is not a multi-agent turn — synthesising its
        own two answers together was pure waste."""
        graph = _graph([_node(GMAIL, "Gmail", "email")])
        sched, _ = _scheduler(graph)
        calls = {"n": 0}

        def decide(self, nodes, message, completed_steps=None, **_kw):
            if len(completed_steps or []) < 2:
                return RouteDecision(action="route", target_agent_id=GMAIL, agent_input=message)
            return RouteDecision(action="finish", reason="both sent")

        def invoke(self, node, task, history=None, **_):
            calls["n"] += 1
            return f"sent #{calls['n']}", [_tool_record("gmail_send")]

        monkeypatch.setattr(SupervisorAgent, "decide", decide)
        monkeypatch.setattr(AgentInvoker, "invoke", invoke)
        monkeypatch.setattr(
            SupervisorAgent, "synthesize",
            lambda self, ctx: pytest.fail("single-agent turn must not synthesize"),
        )

        assert sched.run("email Alice then Bob") == "sent #2"
        assert calls["n"] == 2

    def test_repeat_visit_with_no_tool_calls_finishes(self, monkeypatch):
        """An agent re-routed and producing only prose made no progress — burning
        further hops on it is the churn pattern."""
        graph = _graph([_node(GMAIL, "Gmail", "email")])
        sched, _ = _scheduler(graph)
        calls = {"n": 0}

        def invoke(self, node, task, history=None, **_):
            calls["n"] += 1
            if calls["n"] == 1:
                return "sent", [_tool_record("gmail_send")]
            return "Anything else?", []          # no tools on the revisit

        monkeypatch.setattr(AgentInvoker, "invoke", invoke)
        monkeypatch.setattr(
            SupervisorAgent, "decide",
            lambda self, nodes, message, **_kw: RouteDecision(
                action="route", target_agent_id=GMAIL, agent_input=message),
        )

        assert sched.run("email it") == "sent"
        assert calls["n"] == 2                    # stopped instead of looping to max_hops


# ---------------------------------------------------------------------------
# GraphLoader — what the two modes each build
# ---------------------------------------------------------------------------

class _FakeCursor(list):
    pass


class _FakeAgentsCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query):
        wanted = {str(oid) for oid in query.get("_id", {}).get("$in", [])}
        return _FakeCursor([d for aid, d in self._docs.items() if aid in wanted])


class _FakeLoaderDb:
    def __init__(self, agent_docs):
        self.agents = _FakeAgentsCollection(agent_docs)
        self.tools = SimpleNamespace(find=lambda q: _FakeCursor())
        self.db_connections = SimpleNamespace(find=lambda q: _FakeCursor())


def _agent_doc(agent_id, name, description):
    return {"_id": agent_id, "name": name, "description": description,
            "prompt": f"You are {name}.", "tool_ids": [], "connector_ids": []}


class TestGraphLoader:
    @pytest.fixture(autouse=True)
    def _no_mcp(self, monkeypatch):
        monkeypatch.setattr("ai.multi_orchestration.graph_loader.load_agent_mcp_tools_sync",
                            lambda agent_id: ([], {}, {}))

    def test_supervisor_mode_builds_a_flat_roster(self):
        from ai.multi_orchestration.graph_loader import GraphLoader

        docs = {TIME_TRACE: _agent_doc(TIME_TRACE, "TimeTrace", "time"),
                HR: _agent_doc(HR, "HR", "leave")}
        snapshot = {
            "_id": "orch1", "mode": "supervisor", "sub_agent_ids": list(docs),
            "supervisor_config": {"max_hops": 4, "max_visits_per_agent": 2,
                                  "max_consecutive_handbacks": 1,
                                  "custom_instructions": "prefer HR for people questions"},
        }
        graph = GraphLoader(snapshot, _FakeLoaderDb(docs), organization_id="org1").load()

        assert graph.mode == "supervisor" and graph.is_supervised
        assert graph.main_agent_id is None
        assert graph.adjacency == {} and graph.join_points == set()
        assert set(graph.nodes) == set(docs)
        assert (graph.supervisor_max_hops, graph.max_visits_per_agent,
                graph.supervisor_max_consecutive_handbacks) == (4, 2, 1)
        assert graph.supervisor_instructions == "prefer HR for people questions"
        for node in graph.nodes.values():
            # Without this block a routed agent loses "prior output is your input"
            # and "actually send, do not draft".
            assert "handback" in node.handback_prompt.lower()
            assert "YOUR INPUT" in node.handback_prompt
            assert not node.next_agents

    def test_sequential_mode_is_unchanged(self):
        from ai.multi_orchestration.graph_loader import GraphLoader

        docs = {TIME_TRACE: _agent_doc(TIME_TRACE, "A", "d")}
        snapshot = {"_id": "orch1", "main_agent_id": TIME_TRACE,
                    "sub_agent_ids": [TIME_TRACE], "connections": []}
        graph = GraphLoader(snapshot, _FakeLoaderDb(docs), organization_id="org1").load()

        assert graph.mode == "sequential" and not graph.is_supervised
        assert graph.main_agent_id == TIME_TRACE
        assert graph.nodes[TIME_TRACE].handback_prompt == ""

    def test_missing_mode_field_reads_as_sequential(self):
        """Documents written before supervisor mode existed have no `mode` key."""
        from ai.multi_orchestration.graph_loader import GraphLoader

        docs = {TIME_TRACE: _agent_doc(TIME_TRACE, "A", "d")}
        graph = GraphLoader(
            {"_id": "o", "main_agent_id": TIME_TRACE, "sub_agent_ids": [TIME_TRACE], "connections": []},
            _FakeLoaderDb(docs), organization_id="org1",
        ).load()
        assert graph.mode == "sequential"


# ---------------------------------------------------------------------------
# Sticky candidate selection (executor) — which agent the next turn tries first
# ---------------------------------------------------------------------------

class TestStickyCandidate:
    @staticmethod
    def _prior(*entries):
        return {"execution_path": list(entries)}

    @staticmethod
    def _snapshot(sticky=True, attached=(TIME_TRACE, HR)):
        return {"sub_agent_ids": list(attached),
                "supervisor_config": {"sticky_routing": sticky}}

    def test_last_successful_agent_becomes_the_seed(self):
        from ai.multi_orchestration.executor import _sticky_candidate
        prior = self._prior({"agent_id": TIME_TRACE, "status": "complete"})
        assert _sticky_candidate(self._snapshot(), prior) == [TIME_TRACE]

    def test_supervisor_sentinel_is_never_the_seed(self):
        """A turn the Supervisor answered directly ends with a __supervisor__
        entry, which is not a graph node — seeding it would fail the lookup."""
        from ai.multi_orchestration.executor import _sticky_candidate
        prior = self._prior(
            {"agent_id": TIME_TRACE, "status": "complete"},
            {"agent_id": SUPERVISOR_AGENT_ID, "status": "complete"},
        )
        assert _sticky_candidate(self._snapshot(), prior) == [TIME_TRACE]

    def test_handback_entries_are_skipped(self):
        from ai.multi_orchestration.executor import _sticky_candidate
        prior = self._prior({"agent_id": HR, "status": "handback"})
        assert _sticky_candidate(self._snapshot(), prior) is None

    def test_detached_agent_is_not_seeded(self):
        from ai.multi_orchestration.executor import _sticky_candidate
        prior = self._prior({"agent_id": SHEETS, "status": "complete"})
        assert _sticky_candidate(self._snapshot(attached=(TIME_TRACE, HR)), prior) is None

    def test_sticky_can_be_turned_off(self):
        from ai.multi_orchestration.executor import _sticky_candidate
        prior = self._prior({"agent_id": TIME_TRACE, "status": "complete"})
        assert _sticky_candidate(self._snapshot(sticky=False), prior) is None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TestSchemas:
    def test_defaults_to_sequential(self):
        payload = OrchestrationCreate(name="t", main_agent_id="a1", sub_agent_ids=["a1"])
        assert payload.mode == "sequential" and payload.supervisor_config is None

    def test_supervisor_mode_needs_no_main_agent(self):
        payload = OrchestrationCreate(name="t", mode="supervisor", sub_agent_ids=["a1", "a2"])
        assert payload.main_agent_id is None

    def test_config_defaults_and_bounds(self):
        cfg = SupervisorConfig()
        assert (cfg.max_hops, cfg.max_consecutive_handbacks, cfg.sticky_routing) == (6, 2, True)
        for bad in (0, 100):
            with pytest.raises(Exception):
                SupervisorConfig(max_hops=bad)
