"""Shared Langfuse tag helpers — single source of truth for org/agent tagging."""


def org_tag(org_id: str) -> str:
    return f"org:{org_id}"


def agent_tag(agent_name: str) -> str:
    return "agent:" + agent_name.lower().replace(" ", "_")
