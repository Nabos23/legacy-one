"""Backfill the `agent_mcp_tools` junction collection from existing data.

Phase 1 of the MCP per-tool refactor replaces the old all-or-nothing
`agent.mcp_server_ids` attach with per-tool rows in `agent_mcp_tools`. This
script seeds that collection from what's already in the database, so existing
agents keep working exactly as before the refactor (every tool their attached
server currently exposes stays exposed) — the new per-tool endpoints only
matter for *new* attach/detach decisions going forward.

For every `mcp_servers` doc that still carries the legacy single `agent_id`,
one `agent_mcp_tools` row is upserted per tool currently cached on that server
(`doc["tools"]`).

It also sweeps every `agents` doc's `mcp_server_ids` array for entries where
the referenced server's own `agent_id` does NOT match that agent -- this is
the pre-existing unvalidated "side door" case (a second agent's id pushed
into `mcp_server_ids` via `PUT /agents/{id}` without the server doc ever being
updated). Those are only logged for manual review, not auto-migrated, since
blindly granting all of that server's tools would convert an already-buggy
cross-agent claim into new legitimate-looking junction rows.

Usage:
    uv run python -m backend.scripts.migrate_agent_mcp_tools_junction

Safe to re-run any time -- every write is an idempotent upsert on the
(agent_id, mcp_server_id, tool_name) unique index.
"""

import asyncio
from datetime import datetime, timezone

from bson import ObjectId

from backend.db.database import agent_mcp_tools_collection, agents_collection, mcp_servers_collection
from backend.mcp_server.services import _ensure_agent_mcp_tools_indexes


async def _backfill_from_owned_servers(now) -> int:
    seeded = 0
    cursor = mcp_servers_collection.find({"agent_id": {"$nin": [None, ""]}, "is_deleted": {"$ne": True}})
    async for server in cursor:
        agent_id = server["agent_id"]
        server_id = str(server["_id"])
        specs = server.get("tools") or []
        for spec in specs:
            tool_name = spec.get("name")
            if not tool_name:
                continue
            result = await agent_mcp_tools_collection.update_one(
                {"agent_id": agent_id, "mcp_server_id": server_id, "tool_name": tool_name},
                {
                    "$setOnInsert": {
                        "organization_id": server["organization_id"],
                        "agent_id": agent_id,
                        "mcp_server_id": server_id,
                        "tool_name": tool_name,
                        "created_at": now,
                        "created_by": None,
                    }
                },
                upsert=True,
            )
            if result.upserted_id:
                seeded += 1
    return seeded


async def _report_unvalidated_cross_agent_claims() -> None:
    cursor = agents_collection.find({"mcp_server_ids": {"$exists": True, "$ne": []}, "is_deleted": {"$ne": True}})
    async for agent in cursor:
        agent_id = str(agent["_id"])
        for server_id in agent.get("mcp_server_ids", []):
            if not ObjectId.is_valid(server_id):
                continue
            server = await mcp_servers_collection.find_one({"_id": ObjectId(server_id)})
            if server and server.get("agent_id") != agent_id:
                print(
                    f"REVIEW: agent '{agent_id}' ({agent.get('name')}) claims mcp_server "
                    f"'{server_id}' ({server.get('name')}) via mcp_server_ids, but that "
                    f"server's own agent_id is '{server.get('agent_id')}'. Not auto-migrated "
                    "-- attach the specific tools this agent should have via "
                    "POST /mcp-servers/{server_id}/agents/{agent_id}/tools if this claim is legitimate."
                )


async def main() -> None:
    await _ensure_agent_mcp_tools_indexes()
    now = datetime.now(timezone.utc)
    seeded = await _backfill_from_owned_servers(now)
    print(f"Seeded {seeded} new agent_mcp_tools row(s) from legacy single-owner servers.")
    await _report_unvalidated_cross_agent_claims()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
