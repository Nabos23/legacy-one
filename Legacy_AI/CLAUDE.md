# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

| Task | Command |
|------|---------|
| Install dependencies | `uv sync` |
| Run backend API | `uv run uvicorn backend.main:app --reload` |
| Run LangGraph Studio | `uv run langgraph dev` |
| Run all tests | `uv run pytest` |
| Run backend tests only | `uv run pytest backend/tests` |
| Run MCP tests | `uv run pytest tests` |
| Run single test | `uv run pytest path/to/test_file.py::test_function` |
| Run integration tests | `uv run pytest -m integration` |
| Create admin user | `uv run python -m backend.scripts.seed_admin <email> <password> <org_id> "<name>"` |
| Seed default roles | `uv run python -m backend.scripts.seed_roles` |
| Seed tool registry | `uv run python -m backend.scripts.seed_tool_registry` |
| Seed sample agents | `uv run python -m backend.scripts.seed_agents` |
| Interactive terminal chat | `uv run python -m backend.scripts.terminal_chat` |

## Architecture Overview

This is a **multi-tenant LLM agent platform** with two cooperating planes:

### Control Plane (`backend/`)
**FastAPI + MongoDB** REST API providing:
- **Auth & RBAC** — JWT-based auth with role-based permissions (user, org_manager, org_admin, super_admin)
- **Multi-tenant CRUD** — organizations, users, agents, tools, MCP servers, database connections
- **Admin UI** — starlette-admin at `/admin` for managing resources and live permission toggles
- **Rate limiting & quotas** — per-IP limiting and business quotas, both configurable live
- **Secrets management** — DB connection strings encrypted at rest (Fernet)
- **Schema introspection** — auto-discover remote database schemas (PostgreSQL, MySQL, SQL Server, SQLite, MongoDB)
- **Observability read path** — Langfuse traces, cost/token stats per org/agent

### Orchestration Plane (`ai/`)
**LangGraph** runtime powering the agent execution:
- **Graph structure** — `ai/langgraph.json` → `ai/graph/studio.py:graph` builds a **MainAgent** (supervisor) that routes queries to **SubAgents**
- **Supervisor routing** — MainAgent uses the LLM to route generic queries to the right SubAgent; includes follow-up context awareness
- **SubAgent execution** — each SubAgent has:
  - Tools (built-in + org-defined + MCP-integrated)
  - Database access (via the DB connection registry)
  - RAG search (schema + knowledge base)
  - Memory (per-session append-only message log)
- **Cross-agent collaboration** — agents can invoke human input (ask_human) for approval/clarification via the `/ask_human` API endpoint
- **Memory & persistence** — conversations persisted to MongoDB, auto-compressed/summarized past length thresholds, auto-named by the LLM

### Cross-Cutting Services
- **LiteLLM** — model-agnostic LLM calls; supports OpenAI (GPT-5.4, GPT-4.1) and Anthropic (via prefix)
- **Qdrant** — vector database for schema/RAG search (semantic indexing of database schemas)
- **Langfuse** — observability: traces all agent turns, tracks cost/token usage per org
- **MCP integration** — stdio/SSE/WebSocket MCP servers discovered at registration; tools exposed at sub-agent level with OAuth flow support

## Key Files & Modules

### Backend Structure (`backend/`)
```
├── main.py                 # App factory: routers, middleware, startup seeding
├── auth/                   # JWT generation, login/signup, RBAC middleware, permission checks
├── organization/           # Org CRUD, nested resource listings (agents/tools/connections)
├── user/                   # User queries (super-admin & org-scoped)
├── agent/                  # Agent CRUD; stores tool_ids, rag_ids, mcp_server_ids
├── tool/ toolregistry/     # Org tools reference a global catalog
├── dbconnection/           # Encrypted DB connections, schema introspection & caching
├── chat/                   # Supervisor chat sessions, message history, conversation compression
├── direct_agent/           # 1:1 agent chat (bypass supervisor routing)
├── mcp_server/             # MCP registration, discovery, OAuth flow, tool binding
├── prompt_generator/       # LLM-powered system-prompt generation
├── core/
│   ├── config.py           # Settings from .env (models, API keys, Langfuse, Qdrant)
│   ├── ratelimit.py        # Per-IP rate limiting middleware
│   ├── quota.py            # Business quotas (editable live from /admin)
│   └── db_introspect.py    # Remote schema discovery for supported databases
├── db/
│   ├── database.py         # Motor (async MongoDB) client + sync wrapper
│   └── constants.py        # Permission flag names, role definitions
├── admin.py                # starlette-admin UI configuration
├── tracing/                # Langfuse read endpoints (traces, sessions, stats)
├── scripts/                # Utility scripts: seed_admin, seed_roles, seed_agents, terminal_chat, etc.
└── tests/                  # pytest suite (auth, chat, RBAC, MCP API, integration)
```

