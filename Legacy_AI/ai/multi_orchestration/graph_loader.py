"""GraphLoader — one-shot BFS that pre-hydrates every agent node before execution starts.

Replaces the recursive lazy-loading done inside OrchestrationAgent._load_callable_agents().
All DB queries happen up-front in a single batch, so the execution engine never blocks
waiting for agent documents mid-run.
"""
import logging
from typing import Callable, Dict, List, Optional, Set, Tuple

from bson import ObjectId
from ai.tools.tools import Tools, validate_query_and_connection
from ai.multi_orchestration.runtime_graph import RuntimeAgentNode, RuntimeGraph
from ai.multi_orchestration.supervisor import (
    DEFAULT_MAX_CONSECUTIVE_HANDBACKS,
    DEFAULT_MAX_HOPS,
    DEFAULT_MAX_VISITS_PER_AGENT,
    render_agent_mode_prompt,
)
from backend.mcp_server.services import load_agent_mcp_tools_sync

logger = logging.getLogger(__name__)


def _resolve_tool_parameters(td: dict, db) -> dict:
    """Dynamically resolve tool JSON schema from tool document or tool_registry collection."""
    parameters = (
        td.get("tool_schema")
        or td.get("parameters")
        or td.get("input_schema")
    )
    if not parameters:
        # 1. Try by tool_id if present
        reg_doc = None
        if td.get("tool_id") and ObjectId.is_valid(str(td["tool_id"])):
            try:
                reg_doc = db.tool_registry.find_one({"_id": ObjectId(str(td["tool_id"]))})
            except Exception:
                pass
        
        # 2. Fall back to matching by name or handler in tool_registry
        if not reg_doc:
            tool_name = td.get("name") or td.get("handler")
            if tool_name:
                try:
                    reg_doc = db.tool_registry.find_one({"name": tool_name, "is_deleted": {"$ne": True}})
                except Exception:
                    pass

        if reg_doc:
            parameters = (
                reg_doc.get("tool_schema")
                or reg_doc.get("parameters")
                or reg_doc.get("input_schema")
            )

    if not parameters or not isinstance(parameters, dict):
        parameters = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query or input parameter for this tool."},
            },
            "required": ["query"],
        }
    return parameters


