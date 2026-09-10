from langgraph.graph import START, StateGraph

from ai.agents.summarizer.agent import Summarizer_Agent
from ai.graph.nodes import make_nodes
from ai.graph.state import AgentState
from ai.memory.mongo_store import MongoMemoryStore


def build_graph(db, memory, model: str, main_agent, checkpointer=None):
    """
    Build and compile the agent graph.

    checkpointer:
      - Pass a MemorySaver (or other checkpointer) when running via FastAPI
        so multi-turn conversations survive across HTTP requests.
      - Leave as None when running inside LangGraph Studio / LangGraph API —
        the platform manages persistence automatically and rejects graphs
        that bring their own checkpointer.
    """
    mongo_store = MongoMemoryStore(db, tracer=main_agent._tracer)
    # Inject the persistent store into main_agent so _answer_directly can write to it.
    main_agent._mongo_store = mongo_store

    summarizer = Summarizer_Agent(model=model, tracer=main_agent._tracer)

    (
        router_node,
        sub_agent_node,
        direct_answer_node,
        human_interrupt_node,
        long_term_memory_node,
        dispatch_node,
    ) = make_nodes(db=db, memory=memory, model=model, main_agent=main_agent, mongo_store=mongo_store)

    builder = StateGraph(AgentState)

    builder.add_node("router",            router_node)
    builder.add_node("sub_agent",         sub_agent_node)
    builder.add_node("direct_answer",     direct_answer_node)
    builder.add_node("human_interrupt",   human_interrupt_node)
    builder.add_node("summarizer",        summarizer.as_node())
    builder.add_node("long_term_memory",  long_term_memory_node)
    builder.add_node("dispatch",          dispatch_node)

    # Entry point — first turn goes directly to router (no memory yet)
    builder.add_edge(START, "router")

    # Router output goes to dispatch (fan-in join for subsequent turns)
    builder.add_edge("router", "dispatch")

    # dispatch: apply routing decision from router (memory_summary already
    # refreshed by summarizer, MongoDB write already handled by long_term_memory)
    builder.add_conditional_edges(
        "dispatch",
        lambda s: "sub_agent" if s.get("routed_to") else "direct_answer",
    )

    # Sub-agent: if answered → interrupt; if out-of-scope → re-route
    # Re-routing goes directly back to router → dispatch (no new memory/summary pass)
    builder.add_conditional_edges(
        "sub_agent",
        lambda s: "human_interrupt" if s.get("answered") else "router",
    )

    # Direct answer always goes to interrupt
    builder.add_edge("direct_answer", "human_interrupt")

    # After interrupt: fan-out to three parallel branches
    #   router           — opens turn trace, decides routing
    #   long_term_memory — writes completed turn to MongoDB (off critical path)
    #   summarizer       — compresses message window when threshold met (unchanged logic)
    # All three converge at dispatch before the next agent call.
    builder.add_edge("human_interrupt",  "router")
    builder.add_edge("human_interrupt",  "long_term_memory")
    builder.add_edge("human_interrupt",  "summarizer")

    builder.add_edge("long_term_memory", "dispatch")
    builder.add_edge("summarizer",       "dispatch")

    return builder.compile(checkpointer=checkpointer) if checkpointer else builder.compile()