### Orchestration Structure (`ai/`)
```
├── langgraph.json          # Studio entry point config
├── models.py               # LiteLLM model enum (GPT-5.4-mini, GPT-4.1, Anthropic models)
├── agents/
│   ├── main_agent.py       # MainAgent: supervisor routing logic
│   ├── sub_agent.py        # SubAgent: tool execution, memory, RAG search
│   └── summarizer/         # Conversation compression/summarization
├── graph/
│   ├── studio.py           # Graph instantiation (loaded by langgraph dev)
│   ├── graph.py            # Graph building (nodes, edges, conditional routing)
│   ├── nodes.py            # Node handlers (routing, tool calls, summaries)
│   └── state.py            # Graph state schema (messages, metadata)
├── memory/
│   ├── memory.py           # LocalMemory: append-only session log
│   ├── memory_schema.py    # Message, memory structure definitions
│   └── persistence.py      # MongoDB-backed message storage
├── rag/
│   ├── search_schema.py    # Semantic schema search tool (Qdrant)
│   ├── indexing.py         # Index DB schemas into Qdrant on connection save
│   └── rag_tools.py        # RAG-powered tools for agents
├── tools/
│   ├── builtin_tools.py    # Built-in tools (e.g., search_schema)
│   ├── mcp_runtime.py      # MCP tool execution at the sub-agent level
│   └── tool_executor.py    # Tool invocation & error handling
├── tracing/
│   ├── tracer.py           # AgentTracer wrapping Langfuse
│   ├── context.py          # TracingContext for request-scoped tracing
│   └── tags.py             # Tag helpers for org/user/session/agent spans
└── (tests and supporting modules)
```

## Development Patterns

### Running the Full Stack Locally
```bash
# Terminal 1: Backend API (http://localhost:8000, docs at /docs)
uv run uvicorn backend.main:app --reload

# Terminal 2: LangGraph Studio (http://localhost:8000/studio)
uv run langgraph dev

# Terminal 3: Interactive test
uv run python -m backend.scripts.terminal_chat
```

### Adding a New Agent
1. Create agent in MongoDB via `/admin` or API (`POST /agent`)
2. Define `name`, `description`, optional `guardrails` (comma-separated deny-list for query types)
3. Link tools via `tool_ids`, MCP servers via `mcp_server_ids`, RAG sources via `rag_ids`
4. MainAgent will automatically discover it on the next chat turn (reloads agent summaries from DB)

### Adding a New Tool
1. **Global tool** (super-admin): register in tool registry (`POST /tool-registry`)
2. **Org tool**: reference the registry entry and add org-specific config (`POST /tool`)
3. **MCP tool**: register an MCP server (`POST /mcp-server`), link to an agent via `mcp_server_ids`, tools auto-discovered at sub-agent runtime

### Chat Flow
```
User query
  ↓
FastAPI route (backend/chat/routes.py or backend/direct_agent/routes.py)
  ↓
Create/load conversation (MongoDB)
  ↓
Invoke LangGraph (ai/graph/studio.py:graph.ainvoke)
  ↓
MainAgent routes query to SubAgent (or handles directly)
  ↓
SubAgent:
  - Fetches tools (built-in + org tools + MCP tools)
  - Calls tools (with access to DB connections, schemas, RAG)
  - Stores turn in memory (MongoDB)
  ↓
Response returned to user
```

### Memory & Persistence
- **Per-session memory**: `ai/memory/memory.py` — LocalMemory appends every turn (user + assistant)
- **Compression**: when conversation exceeds length threshold, call summarizer to compress old turns
- **Tracing context**: org/user/session IDs flow through via TracingContext from JWT boundary
- **Ask Human**: SubAgent can invoke `ask_human()` to pause execution and ask user for approval via API (`/ask_human`)

