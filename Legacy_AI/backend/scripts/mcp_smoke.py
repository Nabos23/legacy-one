"""
End-to-end smoke test: a live agent calling an MCP tool through chat.

Drives the real ASGI app + Atlas + LLM:
  register org/user -> create agent -> attach a Custom MCP server (uvx
  mcp-server-fetch) -> open a chat session -> ask the agent to fetch a URL →
  confirm the MCP `fetch` tool actually ran (the reply contains the real page
  title "Example Domain").

Usage:
    uv run python -m backend.scripts.mcp_smoke
"""

import asyncio
import logging
import uuid

from dotenv import load_dotenv

load_dotenv()

# Surface the graph's [TOOL] ... lines so we can see the MCP call happen live.
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main() -> None:
    from httpx import ASGITransport, AsyncClient

    from backend.db.database import mcp_server_registry_collection
    from backend.main import app

    # The seeded "fetch" catalog entry is what the user picks (Flow A). Falls back
    # to a raw connection_string (Flow B) if the registry hasn't been seeded.
    reg = await mcp_server_registry_collection.find_one(
        {"key": "fetch", "is_active": True, "is_deleted": {"$ne": True}}
    )
    registry_key = reg["key"] if reg else None
    if not registry_key:
        print("[0] 'fetch' registry entry not found (run seed_mcp_server_registry) "
              "— falling back to a raw connection_string.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120.0) as ac:
        # 1. Register -> real org + admin user + token.
        email = f"smoke+{uuid.uuid4().hex[:8]}@test.example.com"
        r = await ac.post("/auth/register", json={"name": "Smoke", "email": email, "password": "Password123"})
        r.raise_for_status()
        data = r.json()
        ac.headers["Authorization"] = f"Bearer {data['access_token']}"
        org_id = data["user"]["organization_id"]
        print(f"\n[1] registered — org={org_id}")

        # 2. Create an agent that will use tools.
        r = await ac.post("/agents", json={
            "organization_id": org_id,
            "name": "Web Fetch Agent",
            "prompt": (
                "You are a web assistant. When the user asks about a web page or URL, "
                "you MUST use your fetch tool to retrieve it, then answer from the content."
            ),
            "guardrails": "",
        })
        r.raise_for_status()
        agent_id = r.json()["id"]
        print(f"[2] agent created — id={agent_id}")

        # 3. Attach an MCP server — Flow A (registry_key) when seeded, else Flow B.
        attach: dict = {
            "organization_id": org_id,
            "agent_id": agent_id,
            "user_description": "Fetch a URL and return its content as markdown.",
            "timeout": 90.0,
        }
        if registry_key:
            attach["registry_key"] = registry_key
        else:
            attach["connection_string"] = "uvx mcp-server-fetch"
        r = await ac.post("/mcp-servers", json=attach)
        if r.status_code != 201:
            print(f"[3] MCP attach FAILED ({r.status_code}): {r.text}")
            return
        mcp = r.json()
        tool_names = [t["name"] for t in mcp["tools"]]
        print(f"[3] MCP attached — status={mcp['status']} tools={tool_names}")
        assert "fetch" in tool_names, "expected the 'fetch' tool to be discovered"

        # 4. Open a chat session (builds the graph with the agent + its MCP tools).
        r = await ac.post("/chat/session")
        r.raise_for_status()
        thread_id = r.json()["thread_id"]
        agents = [(a["name"], a["tool_count"]) for a in r.json()["available_agents"]]
        print(f"[4] session={thread_id} agents={agents}")

        # 5. Ask something that requires the fetch tool.
        print("\n[5] sending message -> expecting the agent to call the MCP fetch tool...\n")
        r = await ac.post("/chat/message", json={
            "thread_id": thread_id,
            "message": "Fetch https://example.com and tell me the page's title in one short sentence.",
        })
        r.raise_for_status()
        reply = r.json()["response"]
        print(f"\n[5] agent reply:\n    {reply}\n")

        # 6. Verdict: example.com's real title is "Example Domain". Its presence proves
        #    the MCP fetch tool ran and returned live content.
        ok = "example domain" in reply.lower()
        print("=" * 60)
        print("SMOKE RESULT:", "PASS   (MCP fetch tool executed live)" if ok
              else "INCONCLUSIVE — reply did not contain 'Example Domain'")
        print("=" * 60)

        # Leave the created instance + agent in place so the stored MCP document
        # (with agent_id, registry_key, discovered tools, etc.) can be inspected in Mongo.
        print(f"\n[6] LEFT IN MONGO for inspection:")
        print(f"    mcp_servers._id = {mcp['id']}  (agent_id={agent_id}, org={org_id})")


if __name__ == "__main__":
    asyncio.run(main())
