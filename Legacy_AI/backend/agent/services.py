import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from backend.agent.schemas import AgentCreate, AgentPermissionsDoc, AgentPermissionsPatch, AgentPublic, AgentUpdate
from backend.core.config import settings
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.core.uploads import delete_stored_upload, save_image_upload
from backend.db.database import (
    agent_permissions_collection,
    agents_collection,
    connector_registry_collection,
    db_connections_collection,
    mcp_server_registry_collection,
    mcp_servers_collection,
    organizations_collection,
    teams_collection,
    tool_registry_collection,
    tools_collection,
    tools_permissions_registry_collection,
    users_collection,
)
from backend.notifications import services as notification_services
from backend.team import services as team_services
from .validators import validate_object_id

logger = logging.getLogger("agent.services")

_TOOLS_SECTION_HEADER = "## Registered Tools"
_TOOLS_SECTION_FOOTER = "Use each tool only when the request requires its capability."

_MCP_SECTION_HEADER = "## MCP Server Tools"
_MCP_SECTION_FOOTER = "Call MCP tools only when the user's request explicitly requires their specific capability."

_CONNECTOR_SECTION_HEADER = "## Connected Integrations"
_CONNECTOR_SECTION_FOOTER = "Use these integrations when the user's request involves those services."


def _merge_fragment_into_prompt(prompt: str, fragment: str, header: str, footer: str) -> str:
    """Shared insert logic for all three capability types (tools/mcp/connectors).
    Guarantees the fragment is added regardless of whether the header/footer
    are already present, missing, or partially present -- see the three
    branches below. Self-heals into the correct header+footer shape on the
    first merge no matter what state the prompt started in.
    """
    if header in prompt:
        if footer in prompt:
            return prompt.replace(footer, f"{fragment}\n\n{footer}", 1)
        return f"{prompt.rstrip()}\n\n{fragment}\n\n{footer}"
    return f"{prompt.rstrip()}\n\n{header}\n\n{fragment}\n\n{footer}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _build_tool_fragment(tool_doc: dict, registry_entry: dict | None) -> str:
    """Build one tool's prompt fragment. The tool_registry_collection entry
    is the authoritative source for a tool's name/description -- prefer it
    over the tool instance's fields.
    """
    if registry_entry:
        stored_prompt = registry_entry.get("prompt")
        if stored_prompt:
            return stored_prompt
        name = registry_entry.get("name") or tool_doc.get("name") or "tool"
        desc = registry_entry.get("description") or tool_doc.get("user_description") or ""
    else:
        name = tool_doc.get("name") or "tool"
        desc = tool_doc.get("user_description") or ""
    return f"- **{name}**{': ' + desc if desc else ''}"


async def _merge_tool_into_prompt(
    agent_id: str, tool_doc: dict, registry_entry: dict | None
) -> None:
    """Append one tool's prompt fragment into agent.prompt -- the ONLY field
    the chat runtime reads (see graph.py AgentRuntime: sys_prompt = agent.prompt,
    plus guardrails).
    """
    if not ObjectId.is_valid(agent_id):
        return
    oid = ObjectId(agent_id)
    agent_doc = await agents_collection.find_one({"_id": oid, **NOT_DELETED}, {"prompt": 1})
    if not agent_doc:
        return

    fragment = _build_tool_fragment(tool_doc, registry_entry)
    prompt = _merge_fragment_into_prompt(
        agent_doc.get("prompt") or "", fragment, _TOOLS_SECTION_HEADER, _TOOLS_SECTION_FOOTER
    )

    await agents_collection.update_one({"_id": oid}, {"$set": {"prompt": prompt}})
    logger.info("[PROMPT] merged tool '%s' into prompt for agent=%s", tool_doc.get("name"), agent_id)


# ---------------------------------------------------------------------------
# MCP servers
# ---------------------------------------------------------------------------

def _build_mcp_fragment(server_doc: dict, registry_entry: dict | None) -> str:
    """Build one MCP server's prompt fragment. Prefers the catalog registry
    entry's stored `prompt` block; falls back to listing the server's
    discovered tools (BYO servers, or registry entries without a prompt).
    """
    stored_prompt = registry_entry.get("prompt") if registry_entry else None
    if stored_prompt:
        return stored_prompt
    server_name = server_doc.get("name") or "MCP Server"
    lines = [f"### {server_name}"]
    for t in server_doc.get("tools", []):
        name = t.get("name") or "tool"
        desc = t.get("description") or ""
        lines.append(f"- **{name}**{': ' + desc if desc else ''}")
    return "\n".join(lines)


