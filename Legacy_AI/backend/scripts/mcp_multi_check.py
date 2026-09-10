"""
Verify: an agent can have MULTIPLE MCP servers, all sourced from the 'Custom MCP'
tool_registry entry, and all of their tools become available to the agent at
runtime (exactly like the agent's tools).

  register -> create agent -> attach 2 MCP servers (fetch + time) ->
  show mcp_servers docs (same agent_id), agent.mcp_server_ids (2 ids),
  then load the agent runtime and list the tools it actually sees.

Usage:
    uv run python -m backend.scripts.mcp_multi_check
"""

import asyncio
import uuid

from dotenv import load_dotenv

load_dotenv()

# Multiple distinct MCP servers on ONE agent. Each contributes its own tool(s).
SERVERS = [
    ("uvx mcp-server-fetch", "Fetch a URL and return its content as markdown."),
    ("uvx mcp-server-time", "Get the current time / convert between timezones."),
    ("npx -y @modelcontextprotocol/server-memory", "Persistent knowledge-graph memory."),
]


async def main() -> None:
    from bson import ObjectId
    from httpx import ASGITransport, AsyncClient

    from backend.chat.services import _load_org_agents
    from backend.db.database import (
        DATABASE_NAME,
        agents_collection,
        mcp_servers_collection,
    )
    from backend.main import app

    # This check uses the custom bring-your-own flow (Flow B): raw connection
    # strings, no mcp_server_registry lookup needed.
    print(f"DB={DATABASE_NAME}  (custom connection_string flow)\n")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120.0) as ac:
        email = f"multi+{uuid.uuid4().hex[:8]}@test.example.com"
        r = await ac.post("/auth/register", json={"name": "Multi", "email": email, "password": "Password123"})
        r.raise_for_status()
        data = r.json()
        ac.headers["Authorization"] = f"Bearer {data['access_token']}"
        org_id = data["user"]["organization_id"]

        r = await ac.post("/agents", json={
            "organization_id": org_id, "name": "Multi-MCP Agent",
            "prompt": "You use your tools to fetch web pages and tell the time.", "guardrails": "",
        })
        r.raise_for_status()
        agent_id = r.json()["id"]
        print(f"agent _id={agent_id}\n")

        # Attach BOTH MCP servers to the SAME agent — each a raw connection string.
        for conn, desc in SERVERS:
            r = await ac.post("/mcp-servers", json={
                "organization_id": org_id, "agent_id": agent_id,
                "connection_string": conn, "user_description": desc, "timeout": 90.0,
            })
            if r.status_code != 201:
                print(f"  attach '{conn}' FAILED ({r.status_code}): {r.text[:160]}")
                continue
            b = r.json()
            print(f"  attached '{conn}' -> instance {b['id']}  tools={[t['name'] for t in b['tools']]}")

        # 1) mcp_servers collection: the connection records (one per server).
        print("\n--- mcp_servers docs (connections) for this agent ---")
        async for d in mcp_servers_collection.find({"agent_id": agent_id, "is_deleted": {"$ne": True}}):
            print(f"  _id={d['_id']}  conn='{d['connection_string']}'  discovered={[t['name'] for t in d.get('tools', [])]}")

        # 2) agent.mcp_server_ids: the link array — one id per attached server,
        #    exactly like agent.tool_ids holds one id per attached tool.
        ag = await agents_collection.find_one({"_id": ObjectId(agent_id)})
        print(f"\n--- agent.mcp_server_ids ---\n  {ag.get('mcp_server_ids')}")

        # 4) Runtime: the agent actually sees the tools from BOTH servers.
        runtimes = await _load_org_agents(org_id)
        rt = next(r for r in runtimes if r.agent_id == agent_id)
        mcp_tools = [t["name"] for t in rt.tools if t.get("_is_mcp")]
        print(f"\n--- AgentRuntime.tools (what the live agent sees) ---")
        print(f"  total tools={len(rt.tools)}  mcp tools={mcp_tools}")


if __name__ == "__main__":
    asyncio.run(main())