class GraphLoader:
    def __init__(
        self,
        orchestration_snapshot: dict,
        sync_db,
        organization_id: str,
        user_id: str = "",
    ):
        self._snapshot = orchestration_snapshot
        self._db = sync_db
        self._org_id = organization_id
        self._user_id = user_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> RuntimeGraph:
        max_depth = self._snapshot.get("max_depth", 5)
        mode = self._snapshot.get("mode") or "sequential"
        supervised = mode == "supervisor"
        config = self._snapshot.get("supervisor_config") or {}

        if supervised:
            # No edges: the Supervisor routes dynamically, so every attached
            # agent is a candidate and there is no entry-point agent document.
            main_id: Optional[str] = None
            adjacency, reverse_adjacency, edge_types, edge_labels = {}, {}, {}, {}
            all_ids = {aid for aid in (self._snapshot.get("sub_agent_ids") or []) if aid}
        else:
            main_id = self._snapshot["main_agent_id"]
            adjacency, reverse_adjacency, edge_types, edge_labels, all_ids = self._build_adjacency(
                main_id, self._snapshot.get("connections", [])
            )

        join_points = {
            node for node, inbound in reverse_adjacency.items() if len(inbound) > 1
        }
        all_targets = {to for targets in adjacency.values() for to in targets}
        hub_nodes = {node for node in adjacency if node in all_targets}
        has_parallel = any(et == "parallel" for et in edge_types.values())

        docs_by_id = self._batch_load_agents(all_ids)

        nodes: Dict[str, RuntimeAgentNode] = {}
        for agent_id in all_ids:
            doc = docs_by_id.get(agent_id)
            if not doc:
                logger.warning("[graph-loader] agent %s not found — skipped", agent_id)
                continue
            (
                tools, callables, connector_tool_owner,
                mcp_tool_owner, load_errors, extra_tool_prompt,
            ) = self._load_agent_tools(doc)
            guardrails = doc.get("guardrails", [])
            if isinstance(guardrails, str):
                guardrails = [guardrails] if guardrails else []

            tool_prompt = (doc.get("tool_prompt", "") or "") + extra_tool_prompt

            nodes[agent_id] = RuntimeAgentNode(
                agent_id=agent_id,
                name=doc.get("name", agent_id),
                prompt=doc.get("prompt", "You are a helpful assistant."),
                guardrails=guardrails,
                tools=tools,
                tool_callables=callables,
                description=doc.get("description") or doc.get("prompt", "")[:120],
                tool_prompt=tool_prompt,
                mcp_prompt=doc.get("mcp_prompt", "") or "",
                connector_prompt=doc.get("connector_prompt", "") or "",
                connector_tool_owner=connector_tool_owner,
                mcp_tool_owner=mcp_tool_owner,
                user_description=doc.get("user_description", "") or "",
                capability_load_errors=load_errors,
                # Supervisor mode replaces the sequential PIPELINE CONTEXT block
                # (which needs a static next-agent list) with team context plus
                # the handback rule. Filled in with the peer roster below, once
                # every node is known. Empty in sequential mode.
                handback_prompt="",
            )
            if "ask_human" not in callables:
                logger.warning(
                    "[graph-loader] agent '%s' has no ask_human tool — it cannot "
                    "pause for human input. Seed the registry and backfill: "
                    "python -m backend.scripts.seed_function_tools && "
                    "python -m backend.scripts.backfill_ask_human",
                    doc.get("name", agent_id),
                )

        # Supervisor mode: give every agent the roster of its teammates, so a
        # handback can name the likely owner instead of going into the void.
        # Without it two agents can bounce the same request at each other until
        # the turn dies with nothing for the user.
        if supervised:
            for agent_id, node in nodes.items():
                peers = [
                    {"name": other.name, "purpose": other.description}
                    for other_id, other in nodes.items() if other_id != agent_id
                ]
                node.handback_prompt = render_agent_mode_prompt(peers)

        # Wire each node's next_agents from the adjacency map
        for agent_id, node in nodes.items():
            node.next_agents = [
                {"name": nodes[nid].name, "description": nodes[nid].description}
                for nid in adjacency.get(agent_id, [])
                if nid in nodes
            ]

        logger.info(
            "[graph-loader] mode=%s loaded %d nodes, %d edges, join_points=%s hub_nodes=%s",
            mode, len(nodes), sum(len(v) for v in adjacency.values()), join_points, hub_nodes,
        )
        return RuntimeGraph(
            orchestration_id=str(self._snapshot.get("_id", "")),
            main_agent_id=main_id,
            nodes=nodes,
            adjacency=adjacency,
            reverse_adjacency=reverse_adjacency,
            edge_types=edge_types,
            edge_labels=edge_labels,
            join_points=join_points,
            hub_nodes=hub_nodes,
            has_parallel_branches=has_parallel,
            max_depth=max_depth,
            max_visits_per_agent=config.get("max_visits_per_agent", DEFAULT_MAX_VISITS_PER_AGENT),
            mode=mode,
            supervisor_max_hops=config.get("max_hops", DEFAULT_MAX_HOPS),
            supervisor_max_consecutive_handbacks=config.get(
                "max_consecutive_handbacks", DEFAULT_MAX_CONSECUTIVE_HANDBACKS
            ),
            supervisor_instructions=config.get("custom_instructions", "") or "",
            supervisor_allow_direct_answer=config.get("allow_direct_answer", True),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_adjacency(
        self,
        main_id: str,
        connections: list,
    ) -> Tuple[Dict, Dict, Dict, Dict, Set[str]]:
        adjacency: Dict[str, List[str]] = {}
        reverse_adjacency: Dict[str, List[str]] = {}
        edge_types: Dict[tuple, str] = {}
        edge_labels: Dict[tuple, str] = {}
        all_ids: Set[str] = {main_id}

        for conn in connections:
            frm = conn.get("from_agent_id", "")
            to = conn.get("to_agent_id", "")
            if not frm or not to or frm == to:
                continue
            all_ids.update([frm, to])

            if to not in adjacency.setdefault(frm, []):
                adjacency[frm].append(to)
            if frm not in reverse_adjacency.setdefault(to, []):
                reverse_adjacency[to].append(frm)

            edge_types[(frm, to)] = conn.get("edge_type", "sequential")
            edge_labels[(frm, to)] = conn.get("label", "") or ""

        return adjacency, reverse_adjacency, edge_types, edge_labels, all_ids

    def _batch_load_agents(self, agent_ids: Set[str]) -> Dict[str, dict]:
        valid_ids = [ObjectId(aid) for aid in agent_ids if ObjectId.is_valid(aid)]
        docs = list(self._db.agents.find({
            "_id": {"$in": valid_ids},
            "organization_id": self._org_id,
            "is_deleted": {"$ne": True},
        }))
        return {str(d["_id"]): d for d in docs}

    def _load_agent_tools(
        self, doc: dict
    ) -> Tuple[
        List[dict],
        Dict[str, Callable],
        Dict[str, Dict[str, str]],
        Dict[str, str],
        List[str],
        str,
    ]:
        """Returns (tools, callables, connector_tool_owner, mcp_tool_owner,
        capability_load_errors, extra_tool_prompt).

        `capability_load_errors` records capabilities configured on the agent
        that could not be loaded for this run. They used to be warn-and-drop,
        which left the Supervisor routing to an agent whose Gmail was silently
        gone; surfacing them keeps the agent routable but the failure explicable.
        """
        tools: List[dict] = []
        callables: Dict[str, Callable] = {}
        connector_tool_owner: Dict[str, Dict[str, str]] = {}
        mcp_tool_owner: Dict[str, str] = {}
        load_errors: List[str] = []
        extra_prompt = ""

        # 1. Custom tools from the tools collection (via _TOOL_REGISTRY)
        tool_ids = doc.get("tool_ids", [])
        query_db_conn_id: Optional[str] = None
        has_query_db = False
        if tool_ids:
            from ai.agents.sub_agent import _TOOL_REGISTRY
            valid_ids = [ObjectId(tid) for tid in tool_ids if ObjectId.is_valid(tid)]
            # Exclude soft-deleted instances so a removed tool isn't silently
            # still callable (keeps runtime consistent with regenerate_tool_prompt).
            tool_docs = list(self._db.tools.find({
                "_id": {"$in": valid_ids},
                "is_deleted": {"$ne": True},
            }))
            for td in tool_docs:
                # handler field in the tool doc may be null; fall back to the tool name
                handler_key = td.get("handler") or td.get("name")

                # query_db is a "db_query"-type registry entry with no handler
                # of its own (see backend/scripts/seed_function_tools.py) — it's
                # executed via a dedicated DB runner, not a _TOOL_REGISTRY entry.
                # It historically only worked in the direct single-agent chat
                # path (backend/chat/graph.py); wire the same capability here so
                # orchestration nodes with a query_db tool can actually query.
                if handler_key in {"query_mongo_read", "query_mongo_write", "query_sql_read", "query_sql_write"} or td.get("type") == "db_query":
                    has_query_db = True
                    query_db_conn_id = td.get("db_conn_id") or query_db_conn_id
                    stamped_doc = {
                        **td,
                        "_org_id": self._org_id,
                        "_agent_id": str(doc.get("_id", "")),
                    }
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": td.get("name", handler_key),
                            "description": td.get("description") or td.get("user_description") or (
                                "Execute a query against the organization's connected database."
                            ),
                            "parameters": _resolve_tool_parameters(td, self._db),
                        },
                    })
                    
                    if handler_key in {"query_mongo_read", "query_mongo_write"}:
                        callables[td.get("name", handler_key)] = (
                            lambda inp, d=stamped_doc, sdb=self._db: (
                                validate_query_and_connection(d, inp, sdb, is_mongo=True) or Tools.query_mongo_sync(d, inp, sdb)
                            )
                        )
                    else:
                        callables[td.get("name", handler_key)] = (
                            lambda inp, d=stamped_doc, sdb=self._db: (
                                validate_query_and_connection(d, inp, sdb, is_mongo=False) or Tools.query_sql_sync(d, inp, sdb)
                            )
                        )
                    continue

                handler = _TOOL_REGISTRY.get(handler_key)
                if not handler:
                    logger.warning(
                        "[graph-loader] unknown tool handler '%s' on agent '%s' — skipped",
                        handler_key, doc.get("name"),
                    )
                    load_errors.append(f"{td.get('name') or handler_key} (tool unavailable)")
                    continue
                config = td.get("config", {})
                tools.append({
                    "type": "function",
                    "function": {
                        "name": td["name"],
                        "description": td.get("description") or td.get("user_description") or "",
                        "parameters": _resolve_tool_parameters(td, self._db),
                    },
                })
                agent_id = str(doc.get("_id", ""))
                callables[td["name"]] = lambda inp, h=handler, c=config, aid=agent_id: (
                    inp.update({"_agent_id": aid}), h(inp, **c)
                )[1]

        # 2. Connector tools (Gmail, Google Drive, Sheets, OneDrive, etc.)
        connector_ids = doc.get("connector_ids", [])
        if connector_ids and self._user_id:
            self._load_connector_tools(
                doc, connector_ids, tools, callables, connector_tool_owner, load_errors
            )

        # 3. MCP tools — per-tool attachments (agent_mcp_tools), not whole
        # servers via the legacy agent.mcp_server_ids.
        try:
            mcp_tools, mcp_callables, mcp_owner = load_agent_mcp_tools_sync(str(doc["_id"]))
            if mcp_tools:
                tools.extend(mcp_tools)
                callables.update(mcp_callables)
                mcp_tool_owner.update(mcp_owner)
                logger.info(
                    "[graph-loader] loaded %d MCP tool(s) for agent '%s'",
                    len(mcp_tools), doc.get("name"),
                )
        except Exception as exc:
            logger.error(
                "[graph-loader] MCP load failed for agent '%s': %s",
                doc.get("name"), exc,
            )
            load_errors.append("MCP servers (unreachable)")

        # 4. Auto-inject search_schema alongside query_db, mirroring the direct
        # single-agent chat path (backend/chat/graph.py) — without it the agent
        # has to guess table/column names blind.
        if has_query_db and "search_schema" not in callables:
            db_conn_ids = self._resolve_db_conn_ids(query_db_conn_id)
            if db_conn_ids:
                from ai.rag.search_schema_tool import build_search_schema_tool, execute_search_schema_sync
                schema_tool_doc = build_search_schema_tool(self._org_id, db_conn_ids)
                tools.append({
                    "type": "function",
                    "function": {
                        "name": schema_tool_doc["name"],
                        "description": schema_tool_doc["description"],
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "What data/tables you are looking for.",
                                },
                            },
                            "required": ["query"],
                        },
                    },
                })
                callables[schema_tool_doc["name"]] = (
                    lambda inp, d=schema_tool_doc: execute_search_schema_sync(d, inp)
                )
                extra_prompt = (
                    "\n\nWhen the request involves querying a database, call search_schema "
                    "first to discover the exact table and column names, then call query_db "
                    "using those exact names.\n"
                    "If a query fails with an invalid or unknown object name, the indexed "
                    "schema is stale or the object sits in a different schema — do NOT "
                    "re-issue the identical SQL. Confirm what actually exists first, e.g. "
                    "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE "
                    "TABLE_NAME IN (...), then rewrite the query with the real names. Only "
                    "report a data problem once that check has also failed."
                )
            else:
                logger.warning(
                    "[graph-loader] agent '%s' has query_db but no database connection "
                    "is configured for org=%s — search_schema not injected",
                    doc.get("name"), self._org_id,
                )

        # 5. Auto-inject search_knowledge_base for agents with rag_ids, mirroring
        # the search_schema injection above and backend/chat/graph.py's pattern.
        # rag_ids is re-checked against this specific requesting user (not just
        # baked in as-is) so a personal/team/selected-users KB an agent
        # references is never searchable by a user who shouldn't see it.
        raw_rag_ids = doc.get("rag_ids") or []
        rag_ids = self._filter_visible_kb_ids(raw_rag_ids) if raw_rag_ids else []
        if rag_ids and "search_knowledge_base" not in callables:
            from ai.rag.kb_tool import build_kb_search_tool, execute_kb_search_sync
            kb_tool_doc = build_kb_search_tool(self._org_id, rag_ids)
            tools.append({
                "type": "function",
                "function": {
                    "name": kb_tool_doc["name"],
                    "description": kb_tool_doc["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What information you are looking for.",
                            },
                        },
                        "required": ["query"],
                    },
                },
            })
            # Accepts an optional `history` positional arg — AgentInvoker._wrap
            # special-cases this tool name to pass the turn's recent
            # conversation history for query rephrasing; every other callable
            # keeps the plain single-arg (inp) signature.
            callables[kb_tool_doc["name"]] = (
                lambda inp, history=None, d=kb_tool_doc: execute_kb_search_sync(d, inp, history=history)
            )

        # ask_human is NOT injected here — it is a registry tool auto-assigned to
        # every agent at creation (see backend.agent.services._auto_assign_default_tools),
        # so it arrives through the normal tool_ids path above like any other tool.

        logger.info(
            "[graph-loader] agent '%s' — %d tool(s) loaded (connectors=%d, mcp=%d, custom=%d)",
            doc.get("name"),
            len(tools),
            len([t for t in tools if any(
                t.get("function", {}).get("name", "").startswith(p)
                for p in ("gmail_", "google_drive_", "outlook_", "onedrive_", "slack_")
            )]),
            len(mcp_tool_owner),
            len(tool_ids),
        )
        return tools, callables, connector_tool_owner, mcp_tool_owner, load_errors, extra_prompt

    def _filter_visible_kb_ids(self, kb_ids: List[str]) -> List[str]:
        """Re-check KB visibility for self._user_id before baking rag_ids into
        the search_knowledge_base tool — see filter_visible_kb_ids_sync."""
        from backend.knowledgebase.services import filter_visible_kb_ids_sync

        return filter_visible_kb_ids_sync(self._db, self._org_id, kb_ids, self._user_id)

    def _resolve_db_conn_ids(self, query_db_conn_id: Optional[str]) -> List[str]:
        """Mirror of backend.chat.services._load_org_agents' db_conn_ids resolution:
        use the query_db tool's own connection if it was pinned to one, otherwise
        fall back to every active database connection in the org."""
        if query_db_conn_id:
            return [query_db_conn_id]
        conn_docs = list(self._db.db_connections.find({
            "organization_id": self._org_id,
            "is_deleted": {"$ne": True},
        }))
        return [str(c["_id"]) for c in conn_docs]

    def _get_fresh_access_token(self, connector_id: str, owner_id: str) -> Optional[str]:
        from ai.connectors.token_utils import get_valid_token_sync
        return get_valid_token_sync(self._db, connector_id, owner_id)

    def _load_connector_tools(
        self,
        doc: dict,
        connector_ids: list,
        tools: list,
        callables: dict,
        connector_tool_owner: dict,
        load_errors: list,
    ) -> None:
        """Mirror of sub_agent.load_connectors — sync version using self._db."""
        try:
            from ai.connectors.registry import CONNECTOR_CLASS_MAP
        except Exception as exc:
            logger.error("[graph-loader] connector imports failed: %s", exc)
            return

        agent_name = doc.get("name", "?")
        org_id = doc.get("organization_id", self._org_id)

        for connector_id in connector_ids:
            try:
                registry_doc = self._db.connector_registry.find_one(
                    {"_id": ObjectId(connector_id)}
                )
                if not registry_doc or not registry_doc.get("is_active"):
                    logger.warning(
                        "[graph-loader] connector %s not active — skipped for agent '%s'",
                        connector_id, agent_name,
                    )
                    load_errors.append(
                        f"{(registry_doc or {}).get('name') or connector_id} (connector inactive)"
                    )
                    continue

                provider_id: str = registry_doc["provider_id"]
                owner_id = (
                    org_id
                    if registry_doc.get("owner_scope") == "organization"
                    else self._user_id
                )

                display_name = registry_doc.get("name", provider_id)
                access_token = self._get_fresh_access_token(connector_id, owner_id)
                if not access_token:
                    logger.warning(
                        "[graph-loader] could not obtain valid token for connector %s (provider=%s) agent '%s'",
                        connector_id, provider_id, agent_name,
                    )
                    load_errors.append(f"{display_name} (needs reconnecting)")
                    continue
                cls = CONNECTOR_CLASS_MAP.get(provider_id)
                if not cls:
                    logger.warning(
                        "[graph-loader] no class for provider '%s' agent '%s'",
                        provider_id, agent_name,
                    )
                    load_errors.append(f"{display_name} (unsupported provider)")
                    continue

                c_tools, c_callables = cls(access_token=access_token, agent_id=str(doc.get("_id", ""))).as_tools()
                tools.extend(c_tools)
                callables.update(c_callables)
                meta = {"connector_id": connector_id, "provider_id": provider_id, "display_name": display_name}
                for t in c_tools:
                    fn_name = t.get("function", {}).get("name")
                    if fn_name:
                        connector_tool_owner[fn_name] = meta
                logger.info(
                    "[graph-loader] loaded %d connector tool(s) from '%s' for agent '%s'",
                    len(c_tools), provider_id, agent_name,
                )
            except Exception as exc:
                logger.error(
                    "[graph-loader] failed to load connector %s for agent '%s': %s",
                    connector_id, agent_name, exc,
                )
                load_errors.append(f"{connector_id} (connector failed to load)")