### MCP Server Integration
```
Register MCP server (stdio/SSE/WebSocket)
  ↓
Discovery (introspect tools/capabilities)
  ↓
Link to agent via mcp_server_ids
  ↓
At sub-agent runtime:
  - Open connection (stdio spawn, SSE poll, WS connect)
  - Bind tools to LangGraph
  - Call tools directly (with OAuth token if registered)
  - Close connection on turn end
```

### Testing Strategy
- **Backend tests** (`backend/tests/`): auth, RBAC, CRUD, chat, MCP API routes — unit/integration
- **MCP tests** (`tests/`): MCP client/server interactions, tool discovery, OAuth flow
- **Integration marker** (`pytest -m integration`): gates tests hitting live external MCP servers
- **Mock servers**: `backend/scripts/mock_mcp_server.py` and `mock_weather_mcp_server.py` for testing without live dependencies

## Configuration & Secrets

All settings from `backend/core/config.py` are read from environment or `.env`:
- **API keys**: `OPENAI_API_KEY`, `LANGFUSE_*`, `QDRANT_*`, GitHub/Google OAuth keys
- **Database**: `MONGO_URL`, `DATABASE_NAME`
- **Auth**: `JWT_SECRET_KEY` (must change in production), `ENCRYPTION_KEY` (for at-rest secrets)
- **LangGraph**: `STUDIO_USER_ID`, `STUDIO_ORG_ID` (must point to real org/user for routing to work in Studio)

Critical: `JWT_SECRET_KEY` and `ENCRYPTION_KEY` **must be rotated in production** and never committed.

## Common Workflows

### Debug a Failing Chat
1. **Check backend logs** — uvicorn logs routing decision and tool calls
2. **Check LangGraph Studio** — run `langgraph dev` and replay the graph with test inputs
3. **Check MongoDB** — inspect conversation document in `conversations` collection (session_id)
4. **Check Langfuse** — traces show model calls, token usage, tool invocations

### Add Guardrails to an Agent
1. Edit agent in `/admin` or via API (`PUT /agent/{agent_id}`)
2. Set `guardrails` to comma-separated list of denial keywords (e.g., "delete data, drop tables")
3. MainAgent checks guardrails before routing; if matched, refuses the query

### Introspect a Database
1. Create DB connection with connection string
2. API auto-discovers schema and caches it
3. Schema indexed into Qdrant for semantic search
4. Agents can search schema via `search_schema` tool

### Extend with Custom Tools
1. **Python function**: place in `ai/tools/`, register via tool registry or org tool endpoint
2. **External CLI**: wrap in a `Tool` struct with command string, link via tool registry
3. **MCP server**: stand up an MCP server (stdio/SSE/WebSocket), register via `/mcp-server`, link to agent

## Database Schema Overview

Key MongoDB collections:
- **organizations** — multi-tenant boundary; all other docs scoped to org_id
- **users** — roles (user, org_manager, org_admin, super_admin); hashed passwords
- **agents** — name, description, guardrails, tool_ids, rag_ids, mcp_server_ids
- **tools** — org tools; reference tool_registry entries
- **tool_registry** — global catalog (super-admin only)
- **dbconnections** — encrypted connection strings; schema cached in a GridFS blob
- **conversations** — chat sessions; messages, metadata (agent_id, summary if compressed)
- **conversation_messages** — messages (optimizable: can be moved to a time-series collection)
- **mcp_servers** — registered MCP servers; connection config, OAuth state
- **roles** — permission flag matrix (one doc per role)

## Deployment Checklist

- [ ] Rotate `JWT_SECRET_KEY` and `ENCRYPTION_KEY`
- [ ] Set `OTP_RETURN_IN_RESPONSE=false` (OTP must be sent out-of-band in prod)
- [ ] Configure `LANGFUSE_*` (tracing)
- [ ] Configure `QDRANT_URL` and `QDRANT_API_KEY` (use Qdrant Cloud, not local)
- [ ] Set `MCP_OAUTH_REDIRECT_BASE` to production domain
- [ ] Seed default roles: `uv run python -m backend.scripts.seed_roles`
- [ ] Create admin user: `uv run python -m backend.scripts.seed_admin`
- [ ] Test with `docker compose up --build` (Dockerfile bundles ODBC, Node, uv for MCP servers)
