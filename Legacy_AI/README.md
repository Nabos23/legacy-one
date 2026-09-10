# ONE-AI

A multi-tenant platform for building, configuring, and running **LLM agents** with tools,
database access, retrieval (RAG), MCP server integrations, and full observability.

It pairs a **FastAPI + MongoDB** control plane (organizations, users, agents, tools, RBAC,
admin panel) with a **LangGraph** orchestration layer that runs supervisor-routed and
direct single-agent conversations, backed by **LiteLLM** (model-agnostic), **Qdrant**
(schema/RAG vector search), and **Langfuse** (tracing).

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Project layout](#project-layout)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Running with Docker](#running-with-docker)
- [Seeding & utility scripts](#seeding--utility-scripts)
- [API surface](#api-surface)
- [RBAC](#rbac-roles--permissions)
- [MCP integration](#mcp-integration)
- [Testing](#testing)

---

## Features

- **Multi-tenant organizations** — every resource is scoped to an `organization_id`; a
  `super_admin` role spans all orgs.
- **Role-based access control (RBAC)** — granular `view/create/edit/delete` flags per
  resource, seeded on startup and editable live from the admin panel.
- **Agent management** — create agents with prompts, guardrails, tools, RAG sources, and
  linked MCP servers.
- **Tool registry** — a global catalog of tool types; org-level tools reference catalog
  entries.
- **Database connections** — connection strings are **encrypted at rest** (Fernet) and the
  target DB schema is **auto-introspected** on save (PostgreSQL, MySQL, SQLite, SQL Server,
  MongoDB, Supabase). Large schemas overflow transparently to GridFS.
- **RAG / schema search** — DB schemas are indexed into Qdrant so agents can semantically
  search the schema before querying.
- **Chat orchestration** — two paths: a **supervisor** that routes to the right agent, and
  **direct 1:1** chat with a single agent. Conversations are persisted, summarized/compressed
  past a threshold, and auto-named by the LLM.
- **MCP server integration** — register stdio / SSE / WebSocket MCP servers, discover their
  tools, complete OAuth flows, and expose the tools to agents at the sub-agent level.
- **Prompt generator** — generate an optimized system prompt from an agent name + description.
- **Observability** — Langfuse traces, per-org and per-agent cost/token stats.
- **Operational guardrails** — per-IP rate limiting and business quotas, both editable live.
- **Admin panel** — a starlette-admin UI at `/admin` for managing all resources and roles.

---

## Architecture

The system has **two cooperating planes**:

### 1. Control plane — `backend/` (FastAPI + MongoDB)
REST API for auth, RBAC, and CRUD over organizations, users, agents, tools, the tool
registry, DB connections, and MCP servers. Includes the admin panel, rate limiting, quotas,
and tracing read endpoints. Data lives in MongoDB (via `motor` / `odmantic`).

### 2. Orchestration plane — `ai/` (LangGraph)
The wired custom-agents runtime. `ai/langgraph.json` → `ai/graph/studio.py:graph` builds a
graph with a **MainAgent** (supervisor) that routes to **SubAgents**. MCP tools are bound at
the **sub-agent level**. Supporting modules:

- `ai/agents/` — `main_agent.py`, `sub_agent.py`, and a `summarizer/` for conversation
  compression.
- `ai/graph/` — graph wiring (`graph.py`, `nodes.py`, `state.py`, `studio.py`).
- `ai/memory/` — conversation/memory persistence (Mongo-backed store).
- `ai/rag/` — schema indexing & retrieval (Qdrant) plus a `search_schema` tool.
- `ai/tools/` — built-in tool implementations.
- `ai/tracing/` — Langfuse tracer + per-request tracing context.

> Note: `backend/chat/graph.py` is a separate async FastAPI chat path that coexists with the
> `ai/` LangGraph stack.

Cross-cutting services: **LiteLLM** (provider-agnostic model calls), **Qdrant** (vectors),
**Langfuse** (traces).

---

## Project layout

```
.
├── backend/                  # FastAPI control plane
│   ├── main.py               # App factory: routers, middleware, startup seeding
│   ├── auth/                 # JWT auth, permissions, RBAC constants
│   ├── organization/         # Organization CRUD + nested listings
│   ├── user/                 # User queries (super-admin & org-scoped)
│   ├── agent/                # Agent CRUD
│   ├── tool/  toolregistry/  # Org tools + global tool catalog
│   ├── dbconnection/         # Encrypted DB connections + schema introspection
│   ├── chat/                 # Supervisor chat (sessions, messages, history)
│   ├── direct_agent/         # Direct 1:1 agent chat
│   ├── mcp_server/           # MCP integration (see below)
│   ├── prompt_generator/     # LLM-based system-prompt generation
│   ├── tracing/              # Langfuse read endpoints
│   ├── core/                 # config, rate limiting, quotas, DB introspection
│   ├── db/                   # Mongo client, constants
│   ├── memory/               # Backend-side memory helpers
│   ├── scripts/              # Seeders, smoke tests, verification scripts
│   ├── tests/                # Backend test suite
│   └── docs/API.md           # Full REST API reference
├── ai/                       # LangGraph orchestration plane
│   ├── langgraph.json        # Graph entry point (studio.py:graph)
│   ├── agents/  graph/  memory/  rag/  tools/  tracing/
│   └── models.py             # Model enum (LiteLLM ids)
├── tests/                    # MCP integration/unit tests (top-level)
├── Dockerfile                # uv-based build; bundles ODBC + Node/npx + uvx for MCP
├── docker-compose.yml        # fastapi service (Qdrant runs on Qdrant Cloud)
└── pyproject.toml            # Dependencies (managed with uv)
```

---

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn |
| Data | MongoDB (`motor`, `odmantic`, GridFS) |
| Orchestration | LangGraph |
| LLM gateway | LiteLLM (OpenAI `gpt-4.1` / `gpt-5.4-*`; Anthropic via prefix) |
| Vectors / RAG | Qdrant (`qdrant-client`) |
| Observability | Langfuse |
| Auth | JWT (`python-jose`), bcrypt, Fernet encryption |
| MCP | `mcp` SDK (stdio / SSE / WebSocket + OAuth) |
| DB drivers | SQLAlchemy, psycopg2, PyMySQL, pyodbc (MSSQL) |
| Admin UI | starlette-admin |
| Tooling | `uv`, pytest, pytest-asyncio |

Requires **Python ≥ 3.11**.

---

## Getting started

```bash
# 1. Install uv (https://docs.astral.sh/uv/) if you don't have it, then sync deps
uv sync

# 2. Create a .env (see Configuration below)

# 3. Run the API
uv run uvicorn backend.main:app --reload

# 4. Open the docs
#    Swagger: http://localhost:8000/docs
#    ReDoc:   http://localhost:8000/redoc
#    Admin:   http://localhost:8000/admin
```

Health checks: `GET /` and `GET /mongo-check`.

To run the LangGraph studio graph:

```bash
uv run langgraph dev   # uses ai/langgraph.json → ai/graph/studio.py:graph
```

---

## Configuration

Settings are loaded from environment / `.env` (see `backend/core/config.py`).

| Variable | Default | Purpose |
|---|---|---|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DATABASE_NAME` | `aiddb` | Database name |
| `JWT_SECRET_KEY` | `change-me-in-production` | **Set in production** |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) | Token lifetime |
| `ENCRYPTION_KEY` | derived from `JWT_SECRET_KEY` | Fernet key for secrets at rest |
| `OTP_EXPIRE_MINUTES` | `10` | Password-reset OTP lifetime |
| `OTP_RETURN_IN_RESPONSE` | `true` | Return OTP in API response (**set `false` in prod**) |
| `DEFAULT_MODEL` | `gpt-5.4-mini` | Default LLM (via LiteLLM) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | — / — / `https://cloud.langfuse.com` | Langfuse tracing |
| `QDRANT_URL` / `QDRANT_API_KEY` | `http://qdrant:6333` / — | Qdrant vector DB |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embeddings for schema/RAG indexing |
| `MCP_OAUTH_REDIRECT_BASE` | `http://localhost:8000` | Public origin OAuth redirects back to |
| `MCP_OAUTH_SUCCESS_REDIRECT` | — | Optional post-callback redirect (e.g. frontend page) |
| `MCP_OAUTH_FLOW_TTL_SECONDS` | `900` | How long a pending OAuth consent stays valid |

You will also need provider API keys (e.g. `OPENAI_API_KEY`) for LiteLLM, set in `.env`.

---

## Running with Docker

```bash
docker compose up --build
```

The image (`Dockerfile`) is built with `uv` and bundles everything MCP servers need at
runtime:

- **Microsoft ODBC Driver 17** for `pyodbc` (SQL Server connections),
- **Node.js / npm** so `npx`-based MCP servers (filesystem, github, slack, …) can launch,
- **`uv` + `uvx`** so `uvx`-based MCP servers (`mcp-server-fetch`, `mcp-server-git`, …) can launch.

The API is exposed on **`:8000`**. Qdrant runs on **Qdrant Cloud** (configure
`QDRANT_URL` / `QDRANT_API_KEY` in `.env`); re-add a local `qdrant` service to compose if you
want a local instance.

---

## Seeding & utility scripts

Run with `uv run python -m backend.scripts.<name>`.

| Script | Purpose |
|---|---|
| `seed_admin <email> <password> <org_id> "<name>"` | Create the first admin (needed to log into `/admin`) |
| `seed_roles` | Upsert built-in roles & permission flags (also runs on startup) |
| `migrate_role_permissions` | Migrate roles to the current permission model |
| `seed_tool_registry` | Seed the global tool catalog |
| `seed_mcp_server_registry` | Seed MCP server registry entries |
| `seed_agents` | Seed sample agents |
| `mcp_smoke` / `mcp_multi_check` / `mock_mcp_server` | MCP smoke tests + a mock server |
| `verify_mcp_oauth` / `verify_ai_subagent_mcp` | Verify MCP OAuth and sub-agent tool binding |
| `terminal_chat` | Drive a chat session from the terminal |

---

## API surface

Base URL (local): `http://localhost:8000`. Auth scheme: **Bearer JWT**.
The complete reference (request/response shapes, errors, examples) is in
**[`backend/docs/API.md`](backend/docs/API.md)**.

| Area | Highlights |
|---|---|
| **Auth** | `register`, `signup`, `login`, `logout`, `me`, OTP forgot/verify/reset, admin `users` |
| **Organizations** | CRUD (paginated, soft delete) + nested `agents` / `tools` / `db-connections` / `users` |
| **Users** | `GET /users` (super-admin), org-scoped user listing |
| **Agents** | CRUD; supports `tool_ids`, `rag_ids`, `mcp_server_ids` |
| **Tools / Tool Registry** | Org tools reference a global catalog (registry mutations are super-admin only) |
| **DB Connections** | Encrypted; schema auto-fetched and readable via `/schema` |
| **Chat** | `POST /chat/session`, `POST /chat/message`, `GET /chat/sessions`, history per agent |
| **Direct chat** | 1:1 agent chat that bypasses the supervisor |
| **MCP servers** | Register servers, discover tools, OAuth connect, link to agents |
| **Prompt generator** | `POST /generate-prompt` (no auth) |
| **Tracing** | Traces, sessions, cost/token stats per org and per agent |
| **Health** | `GET /`, `GET /mongo-check` |

Operational policies enforced across the API: **pagination** envelopes on list endpoints,
**soft deletes** (`is_deleted` + `deleted_at`), per-IP **rate limiting**, and business
**quotas** — the latter two editable live from `/admin`.

---

## RBAC (roles & permissions)

Each user has a `role` mapping to boolean permission flags stored in MongoDB and seeded on
startup. Built-in roles:

| Role | Scope | Summary |
|---|---|---|
| `user` | own org | read-only across resources |
| `org_manager` | own org | view + edit agents/tools/orgs |
| `org_admin` | own org | full CRUD within the org + chat |
| `super_admin` | **all orgs** | everything, including the global tool registry & user list |

Flags follow a `view_* / create_* / edit_* / delete_*` pattern per resource and can be toggled
for any role from `/admin` → **Roles** (changes apply within ~5s, no restart). Legacy roles
`member` → `user` and `admin` → `org_admin` are normalized at runtime. Full matrix and
special cases are in [`backend/docs/API.md`](backend/docs/API.md#roles--permissions).

---

## MCP integration

The `backend/mcp_server/` module provides a complete Model Context Protocol integration so
agents can use external tool servers:

| File | Responsibility |
|---|---|
| `models.py` / `schemas.py` | MCP server documents + request/response shapes |
| `routes.py` | Register/list/update MCP servers, trigger discovery, OAuth endpoints |
| `services.py` | Business logic linking MCP servers to orgs/agents |
| `connection.py` | Connection lifecycle for stdio / SSE / WebSocket transports |
| `discovery.py` | Discover the tools/capabilities a server exposes |
| `catalog.py` | Catalog of available MCP servers/tools |
| `client.py` | MCP client wrapper |
| `runtime.py` | Runtime execution of MCP tool calls |
| `oauth.py` / `oauth_runtime.py` / `oauth_storage.py` | OAuth authorization flow, runtime token use, and token persistence |

Agents reference MCP servers via `mcp_server_ids`; their tools are bound at the **sub-agent
level** in the LangGraph runtime (`ai/agents/sub_agent.py`). The OAuth callback is mounted on
the API at the URL configured by `MCP_OAUTH_REDIRECT_BASE`.

---

## Testing

```bash
uv run pytest                 # full suite
uv run pytest backend/tests   # backend (auth, chat, RBAC, MCP API, …)
uv run pytest tests           # MCP unit/integration tests
uv run pytest -m integration  # tests that hit live external MCP servers
```

Tests use `pytest-asyncio` in auto mode (`pyproject.toml`). The `integration` marker gates
tests that make real external connections.
</content>
