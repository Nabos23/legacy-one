import json
import logging
import time
from typing import Dict, List, Optional
from pathlib import Path

import litellm
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from ai.memory.memory import LocalMemory
from ai.memory.memory_schema import MemorySchema
from ai.tools.tools import HumanInterruptException as _HumanInterrupt
from backend.mcp_server.services import build_mcp_tools
from ai.tracing.tracer import AgentTracer
from bson import ObjectId

logger = logging.getLogger(__name__)

_MEMORY_DUMP_DIR = Path("memory_dumps")


def _dump_agent_memory(entries: list, agent_name: str) -> None:
    _MEMORY_DUMP_DIR.mkdir(exist_ok=True)
    filename = _MEMORY_DUMP_DIR / f"memory_{agent_name.lower().replace(' ', '_')}.json"
    data = [
        (e.model_dump() if hasattr(e, "model_dump") else e.dict())
        for e in entries
    ]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


_RETRYABLE = (RateLimitError, ServiceUnavailableError, Timeout)
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2  # seconds, doubles each attempt


def _completion_with_retry(lf_metadata: Optional[dict] = None, **kwargs):
    """
    Wraps litellm.completion with exponential-backoff retry on transient errors.

    lf_metadata is merged into the call's metadata so LiteLLM's Langfuse
    callback links the resulting generation to the active trace and span.
    """
    if lf_metadata:
        existing = kwargs.get("metadata") or {}
        kwargs["metadata"] = {**existing, **lf_metadata}

    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            return litellm.completion(**kwargs)
        except _RETRYABLE as e:
            last_exc = e
            wait = _RETRY_BACKOFF * (2 ** attempt)
            logger.warning(
                "LiteLLM transient error (attempt %d/%d): %s — retrying in %ss",
                attempt + 1, _MAX_RETRIES, e, wait,
            )
            time.sleep(wait)
        except (AuthenticationError, BadRequestError):
            raise
    raise last_exc


