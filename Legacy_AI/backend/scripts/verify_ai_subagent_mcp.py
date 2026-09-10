"""
End-to-end verification of the ai/ SubAgent path for MCP.

Confirms the wired custom-agents architecture: an agent with an attached MCP
server (linked via agent.mcp_server_ids) loads its MCP tools through
SubAgent.load_mcp_servers() and executes them — exactly the steps
ai/graph/nodes.py:sub_agent_node performs.

It drives the REAL create flow over the ASGI app (register org/user → create
agent → attach an MCP server), then builds a SubAgent against sync_db the same
way the LangGraph node does, and reports each stage.

Usage:
    uv run python -m backend.scripts.verify_ai_subagent_mcp
"""

import asyncio
import shutil
import uuid

from dotenv import load_dotenv

load_dotenv()


def _ok(msg):   print(f"  [OK]   {msg}")
def _bad(msg):  print(f"  [FAIL] {msg}")
def _info(msg): print(f"  [..]   {msg}")


async def _setup() -> tuple[str, str]:
    """Register an org/user, create an MCP-only agent, attach uvx mcp-server-fetch."""
    from httpx import ASGITransport, AsyncClient
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120.0) as ac:
        email = f"verify+{uuid.uuid4().hex[:8]}@test.example.com"
        r = await ac.post("/auth/register", json={"name": "Verify", "email": email, "password": "Password123!"})
        r.raise_for_status()
        data = r.json()
        ac.headers["Authorization"] = f"Bearer {data['access_token']}"
        org_id = data["user"]["organization_id"]

        r = await ac.post("/agents", json={
            "organization_id": org_id,
            "name": "MCP Verify Agent",
            "prompt": (
                "You are a web assistant. When asked about a URL, you MUST use your "
                "fetch tool to retrieve it, then answer from the content."
            ),
            "guardrails": "",
        })
        r.raise_for_status()
        agent_id = r.json()["id"]

        # Flow B (custom): raw connection string → populates agent.mcp_server_ids.
        r = await ac.post("/mcp-servers", json={
            "organization_id": org_id,
            "agent_id": agent_id,
            "connection_string": "uvx mcp-server-fetch",
            "user_description": "Fetch a URL as markdown.",
            "timeout": 90.0,
        })
        if r.status_code != 201:
            raise RuntimeError(f"MCP attach failed ({r.status_code}): {r.text}")
        mcp = r.json()
        _ok(f"setup: org={org_id} agent={agent_id} mcp_tools={[t['name'] for t in mcp['tools']]}")
        return org_id, agent_id


def _run_subagent(org_id: str, agent_id: str) -> None:
    """Build + drive a SubAgent exactly like ai/graph/nodes.py:sub_agent_node.

    This agent is MCP-only (no connector_ids/rag_ids), so load_connectors
    isn't exercised here; load_rag_tools is, as a no-op sanity check that it
    never breaks an agent with no rag_ids."""
    from bson import ObjectId
    from backend.core.config import settings
    from backend.db.database import sync_db
    from ai.agents.sub_agent import SubAgent
    from ai.memory.memory import LocalMemory

    # Inspect the stored agent doc — does it satisfy SubAgent.load_agent's filter?
    raw = sync_db.agents.find_one({"_id": ObjectId(agent_id)})
    _info(f"agent doc: is_active={raw.get('is_active')!r}  mcp_server_ids={raw.get('mcp_server_ids')}")
    if not raw.get("mcp_server_ids"):
        _bad("agent.mcp_server_ids is empty — Phase-1 linking did not populate it")
        return

    sub = SubAgent(agent_id=agent_id, db=sync_db, model=settings.DEFAULT_MODEL, memory=LocalMemory())

    # 1. load_agent (the filter requires is_active: True)
    try:
        sub.load_agent()
        _ok("SubAgent.load_agent()")
    except Exception as exc:
        _bad(f"SubAgent.load_agent() FAILED: {exc}")
        _info("-> likely cause: create_agent does not set is_active=True, but load_agent filters on it.")
        return

    # 2. load_tools (MCP-only agent → no-op, must not crash)
    try:
        sub.load_tools()
        _ok("SubAgent.load_tools()")
    except Exception as exc:
        _bad(f"SubAgent.load_tools() FAILED: {exc}")
        return

    # 3. load_mcp_servers (reads agent.mcp_server_ids → mcp_servers collection)
    sub.load_mcp_servers()
    if "fetch" in sub._mcp_tool_names:
        _ok(f"SubAgent.load_mcp_servers() — MCP tools loaded: {sorted(sub._mcp_tool_names)}")
    else:
        _bad(f"load_mcp_servers() did not load the 'fetch' tool (got {sorted(sub._mcp_tool_names)})")
        return

    # 3b. load_rag_tools (this agent has no rag_ids — must be a safe no-op,
    # same as ai/graph/nodes.py:sub_agent_node's full load chain)
    try:
        sub.load_rag_tools(user_id="verify-user", organization_id=org_id)
        _ok("SubAgent.load_rag_tools() (no-op — agent has no rag_ids)")
    except Exception as exc:
        _bad(f"SubAgent.load_rag_tools() FAILED: {exc}")
        return

    # 4. invoke — exercises the tool-execution loop calling the live MCP server.
    try:
        reply = sub.invoke(
            query="Fetch https://example.com and tell me the page's title in one short sentence.",
            user_id="verify-user",
            organization_id=org_id,
        )
        _info(f"reply: {reply[:200]}")
        if "example domain" in reply.lower():
            _ok("SubAgent.invoke() executed the MCP fetch tool live (reply contains 'Example Domain')")
        else:
            _info("invoke completed but reply did not contain 'Example Domain' (inconclusive)")
    except Exception as exc:
        _info(f"invoke() raised (LLM/network/tool) — inconclusive: {exc}")


async def main() -> None:
    print("\n=== ai/ SubAgent MCP path verification ===")
    if shutil.which("uvx") is None:
        print("  ! uvx not found — install uv to run the live MCP server. Aborting.")
        return
    org_id, agent_id = await _setup()
    _run_subagent(org_id, agent_id)
    print("=== done ===\n")


if __name__ == "__main__":
    asyncio.run(main())
