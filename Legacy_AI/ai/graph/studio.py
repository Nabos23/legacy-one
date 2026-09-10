"""
LangGraph Studio entry point.

Usage:
    langgraph dev          # starts the Studio dev server (no Docker)

The compiled graph is exposed as the module-level `graph` variable which
langgraph.json points to. Everything is initialised at import time so Studio
can load the graph without running a full FastAPI server.

Environment variables are read from .env (via langgraph.json → "env": ".env").
Override STUDIO_USER_ID / STUDIO_ORG_ID in .env to match a real user/org in
your database so agent lookups succeed during testing.
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from ai.agents.main_agent import MainAgent
from ai.graph.graph import build_graph
from ai.memory.memory import LocalMemory
from ai.tracing import setup_tracing
from backend.core.config import settings
from backend.db.database import sync_db

logger = logging.getLogger(__name__)

setup_tracing()

_STUDIO_USER_ID = os.getenv("STUDIO_USER_ID", "studio-user")
_STUDIO_ORG_ID  = os.getenv("STUDIO_ORG_ID",  "studio-org")


def _load_agent_summaries() -> list:
    """Load agent summaries from MongoDB at startup for routing in Studio."""
    try:
        docs = list(sync_db.agents.find(
            {"is_deleted": {"$ne": True}},
            {"_id": 1, "name": 1, "description": 1, "guardrails": 1},
        ))
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
        logger.info("Studio: loaded %d agent(s) from DB", len(summaries))
        return summaries
    except Exception as exc:
        logger.warning("Studio: could not load agents from DB (%s) — routing will always direct-answer", exc)
        return []


_memory    = LocalMemory()
_summaries = _load_agent_summaries()

_main_agent = MainAgent(
    agent_summaries=_summaries,
    db=sync_db,
    model=settings.DEFAULT_MODEL,
    memory=_memory,
    user_id=_STUDIO_USER_ID,
    organization_id=_STUDIO_ORG_ID,
)

graph = build_graph(
    db=sync_db,
    memory=_memory,
    model=settings.DEFAULT_MODEL,
    main_agent=_main_agent,
)
