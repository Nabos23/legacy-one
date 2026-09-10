import json
import re
import litellm
from bson import ObjectId
from fastapi import HTTPException, status

from ai.models import Model
from backend.auth.permissions import assert_org_access
from backend.auth.schemas import UserPublic
from backend.core.softdelete import NOT_DELETED
from backend.db.database import (
    agents_collection,
    connector_registry_collection,
    mcp_server_registry_collection,
    mcp_servers_collection,
    tool_registry_collection,
    tools_collection,
)
from backend.prompt_generator.schemas import PromptGeneratorRequest

_SYSTEM_PROMPT = """You are an expert prompt and safety engineer. Generate an optimized system prompt and safety guardrails for an AI agent / workspace from the supplied identity and selected capabilities.

You MUST return a valid JSON object matching this exact schema:
{
  "prompt": "The complete optimized system prompt string...",
  "guardrails": "The safety guardrails, constraints, and operational boundaries string..."
}

Requirements for "prompt":
- Define the agent's role and personality clearly
- Set behavioral guidelines and domain execution rules
- Explain when and how to use the selected tools, MCP server tools, and connectors
- Prefer real tool/integration actions over telling the user to copy/paste or do work manually
- Specify output format preferences
- Include any relevant context from the description
- Be concise yet comprehensive

If any tools are listed below, you MUST list them under a section in "prompt" that starts
with EXACTLY this heading, verbatim, on its own line:
## Registered Tools

Under that heading, list each tool as its own bullet with a short description.
Immediately after the last tool bullet, include this exact sentence, verbatim,
on its own line, to close the section:
Use each tool only when the request requires its capability.

This exact heading and closing sentence are load-bearing: other parts of the
system look for them verbatim to append newly-added tools later, so do not
paraphrase, reformat, or omit them. If no tools are listed below, omit this
section entirely.

Requirements for "guardrails":
- Provide concrete safety constraints, boundary rules, and operational safeguards relevant to the agent's domain and capabilities.
- Examples: Never perform destructive write/delete actions without explicit user confirmation; protect sensitive credentials/API keys; refuse out-of-scope or unauthorized requests.

Return ONLY the raw JSON object, without markdown code blocks, backticks, or any additional text."""


def _format_items(title: str, items: list[dict[str, str]]) -> str:
    if not items:
        return f"{title}: none"
    lines = [f"{title}:"]
    for item in items:
        name = item.get("name") or "Unnamed"
        description = item.get("description") or "No description provided."
        lines.append(f"- {name}: {description}")
    return "\n".join(lines)


async def _resolve_tool_items(tool_ids: list[str]) -> list[dict[str, str]]:
    object_ids = [ObjectId(tid) for tid in tool_ids if ObjectId.is_valid(tid)]
    if not object_ids:
        return []

    tool_docs = await tools_collection.find(
        {"_id": {"$in": object_ids}, **NOT_DELETED}
    ).to_list(length=100)

    registry_ids = [
        ObjectId(t["tool_id"]) for t in tool_docs
        if t.get("tool_id") and ObjectId.is_valid(t["tool_id"])
    ]
    registry_by_id: dict[str, dict] = {}
    if registry_ids:
        registry_docs = await tool_registry_collection.find(
            {"_id": {"$in": registry_ids}, "is_deleted": {"$ne": True}}
        ).to_list(length=100)
        registry_by_id = {str(doc["_id"]): doc for doc in registry_docs}

    items: list[dict[str, str]] = []
    for tool in tool_docs:
        registry = registry_by_id.get(str(tool.get("tool_id", "")), {})
        prompt_or_desc = (
            tool.get("prompt")
            or registry.get("prompt")
            or tool.get("user_description")
            or registry.get("description")
            or ""
        )
        items.append({
            "name": tool.get("name") or registry.get("name") or "Tool",
            "description": prompt_or_desc,
        })
    return items


