import json
import logging
from typing import Dict, List, Optional

from ai.agents.sub_agent import SubAgent, _completion_with_retry, _dump_agent_memory
from ai.memory.memory import LocalMemory
from ai.memory.memory_schema import MemorySchema
from ai.tracing.context import TracingContext
from ai.tracing.tags import agent_tag, org_tag
from ai.tracing.tracer import AgentTracer

logger = logging.getLogger(__name__)


class MainAgent:
    """
    Orchestrator. Answers generic queries directly; routes specialised ones
    to the matching SubAgent.

    Parameters
    ----------
    agent_summaries : list of dicts — each has _id, name, description, optional guardrails.
    db              : pymongo Database (forwarded to SubAgents)
    model           : litellm model string e.g. "gpt-5.4-mini"
    memory          : shared LocalMemory for the session
    user_id         : current user
    organization_id : current org
    session_id      : groups turns into a conversation thread (defaults to user_id)
    tracing_context : optional TracingContext from FastAPI JWT boundary
    """

    _ROUTER_SYSTEM = """You are a routing assistant. Your ONLY job is to select the right sub-agent.

Available sub-agents:
{agent_list}

Respond with valid JSON only — no explanation, no markdown:
{{"agent_id": "<id or null>", "reason": "<one sentence>"}}

Rules:
- Use the conversation history (if provided) to understand context. Short follow-ups
  like "yes", "ok", "correct", "more" should route to the SAME agent as the prior turn.
- Set agent_id to null only if the query is clearly generic AND has no ongoing sub-agent context.
- Never select an agent whose guardrails explicitly refuse this type of query.
- Only use agent IDs exactly as listed above — never invent or modify IDs."""

    _DIRECT_SYSTEM = "You are a knowledgeable, helpful assistant. Answer clearly and concisely."

    def __init__(
        self,
        agent_summaries: List[dict],
        db,
        model: str,
        memory: LocalMemory,
        user_id: str,
        organization_id: str,
        session_id: Optional[str] = None,
        tracing_context: Optional[TracingContext] = None,
    ):
        self._summaries      = agent_summaries
        self._db             = db
        self._model          = model
        self.memory          = memory
        self.user_id         = user_id
        self.organization_id = organization_id

        self._sub_agents: Dict[str, SubAgent] = {}

        ctx = tracing_context
        self._tracer = AgentTracer(
            org_id=ctx.org_id if ctx else organization_id,
            user_id=ctx.user_id if ctx else user_id,
            session_id=ctx.session_id if ctx else (session_id or user_id),
        )
        self.memory.set_tracer(self._tracer)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def invoke(self, query: str) -> str:
        self._tracer.start_trace("main_agent.invoke", input={"query": query})
        try:
            history  = self.memory.get_memory_by_user(self.user_id)
            agent_id = self._route(query, history=history)
            if agent_id:
                output = self._delegate(query, agent_id)
            else:
                output = self._answer_directly(query)
            self._tracer.end_trace(output={"response": output})
            return output
        except Exception:
            self._tracer.end_trace(output={"error": "invoke failed"})
            raise

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _route(self, query: str, excluded: list = None, history: list = None, memory_summary: str = "") -> Optional[str]:
        excluded_set = set(str(x) for x in (excluded or []))
        active       = [s for s in self._summaries if str(s.get("_id", "")) not in excluded_set]
        known_ids    = {str(s["_id"]) for s in active}

        lines = []
        for s in active:
            line = f"  id={str(s['_id'])}  name={s['name']}  — {s['description']}"
            guardrails = s.get("guardrails", [])
            if guardrails:
                line += f"\n    Refuses: {'; '.join(guardrails)}"
            lines.append(line)
        agent_list = "\n".join(lines) or "  (none)"

        system_content = self._ROUTER_SYSTEM.format(agent_list=agent_list)
        if memory_summary:
            system_content += f"\n\nConversation summary so far:\n{memory_summary}"
        messages = [{"role": "system", "content": system_content}]
        for entry in (history or [])[-3:]:
            messages.append({"role": "user",      "content": entry.user_query})
            messages.append({"role": "assistant",  "content": f"[{entry.agent_name}]: {entry.agents_output[:300]}"})
        messages.append({"role": "user", "content": query})

        with self._tracer.span("routing", input={"query": query}) as span:
            try:
                response = _completion_with_retry(
                    lf_metadata=self._tracer.litellm_metadata(),
                    model=self._model,
                    messages=messages,
                    max_tokens=256,
                )
                raw      = response.choices[0].message.content.strip()
                decision = json.loads(raw)
                agent_id  = decision.get("agent_id")
                routed_to = agent_id if agent_id and agent_id not in ("null", None) else None
                if routed_to and routed_to not in known_ids:
                    logger.warning("[main-agent] router returned unknown agent_id '%s' — falling back", routed_to)
                    routed_to = None
                agent_name = next((s["name"] for s in active if str(s.get("_id", "")) == routed_to), "direct") if routed_to else "direct"
                logger.info("[main-agent] routing decision — agent=%s reason=%s", agent_name, decision.get("reason", ""))
                span.end(output=decision)
                return routed_to
            except (json.JSONDecodeError, KeyError):
                logger.warning("Router returned malformed JSON — falling back to direct answer")
                span.end(output={"error": "malformed JSON from router"})
                return None
            except Exception as e:
                logger.error("Routing failed: %s — falling back to direct answer", e)
                span.end(output={"error": str(e)})
                return None

    def _delegate(self, query: str, agent_id: str) -> str:
        with self._tracer.span("delegation", input={"agent_id": agent_id, "query": query}) as span:
            if agent_id not in self._sub_agents:
                sub = SubAgent(
                    agent_id=agent_id,
                    db=self._db,
                    model=self._model,
                    memory=self.memory,
                    tracer=self._tracer,
                )
                sub.load_agent()
                sub.load_tools()
                sub.load_mcp_servers()
                sub.load_connectors(user_id=self.user_id, organization_id=self.organization_id)
                sub.load_rag_tools(user_id=self.user_id, organization_id=self.organization_id)
                self._sub_agents[agent_id] = sub

            sub = self._sub_agents[agent_id]

            self._tracer.tag_agent(agent_id, sub.name)

            # --- PRE-INVOKE MEMORY DUMP ---
            pre_invoke_memory = self.memory.get_memory_by_session(
                user_id=self.user_id, agent_id=agent_id
            )
            logger.info(
                "[main-agent] PRE-INVOKE MEMORY for '%s' — %d entries\n%s",
                sub.name, len(pre_invoke_memory),
                json.dumps(
                    [e.model_dump() if hasattr(e, "model_dump") else e.dict() for e in pre_invoke_memory],
                    indent=2, default=str,
                ),
            )
            _dump_agent_memory(pre_invoke_memory, f"{sub.name.lower().replace(' ', '_')}_pre_invoke_main")
            # --- END PRE-INVOKE MEMORY DUMP ---

            result = sub.invoke(
                query=query,
                user_id=self.user_id,
                organization_id=self.organization_id,
            )
            span.end(output={"response": result})
            return result

    def _answer_directly(self, query: str, memory_summary: str = "") -> str:
        logger.info("[main-agent] answering directly — query=%.150s", query)
        self._tracer.update_trace(
            tags=[org_tag(self.organization_id), agent_tag("direct")],
            metadata={"org_id": self.organization_id, "user_id": self.user_id, "agent_name": "direct"},
        )
        with self._tracer.span("direct_answer", input={"query": query}) as span:
            history  = self._build_history()
            system   = self._DIRECT_SYSTEM
            if memory_summary:
                system += f"\n\nConversation summary so far:\n{memory_summary}"
            messages = [{"role": "system", "content": system}]
            messages += history
            messages.append({"role": "user", "content": query})

            response = _completion_with_retry(
                lf_metadata=self._tracer.litellm_metadata(),
                model=self._model,
                messages=messages,
            )
            reply = response.choices[0].message.content or ""
            span.end(output={"response": reply})

        entry = MemorySchema(
            user_id=self.user_id,
            organization_id=self.organization_id,
            agent_id="main",
            agent_name="MainAgent",
            user_query=query,
            agents_output=reply,
        )
        self.memory.append_memory(entry)
        _dump_agent_memory(
            self.memory.get_memory_by_session(user_id=self.user_id, agent_id="main"),
            "main",
        )
        return reply

    def _build_history(self) -> list:
        past = self.memory.get_memory_by_session(user_id=self.user_id, agent_id="main")
        msgs = []
        for entry in past:
            msgs.append({"role": "user",      "content": entry.user_query})
            msgs.append({"role": "assistant",  "content": entry.agents_output})
        return msgs
