"""OrchestrationAgent — loads its config from MongoDB and runs a tool-use loop.

Can call other agents it is connected to (via AgentPermissions) by using the
injected `call_agent` tool. Depth tracking and cycle prevention are handled
per-invocation through immutable `depth` and `visited` parameters.
"""
import logging
from typing import Dict, List, Optional

from bson import ObjectId

from ai.agents.loop import run_tool_loop
from ai.agents.permissions import AgentPermissions

logger = logging.getLogger(__name__)


class OrchestrationAgent:
    def __init__(
        self,
        agent_id: str,
        orchestration_snapshot: dict,
        permissions: AgentPermissions,
        sync_db,
        model: str,
        organization_id: str,
        depth: int = 0,
        visited: frozenset = frozenset(),
    ):
        self._agent_id = agent_id
        self._snapshot = orchestration_snapshot
        self._permissions = permissions
        self._sync_db = sync_db
        self._model = model
        self._organization_id = organization_id
        self._depth = depth
        self._visited = visited
        self._max_depth: int = orchestration_snapshot.get("max_depth", 5)

        self._doc: dict = {}
        self._tools: List[dict] = []
        self._tool_callables: Dict[str, callable] = {}
        self._callable_agents: List[dict] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> "OrchestrationAgent":
        doc = self._sync_db.agents.find_one({
            "_id": ObjectId(self._agent_id),
            "organization_id": self._organization_id,
            "is_deleted": {"$ne": True},
        })
        if not doc:
            raise ValueError(f"Agent '{self._agent_id}' not found or not in organization.")
        self._doc = doc
        self._load_own_tools()
        self._load_mcp_servers()
        self._load_callable_agents()
        if self._callable_agents:
            self._inject_call_agent_tool()
        return self

    def _load_own_tools(self) -> None:
        from ai.agents.sub_agent import _TOOL_REGISTRY
        tool_ids = self._doc.get("tool_ids", [])
        if not tool_ids:
            return
        object_ids = [ObjectId(tid) for tid in tool_ids if ObjectId.is_valid(tid)]
        tool_docs = list(self._sync_db.tools.find({"_id": {"$in": object_ids}}))
        for doc in tool_docs:
            handler = _TOOL_REGISTRY.get(doc.get("handler"))
            if not handler:
                logger.warning("[orch-agent:%s] unknown tool handler '%s' — skipped", self.name, doc.get("handler"))
                continue
            config = doc.get("config", {})
            self._tools.append({
                "type": "function",
                "function": {
                    "name": doc["name"],
                    "description": doc["description"],
                    "parameters": doc.get("input_schema", {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    }),
                },
            })
            agent_id = self._agent_id
            self._tool_callables[doc["name"]] = lambda inp, h=handler, c=config, aid=agent_id: (
                inp.update({"_agent_id": aid}), h(inp, **c)
            )[1]

    def _load_mcp_servers(self) -> None:
        server_ids = self._doc.get("mcp_server_ids", [])
        if not server_ids:
            return
        object_ids = [ObjectId(sid) for sid in server_ids if ObjectId.is_valid(sid)]
        server_docs = list(self._sync_db.mcp_servers.find({
            "_id": {"$in": object_ids},
            "is_active": True,
            "is_deleted": {"$ne": True},
        }))
        if not server_docs:
            return
        try:
            from backend.mcp_server.services import build_mcp_tools
            tools, callables = build_mcp_tools(server_docs)
            self._tools.extend(tools)
            self._tool_callables.update(callables)
        except Exception as exc:
            logger.error("[orch-agent:%s] MCP load failed: %s", self.name, exc)

    def _load_callable_agents(self) -> None:
        all_ids = self._snapshot.get("sub_agent_ids", [])
        callable_ids = [
            aid for aid in all_ids
            if self._permissions.can_call(self._agent_id, aid)
        ]
        if not callable_ids:
            return
        object_ids = [ObjectId(aid) for aid in callable_ids if ObjectId.is_valid(aid)]
        docs = list(self._sync_db.agents.find({
            "_id": {"$in": object_ids},
            "organization_id": self._organization_id,
            "is_deleted": {"$ne": True},
        }))
        self._callable_agents = [
            {
                "id": str(d["_id"]),
                "name": d.get("name", str(d["_id"])),
                "description": d.get("description") or d.get("prompt", "")[:120],
            }
            for d in docs
        ]

    def _inject_call_agent_tool(self) -> None:
        agent_list_text = "\n".join(
            f"  - id={a['id']} name={a['name']}: {a['description']}"
            for a in self._callable_agents
        )
        self._tools.append({
            "type": "function",
            "function": {
                "name": "call_agent",
                "description": (
                    "Delegate a subtask to a specialist agent in this orchestration.\n"
                    f"Available agents:\n{agent_list_text}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "ID of the agent to call",
                            "enum": [a["id"] for a in self._callable_agents],
                        },
                        "task": {
                            "type": "string",
                            "description": "The specific task or question to delegate",
                        },
                    },
                    "required": ["agent_id", "task"],
                },
            },
        })

        current_id = self._agent_id
        permissions = self._permissions
        snapshot = self._snapshot
        sync_db = self._sync_db
        model = self._model
        org_id = self._organization_id
        max_depth = self._max_depth
        current_depth = self._depth
        current_visited = self._visited

        def _call_agent(inp: dict) -> str:
            target_id = inp.get("agent_id", "")
            task = inp.get("task", "")

            if not permissions.can_call(current_id, target_id):
                return f"Permission denied: agent '{current_id}' cannot call agent '{target_id}'."

            if current_depth >= max_depth:
                return "Maximum delegation depth reached. Answering with available information."

            if target_id in current_visited:
                return f"Circular call detected: agent '{target_id}' is already in the call stack."

            logger.info(
                "[orch-agent:%s] call_agent → '%s' depth=%d task=%.100s",
                current_id, target_id, current_depth + 1, task,
            )
            sub = OrchestrationAgent(
                agent_id=target_id,
                orchestration_snapshot=snapshot,
                permissions=permissions,
                sync_db=sync_db,
                model=model,
                organization_id=org_id,
                depth=current_depth + 1,
                visited=current_visited | {current_id},
            )
            try:
                sub.load()
                return sub.invoke(task)
            except Exception as exc:
                logger.error("[orch-agent:call_agent] error loading/invoking '%s': %s", target_id, exc)
                return f"Agent '{target_id}' could not complete the task: {exc}"

        self._tool_callables["call_agent"] = _call_agent

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(self, task: str) -> str:
        logger.info("[orch-agent:%s] invoke depth=%d task=%.150s", self.name, self._depth, task)
        system = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        output, _, _ = run_tool_loop(
            model=self._model,
            tools=self._tools,
            tool_callables=self._tool_callables,
            messages=messages,
            agent_name=self.name,
        )
        return output or "I was unable to complete this task."

    def _build_system_prompt(self) -> str:
        prompt = self._doc.get("prompt", "You are a helpful assistant.")
        guardrails = self._doc.get("guardrails", [])
        if isinstance(guardrails, str):
            guardrails = [guardrails] if guardrails else []
        if guardrails:
            rules = "\n".join(f"- {g}" for g in guardrails)
            prompt += f"\n\nGUARDRAILS:\n{rules}"
        if self._callable_agents:
            names = ", ".join(a["name"] for a in self._callable_agents)
            prompt += (
                f"\n\nYou are part of a multi-agent orchestration. You can delegate subtasks "
                f"to these specialist agents using the call_agent tool: {names}. "
                "Delegate when the task clearly benefits from their specialization."
            )
        return prompt

    @property
    def name(self) -> str:
        return self._doc.get("name", self._agent_id)