async def _merge_mcp_into_prompt(
    agent_id: str, server_doc: dict, registry_entry: dict | None
) -> None:
    """Append one MCP server's prompt fragment into agent.prompt."""
    if not ObjectId.is_valid(agent_id):
        return
    oid = ObjectId(agent_id)
    agent_doc = await agents_collection.find_one({"_id": oid, **NOT_DELETED}, {"prompt": 1})
    if not agent_doc:
        return

    fragment = _build_mcp_fragment(server_doc, registry_entry)
    prompt = _merge_fragment_into_prompt(
        agent_doc.get("prompt") or "", fragment, _MCP_SECTION_HEADER, _MCP_SECTION_FOOTER
    )

    await agents_collection.update_one({"_id": oid}, {"$set": {"prompt": prompt}})
    logger.info("[PROMPT] merged MCP server '%s' into prompt for agent=%s", server_doc.get("name"), agent_id)


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------

def _build_connector_fragment(connector_doc: dict) -> str:
    """Build one connector's prompt fragment. connector_ids reference
    connector_registry_collection directly (no separate instance doc), so
    there's only one doc to build from -- prefers its stored `prompt`
    block, falls back to listing `available_actions`.
    """
    stored_prompt = connector_doc.get("prompt")
    if stored_prompt:
        return stored_prompt
    name = connector_doc.get("name") or connector_doc.get("provider_id", "Connector")
    lines = [f"### {name}"]
    for action in connector_doc.get("available_actions", []):
        lines.append(f"- {action.replace('_', ' ').title()}")
    return "\n".join(lines)


async def _merge_connector_into_prompt(agent_id: str, connector_doc: dict) -> None:
    """Append one connector's prompt fragment into agent.prompt."""
    if not ObjectId.is_valid(agent_id):
        return
    oid = ObjectId(agent_id)
    agent_doc = await agents_collection.find_one({"_id": oid, **NOT_DELETED}, {"prompt": 1})
    if not agent_doc:
        return

    fragment = _build_connector_fragment(connector_doc)
    prompt = _merge_fragment_into_prompt(
        agent_doc.get("prompt") or "", fragment, _CONNECTOR_SECTION_HEADER, _CONNECTOR_SECTION_FOOTER
    )

    await agents_collection.update_one({"_id": oid}, {"$set": {"prompt": prompt}})
    logger.info("[PROMPT] merged connector '%s' into prompt for agent=%s", connector_doc.get("name"), agent_id)


def _to_public(doc: dict, connectors_map: dict | None = None) -> AgentPublic:
    """Map a MongoDB agent document to the public schema."""
    conn_list = []
    if connectors_map:
        for cid in doc.get("connector_ids", []):
            if cid in connectors_map:
                conn_list.append(connectors_map[cid])

    return AgentPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc["name"],
        prompt=doc.get("prompt") or "",
        guardrails=doc.get("guardrails") or "",
        description=doc.get("description"),
        user_description=doc.get("user_description"),
        instructions=doc.get("instructions"),
        tool_ids=doc.get("tool_ids", []),
        rag_ids=doc.get("rag_ids", []),
        mcp_server_ids=doc.get("mcp_server_ids", []),
        connector_ids=doc.get("connector_ids", []),
        connectors=conn_list,
        is_active=doc.get("is_active", True),
        avatar_type=doc.get("avatar_type", "color"),
        avatar_value=doc.get("avatar_value"),
        avatar_url=doc.get("avatar_url"),
        created_by=doc["created_by"],
        created_at=doc["created_at"],
        owner_scope=doc.get("owner_scope", "organization"),
        allowed_user_ids=doc.get("allowed_user_ids", []),
        team_id=doc.get("team_id"),
    )


async def _fetch_connectors_summary(connector_ids: list[str]) -> dict[str, dict]:
    """Batch-resolve connector ids to connector summary dicts."""
    valid_ids = {ObjectId(c) for c in set(connector_ids) if c and ObjectId.is_valid(c)}
    if not valid_ids:
        return {}
    cursor = connector_registry_collection.find(
        {"_id": {"$in": list(valid_ids)}},
        {"name": 1, "provider_id": 1, "icon": 1}
    )
    result = {}
    async for doc in cursor:
        result[str(doc["_id"])] = {
            "id": str(doc["_id"]),
            "name": doc.get("name", ""),
            "provider_id": doc.get("provider_id", ""),
            "icon": doc.get("icon", ""),
        }
    return result


