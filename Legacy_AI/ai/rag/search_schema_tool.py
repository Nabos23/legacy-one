"""
Synthetic tool definition and executor for search_schema.

This tool is never stored in MongoDB — it is injected at runtime into any
agent that already has at least one DB tool (identified by db_conn_id).
The graph's _execute_tool detects the _is_search_schema flag and routes here.
"""

from ai.rag.schema_retriever import get_relevant_schema_sync


def build_search_schema_tool(org_id: str, db_conn_ids: list[str]) -> dict:
    """
    Return a synthetic tool doc that matches the shape real tool docs have,
    so AgentRuntime and _build_agent_node handle it without any special-casing.

    db_conn_ids is baked in so the agent never needs to know about tenancy.
    """
    return {
        "name": "search_schema",
        "description": (
            "Search the connected database schema to find relevant tables and columns. "
            "ALWAYS call this tool first before calling any query_db tool, "
            "so you know the exact table names and column names to use."
        ),
        "db_conn_id": None,
        "_is_search_schema": True,
        "_org_id": org_id,
        "_db_conn_ids": db_conn_ids,
    }


async def execute_search_schema(tool_doc: dict, args: dict) -> str:
    """Thin async wrapper — the actual work is `execute_search_schema_sync`
    below, the exact same code the ai/multi_orchestration engine calls
    directly. Running it here via `run_in_threadpool` means there is only
    ever one search_schema executor, whichever engine is asking."""
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(execute_search_schema_sync, tool_doc, args)


def execute_search_schema_sync(tool_doc: dict, args: dict) -> str:
    """Sync counterpart of `execute_search_schema` for the ai/multi_orchestration
    engine, which calls tool callables synchronously (see ai/agents/loop.py)."""
    query = args.get("query", "").strip()
    db_conn_ids: list[str] = tool_doc.get("_db_conn_ids", [])
    org_id: str = tool_doc.get("_org_id", "")

    if not query:
        return "Provide a query describing what data you are looking for."
    if not db_conn_ids:
        return "No database connections are configured for this agent."

    return get_relevant_schema_sync(query=query, db_conn_ids=db_conn_ids, org_id=org_id)
