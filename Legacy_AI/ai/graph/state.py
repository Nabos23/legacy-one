from typing import Optional, TypedDict


class AgentState(TypedDict):
    user_query:        str
    agent_summaries:   list          # [{_id, name, description, guardrails?}, ...]
    user_id:           str
    organization_id:   str
    routed_to:         Optional[str] # agent_id chosen by router, None → direct
    excluded:          list          # agent_ids ruled out this turn (out-of-scope)
    reply:             str           # reply ready to show the user
    answered:          bool          # True when reply is ready for interrupt
    last_agent_name:   str           # display name of agent that produced the reply
    last_agent_id:     Optional[str] # agent_id, None when MainAgent answered directly
    messages:          list          # sliding window of turn dicts (role, agent_name, user_query, content)
    interaction_count: int           # incremented each completed turn; drives summariser trigger
    memory_summary:    str           # compressed summary produced by Summarizer_Agent
