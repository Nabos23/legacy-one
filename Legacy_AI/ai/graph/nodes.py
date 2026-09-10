import json
import logging

from langgraph.types import interrupt

from ai.agents.sub_agent import SubAgent, _completion_with_retry, _dump_agent_memory
from ai.memory.memory_schema import MemorySchema

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scope check — only thing that lives here; routing belongs to MainAgent
# ---------------------------------------------------------------------------
_SCOPE_SYSTEM = (
    "You are a scope checker. Decide if a user message is within an agent's domain. "
    "Short follow-ups like 'yes', 'ok', 'correct', 'no', 'thanks' that continue an "
    "existing conversation with this agent are always considered in-scope. "
    "Reply with only 'yes' or 'no'."
)


def _is_in_scope(query: str, agent_doc: dict, model: str, history: list = None) -> bool:
    name        = agent_doc.get("name", "agent")
    description = agent_doc.get("description", "")
    guardrails  = agent_doc.get("guardrails", [])

    history_block = ""
    if history:
        lines = []
        for e in history[-3:]:
            lines.append(f"  User: {e.user_query}")
            lines.append(f"  {e.agent_name}: {e.agents_output[:200]}")
        history_block = "Recent conversation with this agent:\n" + "\n".join(lines) + "\n\n"

    prompt = (
        f"Agent: {name}\n"
        f"Description: {description}\n"
        f"Guardrails: {'; '.join(guardrails)}\n\n"
        f"{history_block}"
        f'Current user message: "{query}"\n\n'
        "Is this message in-scope for this agent?\n"
        "Answer YES if:\n"
        "  - The message is about this agent's domain, OR\n"
        "  - The message is a short follow-up / confirmation (yes, ok, no, correct, etc.) "
        "that continues the conversation shown above.\n"
        "Answer NO only if the message is clearly about a completely different domain.\n"
        "Reply with only yes or no."
    )
    try:
        response = _completion_with_retry(
            model=model,
            messages=[
                {"role": "system", "content": _SCOPE_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=5,
        )
        return response.choices[0].message.content.strip().lower().startswith("y")
    except Exception:
        return True  # assume in-scope if check fails


# ---------------------------------------------------------------------------
# Node factory
# ---------------------------------------------------------------------------
def make_nodes(db, memory, model: str, main_agent, mongo_store=None):
    _sub_cache: dict = {}

    # ------------------------------------------------------------------
    # 1. Router — delegates entirely to MainAgent._route()
    #    Single source of truth for routing logic: prompt, guardrails,
    #    exclusion, and ID validation all live in MainAgent.
    #    Also opens a Langfuse trace for this turn (one trace per user turn,
    #    closed in human_interrupt_node before yielding the reply).
    # ------------------------------------------------------------------
    def router_node(state):
        main_agent._tracer.start_trace(
            "graph.turn",
            input={"query": state["user_query"]},
        )

        excluded = list(state.get("excluded", []))
        # Last 3 memory entries give the router conversation context so that
        # short follow-ups ("yes", "ok", "more") stay with the right agent.
        history  = memory.get_memory_by_user(state["user_id"])[-3:]
        routed_to = main_agent._route(
            state["user_query"],
            excluded=excluded,
            history=history,
            memory_summary=state.get("memory_summary", ""),
        )
        return {"routed_to": routed_to, "answered": False}

    # ------------------------------------------------------------------
    # 2. Sub-agent — scope check + invoke (NO interrupt here)
    # ------------------------------------------------------------------
    def sub_agent_node(state):
        agent_id = state["routed_to"]

        if agent_id not in _sub_cache:
            sub = SubAgent(
                agent_id=agent_id,
                db=db,
                model=model,
                memory=memory,
                tracer=main_agent._tracer,
                mongo_store=mongo_store,
            )
            sub.load_agent()
            sub.load_tools()
            sub.load_mcp_servers()
            sub.load_connectors(user_id=state["user_id"], organization_id=state["organization_id"])
            sub.load_rag_tools(user_id=state["user_id"], organization_id=state["organization_id"])
            _sub_cache[agent_id] = sub
        sub = _sub_cache[agent_id]

        # Pass recent conversation with THIS agent so confirmations ("yes", "ok")
        # are correctly judged as in-scope follow-ups, not standalone queries.
        agent_history = memory.get_memory_by_session(
            user_id=state["user_id"], agent_id=agent_id
        )[-3:]
        if not _is_in_scope(state["user_query"], sub._doc, model, history=agent_history):
            logger.info("Query out of scope for '%s' — re-routing", sub.name)
            return {
                "excluded":  state.get("excluded", []) + [agent_id],
                "routed_to": None,
                "answered":  False,
            }

        # Tag the root trace with this agent's identity so Langfuse filtering
        # (per-agent trace views, /api/agents/{id}/traces) works correctly.
        main_agent._tracer.tag_agent(agent_id, sub.name)

        # --- PRE-INVOKE MEMORY DUMP ---
        pre_invoke_memory = memory.get_memory_by_session(
            user_id=state["user_id"], agent_id=agent_id
        )
        logger.info(
            "[nodes:sub_agent_node] PRE-INVOKE MEMORY for '%s' — %d entries\n%s",
            sub.name, len(pre_invoke_memory),
            json.dumps(
                [e.model_dump() if hasattr(e, "model_dump") else e.dict() for e in pre_invoke_memory],
                indent=2, default=str,
            ),
        )
        _dump_agent_memory(pre_invoke_memory, f"{sub.name.lower().replace(' ', '_')}_pre_invoke_node")
        # --- END PRE-INVOKE MEMORY DUMP ---

        reply = sub.invoke(
            query=state["user_query"],
            user_id=state["user_id"],
            organization_id=state["organization_id"],
            memory_summary=state.get("memory_summary", ""),
        )

        return {
            "reply":           reply,
            "last_agent_name": sub.name,
            "last_agent_id":   agent_id,
            "answered":        True,
            "routed_to":       agent_id,
        }

    # ------------------------------------------------------------------
    # 3. Direct answer — delegates to MainAgent._answer_directly()
    # ------------------------------------------------------------------
    def direct_answer_node(state):
        reply = main_agent._answer_directly(
            state["user_query"],
            memory_summary=state.get("memory_summary", ""),
        )

        return {
            "reply":           reply,
            "last_agent_name": "MainAgent",
            "last_agent_id":   None,
            "answered":        True,
            "routed_to":       None,
        }

    # ------------------------------------------------------------------
    # 4. Human interrupt — closes the Langfuse trace for this turn, then
    #    yields control back to the caller via interrupt().
    #    On resume, returns the next query so the graph re-enters router_node
    #    which opens a fresh trace for the new turn.
    # ------------------------------------------------------------------
    def human_interrupt_node(state):
        main_agent._tracer.end_trace(
            output={
                "reply": state["reply"],
                "agent": state["last_agent_name"],
            }
        )

        # Record this completed turn in the sliding message window and bump counter.
        turn_message = {
            "role":       "turn",
            "agent_name": state.get("last_agent_name", "Agent"),
            "user_query": state["user_query"],
            "content":    state["reply"],
        }
        updated_messages = list(state.get("messages", [])) + [turn_message]
        updated_count    = state.get("interaction_count", 0) + 1

        next_query = interrupt({
            "reply":     state["reply"],
            "agent":     state["last_agent_name"],
            "routed_to": state.get("last_agent_id"),
        })
        return {
            "user_query":        next_query,
            "answered":          False,
            "excluded":          [],
            "routed_to":         None,
            "messages":          updated_messages,
            "interaction_count": updated_count,
        }

    # ------------------------------------------------------------------
    # 5. Long-term memory — writes the just-completed turn to MongoDB.
    #    Runs in parallel with router and summarizer after human_interrupt.
    #    Uses messages[-1] (appended by human_interrupt_node) to recover
    #    the previous turn's user_query + reply without touching state schema.
    # ------------------------------------------------------------------
    def long_term_memory_node(state):
        if not mongo_store:
            return {}
        messages = state.get("messages", [])
        if not messages:
            return {}
        last_msg = messages[-1]
        if last_msg.get("role") != "turn":
            return {}
        entry = MemorySchema(
            user_id=state["user_id"],
            organization_id=state["organization_id"],
            agent_id=state.get("last_agent_id") or "main",
            agent_name=last_msg.get("agent_name", "Agent"),
            user_query=last_msg.get("user_query", ""),
            agents_output=last_msg.get("content", ""),
        )
        mongo_store.write(entry)
        return {}

    # ------------------------------------------------------------------
    # 6. Dispatch — no-op fan-in join.
    #    Waits for router + long_term_memory + summarizer to all complete,
    #    then applies the routing decision already sitting in state.
    # ------------------------------------------------------------------
    def dispatch_node(state):
        return {}

    return (
        router_node,
        sub_agent_node,
        direct_answer_node,
        human_interrupt_node,
        long_term_memory_node,
        dispatch_node,
    )