async def _resolve_mcp_items(server_ids: list[str]) -> list[dict[str, str]]:
    object_ids = [ObjectId(sid) for sid in server_ids if ObjectId.is_valid(sid)]
    if not object_ids:
        return []

    server_docs = await mcp_servers_collection.find(
        {"_id": {"$in": object_ids}, **NOT_DELETED}
    ).to_list(length=100)

    registry_keys = [doc["registry_key"] for doc in server_docs if doc.get("registry_key")]
    registry_by_key: dict[str, dict] = {}
    if registry_keys:
        registry_docs = await mcp_server_registry_collection.find(
            {"key": {"$in": registry_keys}, "is_deleted": {"$ne": True}}
        ).to_list(length=100)
        registry_by_key = {doc["key"]: doc for doc in registry_docs}

    items: list[dict[str, str]] = []
    for server in server_docs:
        registry = registry_by_key.get(server.get("registry_key", ""), {})
        tool_bits = []
        for tool in server.get("tools", []):
            name = tool.get("name") or "tool"
            desc = tool.get("prompt") or tool.get("description") or ""
            tool_bits.append(f"{name}{' - ' + desc if desc else ''}")
        prompt_or_desc = (
            server.get("prompt")
            or server.get("user_description")
            or registry.get("prompt")
            or registry.get("description")
            or ""
        )
        description_parts = [
            prompt_or_desc,
            "Exposed tools: " + "; ".join(tool_bits) if tool_bits else "",
        ]
        items.append({
            "name": server.get("name") or registry.get("name") or "MCP Server",
            "description": " ".join(part for part in description_parts if part).strip(),
        })
    return items


async def _resolve_connector_items(connector_ids: list[str]) -> list[dict[str, str]]:
    object_ids = [ObjectId(cid) for cid in connector_ids if ObjectId.is_valid(cid)]
    if not object_ids:
        return []

    connector_docs = await connector_registry_collection.find(
        {"_id": {"$in": object_ids}, "is_deleted": {"$ne": True}}
    ).to_list(length=100)

    items: list[dict[str, str]] = []
    for connector in connector_docs:
        actions = connector.get("available_actions", [])
        action_text = ", ".join(action.replace("_", " ") for action in actions)
        prompt_or_desc = connector.get("prompt") or connector.get("description") or ""
        description_parts = [
            prompt_or_desc,
            f"Available actions: {action_text}" if action_text else "",
        ]
        items.append({
            "name": connector.get("name") or connector.get("provider_id") or "Connector",
            "description": " ".join(part for part in description_parts if part).strip(),
        })
    return items


async def _build_agent_context(payload: PromptGeneratorRequest, current_user: UserPublic) -> str:
    if not payload.agent_id:
        return (
            f"Agent Name: {payload.agent_name}\n"
            f"Agent Description: {payload.agent_description}\n"
            "Selected Tools: none\n"
            "Selected MCP Servers: none\n"
            "Selected Connectors: none"
        )

    if not ObjectId.is_valid(payload.agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    agent = await agents_collection.find_one(
        {"_id": ObjectId(payload.agent_id), **NOT_DELETED}
    )
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    assert_org_access(current_user, agent["organization_id"])

    description = (
        agent.get("description")
        or agent.get("user_description")
        or payload.agent_description
        or ""
    )
    tool_items = await _resolve_tool_items(agent.get("tool_ids", []))
    mcp_items = await _resolve_mcp_items(agent.get("mcp_server_ids", []))
    connector_items = await _resolve_connector_items(agent.get("connector_ids", []))

    return "\n\n".join([
        f"Agent Name: {agent.get('name') or payload.agent_name or 'Unnamed Agent'}",
        f"Agent Description: {description}",
        _format_items("Selected Tools", tool_items),
        _format_items("Selected MCP Servers", mcp_items),
        _format_items("Selected Connectors", connector_items),
    ])


def _clean_and_parse_json(content: str) -> tuple[str, str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            prompt = str(data.get("prompt", "")).strip()
            guardrails = str(data.get("guardrails", "")).strip()
            return prompt, guardrails
    except Exception:
        pass

    return cleaned, ""


async def generate_prompt(
    payload: PromptGeneratorRequest,
    current_user: UserPublic,
) -> tuple[str, str]:
    user_msg = await _build_agent_context(payload, current_user)
    model = Model.GPT_5_4_NANO.value

    resp = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.7,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    raw_content = resp.choices[0].message.content.strip()
    return _clean_and_parse_json(raw_content)