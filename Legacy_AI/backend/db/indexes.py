import logging
from typing import Any

import pymongo
from pymongo import IndexModel

from backend.db import database as dbm

logger = logging.getLogger(__name__)

ASC = pymongo.ASCENDING
DESC = pymongo.DESCENDING


def _specs() -> dict[str, list[IndexModel]]:
    return {
        "users_collection": [
            IndexModel([("email", ASC)], name="email_lookup", background=True),
            IndexModel(
                [("organization_id", ASC), ("name", ASC)],
                name="org_name_scope",
                background=True,
            ),
            IndexModel([("google_id", ASC)], name="google_id_lookup", sparse=True, background=True),
            IndexModel([("github_id", ASC)], name="github_id_lookup", sparse=True, background=True),
        ],
        "organizations_collection": [
            IndexModel([("created_at", DESC)], name="created_at_order", background=True),
            IndexModel([("created_by", ASC)], name="created_by_lookup", background=True),
        ],
        "tools_collection": [
            IndexModel([("organization_id", ASC)], name="org_scope", background=True),
            IndexModel([("agent_id", ASC)], name="agent_lookup", background=True),
        ],
        "tool_registry_collection": [
            IndexModel([("created_at", DESC)], name="created_at_order", background=True),
        ],
        "teams_collection": [
            IndexModel([("member_ids", ASC)], name="member_lookup", background=True),
            IndexModel([("organization_id", ASC)], name="org_scope", background=True),
        ],
        "db_connections_collection": [
            IndexModel([("organization_id", ASC)], name="org_scope", background=True),
        ],
        "mcp_servers_collection": [
            IndexModel([("organization_id", ASC)], name="org_scope", background=True),
        ],
        "chat_sessions_collection": [
            IndexModel([("thread_id", ASC)], name="thread_lookup", background=True),
            IndexModel(
                [("organization_id", ASC), ("created_at", DESC)],
                name="org_created_at_order",
                background=True,
            ),
            IndexModel(
                [("orchestration_id", ASC), ("organization_id", ASC), ("user_id", ASC)],
                name="orchestration_scope",
                background=True,
            ),
        ],
        "notifications_collection": [
            IndexModel(
                [("organization_id", ASC), ("user_id", ASC), ("created_at", DESC)],
                name="org_user_created_at",
                background=True,
            ),
        ],
        "roles_collection": [
            IndexModel([("role", ASC)], name="role_lookup", background=True),
        ],
        "org_role_permissions_collection": [
            IndexModel(
                [("organization_id", ASC), ("role", ASC)],
                name="org_role_lookup",
                background=True,
            ),
        ],
    }


async def ensure_core_indexes() -> dict[str, Any]:
    report: dict[str, Any] = {}
    for attr, models in _specs().items():
        collection = getattr(dbm, attr, None)
        if collection is None:
            report[attr] = "missing-collection"
            logger.warning("[indexes] no such collection attribute: %s", attr)
            continue
        try:
            created = await collection.create_indexes(models)
            report[attr] = created
        except Exception as exc:
            report[attr] = f"error: {exc}"
            logger.warning("[indexes] could not create indexes on %s: %s", attr, exc)
    return report
