"""Seed the `tool_registry` collection with the built-in 'Custom MCP' tool.

The Custom MCP entry is the catalog item users pick to connect an agent to any
MCP server in the world — either by pasting a connection string or by browsing
the catalog (GET /mcp-servers/catalog). Selecting it drives the MCP-server
create flow (POST /mcp-servers), which probes the connection and caches the
server's tools so the agent can use them at query time.

Usage (from project root):
    uv run python -m backend.scripts.seed_tool_registry

Re-running is safe: the entry is upserted by `name`.
"""

from datetime import datetime, timezone

from pymongo import MongoClient

from backend.db import constants as c
from backend.db.database import DATABASE_NAME, MONGO_URL

CUSTOM_MCP = {
    "name": "Custom MCP",
    "type": "mcp",
    "description": (
        "Connect this agent to any MCP server. Provide a connection string "
        "(an http(s)/ws URL or a launcher command like "
        "'npx -y @modelcontextprotocol/server-filesystem /tmp'), or browse the "
        "catalog. The server is probed and all its tools are discovered and "
        "stored, then made available to the agent."
    ),
    "tool_schema": {
        "connection_string": {"type": "string", "required": False},
        "token": {"type": "string", "required": False},
        "catalog_key": {"type": "string", "required": False},
    },
    "is_active": True,
}


def main() -> None:
    registry = MongoClient(MONGO_URL)[DATABASE_NAME][c.TOOL_REGISTRY_COLLECTION]
    now = datetime.now(timezone.utc)

    registry.update_one(
        {"name": CUSTOM_MCP["name"]},
        {
            "$set": {
                "type": CUSTOM_MCP["type"],
                "description": CUSTOM_MCP["description"],
                "tool_schema": CUSTOM_MCP["tool_schema"],
                "is_active": CUSTOM_MCP["is_active"],
                "is_deleted": False,
            },
            "$setOnInsert": {"name": CUSTOM_MCP["name"], "created_at": now},
        },
        upsert=True,
    )
    print(f"Seeded tool_registry entry '{CUSTOM_MCP['name']}' (type=mcp).")


if __name__ == "__main__":
    main()
