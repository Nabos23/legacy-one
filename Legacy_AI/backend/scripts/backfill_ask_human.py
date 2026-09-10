"""Backfill: assign the auto_assign registry tools (e.g. ask_human) to every
existing agent that doesn't already have them, and rebuild their tool_prompt.

Run once after seeding the registry:
    python -m backend.scripts.seed_function_tools
    python -m backend.scripts.backfill_ask_human

Idempotent: an agent that already has the tool is skipped. Uses synchronous
pymongo (no event loop) so it runs standalone without the async DB client.
"""
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient

from backend.db import constants as c
from backend.db.database import DATABASE_NAME, MONGO_URL

NOT_DELETED = {"is_deleted": {"$ne": True}}


def _rebuild_tool_prompt(db, agent_id: str) -> None:
    """Sync mirror of backend.agent.services.regenerate_tool_prompt."""
    oid = ObjectId(agent_id)
    agent = db[c.AGENTS_COLLECTION].find_one({"_id": oid, **NOT_DELETED}, {"tool_ids": 1})
    if not agent:
        return
    tool_ids = [ObjectId(t) for t in agent.get("tool_ids", []) if ObjectId.is_valid(t)]
    tool_docs = list(db[c.TOOLS_COLLECTION].find({"_id": {"$in": tool_ids}, **NOT_DELETED}))
    if not tool_docs:
        db[c.AGENTS_COLLECTION].update_one({"_id": oid}, {"$set": {"tool_prompt": ""}})
        return

    reg_ids = [ObjectId(t["tool_id"]) for t in tool_docs if t.get("tool_id") and ObjectId.is_valid(t["tool_id"])]
    reg_by_id = {str(r["_id"]): r for r in db[c.TOOL_REGISTRY_COLLECTION].find({"_id": {"$in": reg_ids}})}

    lines = ["## Registered Tools", ""]
    for t in tool_docs:
        reg = reg_by_id.get(str(t.get("tool_id", "")))
        stored_prompt = reg.get("prompt") if reg else None
        if stored_prompt:
            lines.append(stored_prompt)
        else:
            desc = t.get("user_description") or ""
            lines.append(f"- **{t.get('name', 'tool')}**{': ' + desc if desc else ''}")
        lines.append("")
    lines += ["Use each tool only when the request requires its capability."]
    db[c.AGENTS_COLLECTION].update_one({"_id": oid}, {"$set": {"tool_prompt": "\n".join(lines)}})


def main() -> None:
    db = MongoClient(MONGO_URL)[DATABASE_NAME]

    entries = list(db[c.TOOL_REGISTRY_COLLECTION].find(
        {"auto_assign": True, "is_active": True, "is_deleted": {"$ne": True}}
    ))
    if not entries:
        print("No auto_assign registry tools found. Run seed_function_tools first.")
        return
    print(f"Auto-assign tools: {[e['name'] for e in entries]}")

    now = datetime.now(timezone.utc)
    agents = list(db[c.AGENTS_COLLECTION].find(NOT_DELETED))
    updated = 0

    for agent in agents:
        agent_id = str(agent["_id"])
        org_id = agent.get("organization_id", "")

        assigned_reg_ids = set()
        tool_ids = [ObjectId(t) for t in agent.get("tool_ids", []) if ObjectId.is_valid(t)]
        if tool_ids:
            for inst in db[c.TOOLS_COLLECTION].find({"_id": {"$in": tool_ids}, **NOT_DELETED}):
                assigned_reg_ids.add(inst.get("tool_id"))

        new_ids = []
        for reg in entries:
            if str(reg["_id"]) in assigned_reg_ids:
                continue
            res = db[c.TOOLS_COLLECTION].insert_one({
                "organization_id": org_id,
                "agent_id": agent_id,
                "user_description": reg.get("description", ""),
                "tool_id": str(reg["_id"]),
                "name": reg["name"],
                "handler": reg.get("handler") or reg["name"],
                "input_schema": reg.get("tool_schema", {}),
                "created_at": now,
                "is_deleted": False,
            })
            new_ids.append(str(res.inserted_id))

        if new_ids:
            db[c.AGENTS_COLLECTION].update_one(
                {"_id": agent["_id"]},
                {"$addToSet": {"tool_ids": {"$each": new_ids}}},
            )
            updated += 1
            print(f"  + assigned to {agent.get('name', agent_id)} ({agent_id})")

        # Always rebuild tool_prompt so updated registry prompt blocks (e.g. a
        # revised ask_human block) propagate to agents that already had the tool.
        _rebuild_tool_prompt(db, agent_id)

    print(f"Done. Assigned to {updated} new agent(s); rebuilt tool_prompt for {len(agents)}.")


if __name__ == "__main__":
    main()
