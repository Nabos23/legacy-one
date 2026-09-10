"""Synthetic tool definition and executor for search_knowledge_base.

Never stored in MongoDB — injected at runtime into any agent whose
`rag_ids` is non-empty, the same way ai/rag/search_schema_tool.py injects
search_schema for agents with a db_conn_id. The graph's _execute_tool
detects the `_is_kb_search` flag and routes here.
"""

from ai.rag.kb_retriever import search_knowledge_base, search_knowledge_base_sync


def build_kb_search_tool(org_id: str, kb_ids: list[str]) -> dict:
    """Return a synthetic tool doc, in the same shape real tool docs have, so
    AgentRuntime / _build_agent_node handle it without special-casing.

    kb_ids is baked in so the agent never needs to know which KBs it may see.
    """
    return {
        "name": "search_knowledge_base",
        "description": (
            "Search the organization's uploaded documents (policies, procedures, "
            "reference material) for information relevant to the user's question. "
            "Call this whenever the user asks about company knowledge that isn't "
            "part of your own instructions."
        ),
        "_is_kb_search": True,
        "_org_id": org_id,
        "_kb_ids": kb_ids,
    }


async def execute_kb_search(tool_doc: dict, args: dict, history: list[dict] | None = None) -> str:
    """Thin async wrapper — see search_schema_tool.execute_search_schema for
    why this stays a run_in_threadpool wrapper around the one sync impl."""
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(execute_kb_search_sync, tool_doc, args, history)


def execute_kb_search_sync(tool_doc: dict, args: dict, history: list[dict] | None = None) -> str:
    """Sync counterpart for the ai/multi_orchestration engine's tool-callable loop."""
    query = (args.get("query") or "").strip()
    kb_ids: list[str] = tool_doc.get("_kb_ids", [])
    org_id: str = tool_doc.get("_org_id", "")

    if not query:
        return "Provide a query describing what information you are looking for."
    if not kb_ids:
        return "No knowledge bases are configured for this agent."

    return search_knowledge_base_sync(query=query, org_id=org_id, kb_ids=kb_ids, history=history)