class SubAgent:

    def __init__(
        self,
        agent_id: str,
        db,
        model: str,
        memory: LocalMemory,
        tracer: Optional[AgentTracer] = None,
        mongo_store=None,
    ):
        self.agent_id = agent_id
        self._db = db
        self._model = model
        self.memory = memory
        self._tracer = tracer or AgentTracer(org_id="", user_id="")
        self._mongo_store = mongo_store

        self._doc: dict = {}
        self._tools: List[dict] = []
        self._tool_callables: Dict[str, callable] = {}
        self._mcp_tool_names: set = set()  # subset of tools sourced from MCP servers

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_agent(self) -> "SubAgent":
        # Treat a missing `is_active` as active (agents created via the API don't
        # set it) and exclude soft-deleted agents. Only an explicit is_active=False
        # is considered inactive.
        doc = self._db.agents.find_one({
            "_id": ObjectId(self.agent_id),
            "is_active": {"$ne": False},
            "is_deleted": {"$ne": True},
        })
        if not doc:
            raise ValueError(f"Agent '{self.agent_id}' not found or inactive.")
        self._doc = doc
        return self

    def load_tools(self) -> "SubAgent":
        tool_ids = self._doc.get("tool_ids", [])
        if not tool_ids:
            return self

        object_ids = [ObjectId(tid) if not isinstance(tid, type(ObjectId())) else tid for tid in tool_ids]
        tool_docs = list(self._db.tools.find({"_id": {"$in": object_ids}}))

        for doc in tool_docs:
            handler = _TOOL_REGISTRY.get(doc["handler"])
            if not handler:
                raise ValueError(f"Tool handler '{doc['handler']}' is not registered.")

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
            agent_id = self.agent_id
            self._tool_callables[doc["name"]] = lambda inp, h=handler, c=config, aid=agent_id: (
                inp.update({"_agent_id": aid}), h(inp, **c)
            )[1]

        return self

    def load_connectors(self, user_id: str, organization_id: str) -> "SubAgent":
        """Load connector tools for every connector_id stored on this agent's doc."""
        from ai.connectors.registry import CONNECTOR_CLASS_MAP
        from ai.connectors.token_utils import get_valid_token_sync

        connector_ids = self._doc.get("connector_ids", [])
        if not connector_ids:
            return self

        for connector_id in connector_ids:
            try:
                registry_doc = self._db.connector_registry.find_one({"_id": ObjectId(connector_id)})
                if not registry_doc or not registry_doc.get("is_active"):
                    continue

                provider_id: str = registry_doc["provider_id"]
                owner_id = organization_id if registry_doc.get("owner_scope") == "organization" else user_id

                access_token = get_valid_token_sync(self._db, connector_id, owner_id)
                if not access_token:
                    logger.warning(
                        "No valid token for connector %s (provider=%s) — skipping", connector_id, provider_id
                    )
                    continue

                cls = CONNECTOR_CLASS_MAP.get(provider_id)
                if not cls:
                    logger.warning("No connector class for provider '%s' — skipping", provider_id)
                    continue

                instance = cls(access_token=access_token, agent_id=self.agent_id)
                tools, callables = instance.as_tools()
                self._tools.extend(tools)
                self._tool_callables.update(callables)
                logger.info(
                    "Loaded %d connector tool(s) from '%s' for agent '%s'",
                    len(tools), provider_id, self.name,
                )
            except Exception as exc:  # noqa: BLE001 - never fail agent load on connector issues
                logger.error("Failed to load connector %s for agent '%s': %s", connector_id, self.name, exc)

        return self

    def load_rag_tools(self, user_id: str, organization_id: str) -> "SubAgent":
        """Auto-inject search_knowledge_base for agents with rag_ids attached,
        mirroring backend/chat/graph.py's and ai/multi_orchestration's
        injection of the same synthetic tool. rag_ids is re-checked against
        this specific requesting user first, so a personal/team/selected-users
        KB is never searchable by someone who shouldn't see it."""
        raw_rag_ids = self._doc.get("rag_ids", [])
        if not raw_rag_ids:
            return self

        from backend.knowledgebase.services import filter_visible_kb_ids_sync

        rag_ids = filter_visible_kb_ids_sync(self._db, organization_id, raw_rag_ids, user_id)
        if not rag_ids:
            return self

        from ai.rag.kb_tool import build_kb_search_tool, execute_kb_search_sync

        kb_tool_doc = build_kb_search_tool(organization_id, rag_ids)
        self._tools.append({
            "type": "function",
            "function": {
                "name": kb_tool_doc["name"],
                "description": kb_tool_doc["description"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What information you are looking for."},
                    },
                    "required": ["query"],
                },
            },
        })
        # Accepts an optional `history` positional arg — _run's tool-call loop
        # special-cases this tool name to pass recent conversation history for
        # query rephrasing; every other callable in _tool_callables keeps the
        # plain single-arg (inp) calling convention.
        self._tool_callables[kb_tool_doc["name"]] = (
            lambda inp, history=None, d=kb_tool_doc: execute_kb_search_sync(d, inp, history=history)
        )
        return self

    def load_mcp_servers(self) -> "SubAgent":
        """Merge in tools from every MCP server linked to this agent.

        Tool definitions come from each server's cached `tools` list (populated
        at registration/discovery time), so no connection is opened just to load
        the agent. A live MCP session is established lazily, only when one of the
        server's tools is actually invoked (see backend.mcp_server.services).
        """
        server_ids = self._doc.get("mcp_server_ids", [])
        if not server_ids:
            return self

        object_ids = [
            ObjectId(sid) if not isinstance(sid, type(ObjectId())) else sid
            for sid in server_ids
        ]
        server_docs = list(self._db.mcp_servers.find({
            "_id": {"$in": object_ids},
            "is_active": True,
            "is_deleted": {"$ne": True},
        }))

        try:
            tools, callables = build_mcp_tools(server_docs)
            self._tools.extend(tools)
            self._tool_callables.update(callables)
            self._mcp_tool_names.update(callables.keys())
            logger.info(
                "Loaded %d MCP tool(s) from %d server(s) for agent '%s'",
                len(tools), len(server_docs), self.name,
            )
        except Exception as exc:  # noqa: BLE001 - never fail agent load on MCP issues
            logger.error("Failed to build MCP tools for agent '%s': %s", self.name, exc)

        return self

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(self, query: str, user_id: str, organization_id: str, memory_summary: str = "") -> str:
        logger.info("[sub-agent:%s] invoke — user=%s query=%.150s", self.name, user_id, query)
        self._tracer.set_agent_context(
            agent_id=str(self._doc["_id"]),
            agent_name=self.name,
        )

        span_meta = {
            "agent_id": str(self._doc["_id"]),
            "agent_name": self.name,
            "org_id": organization_id,
        }
        with self._tracer.span(
            f"agent:{self.name}",
            input={"query": query},
            metadata=span_meta,
        ) as span:
            system = self._build_system_prompt(memory_summary=memory_summary)
            messages = self._build_history(user_id) + [{"role": "user", "content": query}]

            # --- PRE-INVOKE MEMORY DUMP ---
            pre_invoke_memory = self.memory.get_memory_by_session(
                user_id=user_id, agent_id=str(self._doc["_id"])
            )
            logger.info(
                "[sub-agent:%s] PRE-INVOKE MEMORY — %d history entries\n"
                "=== SYSTEM PROMPT ===\n%s\n"
                "=== MESSAGE HISTORY (%d msgs) ===\n%s",
                self.name, len(pre_invoke_memory),
                system,
                len(messages),
                json.dumps(messages, indent=2, default=str),
            )
            _dump_agent_memory(pre_invoke_memory, f"{self.name.lower().replace(' ', '_')}_pre_invoke")
            # --- END PRE-INVOKE MEMORY DUMP ---

            output, tool_name, tool_output = self._run(system, messages)

        entry = MemorySchema(
            user_id=user_id,
            organization_id=organization_id,
            agent_id=str(self._doc["_id"]),
            agent_name=self.name,
            user_query=query,
            agents_output=output,
            tool_called=tool_name is not None,
            tool_name=tool_name,
            tool_output=tool_output,
        )
        self.memory.append_memory(entry)
        _dump_agent_memory(
            self.memory.get_memory_by_session(user_id=user_id, agent_id=str(self._doc["_id"])),
            self.name,
        )

        span.end(output={"response": output})
        return output

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self, system: str, messages: list):
        all_messages = [{"role": "system", "content": system}] + messages
        kwargs = dict(model=self._model, messages=all_messages)
        if self._tools:
            kwargs["tools"] = self._tools

        logger.info(
            "[sub-agent:%s] llm call — model=%s messages=%d tools=%d",
            self.name, self._model, len(all_messages), len(self._tools),
        )
        response = _completion_with_retry(
            lf_metadata=self._tracer.litellm_metadata(), **kwargs
        )
        usage = getattr(response, "usage", None)
        if usage:
            logger.info(
                "[sub-agent:%s] llm response — finish=%s prompt_tokens=%s completion_tokens=%s",
                self.name, response.choices[0].finish_reason,
                getattr(usage, "prompt_tokens", "?"), getattr(usage, "completion_tokens", "?"),
            )

        last_tool_name: Optional[str] = None
        last_tool_output: Optional[str] = None
        tool_call_round = 0

        while response.choices[0].finish_reason == "tool_calls":
            tool_call_round += 1
            assistant_msg = response.choices[0].message
            all_messages.append(assistant_msg)

            for tc in assistant_msg.tool_calls:
                tool_name = tc.function.name
                fn = self._tool_callables.get(tool_name)
                if fn is None:
                    raise ValueError(f"Model requested unknown tool '{tool_name}'")

                inp = json.loads(tc.function.arguments)
                logger.info(
                    "[sub-agent:%s] tool call #%d — tool=%s args=%.200s",
                    self.name, tool_call_round, tool_name, str(inp),
                )

                with self._tracer.span(
                    f"tool:{tool_name}",
                    input=inp,
                    metadata={"tool_call_id": tc.id},
                ) as tool_span:
                    try:
                        # search_knowledge_base is the only callable that
                        # accepts recent conversation history (for query
                        # rephrasing) — every other tool keeps the plain
                        # single-arg signature.
                        if tool_name == "search_knowledge_base":
                            # `messages` (this method's param) is the plain
                            # {"role","content"} history built before the tool
                            # loop started — safe to hand to rephrase, unlike
                            # `all_messages`, which now also holds raw litellm
                            # message objects appended by the loop above.
                            result = fn(inp, messages[-6:])
                        else:
                            result = fn(inp)
                    except _HumanInterrupt as hitl:
                        # There is no run to pause here, so surface the question as
                        # the agent's reply and let the user answer in the next turn.
                        tool_span.end(output={"result": str(hitl.question)})
                        return str(hitl.question), tool_name, str(hitl.question)
                    tool_output = str(result)
                    tool_span.end(output={"result": tool_output})

                logger.info(
                    "[sub-agent:%s] tool result — tool=%s output_len=%d",
                    self.name, tool_name, len(tool_output),
                )
                last_tool_name = tool_name
                last_tool_output = tool_output

                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_output,
                })

            kwargs["messages"] = all_messages
            logger.info(
                "[sub-agent:%s] llm follow-up call — round=%d messages=%d",
                self.name, tool_call_round, len(all_messages),
            )
            response = _completion_with_retry(
                lf_metadata=self._tracer.litellm_metadata(), **kwargs
            )
            usage = getattr(response, "usage", None)
            if usage:
                logger.info(
                    "[sub-agent:%s] llm response — finish=%s prompt_tokens=%s completion_tokens=%s",
                    self.name, response.choices[0].finish_reason,
                    getattr(usage, "prompt_tokens", "?"), getattr(usage, "completion_tokens", "?"),
                )

        output = response.choices[0].message.content or ""
        logger.info("[sub-agent:%s] done — output_len=%d tool_rounds=%d", self.name, len(output), tool_call_round)
        return output, last_tool_name, last_tool_output

    def _build_system_prompt(self, memory_summary: str = "") -> str:
        prompt = self._doc.get("prompt", "You are a helpful assistant.")
        guardrails = self._doc.get("guardrails", [])
        if guardrails:
            rules = "\n".join(f"- {g}" for g in guardrails)
            prompt += f"\n\nGUARDRAILS:\n{rules}"
        if memory_summary:
            prompt += f"\n\nConversation summary so far:\n{memory_summary}"
        return prompt

    def _build_history(self, user_id: str) -> list:
        past = self.memory.get_memory_by_session(
            user_id=user_id,
            agent_id=str(self._doc.get("_id", self.agent_id)),
        )
        msgs = []
        for entry in past:
            msgs.append({"role": "user", "content": entry.user_query})
            msgs.append({"role": "assistant", "content": entry.agents_output})
        return msgs

    @property
    def name(self) -> str:
        return self._doc.get("name", self.agent_id)


# ---------------------------------------------------------------------------
# Tool handler registry
# key must match the `handler` field stored in MongoDB
# ---------------------------------------------------------------------------
_TOOL_REGISTRY: Dict[str, callable] = {}


def register_tool(handler_name: str):
    def decorator(fn):
        _TOOL_REGISTRY[handler_name] = fn
        return fn
    return decorator


# Register built-in tool handlers.
from ai.tools.tools import Tools  # noqa: E402
_TOOL_REGISTRY["search_internet"] = Tools.search_internet
_TOOL_REGISTRY["ask_human"] = Tools.ask_human
_TOOL_REGISTRY["generate_document"] = Tools.generate_document
_TOOL_REGISTRY["query_mongo_read"] = Tools.query_mongo_read
_TOOL_REGISTRY["query_mongo_write"] = Tools.query_mongo_write
_TOOL_REGISTRY["query_sql_read"] = Tools.query_sql_read
_TOOL_REGISTRY["query_sql_write"] = Tools.query_sql_write
