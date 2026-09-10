"""
One-off backfill: regenerate tool_prompt and mcp_prompt for every existing agent
that doesn't have them yet (or has them empty).

Run inside the app container:
    docker compose exec fastapi uv run --no-sync python -m backend.scripts.backfill_agent_prompts
"""
import asyncio
import logging

from backend.agent.services import regenerate_mcp_prompt, regenerate_tool_prompt
from backend.core.softdelete import NOT_DELETED
from backend.db.database import agents_collection

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    cursor = agents_collection.find(NOT_DELETED, {"_id": 1, "name": 1})
    agents = await cursor.to_list(length=None)
    logger.info("Found %d agent(s) to backfill", len(agents))

    for agent in agents:
        agent_id = str(agent["_id"])
        name = agent.get("name", agent_id)
        await regenerate_tool_prompt(agent_id)
        await regenerate_mcp_prompt(agent_id)
        logger.info("  ✓ %s (id=%s)", name, agent_id)

    logger.info("Backfill complete.")


if __name__ == "__main__":
    asyncio.run(main())
