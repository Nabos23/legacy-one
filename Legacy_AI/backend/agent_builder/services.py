import json
import re
import litellm
from ai.models import Model
from backend.agent_builder.schemas import AgentBlueprint, BuilderOption, BuilderQuestion, BuilderRequest
from backend.db.database import connector_registry_collection, mcp_server_registry_collection, tool_registry_collection

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from", "get",
    "give", "has", "have", "how", "i", "if", "in", "into", "is", "it", "its",
    "me", "my", "of", "on", "or", "our", "return", "should", "that", "the",
    "then", "this", "to", "use", "using", "want", "what", "when", "will",
    "with", "you", "your",
}

def _tokens(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", value.lower()) if w not in _STOPWORDS}

def _matches(prompt: str, item: dict) -> bool:
    haystack = " ".join(str(item.get(k, "")) for k in ("name", "provider_id", "key", "description", "category", "type"))
    words = _tokens(prompt)
    item_words = _tokens(haystack)
    return bool(words & item_words) or any(
        alias in prompt.lower() and alias in haystack.lower()
        for alias in ("email", "calendar", "slack", "github", "jira", "notion", "salesforce")
    )

def _available_options(connectors: list[dict], mcp_entries: list[dict], tool_entries: list[dict]) -> list[dict]:
    """The full active catalog (not just the top prompt-matched candidates),
    shaped as BuilderOption dicts so the client can offer it as a substitute
    picker when the prompt named something unmatched. `value` is prefixed
    with its kind so the client knows which blueprint list to attach it to."""
    options = [
        {"value": f"connector:{c['_id']}", "label": c.get("name") or c.get("provider_id") or "Connector", "description": c.get("description")}
        for c in connectors
    ]
    options += [
        {"value": f"mcp:{m['key']}", "label": m.get("name") or m["key"], "description": m.get("description")}
        for m in mcp_entries if m.get("key")
    ]
    options += [
        {"value": f"tool:{t['_id']}", "label": t.get("name") or "Tool", "description": t.get("description")}
        for t in tool_entries
    ]
    return options

async def build_blueprint(payload: BuilderRequest) -> AgentBlueprint:
    connectors = await connector_registry_collection.find(
        {"is_active": True, "is_visible": {"$ne": False}, "is_deleted": {"$ne": True}}
    ).to_list(length=200)
    mcp_entries = await mcp_server_registry_collection.find(
        {"is_active": {"$ne": False}, "is_deleted": {"$ne": True}}
    ).to_list(length=200)
    tool_entries = await tool_registry_collection.find(
        {"is_active": {"$ne": False}, "is_deleted": {"$ne": True}}
    ).to_list(length=200)

    candidates = [c for c in connectors if _matches(payload.prompt, c)]
    mcp_candidates = [m for m in mcp_entries if _matches(payload.prompt, m)]
    tool_candidates = [t for t in tool_entries if _matches(payload.prompt, t)]
    available_options = _available_options(connectors, mcp_entries, tool_entries)
    catalog = {
        "connectors": [{"id": str(c["_id"]), "provider_id": c.get("provider_id"), "name": c.get("name"), "description": c.get("description", "")} for c in candidates[:20]],
        "mcp": [{"key": m.get("key"), "name": m.get("name"), "description": m.get("description", ""), "requires": m.get("requires", [])} for m in mcp_candidates[:20]],
        "tools": [{"id": str(t["_id"]), "name": t.get("name"), "type": t.get("type"), "description": t.get("description", "")} for t in tool_candidates[:20]],
    }
    system = """Turn a user's request into a deployable AI-agent blueprint. Use only catalog IDs/keys supplied.

Default to ready=true with zero questions. Only ask a question when the request cannot proceed at all without it — in practice this means: two or more integrations in the catalog plausibly provide the same required capability, and neither the prompt nor the answers already resolve it. If the catalog has zero or one plausible match, do not ask about integration choice either.

Never ask about anything else: recipients, subject/body text, attachment handling, confirmation policy, formatting, tone, scheduling, or any other operational detail. If the prompt leaves those unspecified, fill them with a sensible default and state the assumption in the description or guardrails instead of asking. Never ask a question whose answer is already stated or implied in the prompt or in answers.

The catalog has three sections: connectors (OAuth integrations like Outlook/Gmail/Slack — pick these for "send an email/message" type capabilities), tools (first-party function tools, e.g. generate_pdf for producing/returning a PDF or report, query_db for querying the organization's connected database — pick every tool candidate whose capability the request actually needs; never leave a capability the user asked for unfulfilled when a matching tool exists), and mcp (third-party MCP servers — some require a `requires` placeholder like <PATH> that nothing in this flow can collect, so only pick an mcp entry with a non-empty `requires` list if no connector or tool candidate covers the same need; never pick a local/stdio mcp entry just because its description loosely overlaps the request).

At most one question total, ever. Keep the system prompt operational and explicit about using selected integrations and tools. Guardrails must be at least 10 characters.

If the request names or clearly implies a specific capability/service/integration that has NO plausible match anywhere in the catalog (not in connectors, tools, or mcp), add a short human-readable label for it (e.g. "Zendesk", "SMS via Twilio") to `unmatched_capabilities`. Do this in addition to building the best blueprint you can from what IS available — never leave the whole response empty just because one capability is missing. Do not guess speculatively; only flag something as unmatched when the request is specific about it and the catalog truly has nothing close.

Return JSON only with: name, description, system_prompt, guardrails, connector_ids, connector_names, mcp_registry_keys, mcp_names, tool_ids, tool_names, unmatched_capabilities, questions [{id,text,options:[{value,label,description}]}], ready. ready is false only when questions is non-empty."""
    try:
        response = await litellm.acompletion(
            model=Model.GPT_5_4_NANO.value,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": json.dumps({"request": payload.prompt, "answers": payload.answers, "catalog": catalog})}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1400,
        )
        data = json.loads(response.choices[0].message.content)
        valid_connector_ids = {row["id"] for row in catalog["connectors"]}
        valid_mcp_keys = {row["key"] for row in catalog["mcp"] if row.get("key")}
        valid_tool_ids = {row["id"] for row in catalog["tools"]}
        db_tool_ids = {row["id"] for row in catalog["tools"] if row.get("type") == "db_query"}
        data["connector_ids"] = [v for v in data.get("connector_ids", []) if v in valid_connector_ids]
        data["mcp_registry_keys"] = [v for v in data.get("mcp_registry_keys", []) if v in valid_mcp_keys]
        data["tool_ids"] = [v for v in data.get("tool_ids", []) if v in valid_tool_ids]
        data["db_tool_ids"] = [v for v in data["tool_ids"] if v in db_tool_ids]
        data["requires_db_connection"] = bool(data["db_tool_ids"])
        data["unmatched_capabilities"] = [v for v in data.get("unmatched_capabilities", []) if isinstance(v, str) and v.strip()][:10]
        data["available_options"] = available_options
        return AgentBlueprint.model_validate(data)
    except Exception:
        chosen = candidates[:1]
        if len(candidates) > 1 and not payload.answers.get("integration"):
            return AgentBlueprint(
                name="Custom automation agent", description=payload.prompt,
                system_prompt=f"You are an automation agent. Your objective is: {payload.prompt}",
                guardrails="Confirm high-impact or destructive actions before executing them.",
                questions=[BuilderQuestion(id="integration", text="Which service should this agent use?", options=[BuilderOption(value=str(c["_id"]), label=c.get("name", "Connector"), description=c.get("description")) for c in candidates[:6]])],
                available_options=available_options,
            )
        if payload.answers.get("integration"):
            chosen = [c for c in candidates if str(c["_id"]) == payload.answers["integration"]]
        return AgentBlueprint(
            name="Custom automation agent", description=payload.prompt,
            system_prompt=f"You are an automation agent. Complete this objective using the attached capabilities: {payload.prompt}",
            guardrails="Protect private data and confirm destructive or irreversible actions.",
            connector_ids=[str(c["_id"]) for c in chosen], connector_names=[c.get("name", "Connector") for c in chosen], ready=True,
            available_options=available_options,
        )