async def _validate_org_exists(org_id: str) -> None:
    """Raise 404 if org_id is not a valid ObjectId or the org doesn't exist."""
    if not ObjectId.is_valid(org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    doc = await organizations_collection.find_one(
        {"_id": ObjectId(org_id), "is_deleted": {"$ne": True}}
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )


async def _validate_allowed_user_ids(org_id: str, user_ids: List[str]) -> List[str]:
    """Validate that every id in `user_ids` is a real user belonging to `org_id`,
    dedupe, and return the cleaned list. Prevents an org_admin/org_manager from
    granting agent visibility to a user outside their own organization."""
    unique_ids = list(dict.fromkeys(uid for uid in user_ids if uid))
    if not unique_ids:
        return []
    object_ids = [ObjectId(uid) for uid in unique_ids if ObjectId.is_valid(uid)]
    if len(object_ids) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected user ids are invalid.",
        )
    count = await users_collection.count_documents(
        {"_id": {"$in": object_ids}, "organization_id": org_id}
    )
    if count != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected users do not belong to this organization.",
        )
    return unique_ids


async def _validate_team_id(org_id: str, team_id: Optional[str]) -> Optional[str]:
    """Validate that `team_id` is a real, non-deleted team belonging to `org_id`.
    Prevents an org_admin/org_manager from assigning an agent to a team outside
    their own organization."""
    if not team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is required for team visibility.")
    if not ObjectId.is_valid(team_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is invalid.")
    doc = await teams_collection.find_one(
        {"_id": ObjectId(team_id), "organization_id": org_id, **NOT_DELETED}
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected team does not belong to this organization.")
    return team_id


async def sync_connector_permissions(
    entity_id: str,
    org_id: str,
    connector_ids: List[str],
    user_permissions: Optional[Dict[str, Dict[str, bool]]] = None,
    is_project: bool = False,
) -> Dict[str, Dict[str, bool]]:
    """Sync connector permissions in agent_permissions_collection for an agent or project."""
    if not ObjectId.is_valid(entity_id):
        return {}

    now = datetime.now(timezone.utc)
    user_perms_map = user_permissions or {}
    connectors_perm_dict: Dict[str, Dict[str, bool]] = {}

    valid_oids = [ObjectId(cid) for cid in connector_ids if ObjectId.is_valid(cid)]
    if not valid_oids:
        return {}

    connector_docs = await connector_registry_collection.find(
        {"_id": {"$in": valid_oids}, "is_deleted": {"$ne": True}}
    ).to_list(length=len(valid_oids))

    for doc in connector_docs:
        provider_id = doc.get("provider_id")
        if not provider_id:
            continue
        cid_str = str(doc["_id"])

        perm_reg_doc = await tools_permissions_registry_collection.find_one(
            {"$or": [{"connector_id": cid_str}, {"provider_id": provider_id}]}
        )
        available_categories = list((perm_reg_doc.get("permissions") or {}).keys()) if perm_reg_doc else ["read", "write", "delete"]

        user_perms = user_perms_map.get(provider_id) or user_perms_map.get(cid_str) or {}
        enabled_perms = {
            category: bool(user_perms[category]) if category in user_perms else True
            for category in available_categories
        }
        connectors_perm_dict[provider_id] = enabled_perms

    query = {"project_id": str(entity_id)} if is_project else {"agent_id": str(entity_id)}
    set_fields = {
        "organization_id": org_id,
        "permissions.connectors": connectors_perm_dict,
        "updated_at": now,
    }
    set_on_insert = {
        "project_id" if is_project else "agent_id": str(entity_id),
        "created_at": now,
    }

    await agent_permissions_collection.update_one(
        query,
        {
            "$set": set_fields,
            "$setOnInsert": set_on_insert,
        },
        upsert=True,
    )
    return connectors_perm_dict


async def bind_runtime_db_tools(tools: List[dict], org_id: str) -> List[str]:
    """Inspect runtime tools, bind org DB connections if DB query tools are present, and return db_conn_ids."""
    db_conn_ids = [t["db_conn_id"] for t in tools if t.get("db_conn_id")]
    has_db_tool = any(
        t.get("name") in ["query_mongo_read", "query_sql_read", "query_mongo_write", "query_sql_write"]
        or t.get("handler") in ["query_mongo_read", "query_sql_read", "query_mongo_write", "query_sql_write"]
        for t in tools
    )
    if has_db_tool:
        if not db_conn_ids:
            conn_cursor = db_connections_collection.find(
                {"organization_id": org_id, **NOT_DELETED}
            )
            conn_docs = await conn_cursor.to_list(length=100)
            db_conn_ids = [str(c["_id"]) for c in conn_docs]
            for t in tools:
                if not t.get("db_conn_id") and db_conn_ids:
                    t["db_conn_id"] = db_conn_ids[0]
    return db_conn_ids


async def _auto_assign_default_tools(agent_id: str, org_id: str) -> None:
    """Attach every registry tool flagged `auto_assign` (e.g. ask_human) to a
    newly created agent, merging each into the agent's prompt at creation time.
    """
    if not ObjectId.is_valid(agent_id):
        return
    entries = await tool_registry_collection.find(
        {"auto_assign": True, "is_active": True, "is_deleted": {"$ne": True}}
    ).to_list(length=50)
    if not entries:
        logger.warning(
            "[PROMPT] no auto_assign tools in registry — agent %s has no ask_human. "
            "Run: python -m backend.scripts.seed_function_tools", agent_id,
        )
        return

    now = datetime.now(timezone.utc)
    for reg in entries:
        instance = {
            "organization_id": org_id,
            "agent_id": agent_id,
            "user_description": reg.get("description", ""),
            "tool_id": str(reg["_id"]),
            "name": reg["name"],
            "handler": reg.get("handler") or reg["name"],
            "input_schema": reg.get("tool_schema", {}),
            "created_at": now,
            "is_deleted": False,
        }
        res = await tools_collection.insert_one(instance)
        instance["_id"] = res.inserted_id

        await agents_collection.update_one(
            {"_id": ObjectId(agent_id)},
            {"$addToSet": {"tool_ids": {"$each": [str(res.inserted_id)]}}},
        )
        await _merge_tool_into_prompt(agent_id, instance, reg)

    logger.info(
        "[PROMPT] auto-assigned %d default tool(s) to agent=%s: %s",
        len(entries), agent_id, [e["name"] for e in entries],
    )


async def create_agent(
    payload: AgentCreate,
    created_by: str,
    owner_scope: str = "organization",
    allowed_user_ids: Optional[List[str]] = None,
    team_id: Optional[str] = None,
) -> AgentPublic:
    await _validate_org_exists(payload.organization_id)
    cleaned_allowed_user_ids: List[str] = []
    if owner_scope == "selected_users":
        cleaned_allowed_user_ids = await _validate_allowed_user_ids(
            payload.organization_id, allowed_user_ids or []
        )
    cleaned_team_id: Optional[str] = None
    if owner_scope == "team":
        cleaned_team_id = await _validate_team_id(payload.organization_id, team_id)
    doc = {
        "organization_id": payload.organization_id,
        "name": payload.name,
        "prompt": payload.prompt,
        "guardrails": payload.guardrails,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc),
        "is_active": True,
        "is_deleted": False,
        "owner_scope": owner_scope,
        "allowed_user_ids": cleaned_allowed_user_ids,
        "team_id": cleaned_team_id,
    }
    if payload.description:
        doc["description"] = payload.description
    if payload.user_description:
        doc["user_description"] = payload.user_description
    if payload.tool_ids:
        doc["tool_ids"] = payload.tool_ids
    if payload.rag_ids:
        doc["rag_ids"] = payload.rag_ids
    if payload.mcp_server_ids:
        doc["mcp_server_ids"] = payload.mcp_server_ids
    if payload.connector_ids:
        doc["connector_ids"] = payload.connector_ids
    if payload.avatar_type:
        doc["avatar_type"] = payload.avatar_type
    if payload.avatar_value is not None:
        doc["avatar_value"] = payload.avatar_value
    result = await agents_collection.insert_one(doc)
    doc["_id"] = result.inserted_id

    # Initialize permissions and merge prompts for connector_ids during creation
    if payload.connector_ids:
        valid_ids = [ObjectId(cid) for cid in payload.connector_ids if ObjectId.is_valid(cid)]
        if valid_ids:
            connector_docs = await connector_registry_collection.find(
                {"_id": {"$in": valid_ids}}
            ).to_list(length=100)
            for connector_doc in connector_docs:
                await _merge_connector_into_prompt(str(result.inserted_id), connector_doc)

        await sync_connector_permissions(
            str(result.inserted_id),
            payload.organization_id,
            payload.connector_ids,
            payload.connector_permissions,
            is_project=False,
        )

    await _auto_assign_default_tools(str(result.inserted_id), payload.organization_id)
    refreshed = await agents_collection.find_one({"_id": result.inserted_id})
    if refreshed:
        doc = refreshed

    await notification_services.create_notification(
        organization_id=payload.organization_id,
        type="agent",
        title="Agent created",
        message=f"{payload.name} was created and is ready to deploy.",
    )
    return _to_public(doc)


async def update_agent_avatar(agent_id: str, file: UploadFile) -> AgentPublic:
    """Upload and set an agent's profile image, replacing any previous upload."""
    oid = validate_object_id(agent_id)
    existing = await agents_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    previous_url = existing.get("avatar_url")
    url_path = await save_image_upload(file, subdir="agent-avatars")
    avatar_url = f"{settings.BACKEND_BASE_URL}{url_path}"

    doc = await agents_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {
            "$set": {
                "avatar_url": avatar_url,
                "avatar_type": "image",
                "avatar_value": None,
            }
        },
        return_document=True,
    )
    if not doc:
        delete_stored_upload(url_path)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    if previous_url and previous_url != avatar_url:
        previous_path = previous_url.removeprefix(settings.BACKEND_BASE_URL)
        delete_stored_upload(previous_path)

    return _to_public(doc)

AGENT_SORTABLE_FIELDS = {"name", "created_at", "is_active"}


async def assert_agent_visible(current_user_id: str, agent: AgentPublic) -> None:
    """Single-agent counterpart to `build_agent_visibility_clauses`, for routes
    that already fetched one agent by id (get/update/avatar/status/delete).

    Personal agents (owner_scope == 'user') are visible/actionable ONLY to
    their creator, "selected_users" agents are visible only to their creator +
    whoever is in allowed_user_ids, and "team" agents are visible only to
    their creator + current members of the assigned team -- 404 (not 403) for
    everyone else, including org_admin/org_manager/super_admin, so the
    existence of another user's restricted agent is never leaked. Must stay in
    sync with `build_agent_visibility_clauses`, which enforces the same rule
    at the query level for the listing endpoints.
    """
    if agent.owner_scope == "user" and agent.created_by != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    if (
        agent.owner_scope == "selected_users"
        and agent.created_by != current_user_id
        and current_user_id not in agent.allowed_user_ids
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    if agent.owner_scope == "team" and agent.created_by != current_user_id:
        if not agent.team_id or not await team_services.is_member(agent.team_id, current_user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")


async def build_agent_visibility_clauses(requesting_user_id: str) -> list[dict]:
    """Mongo `$or` clauses restricting results to agents `requesting_user_id`
    may see: organization-wide agents (or legacy docs missing owner_scope --
    `$nin` matches both), their own personal agents, "selected_users" agents
    they created or were granted access to, and "team" agents they created or
    are a current member of. No admin bypass -- agents are fully private
    outside these sets for everyone, including org_admin/org_manager/super_admin.

    This is the single visibility rule for the whole app: used for the
    /agents listing endpoints (via `_build_agent_query` below), and reused
    as-is by chat/direct_agent/widget code that resolves agents outside the
    /agents CRUD routes (chat.services._load_org_agents,
    direct_agent.services._load_single_agent,
    widget.services._validate_agent_in_org) so a personal/selected-users/team
    agent can never be reached through chat or a public widget either, not
    just hidden from listings.
    """
    team_ids = await team_services.get_team_ids_for_user(requesting_user_id)
    clauses = [
        {"owner_scope": {"$nin": ["user", "selected_users", "team"]}},
        {"owner_scope": "user", "created_by": requesting_user_id},
        {"owner_scope": "selected_users", "created_by": requesting_user_id},
        {"owner_scope": "selected_users", "allowed_user_ids": requesting_user_id},
        {"owner_scope": "team", "created_by": requesting_user_id},
    ]
    if team_ids:
        clauses.append({"owner_scope": "team", "team_id": {"$in": team_ids}})
    return clauses


async def _build_agent_query(
    *,
    organization_id: Optional[str] = None,
    requesting_user_id: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    has_tools: Optional[bool] = None,
    has_connectors: Optional[bool] = None,
    has_mcp: Optional[bool] = None,
) -> dict:
    """Shared filter-building for list_agents / list_agents_by_org so both
    stay in sync as filters are added."""
    query: dict = {**NOT_DELETED}
    if organization_id:
        query["organization_id"] = organization_id
    if requesting_user_id is not None:
        query["$or"] = await build_agent_visibility_clauses(requesting_user_id)
    if search:
        query["name"] = {"$regex": re.escape(search), "$options": "i"}
    if is_active is not None:
        query["is_active"] = is_active
    if has_tools is not None:
        query["tool_ids.0"] = {"$exists": has_tools}
    if has_connectors is not None:
        query["connector_ids.0"] = {"$exists": has_connectors}
    if has_mcp is not None:
        query["mcp_server_ids.0"] = {"$exists": has_mcp}
    return query


def _resolve_agent_sort(sort_by: Optional[str], sort_order: str) -> list[tuple[str, int]]:
    field = sort_by if sort_by in AGENT_SORTABLE_FIELDS else "created_at"
    direction = 1 if sort_order == "asc" else -1
    return [(field, direction)]


async def list_agents(
    skip: int = 0,
    limit: int = 20,
    requesting_user_id: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    has_tools: Optional[bool] = None,
    has_connectors: Optional[bool] = None,
    has_mcp: Optional[bool] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> tuple[List[AgentPublic], int]:
    query = await _build_agent_query(
        requesting_user_id=requesting_user_id,
        search=search,
        is_active=is_active,
        has_tools=has_tools,
        has_connectors=has_connectors,
        has_mcp=has_mcp,
    )
    total = await agents_collection.count_documents(query)
    cursor = (
        agents_collection.find(query)
        .sort(_resolve_agent_sort(sort_by, sort_order))
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    all_connector_ids = [cid for doc in docs for cid in doc.get("connector_ids", [])]
    conn_map = await _fetch_connectors_summary(all_connector_ids)
    return [_to_public(doc, conn_map) for doc in docs], total


async def list_agents_by_org(
    org_id: str,
    skip: int = 0,
    limit: int = 20,
    requesting_user_id: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    has_tools: Optional[bool] = None,
    has_connectors: Optional[bool] = None,
    has_mcp: Optional[bool] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> tuple[List[AgentPublic], int]:
    """List agents that belong to a specific organization (paginated)."""
    query = await _build_agent_query(
        organization_id=org_id,
        requesting_user_id=requesting_user_id,
        search=search,
        is_active=is_active,
        has_tools=has_tools,
        has_connectors=has_connectors,
        has_mcp=has_mcp,
    )
    total = await agents_collection.count_documents(query)
    cursor = (
        agents_collection.find(query)
        .sort(_resolve_agent_sort(sort_by, sort_order))
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    all_connector_ids = [cid for doc in docs for cid in doc.get("connector_ids", [])]
    conn_map = await _fetch_connectors_summary(all_connector_ids)
    return [_to_public(doc, conn_map) for doc in docs], total


async def get_agent(agent_id: str) -> AgentPublic:
    oid = validate_object_id(agent_id)
    doc = await agents_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )
    conn_map = await _fetch_connectors_summary(doc.get("connector_ids", []))
    return _to_public(doc, conn_map)


async def update_agent(agent_id: str, payload: AgentUpdate) -> AgentPublic:
    oid = validate_object_id(agent_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update.")
    
    existing = await agents_collection.find_one(
        {"_id": oid, **NOT_DELETED},
        {"tool_ids": 1, "mcp_server_ids": 1, "connector_ids": 1, "organization_id": 1},
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    if "allowed_user_ids" in updates:
        updates["allowed_user_ids"] = await _validate_allowed_user_ids(
            existing["organization_id"], updates["allowed_user_ids"] or []
        )

    if "team_id" in updates and updates["team_id"]:
        updates["team_id"] = await _validate_team_id(existing["organization_id"], updates["team_id"])

    if updates.get("owner_scope") and updates["owner_scope"] != "team":
        updates["team_id"] = None
    if updates.get("owner_scope") and updates["owner_scope"] != "selected_users":
        updates["allowed_user_ids"] = []

    if updates.get("avatar_type") in ("color", "emoji", "sticker", "brand"):
        previous_url = existing.get("avatar_url")
        if previous_url:
            previous_path = previous_url.removeprefix(settings.BACKEND_BASE_URL)
            delete_stored_upload(previous_path)
        updates["avatar_url"] = None

    old_tool_ids = set(existing.get("tool_ids", []))
    old_mcp_ids = set(existing.get("mcp_server_ids", []))
    old_connector_ids = set(existing.get("connector_ids", []))

    existing = await agents_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    if updates.get("avatar_type") in ("color", "emoji", "sticker", "brand"):
        previous_url = existing.get("avatar_url")
        if previous_url:
            previous_path = previous_url.removeprefix(settings.BACKEND_BASE_URL)
            delete_stored_upload(previous_path)
        updates["avatar_url"] = None

    doc = await agents_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    _invalidate_org_graph_cache(doc.get("organization_id"), agent_id)

    prompt_touched = False

    if "tool_ids" in updates:
        added_ids = set(updates["tool_ids"] or []) - old_tool_ids
        for tid in added_ids:
            if not ObjectId.is_valid(tid):
                continue
            tool_doc = await tools_collection.find_one({"_id": ObjectId(tid), **NOT_DELETED})
            if not tool_doc:
                continue
            registry_entry = None
            if tool_doc.get("tool_id") and ObjectId.is_valid(tool_doc["tool_id"]):
                registry_entry = await tool_registry_collection.find_one({"_id": ObjectId(tool_doc["tool_id"])})
            await _merge_tool_into_prompt(agent_id, tool_doc, registry_entry)
            prompt_touched = True

    if "mcp_server_ids" in updates:
        added_ids = set(updates["mcp_server_ids"] or []) - old_mcp_ids
        for sid in added_ids:
            if not ObjectId.is_valid(sid):
                continue
            server_doc = await mcp_servers_collection.find_one({"_id": ObjectId(sid), **NOT_DELETED})
            if not server_doc:
                continue
            registry_entry = None
            if server_doc.get("registry_key"):
                registry_entry = await mcp_server_registry_collection.find_one(
                    {"key": server_doc["registry_key"], "is_deleted": {"$ne": True}}
                )
            await _merge_mcp_into_prompt(agent_id, server_doc, registry_entry)
            prompt_touched = True

    if "connector_ids" in updates or "connector_permissions" in updates:
        conn_ids = updates.get("connector_ids") if "connector_ids" in updates else list(old_connector_ids)
        added_ids = set(conn_ids or []) - old_connector_ids
        valid_ids = [ObjectId(cid) for cid in added_ids if ObjectId.is_valid(cid)]
        if valid_ids:
            connector_docs = await connector_registry_collection.find(
                {"_id": {"$in": valid_ids}}
            ).to_list(length=100)
            for connector_doc in connector_docs:
                await _merge_connector_into_prompt(agent_id, connector_doc)
                prompt_touched = True

        await sync_connector_permissions(
            agent_id,
            existing["organization_id"],
            conn_ids or [],
            updates.get("connector_permissions"),
            is_project=False,
        )

    if prompt_touched:
        refreshed = await agents_collection.find_one({"_id": oid})
        if refreshed:
            doc = refreshed

    return _to_public(doc)


def _invalidate_org_graph_cache(organization_id: Optional[str], agent_id: str) -> None:
    """Best-effort: clear the per-org (and single-agent) compiled graph caches."""
    try:
        from backend.chat.graph import invalidate_org_graph, invalidate_single_agent_graph
        if organization_id:
            invalidate_org_graph(organization_id)
            invalidate_single_agent_graph(organization_id, agent_id)
    except Exception:  # noqa: BLE001 - cache invalidation must never break the request
        pass


async def get_agent_summaries_for_org(
    organization_id: str, requesting_user_id: Optional[str] = None
) -> list:
    """
    Return lightweight agent dicts for MainAgent routing.
    Uses _id (str), name, description, and guardrails (always a list).

    `requesting_user_id`, when provided, restricts results to agents visible
    to that user (see build_agent_visibility_clauses) -- personal/
    selected_users agents must never leak into another user's routing
    context.
    """
    query: dict = {"organization_id": organization_id, **NOT_DELETED}
    if requesting_user_id is not None:
        query["$or"] = await build_agent_visibility_clauses(requesting_user_id)
    cursor = agents_collection.find(
        query,
        {"_id": 1, "name": 1, "description": 1, "guardrails": 1},
    )
    docs = await cursor.to_list(length=None)
    summaries = []
    for doc in docs:
        guardrails = doc.get("guardrails", [])
        if isinstance(guardrails, str):
            guardrails = [g.strip() for g in guardrails.split(",") if g.strip()]
        summaries.append({
            "_id":         str(doc["_id"]),
            "name":        doc.get("name", ""),
            "description": doc.get("description") or "",
            "guardrails":  guardrails,
        })
    return summaries


async def toggle_agent_status(agent_id: str, is_active: bool) -> AgentPublic:
    oid = validate_object_id(agent_id)
    doc = await agents_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": {"is_active": is_active}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )
    _invalidate_org_graph_cache(doc.get("organization_id"), agent_id)
    return _to_public(doc)


async def delete_agent(agent_id: str) -> None:
    """Soft-delete an agent and every tool owned by it."""
    oid = validate_object_id(agent_id)
    result = await agents_collection.update_one(
        {"_id": oid, **NOT_DELETED}, soft_delete_update()
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )
    await tools_collection.update_many(
        {"agent_id": agent_id, **NOT_DELETED},
        soft_delete_update(),
    )

# ---------------------------------------------------------------------------
# Agent permissions services
# ---------------------------------------------------------------------------

async def get_agent_permissions(agent_id: str) -> AgentPermissionsDoc:
    """Fetch the permissions document for an agent. Creates default empty permissions if not found."""
    doc = await agent_permissions_collection.find_one({"agent_id": agent_id})
    if not doc:
        agent_doc = await agents_collection.find_one({"_id": ObjectId(agent_id)}) if ObjectId.is_valid(agent_id) else None
        org_id = agent_doc.get("organization_id", "") if agent_doc else ""
        now = datetime.now(timezone.utc)
        doc = {
            "agent_id": agent_id,
            "organization_id": org_id,
            "permissions": {},
            "created_at": now,
            "updated_at": now,
        }
        res = await agent_permissions_collection.insert_one(doc)
        doc["_id"] = res.inserted_id

    return AgentPermissionsDoc(
        id=str(doc["_id"]),
        agent_id=doc["agent_id"],
        organization_id=doc["organization_id"],
        permissions=doc.get("permissions", {}),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )

async def patch_agent_permissions(
    agent_id: str, patch: AgentPermissionsPatch
) -> AgentPermissionsDoc:
    """Flip one or more connector flags. Only the keys in the body are touched."""
    if not patch.connectors:
        return await get_agent_permissions(agent_id)

    set_fields: dict = {"updated_at": datetime.now(timezone.utc)}

    if patch.connectors:
        for provider_id, conn_perms in patch.connectors.items():
            perms_dict = conn_perms.model_dump(exclude_unset=True) if hasattr(conn_perms, "model_dump") else conn_perms.dict(exclude_unset=True)
            for action_type, val in perms_dict.items():
                if val is not None:
                    set_fields[f"permissions.connectors.{provider_id}.{action_type}"] = val

    agent_doc = await agents_collection.find_one({"_id": ObjectId(agent_id)}) if ObjectId.is_valid(agent_id) else None
    org_id = agent_doc.get("organization_id", "") if agent_doc else ""

    result = await agent_permissions_collection.find_one_and_update(
        {"agent_id": agent_id},
        {
            "$set": set_fields,
            "$setOnInsert": {
                "agent_id": agent_id,
                "organization_id": org_id,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
        return_document=True,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permissions document not found for this agent.",
        )
    return AgentPermissionsDoc(
        id=str(result["_id"]),
        agent_id=result["agent_id"],
        organization_id=result["organization_id"],
        permissions=result.get("permissions", {}),
        created_at=result["created_at"],
        updated_at=result["updated_at"],
    )

async def add_agent_permission(
    agent_id: str, org_id: str, name: str, enabled: Any, permission_type: str = "tools"
) -> None:
    """Upsert a tool/connector permission into the agent's permissions doc."""
    now = datetime.now(timezone.utc)
    await agent_permissions_collection.update_one(
        {"agent_id": agent_id},
        {
            "$set": {
                f"permissions.{permission_type}.{name}": enabled,
                "updated_at": now,
            },
            "$setOnInsert": {
                "agent_id": agent_id,
                "organization_id": org_id,
                "created_at": now,
            },
        },
        upsert=True,
    )


async def remove_agent_permission(
    agent_id: str, name: str, permission_type: str = "tools"
) -> None:
    """Remove a tool/connector key from the agent's permissions doc."""
    await agent_permissions_collection.update_one(
        {"agent_id": agent_id},
        {
            "$unset": {f"permissions.{permission_type}.{name}": ""},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
