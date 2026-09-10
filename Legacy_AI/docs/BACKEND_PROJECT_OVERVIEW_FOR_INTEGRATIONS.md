# BACKEND PROJECT OVERVIEW FOR INTEGRATIONS

**Repository:** ONE-AI  
**Date:** June 29, 2026  
**Author:** Senior Backend Architect Review  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Backend Repository Structure](#2-backend-repository-structure)
3. [FastAPI Application Architecture](#3-fastapi-application-architecture)
4. [Authentication and Authorization](#4-authentication-and-authorization)
5. [Multi-Tenant Architecture](#5-multi-tenant-architecture)
6. [Data Models and MongoDB Collections](#6-data-models-and-mongodb-collections)
7. [API Surface](#7-api-surface)
8. [Agent Management](#8-agent-management)
9. [Tool Registry and Org Tools](#9-tool-registry-and-org-tools)
10. [MCP Server Integration](#10-mcp-server-integration)
11. [Chat and Direct Agent Flows](#11-chat-and-direct-agent-flows)
12. [AI / LangGraph Runtime](#12-ai--langgraph-runtime)
13. [Database Connections and RAG](#13-database-connections-and-rag)
14. [Security Review](#14-security-review)
15. [Observability](#15-observability)
16. [Integration Readiness Assessment](#16-integration-readiness-assessment)
17. [Recommended Backend Connector Architecture](#17-recommended-backend-connector-architecture)
18. [Backend Implementation Tasks](#18-backend-implementation-tasks)
19. [Backend Risks and Unknowns](#19-backend-risks-and-unknowns)
20. [Final Summary](#20-final-summary)

---

## 1. Executive Summary

### What this backend does
ONE-AI is a multi-tenant platform for building, configuring, and running LLM-powered agents. The backend is a **FastAPI + MongoDB** control plane paired with a **LangGraph** AI orchestration layer. It enables organizations to create agents with custom prompts, assign tools (database query tools, internet search, MCP server tools), and run conversations routed by a supervisor agent or directly with individual agents.

### Main business purpose
Provide a self-service platform where organizations can deploy LLM agents that connect to their databases, use external tools via MCP protocol, and answer questions through chat interfaces — all with multi-tenancy, RBAC, and observability built in.

### Main architecture
Two cooperating planes:
- **Control Plane** (`backend/`): FastAPI REST API for auth, RBAC, CRUD over organizations, users, agents, tools, DB connections, MCP servers, chat sessions. Data in MongoDB via `motor`/`odmantic`. Admin panel via `starlette-admin`.
- **Orchestration Plane** (`ai/`): LangGraph-based agent runtime with a supervisor that routes to sub-agents. Uses LiteLLM for model-agnostic LLM calls, Qdrant for schema/RAG vector search, and Langfuse for tracing.

### Current maturity level
**Mid-stage MVP / Early Production.** Core CRUD, auth, RBAC, multi-agent chat, MCP integration, and observability are all functional. The codebase is well-structured with clear module boundaries. However, there are no external integrations (Slack, Jira, etc.), no webhook infrastructure, no background job queue, no token refresh scheduler, and limited test coverage for edge cases.

### Whether the README matches the actual backend code
**Yes — the README is accurate and comprehensive.** It correctly describes both planes, the project layout, tech stack, configuration, seeding scripts, API surface, RBAC model, and MCP integration. Minor discrepancy: the README mentions `backend/mcp_server/connection.py`, `discovery.py`, `catalog.py`, `client.py`, `runtime.py`, `oauth.py`, `oauth_runtime.py`, `oauth_storage.py` as separate files, but in practice all MCP service logic is consolidated into a single `backend/mcp_server/services.py` file (1370 lines). This is a documentation-vs-code discrepancy: the functionality is all present, just organized differently.

---

## 2. Backend Repository Structure

```
.
├── backend/                      # FastAPI control plane
│   ├── main.py                   # App factory: routers, middleware, startup seeding
│   ├── admin.py                  # starlette-admin panel at /admin (ODMantic models)
│   ├── dependencies.py           # FastAPI dependencies: get_current_user, require_permission
│   ├── auth/                     # JWT auth, signup/login, OTP password reset, RBAC
│   │   ├── constants.py          # Role/permission definitions (static fallback)
│   │   ├── models.py             # User, PermissionModel, RolePermission Pydantic models
│   │   ├── permissions.py        # Permission resolution, role cache, org access guards
│   │   ├── routes.py             # Auth endpoints: register, login, logout, me, OTP
│   │   ├── schemas.py            # Request/response schemas for auth
│   │   ├── services.py           # Auth business logic: user CRUD, password hashing, OTP
│   │   └── validators.py         # Email/password validation rules
│   ├── organization/             # Organization CRUD + nested resource listings
│   │   ├── models.py             # Organization Pydantic model
│   │   ├── routes.py             # Org CRUD, nested agents/tools/users/db-connections/settings
│   │   ├── schemas.py            # OrganizationCreate/Update/Public
│   │   └── services.py           # Org business logic, soft delete, search
│   ├── user/                     # User management (super-admin scoped)
│   │   ├── routes.py             # GET /users (super-admin only)
│   │   └── services.py           # User listing with search/role filters
│   ├── agent/                    # Agent CRUD
│   │   ├── models.py             # Agent Pydantic model
│   │   ├── routes.py             # Agent CRUD endpoints
│   │   ├── schemas.py            # AgentCreate/Update/Public
│   │   ├── services.py           # Agent business logic, prompt regeneration, cache invalidation
│   │   └── validators.py         # ObjectId validation
│   ├── tool/                     # Org-level tool instances
│   │   ├── models.py             # Tool, ToolRegistry, ChatSession, Message, DbConnection, RagSource
│   │   ├── routes.py             # Tool CRUD endpoints
│   │   ├── schemas.py            # ToolCreate/Update/Public
│   │   └── services.py           # Tool business logic, quota enforcement, agent linkage
│   ├── toolregistry/             # Global tool catalog (super-admin managed)
│   │   ├── routes.py             # ToolRegistry CRUD (super-admin for write)
│   │   ├── schemas.py            # ToolRegistryCreate/Update/Public
│   │   └── services.py           # ToolRegistry business logic
│   ├── dbconnection/             # Encrypted DB connections + schema introspection
│   │   ├── constants.py          # GridFS bucket name, inline size limit
│   │   ├── routes.py             # DB connection CRUD, preview, schema, descriptions
│   │   ├── schemas.py            # DbConnectionCreate/Update/Public, PreviewRequest
│   │   └── services.py           # Encryption, schema fetch, GridFS, Qdrant indexing
│   ├── chat/                     # Supervisor chat (multi-agent routing)
│   │   ├── __init__.py
│   │   ├── graph.py              # LangGraph builder: supervisor + sub-agent nodes, tool execution
│   │   ├── routes.py             # Chat session/message endpoints
│   │   ├── schemas.py            # ChatRequest/Response, session history
│   │   ├── services.py           # Session lifecycle, message handling, memory, title generation
│   │   └── tracing_ctx.py        # Per-request Langfuse tracer via ContextVar
│   ├── direct_agent/             # Direct 1:1 agent chat (bypasses supervisor)
│   │   ├── __init__.py
│   │   ├── routes.py             # POST /chat (direct agent)
│   │   ├── schemas.py            # DirectChatRequest/Response
│   │   └── services.py           # Single-agent graph invocation, session management
│   ├── mcp_server/               # MCP server integration (stdio/SSE/WebSocket + OAuth)
│   │   ├── models.py             # McpServer, McpRegistryEntry Pydantic models
│   │   ├── routes.py             # MCP CRUD, catalog, test connection, OAuth start/callback
│   │   ├── schemas.py            # McpServerCreate/Update/Public, OAuth schemas
│   │   └── services.py           # All MCP logic: token storage, OAuth, connection, discovery, catalog, CRUD (1370 lines)
│   ├── prompt_generator/         # LLM-based system prompt generation
│   │   ├── routes.py             # POST /generate-prompt
│   │   ├── schemas.py            # PromptGeneratorRequest/Response
│   │   └── services.py           # LLM prompt generation logic
│   ├── tracing/                  # Langfuse observability read endpoints
│   │   ├── __init__.py
│   │   ├── routes.py             # Trace list, detail, stats; session list; agent-scoped views
│   │   ├── schemas.py            # TracesResponse, TraceDetail, TraceStats, SessionsResponse
│   │   └── services.py           # Langfuse API proxy with cache, rate-limit retry, normalization
│   ├── notifications/            # Per-user and org-wide notifications
│   │   ├── __init__.py
│   │   ├── routes.py             # Notification list, unread count, mark read, dismiss
│   │   ├── schemas.py            # NotificationPublic, UnreadCountResponse
│   │   └── services.py           # Notification CRUD, org+user scoping
│   ├── org_settings/             # Per-organization settings
│   │   ├── __init__.py
│   │   ├── schemas.py            # OrgSettingsUpdate/Public
│   │   └── services.py           # Settings upsert with defaults
│   ├── memory/                   # Backend-side memory helpers
│   │   ├── __init__.py
│   │   ├── conversation_store.py # Async MongoDB CRUD for conversation_logs
│   │   ├── schemas.py            # ConversationDocument, TurnEntry, SummaryEntry
│   │   └── sub_agent_memory.py   # Per-agent memory: fetch, append, compress, seed
│   ├── core/                     # Cross-cutting concerns
│   │   ├── config.py             # Settings (pydantic-settings from .env)
│   │   ├── constants.py          # Shared constants: pagination, rate limit, quota defaults
│   │   ├── db_introspect.py      # External DB schema fetching (SQL/MongoDB/Supabase)
│   │   ├── email.py              # SMTP OTP email delivery
│   │   ├── encryption.py         # Fernet encrypt/decrypt/mask for secrets at rest
│   │   ├── pagination.py         # Page/Pagination generic helpers
│   │   ├── query_audit.py        # Query audit logging to MongoDB
│   │   ├── query_runner.py       # Execute read-only SQL/MongoDB queries (agent tool)
│   │   ├── quota.py              # Business quotas (orgs/day, tools/org)
│   │   ├── ratelimit.py          # Per-IP fixed-window rate limiting middleware
│   │   ├── security.py           # JWT encode/decode, bcrypt password hashing
│   │   └── softdelete.py         # Soft delete helpers (is_deleted + deleted_at)
│   ├── db/                       # Database setup
│   │   ├── constants.py          # Collection names (24 collections)
│   │   └── database.py           # Motor async + PyMongo sync clients, collection references
│   ├── scripts/                  # Seeders, smoke tests, verification scripts (25+ scripts)
│   ├── tests/                    # Backend test suite (25+ test files)
│   └── docs/                     # API.md — full REST API reference
├── ai/                           # LangGraph orchestration plane
│   ├── __init__.py
│   ├── models.py                 # Model enum (GPT-4.1, GPT-5.4-mini/nano)
│   ├── agents/                   # Agent implementations
│   │   ├── main_agent.py         # MainAgent (supervisor) — standalone LangGraph path
│   │   ├── sub_agent.py          # SubAgent — standalone LangGraph path
│   │   └── summarizer/           # Conversation compression
│   │       ├── agent.py          # Summarizer_Agent
│   │       ├── prompt.py         # Summarizer prompt template
│   │       └── tools.py          # Summarizer tools
│   ├── graph/                    # LangGraph wiring
│   │   ├── graph.py              # Graph building (standalone path)
│   │   ├── nodes.py              # Node functions
│   │   ├── state.py              # Graph state definition
│   │   └── studio.py             # LangGraph Studio entry point
│   ├── memory/                   # Conversation/memory persistence
│   │   ├── memory.py             # Memory module
│   │   ├── memory_schema.py      # Memory schemas
│   │   └── mongo_store.py        # MongoDB-backed memory store
│   ├── rag/                      # Schema indexing & retrieval
│   │   ├── schema_indexer.py     # Qdrant embedding + indexing pipeline
│   │   ├── schema_retriever.py   # Vector search for relevant schema
│   │   └── search_schema_tool.py # Synthetic tool: search_schema for agents
│   ├── tools/                    # Built-in tool implementations
│   │   └── tools.py              # Tools class: query_db, search_internet
│   └── tracing/                  # Langfuse tracing
│       ├── __init__.py           # setup_tracing(): LiteLLM → Langfuse callback
│       ├── context.py            # TracingContext DTO
│       ├── tags.py               # Tag helpers (org_tag, agent_tag)
│       └── tracer.py             # AgentTracer: Langfuse trace/span lifecycle
├── tests/                        # Top-level MCP integration/unit tests
├── Dockerfile                    # uv-based build with ODBC, Node/npx, uvx
├── docker-compose.yml            # FastAPI service definition
├── pyproject.toml                # Dependencies (uv-managed)
└── README.md                     # Comprehensive project documentation
```

### Deployment and Containerization

#### Dockerfile (`Dockerfile`)
- **Multi-stage build:** `python:3.11-slim` builder + runtime
- **Package manager:** `uv` (Astral) — copies `uv` and `uvx` binaries from `ghcr.io/astral-sh/uv:latest`
- **Dependency install:** `uv sync --frozen --no-dev --no-install-project` from lockfile
- **System dependencies installed in runtime image:**
  - Microsoft ODBC Driver 17 for SQL Server (required by `pyodbc` for MSSQL connections)
  - Node.js + npm — needed for `npx`-based MCP servers (filesystem, github, slack, etc.)
  - `uv` + `uvx` — needed for `uvx`-based MCP servers (mcp-server-fetch, mcp-server-git, etc.)
- **Exposed port:** 8000
- **CMD:** `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

#### docker-compose.yml
- **Single service:** `fastapi` (named `fastapi_app`)
- **Port mapping:** 8000:8000
- **Env:** `.env` file
- **Volumes:** Source code mounted at `/app` (dev), `uv_cache` named volume at `/root/.cache/uv`
- **Dev command:** `uv run --no-sync uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`
- **Network:** `app_network` (bridge)
- **Notable:** No MongoDB, Qdrant, or Redis containers — assumes external services

### Notable observations

| Observation | Details |
|---|---|
| **Well-organized** | Clean module separation with consistent `routes/schemas/services/models` pattern per domain |
| **No unused folders** | Every folder has a clear purpose |
| **Large monolith service** | `backend/mcp_server/services.py` is 1370 lines — combines what README describes as 8 separate files |
| **Two chat paths** | `backend/chat/` (supervisor) and `backend/direct_agent/` (1:1) share graph/memory infrastructure |
| **Two AI paths** | `ai/` (standalone LangGraph) and `backend/chat/graph.py` (FastAPI-embedded) coexist |
| **`backend/tool/models.py`** | Contains models for multiple domains (ToolRegistry, ChatSession, Message, RagSource, DbConnection) — would benefit from splitting |
| **No database containers** | `docker-compose.yml` only defines the FastAPI service — MongoDB, Qdrant, and any future Redis must be provisioned separately |

---

## 3. FastAPI Application Architecture

### App entry point
- **File:** `backend/main.py`
- **Object:** `app = FastAPI(...)` (line 88)
- **Launch:** `uv run uvicorn backend.main:app --reload`

### Router registration
All routers are registered in `backend/main.py` (lines 99-112):

| Router | Prefix | Module |
|---|---|---|
| `auth_router` | `/auth` | `backend.auth.routes` |
| `organization_router` | `/organizations` | `backend.organization.routes` |
| `agent_router` | `/agents` | `backend.agent.routes` |
| `db_connection_router` | `/db-connections` | `backend.dbconnection.routes` |
| `tool_router` | `/tools` | `backend.tool.routes` |
| `chat_router` | `/chat` | `backend.chat.routes` |
| `direct_chat_router` | `/chat` | `backend.direct_agent.routes` |
| `tool_registry_router` | `/tool-registry` | `backend.toolregistry.routes` |
| `mcp_server_router` | `/mcp-servers` | `backend.mcp_server.routes` |
| `prompt_generator_router` | `/generate-prompt` | `backend.prompt_generator.routes` |
| `mcp_oauth_callback_router` | `/mcp-servers` | `backend.mcp_server.routes` |
| `tracing_router` | (no prefix) | `backend.tracing.routes` |
| `user_router` | `/users` | `backend.user.routes` |
| `notifications_router` | `/notifications` | `backend.notifications.routes` |

### Middleware (applied in order, outermost first)
1. **CORSMiddleware** (line 123) — `allow_origins=["*"]`, `allow_credentials=True`, all methods/headers
2. **SecurityHeadersMiddleware** (line 115) — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `HSTS`
3. **RateLimitMiddleware** (line 114) — Per-IP fixed-window rate limiting from `rate_limit_config` collection

### Startup events
- **Function:** `_seed_config()` in `backend/main.py` (line 143)
- Runs on `@app.on_event("startup")`:
  1. `setup_tracing()` — Activates LiteLLM → Langfuse callback
  2. `ensure_default_config()` — Seeds rate limit config document
  3. `ensure_default_quota()` — Seeds quota config document
  4. `ensure_default_roles()` — Upserts built-in permissions and role mappings
  5. `_check_qdrant()` — Tests Qdrant connectivity

### Dependency injection
- **File:** `backend/dependencies.py`
- **`get_current_user()`** — Decodes Bearer JWT → resolves user from MongoDB
- **`require_permission(permission)`** — Factory returning a dependency that checks RBAC
- **`get_current_admin()`** — Requires `create_user` permission
- **`require_super_admin()`** — Requires `super_admin` role
- **`get_tracing_context()`** — Builds `TracingContext` from authenticated user + request headers

### Error handling
- **Global catch-all:** `_unhandled_exception_handler` (line 132) — Returns generic 500, logs full exception server-side, never leaks stack traces
- **Per-route:** HTTPException raised in services with appropriate status codes (400, 401, 403, 404, 409, 422, 429)

### Health checks
- `GET /` → `{"message": "FastAPI is running 🚀"}` (line 172)
- `GET /mongo-check` → Pings MongoDB, returns 200 or 503 (line 177)

### Admin panel setup
- **File:** `backend/admin.py`
- **Mount:** `admin.mount_to(app)` in `main.py` (line 169)
- **URL:** `/admin`
- **Auth:** `AdminAuthProvider` — authenticates against `users` collection, requires `admin`/`org_admin`/`super_admin` role
- **Session:** `SessionMiddleware` with `JWT_SECRET_KEY`
- **Views:** Organization, User, Agent, Tool, DbConnection, ToolRegistry, Permission, RolePermission, Role, RateLimitConfig, QuotaConfig
- **Sensitive fields hidden:** `password` (User), `connection_string` (DbConnection)

---

## 4. Authentication and Authorization

### Login/Signup/Register flow

| Endpoint | Function | File | Description |
|---|---|---|---|
| `POST /auth/register` | `register()` | `backend/auth/routes.py:30` | Self-service: auto-creates org + admin user, returns JWT |
| `POST /auth/login` | `login()` | `backend/auth/routes.py:59` | Email/password → JWT |
| `POST /auth/users` | `create_user()` | `backend/auth/routes.py:46` | Admin-provisioned user creation with JWT return |
| `POST /auth/admin/users` | `create_user_as_admin()` | `backend/auth/routes.py:65` | Admin creates user in their org, no JWT returned |
| `POST /auth/logout` | `logout()` | `backend/auth/routes.py:40` | Stateless — client discards token |
| `GET /auth/me` | `me()` | `backend/auth/routes.py:76` | Returns current authenticated user |
| `GET /auth/me/permissions` | `me_permissions()` | `backend/auth/routes.py:82` | Returns resolved permissions for current user's role |

### JWT handling
- **File:** `backend/core/security.py`
- **Algorithm:** HS256 (configurable via `JWT_ALGORITHM`)
- **Secret:** `JWT_SECRET_KEY` (defaults to `"change-me-in-production"`)
- **Expiry:** 24 hours (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Payload:** `{"sub": user_id, "exp": timestamp}`
- **Functions:** `create_access_token(subject, expires_minutes)`, `decode_access_token(token) -> Optional[str]`

### Current user dependency
- **File:** `backend/dependencies.py`
- **Function:** `get_current_user()` — Extracts Bearer token via `HTTPBearer`, decodes JWT, looks up user by `_id` in MongoDB, returns `UserPublic`

### Password hashing
- **File:** `backend/core/security.py`
- **Library:** `bcrypt`
- **Functions:** `hash_password(password)`, `verify_password(plain, hashed)`
- **Truncation:** Input truncated to 72 bytes (bcrypt limit) via `MAX_BCRYPT_BYTES`

### OTP/Password reset
- **File:** `backend/auth/services.py`
- **Flow:** `POST /auth/forgot-password` → generates 6-digit OTP, stores bcrypt hash in `password_resets` collection, emails via SMTP
- **Verification:** `POST /auth/verify-otp` → validates OTP and checks expiry
- **Reset:** `POST /auth/reset-password` → verifies OTP, updates password, deletes reset record
- **Security:** OTP hashed with bcrypt before storage. `OTP_RETURN_IN_RESPONSE` flag (defaults false) — when true, returns OTP in response (dev only)

### RBAC implementation
- **File:** `backend/auth/permissions.py`
- **File:** `backend/auth/constants.py`

**Permission type:** `Literal` of 30 permissions following `view_*/create_*/edit_*/delete_*` pattern per resource.

**Roles (4 built-in):**

| Role | Scope | Key permissions |
|---|---|---|
| `super_admin` | All orgs | All 30 permissions |
| `org_admin` | Own org | All except `create_org` |
| `org_manager` | Own org | View all + edit agents/tools/orgs + chat |
| `user` | Own org | View all + create chat/session |

**Resolution:** `_load_roles()` reads from `role_permissions` collection with 5-second TTL cache. Falls back to static `ROLE_DEFINITIONS` in `backend/auth/constants.py`.

**Legacy aliases:** `admin` → `org_admin`, `member` → `user`, normalized at runtime via `normalize_role()`.

### Permission checks
- **`user_has_permission(user, permission)`** — Super admin always passes; others checked against role's permission map
- **`assert_org_access(user, org_id)`** — Non-super-admins can only access their own org
- **`assert_organization_access(user, org_id)`** — Also checks org existence + creator access
- **`assert_super_admin(user)`** — Raises 403 if not super_admin

### Organization scoping
Every resource query filters by `organization_id`. Super admins bypass via explicit checks in route handlers. See Section 5 for details.

### Security gaps
1. **No JWT refresh tokens** — 24-hour expiry with no rotation mechanism
2. **No JWT revocation/blacklist** — Logout is purely client-side
3. **No account lockout** — No brute-force protection on login beyond rate limiting
4. **No 2FA enforcement** — `org_settings.require_2fa` field exists but is not enforced
5. **No email verification** on signup — users can register with any email
6. **OTP not rate-limited** separately — relies on global IP rate limit only

---

## 5. Multi-Tenant Architecture

### How organization_id is used
Every user belongs to exactly one organization via `user.organization_id`. All resources (agents, tools, DB connections, MCP servers, chat sessions, notifications, conversation logs) carry an `organization_id` field. All queries filter by this field for non-super-admin users.

### Which models are tenant-scoped

| Model/Collection | Tenant field | Scoping enforced |
|---|---|---|
| `users` | `organization_id` | Yes — login returns org's DB connections |
| `agents` | `organization_id` | Yes — routes check `assert_org_access` |
| `tools` | `organization_id` | Yes — routes check `assert_org_access` |
| `db_connections` | `organization_id` | Yes — routes check `assert_org_access` |
| `mcp_servers` | `organization_id` | Yes — routes check `assert_org_access` |
| `chat_sessions` | `organization_id` | Yes — queries always include org_id |
| `conversation_logs` | `organization_id` | Yes — filter includes user_id + session_id |
| `notifications` | `organization_id` | Yes — scoped to org + user |
| `organization_settings` | `organization_id` | Yes |
| `query_audit_logs` | `org_id` | Write-only, no read API exposed |
| `tool_registry` | **NOT scoped** | Global — managed by super_admin |
| `mcp_server_registry` | **NOT scoped** | Global — catalog shared across orgs |
| `roles` / `role_permissions` / `permissions` | **NOT scoped** | Global — shared RBAC definitions |
| `rate_limit_config` / `quota_config` | **NOT scoped** | Global singletons |
| `password_resets` | `email` only | Per-email, not per-org |

### Which routes enforce tenant scoping
All CRUD routes for org-scoped resources call `assert_org_access(current_user, org_id)` or `assert_organization_access(current_user, org_id)`. List endpoints show only the current user's org unless `is_super_admin`. MCP server list is scoped by `current_user.organization_id`.

### Super admin behavior
- Bypasses all `assert_org_access` / `assert_organization_access` checks
- Can view all organizations, agents, tools, users
- Can filter by `organization_id` query parameter on chat/tracing endpoints
- Can manage tool registry (global catalog)

### Possible tenant isolation risks
1. **Agent ID in direct chat** — `POST /chat` accepts `agent_id` but validates against `organization_id` + `agent_id` combination (safe)
2. **DB query tool** — `query_db` in `ai/tools/tools.py` always scopes `db_connections_collection` queries by `organization_id` (safe)
3. **MCP tool execution** — MCP tools are bound per-agent which is per-org; but the `_SESSIONS` cache in `mcp_server/services.py` is process-global keyed by server `_id` — two orgs cannot share an MCP server doc so this is safe
4. **Conversation store** — Indexed by `(session_id, user_id, agent_id)` with org_id on the document — safe
5. **Qdrant schema index** — Points carry `org_id` payload and queries always filter by it (safe)
6. **Risk: Chat session access** — `direct_agent/services.py` validates session ownership by `user_id` but does not check `organization_id` on the session lookup (line 92-93). A user could potentially access a session from another org if they knew the `thread_id`. **This is a minor isolation gap.**

---

## 6. Data Models and MongoDB Collections

### 6.1 Users Collection (`users`)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `organization_id` | string | Tenant scope |
| `name` | string | Display name |
| `email` | EmailStr | Unique, used for login |
| `role` | string | Role slug (user, org_manager, org_admin, super_admin) |
| `password` | string | bcrypt hash |
| `created_at` | datetime | UTC timestamp |

- **File:** `backend/auth/models.py` (Pydantic), `backend/admin.py` (ODMantic)
- **Soft delete:** No
- **Indexes:** None explicitly declared (email uniqueness enforced at application level)
- **Security-sensitive:** `password` field hidden from admin UI and public schemas

### 6.2 Organizations Collection (`organizations`)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `name` | string | Org name |
| `description` | string? | Optional |
| `created_by` | string | User ID of creator |
| `created_at` | datetime | UTC |
| `updated_at` | datetime | UTC |
| `is_deleted` | bool | Soft delete flag |
| `deleted_at` | datetime? | Soft delete timestamp |

- **File:** `backend/organization/models.py` (Pydantic), `backend/admin.py` (ODMantic)
- **Soft delete:** Yes (`is_deleted`, `deleted_at`)

### 6.3 Agents Collection (`agents`)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `organization_id` | string | Tenant scope |
| `name` | string | Agent name |
| `description` | string? | Internal description |
| `user_description` | string? | User-facing description |
| `prompt` | string | System prompt |
| `instructions` | string? | Additional instructions |
| `guardrails` | string | Guardrail rules |
| `tool_ids` | string[] | References to `tools` collection |
| `rag_ids` | string[] | References to RAG sources |
| `mcp_server_ids` | string[] | References to `mcp_servers` collection |
| `tool_prompt` | string? | Auto-generated tool hint prompt |
| `mcp_prompt` | string? | Auto-generated MCP tool hint prompt |
| `created_by` | string | Creator user ID |
| `created_at` | datetime | UTC |
| `is_deleted` | bool | Soft delete flag |
| `deleted_at` | datetime? | Soft delete timestamp |

- **File:** `backend/agent/models.py`
- **Soft delete:** Yes
- **Relationships:** Many-to-many with tools (via `tool_ids`), MCP servers (via `mcp_server_ids`)

### 6.4 Tools Collection (`tools`)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `organization_id` | string | Tenant scope |
| `agent_id` | string? | Owning agent |
| `name` | string? | Copied from registry entry |
| `description` | string? | Description |
| `user_description` | string? | User-facing |
| `db_conn_id` | string? | Linked DB connection |
| `tool_id` | string | Reference to `tool_registry` entry |
| `created_at` | datetime | UTC |
| `is_deleted` | bool | Soft delete flag |
| `deleted_at` | datetime? | |

- **File:** `backend/tool/models.py`
- **Soft delete:** Yes

### 6.5 Tool Registry Collection (`tool_registry`)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `name` | string | Tool name |
| `description` | string? | |
| `type` | string | Tool type (e.g., `db_query`, `search_internet`) |
| `is_active` | bool | Whether available for use |
| `tool_schema` | dict? | JSON schema for the tool |
| `created_at` | datetime | UTC |
| `is_deleted` | bool | Soft delete flag |

- **File:** `backend/tool/models.py` (ToolRegistry class)
- **Scope:** Global (not org-scoped)
- **Soft delete:** Yes

### 6.6 DB Connections Collection (`db_connections`)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `organization_id` | string | Tenant scope |
| `connection_string` | string | **Fernet-encrypted** at rest |
| `schema` | dict? | Introspected DB schema (inline when small) |
| `schema_gridfs_id` | string? | GridFS reference for large schemas |
| `schema_indexed` | bool? | Whether indexed in Qdrant |
| `schema_table_count` | int? | Tables indexed |
| `created_at` | datetime | UTC |
| `is_deleted` | bool | Soft delete flag |
| `deleted_at` | datetime? | |

- **File:** `backend/tool/models.py` (DbConnection class)
- **Soft delete:** Yes
- **Security-sensitive:** `connection_string` encrypted, masked in public responses

### 6.7 MCP Servers Collection (`mcp_servers`)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `organization_id` | string | Tenant scope |
| `agent_id` | string | Bound to a specific agent |
| `registry_key` | string? | Reference to catalog entry (Flow A) |
| `auth_type` | string | `none` / `bearer` / `oauth` |
| `name` | string? | Server name |
| `user_description` | string? | |
| `connection_string` | string? | URL or command |
| `transport` | string? | `stdio` / `streamable_http` / `sse` / `websocket` |
| `headers` | dict? | HTTP headers (may contain Bearer token) |
| `tools` | dict[] | Cached discovered tools |
| `tool_count` | int | |
| `status` | string | `pending` / `connected` / `error` |
| `last_error` | string? | |
| `discovered_at` | datetime? | |
| `timeout` | float | Default 30s |
| `is_active` | bool | |
| `created_at` | datetime | UTC |
| `is_deleted` | bool | Soft delete flag |

- **File:** `backend/mcp_server/models.py`
- **Soft delete:** Yes

### 6.8 MCP Server Registry Collection (`mcp_server_registry`)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `key` | string | Unique slug (e.g., "filesystem") |
| `name` | string | Display name |
| `description` | string | |
| `category` | string? | E.g., "developer-tools" |
| `transport` | string? | Default transport |
| `connection_string` | string | Template with `<PLACEHOLDER>` tokens |
| `requires` | string[] | Required placeholder keys |
| `source` | string | `curated` / `registry` |
| `homepage` | string? | |
| `repo_url` | string? | |
| `is_active` | bool | |
| `created_at` | datetime | UTC |
| `is_deleted` | bool | |

- **File:** `backend/mcp_server/models.py` (McpRegistryEntry)
- **Scope:** Global (not org-scoped)

### 6.9 MCP OAuth Flows Collection (`mcp_oauth_flows`)

| Field | Type | Description |
|---|---|---|
| `state` | string | OAuth state parameter (CSRF token) |
| `code_verifier` | string | **Encrypted** PKCE verifier |
| `client_info` | string | **Encrypted** client registration JSON |
| `client_id` | string | OAuth client ID |
| `token_endpoint` | string | Token exchange URL |
| `server_url` | string | MCP server URL |
| `scope` | string? | Requested OAuth scope |
| `resource` | string? | OAuth resource parameter |
| `redirect_uri` | string | Callback URL |
| `organization_id` | string | |
| `agent_id` | string | |
| `user_description` | string? | |
| `created_at` | float | Unix timestamp |
| `expires_at` | float | TTL (default 900s) |

### 6.10 MCP OAuth Tokens Collection (`mcp_oauth_tokens`)

| Field | Type | Description |
|---|---|---|
| `storage_key` | string | `mcp_servers` document ID |
| `tokens` | string | **Encrypted** OAuth token JSON |
| `client_info` | string | **Encrypted** client registration JSON |
| `token_endpoint` | string | For token refresh |
| `resource` | string? | OAuth resource |
| `expires_at` | float? | Token expiry (Unix timestamp) |
| `updated_at` | float | Last update |

### 6.11 Chat Sessions Collection (`chat_sessions`)

| Field | Type | Description |
|---|---|---|
| `thread_id` | string | UUID, primary identifier |
| `lg_thread_id` | string? | LangGraph internal thread ID |
| `epoch` | int | Session epoch (default 1) |
| `organization_id` | string | Tenant scope |
| `user_id` | string | Session owner |
| `agent_ids` | string[] | Agents participating in this session |
| `name` | string? | Auto-generated or manual title |
| `mode` | string? | `"single"` for direct agent sessions |
| `created_at` | datetime | UTC |
| `is_deleted` | bool | |

### 6.12 Conversation Logs Collection (`conversation_logs`)

| Field | Type | Description |
|---|---|---|
| `session_id` | string | Chat session thread_id |
| `user_id` | string | |
| `organization_id` | string | Tenant scope |
| `agent_id` | string | Per-agent conversation |
| `conversations` | array | Mixed TurnEntry / SummaryEntry objects |
| `total_messages` | int | Running count |
| `total_summaries` | int | Compression count |
| `new_messages_since_compression` | int | |
| `created_at` | datetime | |
| `updated_at` | datetime | |

- **Index:** Unique compound on `(session_id, user_id, agent_id)` with partial filter
- **File:** `backend/memory/conversation_store.py`

### 6.13 Notifications Collection (`notifications`)

| Field | Type | Description |
|---|---|---|
| `organization_id` | string | Tenant scope |
| `user_id` | string? | `None` = org-wide (visible to every member) |
| `type` | NotificationType | `"agent"` \| `"tool"` \| `"alert"` \| `"success"` \| `"system"` |
| `title` | string | Notification title |
| `message` | string | Notification body |
| `read` | bool | Read status (default `false`) |
| `created_at` | datetime | UTC |

- **File:** `backend/notifications/schemas.py`
- **Notification types** (`NotificationType`): `Literal["agent", "tool", "alert", "success", "system"]`
- **Scoping:** Notifications can be per-user (`user_id` set) or org-wide (`user_id = None`)

### 6.14 Organization Settings Collection (`organization_settings`)

| Field | Type | Default | Description |
|---|---|---|---|
| `organization_id` | string | — | Tenant scope |
| `maintenance_mode` | bool | `false` | Org in maintenance mode |
| `require_2fa` | bool | `false` | Require 2FA (field exists but NOT enforced) |
| `session_timeout_enabled` | bool | `true` | Enable session timeout |
| `session_duration` | string | `"30m"` | Session timeout duration |
| `audit_logging` | bool | `true` | Enable audit logging |
| `default_model` | string | `"gpt-4o"` | Default LLM model for the org |
| `updated_at` | datetime? | — | Last update timestamp |

- **File:** `backend/org_settings/schemas.py` (OrgSettingsPublic/OrgSettingsUpdate), `backend/org_settings/services.py`
- **Behavior:** Upsert with defaults — if an org has no stored settings, defaults are applied. New fields automatically get defaults without migration.

### 6.15 Other Collections

| Collection | Purpose | File |
|---|---|---|
| `password_resets` | OTP storage for password reset | `backend/auth/services.py` |
| `roles` | Legacy role definitions with permission flag maps | `backend/admin.py` |
| `permissions` | Individual permission definitions | `backend/auth/models.py` |
| `role_permissions` | Role-to-permission mappings (list of permission names) | `backend/auth/models.py` |
| `rate_limit_config` | Global rate limit configuration singleton | `backend/core/ratelimit.py` |
| `quota_config` | Global quota configuration singleton | `backend/core/quota.py` |
| `rag_sources` | RAG source definitions (placeholder) | `backend/tool/models.py` |
| `messages` | Legacy message storage (model exists, not actively used) | `backend/tool/models.py` |
| `query_audit_logs` | Audit trail for agent DB queries | `backend/core/query_audit.py` |

**Total: 24 MongoDB collections** defined in `backend/db/constants.py`.

---

## 7. API Surface

### Auth (`/auth`)

| Method | Path | Purpose | Auth | Permission | Request Schema | Response Schema | Handler |
|---|---|---|---|---|---|---|---|
| POST | `/auth/register` | Self-service registration | No | — | `RegisterRequest` | `TokenResponse` | `auth.routes.register` |
| POST | `/auth/login` | Login | No | — | `LoginRequest` | `TokenResponse` | `auth.routes.login` |
| POST | `/auth/logout` | Logout (stateless) | No | — | — | `MessageResponse` | `auth.routes.logout` |
| POST | `/auth/users` | Admin create user + JWT | Yes | `create_user` | `SignupRequest` | `TokenResponse` | `auth.routes.create_user` |
| POST | `/auth/admin/users` | Admin create user (no JWT) | Yes | `create_user` | `AdminCreateUserRequest` | `UserPublic` | `auth.routes.create_user_as_admin` |
| GET | `/auth/me` | Current user | Yes | — | — | `UserPublic` | `auth.routes.me` |
| GET | `/auth/me/permissions` | Current permissions | Yes | — | — | dict | `auth.routes.me_permissions` |
| POST | `/auth/forgot-password` | Request OTP | No | — | `ForgotPasswordRequest` | `MessageResponse` | `auth.routes.forgot_password` |
| POST | `/auth/verify-otp` | Verify OTP | No | — | `VerifyOtpRequest` | `MessageResponse` | `auth.routes.verify_otp` |
| POST | `/auth/reset-password` | Reset password | No | — | `ResetPasswordRequest` | `MessageResponse` | `auth.routes.reset_password` |

### Organizations (`/organizations`)

| Method | Path | Purpose | Auth | Permission | Handler |
|---|---|---|---|---|---|
| POST | `/organizations` | Create org | Yes | `create_org` | `organization.routes.create_organization` |
| GET | `/organizations` | List orgs (paginated, searchable) | Yes | `view_org` | `organization.routes.list_organizations` |
| GET | `/organizations/{org_id}` | Get org | Yes | `view_org` | `organization.routes.get_organization` |
| PUT | `/organizations/{org_id}` | Update org | Yes | `edit_org` | `organization.routes.update_organization` |
| DELETE | `/organizations/{org_id}` | Soft-delete org | Yes | `delete_org` | `organization.routes.delete_organization` |
| GET | `/organizations/{org_id}/agents` | List org agents | Yes | `view_org` | `organization.routes.list_organization_agents` |
| GET | `/organizations/{org_id}/tools` | List org tools | Yes | `view_org` | `organization.routes.list_organization_tools` |
| GET | `/organizations/{org_id}/db-connections` | List org DB connections | Yes | `view_org` | `organization.routes.list_organization_db_connections` |
| GET | `/organizations/{org_id}/users` | List org users (searchable) | Yes | `view_org` | `organization.routes.list_organization_users` |
| GET | `/organizations/{org_id}/settings` | Get org settings | Yes | `view_org` | `organization.routes.get_organization_settings` |
| PUT | `/organizations/{org_id}/settings` | Update org settings | Yes | `edit_org` | `organization.routes.update_organization_settings` |

### Agents (`/agents`)

| Method | Path | Purpose | Auth | Permission | Handler |
|---|---|---|---|---|---|
| POST | `/agents` | Create agent | Yes | `create_agent` | `agent.routes.create_agent` |
| GET | `/agents` | List agents | Yes | `view_agent` | `agent.routes.list_agents` |
| GET | `/agents/org/{org_id}` | List agents by org | Yes | `view_agent` | `agent.routes.get_agents_by_org` |
| GET | `/agents/{agent_id}` | Get agent | Yes | `view_agent` | `agent.routes.get_agent` |
| PUT | `/agents/{agent_id}` | Update agent | Yes | `edit_agent` | `agent.routes.update_agent` |
| DELETE | `/agents/{agent_id}` | Soft-delete agent | Yes | `delete_agent` | `agent.routes.delete_agent` |

### Tools (`/tools`)

| Method | Path | Purpose | Auth | Permission | Handler |
|---|---|---|---|---|---|
| POST | `/tools` | Create tool | Yes | `create_tool` | `tool.routes.create_tool` |
| GET | `/tools` | List tools | Yes | `view_tool` | `tool.routes.list_tools` |
| GET | `/tools/org/{org_id}` | List tools by org | Yes | `view_tool` | `tool.routes.get_tools_by_org` |
| GET | `/tools/{tool_id}` | Get tool | Yes | `view_tool` | `tool.routes.get_tool` |
| PUT | `/tools/{tool_id}` | Update tool | Yes | `edit_tool` | `tool.routes.update_tool` |
| DELETE | `/tools/{tool_id}` | Soft-delete tool | Yes | `delete_tool` | `tool.routes.delete_tool` |

### Tool Registry (`/tool-registry`)

| Method | Path | Purpose | Auth | Permission | Handler |
|---|---|---|---|---|---|
| POST | `/tool-registry` | Create registry entry | Yes | `super_admin` | `toolregistry.routes.create_tool_registry` |
| GET | `/tool-registry` | List registry | Yes | `view_tool_registry` | `toolregistry.routes.list_tool_registry` |
| GET | `/tool-registry/{id}` | Get entry | Yes | `view_tool_registry` | `toolregistry.routes.get_tool_registry` |
| PUT | `/tool-registry/{id}` | Update entry | Yes | `super_admin` | `toolregistry.routes.update_tool_registry` |
| DELETE | `/tool-registry/{id}` | Soft-delete entry | Yes | `super_admin` | `toolregistry.routes.delete_tool_registry` |

### DB Connections (`/db-connections`)

| Method | Path | Purpose | Auth | Permission | Handler |
|---|---|---|---|---|---|
| POST | `/db-connections/preview` | Preview schema + LLM descriptions | Yes | `create_db_connection` | `dbconnection.routes.preview_db_connection` |
| POST | `/db-connections` | Create connection | Yes | `create_db_connection` | `dbconnection.routes.create_db_connection` |
| GET | `/db-connections` | List connections | Yes | `view_db_connection` | `dbconnection.routes.list_db_connections` |
| GET | `/db-connections/{id}` | Get connection | Yes | `view_db_connection` | `dbconnection.routes.get_db_connection` |
| GET | `/db-connections/{id}/schema` | Get DB schema | Yes | `view_db_connection` | `dbconnection.routes.get_db_connection_schema` |
| PUT | `/db-connections/{id}` | Update connection | Yes | `edit_db_connection` | `dbconnection.routes.update_db_connection` |
| DELETE | `/db-connections/{id}` | Soft-delete | Yes | `delete_db_connection` | `dbconnection.routes.delete_db_connection` |
| POST | `/db-connections/{id}/descriptions` | Save table descriptions | Yes | `edit_db_connection` | `dbconnection.routes.save_table_descriptions` |

### Chat (`/chat`)

| Method | Path | Purpose | Auth | Permission | Handler |
|---|---|---|---|---|---|
| POST | `/chat/session` | Create supervisor session | Yes | `create_chat_session` | `chat.routes.create_session` |
| GET | `/chat/sessions` | List user sessions | Yes | `view_chat_session` | `chat.routes.list_sessions` |
| PATCH | `/chat/sessions/{thread_id}` | Rename session | Yes | `edit_chat_session` | `chat.routes.rename_session` |
| GET | `/chat/sessions/{thread_id}/history` | Get session history | Yes | `view_chat_session` | `chat.routes.get_session_history` |
| POST | `/chat/message` | Send message | Yes | `create_chat` | `chat.routes.send_message` |
| POST | `/chat` | Direct agent chat | Yes | — | `direct_agent.routes.direct_chat` |

### MCP Servers (`/mcp-servers`)

| Method | Path | Purpose | Auth | Permission | Handler |
|---|---|---|---|---|---|
| GET | `/mcp-servers/catalog` | Browse MCP catalog | Yes | `view_tool` | `mcp_server.routes.list_catalog` |
| POST | `/mcp-servers/test-connection` | Test connection | Yes | `view_tool` | `mcp_server.routes.test_connection` |
| POST | `/mcp-servers/oauth/start` | Start OAuth flow | Yes | `create_tool` | `mcp_server.routes.oauth_start` |
| GET | `/mcp-servers/oauth/callback` | OAuth callback | **No** | — | `mcp_server.routes.oauth_callback` |
| GET | `/mcp-servers/agent/{agent_id}` | List by agent | Yes | `view_tool` | `mcp_server.routes.list_by_agent` |
| POST | `/mcp-servers` | Create MCP server | Yes | `create_tool` | `mcp_server.routes.create_mcp_server` |
| GET | `/mcp-servers` | List MCP servers | Yes | `view_tool` | `mcp_server.routes.list_mcp_servers` |
| GET | `/mcp-servers/{id}` | Get MCP server | Yes | `view_tool` | `mcp_server.routes.get_mcp_server` |
| PUT | `/mcp-servers/{id}` | Update MCP server | Yes | `edit_tool` | `mcp_server.routes.update_mcp_server` |
| POST | `/mcp-servers/{id}/discover` | Re-discover tools | Yes | `edit_tool` | `mcp_server.routes.discover_mcp_server` |
| DELETE | `/mcp-servers/{id}` | Soft-delete | Yes | `delete_tool` | `mcp_server.routes.delete_mcp_server` |

### Other Endpoints

| Method | Path | Purpose | Auth | Handler |
|---|---|---|---|---|
| POST | `/generate-prompt` | Generate agent prompt via LLM | Yes | `prompt_generator.routes.generate_agent_prompt` |

**Prompt Generator details:**
- **File:** `backend/prompt_generator/services.py`
- **Model:** `Model.GPT_5_4_NANO` (cheapest model for prompt generation)
- **Input schema:** `PromptGeneratorRequest` — `{agent_name: str, agent_description: str}`
- **Output schema:** `PromptGeneratorResponse` — `{prompt: str, model: str}`
- **System prompt:** Expert prompt engineer role — generates optimized system prompts with role definition, behavioral guidelines, output format preferences, and constraints
- **Temperature:** 0.7, **Max tokens:** 1024

| GET | `/users` | List all users (super-admin) | Yes (`super_admin`) | `user.routes.list_users` |

**User Service details:**
- **File:** `backend/user/services.py`
- **Functions:** `list_users(skip, limit, search, role)` and `list_users_by_org(org_id, skip, limit, search, role)`
- **Search:** Case-insensitive regex match on `name` or `email` fields (`$or` query with `$regex`)
- **Filtering:** Optional `role` parameter to filter by role slug
- **Sorting:** `created_at` descending
- **Returns:** `(list[UserPublic], total_count)` tuple for pagination
| GET | `/traces` | List Langfuse traces | Yes (`view_trace`) | `tracing.routes.list_traces` |
| GET | `/traces/stats` | Cost/token stats | Yes (`view_trace`) | `tracing.routes.get_trace_stats` |
| GET | `/traces/{id}` | Trace detail | Yes (`view_trace`) | `tracing.routes.get_trace` |
| GET | `/sessions` | List Langfuse sessions | Yes (`view_trace`) | `tracing.routes.list_sessions` |
| GET | `/agents/{id}/traces` | Agent traces | Yes (`view_trace`) | `tracing.routes.list_agent_traces` |
| GET | `/agents/{id}/stats` | Agent stats | Yes (`view_trace`) | `tracing.routes.get_agent_stats` |
| GET | `/notifications` | List notifications | Yes | `notifications.routes.list_notifications` |
| GET | `/notifications/unread-count` | Unread count | Yes | `notifications.routes.unread_count` |
| POST | `/notifications/read-all` | Mark all read | Yes | `notifications.routes.mark_all_read` |
| PATCH | `/notifications/{id}/read` | Mark one read | Yes | `notifications.routes.mark_read` |
| DELETE | `/notifications/{id}` | Dismiss | Yes | `notifications.routes.dismiss` |

---

## 8. Agent Management

### Agent CRUD
- **Create:** `POST /agents` → `agent.services.create_agent()` — validates org exists, stores agent doc, sends notification
- **Read:** `GET /agents/{id}` → `agent.services.get_agent()` — returns `AgentPublic` with all fields including auto-generated `tool_prompt` and `mcp_prompt`
- **Update:** `PUT /agents/{id}` → `agent.services.update_agent()` — partial update, invalidates graph cache, regenerates `tool_prompt` and `mcp_prompt`
- **Delete:** `DELETE /agents/{id}` → `agent.services.delete_agent()` — soft delete, unlinks tools

### Prompt handling
- `prompt` — The main system prompt, stored on the agent
- `guardrails` — Appended to the system prompt at runtime
- `tool_prompt` — Auto-generated from agent's `tool_ids` via `regenerate_tool_prompt()` — lists all tools and their descriptions
- `mcp_prompt` — Auto-generated from agent's `mcp_server_ids` via `regenerate_mcp_prompt()` — lists all MCP tools
- Runtime assembly (in `backend/chat/graph.py:_build_agent_node`): `sys_prompt = prompt + tool_prompt + mcp_prompt + guardrails + search_schema instruction`

### Guardrails
Stored as a string on the agent. Appended to the system prompt at runtime. Some agent docs store as comma-separated list, normalized to list in `get_agent_summaries_for_org()`.

### Assigned tools
- `tool_ids: List[str]` — references `tools` collection documents
- Tools are created via `POST /tools` with `agent_id` in payload, which auto-adds the tool's `_id` to `agent.tool_ids`
- On tool delete, the tool is unlinked from the agent

### RAG source assignment
- `rag_ids: List[str]` — field exists on the model but RAG source management is minimal (no dedicated CRUD routes for RAG sources)
- Schema-based RAG (search_schema tool) is auto-injected for agents with DB tools

### MCP server assignment
- `mcp_server_ids: List[str]` — references `mcp_servers` collection
- On MCP server creation, the server's `_id` is added to `agent.mcp_server_ids` via `_attach_to_agent()`
- On MCP server deletion, removed via `_detach_from_agent()`

### How agents are used in chat
1. **Supervisor path:** All org agents are loaded, a supervisor + sub-agent LangGraph is built. The supervisor routes user messages to the appropriate sub-agent
2. **Direct path:** A single agent graph (START → agent → END) is built for 1:1 chat

---

## 9. Tool Registry and Org Tools

### How global tool registry works
- **Collection:** `tool_registry`
- **Purpose:** Global catalog of available tool types (e.g., "Query DB Tool" type=`db_query`, "Search Internet" type=`search_internet`)
- **Management:** Super-admin only (create/update/delete via `/tool-registry` endpoints)
- **Fields:** `name`, `type`, `description`, `is_active`, `tool_schema`
- **Seeding:** `backend/scripts/seed_tool_registry.py`

### How org-level tools work
- **Collection:** `tools`
- **Purpose:** Org-specific tool instances that reference a global registry entry
- **Fields:** `organization_id`, `agent_id`, `tool_id` (→ tool_registry `_id`), `name` (copied from registry), `user_description`, `db_conn_id`
- **Quota:** Enforced by `enforce_tools_per_org()` (default 10 per org)

### How tools are created
1. `POST /tools` with `{organization_id, agent_id, tool_id, user_description}`
2. Validates: org exists, tool_id references an active registry entry, within quota
3. Copies `name` from registry entry
4. Inserts into `tools` collection
5. Adds the new tool `_id` to `agent.tool_ids` via `$addToSet`
6. Regenerates `agent.tool_prompt`
7. Sends notification

### How tools are assigned to agents
- On creation: tool's `agent_id` field + tool `_id` added to `agent.tool_ids`
- On deletion: `tool_prompt` regenerated for the agent

### How built-in tools are executed
In `backend/chat/graph.py:_execute_tool()`:
1. **search_schema** — Detected by `_is_search_schema` flag → routes to `ai/rag/search_schema_tool.py:execute_search_schema()`
2. **Named handlers** — Looks for a static method on `ai.tools.tools.Tools` class by name (e.g., `search_internet`)
3. **Default (query_db)** — Falls back to `Tools.query_db()` which decrypts the connection string and runs a read-only query

### How tool type/routing is implemented
Tool type (`db_query`, `search_internet`) is on the registry entry. At runtime, the tool name (slugified) is matched against:
- The `Tools` class static methods
- `tool_map` dict built from stamped tool docs
- MCP tool callables

### Code-Level Tool Registry (`_TOOL_REGISTRY`)
Separate from the MongoDB-backed tool registry, there is a **code-level tool registration mechanism** in `ai/agents/sub_agent.py`:
- `_TOOL_REGISTRY: Dict[str, callable] = {}` (line 369) — maps handler name strings to Python callables
- `@register_tool(handler_name)` decorator (line 372) — registers functions into the dict
- When `SubAgent.load_tools()` processes MongoDB tool documents, it looks up each tool's `handler` field in this registry to find the callable
- **Currently empty in production** — no tools are registered via this decorator. The backend chat path uses a different mechanism (`_execute_tool()` in `backend/chat/graph.py`) that routes by tool name to static methods on `ai.tools.tools.Tools`
- **Integration relevance:** This registry pattern could be extended to register integration tool handlers (e.g., `@register_tool("slack_send_message")`)

### Known bugs or limitations
1. **Tool schema not used at runtime** — `tool_schema` field on registry entries exists but is not used to validate tool inputs or generate parameters; all tools get a generic `{"query": "string"}` parameter schema
2. **No tool versioning** — Registry entry updates don't propagate to existing org tools
3. **Agent-tool coupling** — A tool is created for a specific agent; there's no way to share a tool across agents without creating duplicates
4. **Two separate tool execution paths** — The backend chat path (`_execute_tool()` in `backend/chat/graph.py`) and the standalone path (`_TOOL_REGISTRY` in `ai/agents/sub_agent.py`) use different mechanisms to resolve and execute tools. Adding a new tool type requires updating both paths.

---

## 10. MCP Server Integration

### MCP server model
- **File:** `backend/mcp_server/models.py`
- `McpServer` — Instance bound to an org + agent, stores connection info and cached tools
- `McpRegistryEntry` — Global catalog template with placeholders

### MCP server registration
Two flows:
- **Flow A (catalog):** `registry_key` → resolve template from `mcp_server_registry`, fill `<PLACEHOLDER>` tokens
- **Flow B (custom):** Raw `connection_string` provided directly

### MCP server discovery
`probe_connection_string()` → `parse_connection_string()` → `list_mcp_tools()`:
1. Parse connection string to determine transport
2. Open `_MCPSessionThread` (dedicated daemon thread with its own event loop)
3. Connect via appropriate MCP client (stdio/streamable_http/sse/websocket)
4. Initialize session, list tools
5. Cache tool specs (`{name, description, input_schema}`) on the server document

### OAuth flow
1. **Start:** `POST /mcp-servers/oauth/start` → discovers OAuth endpoints via MCP spec, performs Dynamic Client Registration, generates PKCE + state, stores flow in `mcp_oauth_flows`
2. **Callback:** `GET /mcp-servers/oauth/callback` → exchanges code for tokens, creates `mcp_servers` doc with `auth_type=oauth`, stores encrypted tokens in `mcp_oauth_tokens`, discovers tools
3. **Runtime:** `resolve_oauth_headers()` reads tokens, refreshes if near expiry, returns `Authorization: Bearer` header

### OAuth token storage
- **Class:** `MongoTokenStorage` in `backend/mcp_server/services.py`
- Uses **sync PyMongo** (not motor) because MCP sessions run on dedicated threads
- Tokens and client_info **encrypted at rest** via `backend.core.encryption`
- Token refresh via `_refresh_sync()` — exchanges refresh_token for new access_token

### Runtime execution
- `connect_mcp_server()` → Opens a persistent `_MCPSessionThread`, returns LiteLLM tool specs + sync callables
- `build_mcp_tools()` → For a list of server docs, creates lazy callables that open sessions on first use
- `call_mcp_tool()` → Reuses process-level cached sessions (`_SESSIONS` dict)

### Tool discovery
- `list_mcp_tools()` → Connect, `session.list_tools()`, disconnect
- Tools cached as `[{name, description, input_schema}]` on the server document
- Re-discover via `POST /mcp-servers/{id}/discover`

### Tool binding to sub-agents
- In `backend/chat/services.py:load_agent_mcp()` → reads `agent.mcp_server_ids`, loads active server docs, calls `build_mcp_tools()`
- Returns `(mcp_tools, mcp_callables)` which are passed to `AgentRuntime`
- In `_build_agent_node()`: MCP tools are merged with DB tools into a single `tool_specs` list; MCP callables keyed by raw tool name in `mcp_callables` dict

### Supported transports
1. **stdio** — Local process (npx, uvx, python, node, etc.)
2. **streamable_http** — Current MCP remote standard (http/https URLs)
3. **sse** — Legacy HTTP+SSE (URLs ending in `/sse`)
4. **websocket** — WebSocket (ws/wss URLs)

### Risks and limitations
1. **Session lifecycle** — `_MCPSessionThread` runs on daemon threads; no graceful cleanup on shutdown
2. **Process-level cache** — `_SESSIONS` dict is not bounded or evicted; long-running servers accumulate sessions
3. **No health monitoring** — Cached sessions may become stale without detection
4. **Blocking calls** — MCP tool execution blocks the daemon thread; timeouts may strand threads
5. **OAuth token refresh race** — No locking on `_refresh_sync()` under concurrent requests

---

## 11. Chat and Direct Agent Flows

### Supervisor chat path
1. `POST /chat/session` → `chat.services.create_session()`:
   - Loads all org agents via `_load_org_agents()`
   - Builds LangGraph (supervisor + sub-agents) via `get_or_build_graph()`
   - Creates `chat_sessions` document with UUID thread_id
   - Returns `SessionPublic` with available agents

2. `POST /chat/message` → `chat.services.send_message()`:
   - Validates session exists
   - Reloads org agents (fresh on every message)
   - Kicks off title generation concurrently (first message only)
   - Reconstructs full conversation history from MongoDB
   - Invokes LangGraph with history + new message
   - Extracts final AI response
   - Records turn via `SubAgentMemory.record_turn()`
   - Triggers compression if threshold reached
   - Returns response with session name

### Direct agent chat path
`POST /chat` → `direct_agent.services.direct_chat()`:
- Loads single agent by `agent_id` + `org_id`
- Creates or reuses session (`session_id` parameter)
- Builds single-agent graph via `get_or_build_single_agent_graph()`
- Same memory/compression flow as supervisor path

### Session creation
- UUID-based `thread_id`
- Stored in `chat_sessions` collection
- Supervisor sessions include `lg_thread_id` for LangGraph internal thread

### Message persistence
- **NOT stored per-message** in a `messages` collection
- Instead stored as conversation turns in `conversation_logs` collection via `ConversationStore`
- Each turn: `{human_message, agent_message, timestamp, tool_called, tool_name}`

### Conversation history
- Reconstructed on every message from `conversation_logs`:
  - Summaries → `SystemMessage`
  - Turns → `HumanMessage` + `AIMessage` pairs
  - Ordered by timestamp

### Summary/compression logic
- **File:** `backend/memory/sub_agent_memory.py`
- **Threshold:** `TURNS_BEFORE_COMPRESS = 20` (minimum before first compression)
- **Interval:** `COMPRESS_INTERVAL = 10` (compress when `total_messages % 10 == 0`)
- **Keep:** `KEEP_AFTER_COMPRESS = 10` (most recent turns kept after compression)
- **Process:** Invokes `Summarizer_Agent` to generate a summary, replaces old conversations with `[summary, ...recent_turns]`

### Difference between backend/chat and ai/ LangGraph flow
- **`backend/chat/graph.py`** — Dynamically builds a LangGraph at runtime from MongoDB agent/tool documents. Used by the FastAPI chat endpoints. Shares tool execution and memory with the backend.
- **`ai/graph/`** — Standalone LangGraph entry point (`ai/graph/studio.py:graph`) for LangGraph Studio / `langgraph dev`. Uses `ai/agents/main_agent.py` and `ai/agents/sub_agent.py` which load agents directly from MongoDB. Primarily for development/testing.
- Both paths share: `ai/tools/tools.py`, `ai/rag/`, `ai/tracing/`, `ai/memory/`

---

## 12. AI / LangGraph Runtime

### Two Coexisting Runtime Paths

The codebase has **two distinct LangGraph runtime paths** that share some common modules:

| Path | Entry Point | Used By | Graph Builder |
|---|---|---|---|
| **Backend (FastAPI)** | `backend/chat/graph.py:build_graph()` / `build_single_agent_graph()` | FastAPI chat endpoints (`/chat/message`, `POST /chat`) | Dynamic graph from MongoDB agent/tool docs at request time |
| **Standalone (Studio)** | `ai/graph/studio.py:graph` | LangGraph Studio / `langgraph dev` | Pre-built at import time from MongoDB |

**Shared modules between both paths:** `ai/tools/tools.py`, `ai/rag/`, `ai/tracing/`, `ai/agents/summarizer/`

**Separate modules:**
- Backend path uses `backend/chat/graph.py` for graph construction, `backend/memory/` for persistence
- Standalone path uses `ai/agents/main_agent.py` + `ai/agents/sub_agent.py` for agent logic, `ai/memory/` for persistence, `ai/graph/` for graph wiring

### Backend Path: FastAPI-Embedded LangGraph

#### Supervisor node
- `_build_supervisor_node()` in `backend/chat/graph.py` (line 325):
  - System prompt lists available agents with truncated descriptions
  - Uses routing tools (one per agent): `delegate_to_{slug}` functions
  - Two states: routing (first pass) and synthesis (after agent responds)

#### Sub-agent node
- `_build_agent_node()` in `backend/chat/graph.py` (line 192):
  - Each agent gets its own node with system prompt + tools
  - Tool-use loop: up to `MAX_TOOL_STEPS = 5` iterations
  - After tools exhaust, forces a final synthesis answer

#### Tool binding
- DB tools: slugified name → `_execute_tool()` which routes to `Tools.query_db()`, `Tools.search_internet()`, or `execute_search_schema()`
- MCP tools: raw name → lazy MCP session callable via `run_in_threadpool()`

### Standalone Path: `ai/graph/` LangGraph

#### Graph State (`ai/graph/state.py`)
- **Class:** `AgentState(TypedDict)` — the full state flowing through the graph
- **Fields:**

| Field | Type | Purpose |
|---|---|---|
| `user_query` | `str` | Current user message |
| `agent_summaries` | `list` | `[{_id, name, description, guardrails?}, ...]` |
| `user_id` | `str` | Current user |
| `organization_id` | `str` | Tenant scope |
| `routed_to` | `Optional[str]` | Agent ID chosen by router, `None` → direct answer |
| `excluded` | `list` | Agent IDs ruled out this turn (out-of-scope re-routing) |
| `reply` | `str` | Reply ready to show the user |
| `answered` | `bool` | `True` when reply is ready for interrupt |
| `last_agent_name` | `str` | Display name of agent that produced the reply |
| `last_agent_id` | `Optional[str]` | Agent ID, `None` when MainAgent answered directly |
| `messages` | `list` | Sliding window of turn dicts `{role, agent_name, user_query, content}` |
| `interaction_count` | `int` | Incremented each completed turn; drives summarizer trigger |
| `memory_summary` | `str` | Compressed summary produced by `Summarizer_Agent` |

#### Graph Topology (`ai/graph/graph.py`)
- **Builder:** `build_graph(db, memory, model, main_agent, checkpointer=None)`
- **6 Nodes:**

| Node | Purpose | Function |
|---|---|---|
| `router` | Opens Langfuse trace, calls `MainAgent._route()` to decide routing | `router_node` |
| `sub_agent` | Scope check + invoke SubAgent (no interrupt here) | `sub_agent_node` |
| `direct_answer` | Delegates to `MainAgent._answer_directly()` | `direct_answer_node` |
| `human_interrupt` | Closes Langfuse trace, records turn in sliding window, calls `interrupt()` to yield control | `human_interrupt_node` |
| `long_term_memory` | Writes completed turn to MongoDB via `MongoMemoryStore` (off critical path) | `long_term_memory_node` |
| `summarizer` | Compresses message window when threshold met via `Summarizer_Agent` | `summarizer.as_node()` |
| `dispatch` | No-op fan-in join — waits for parallel branches then applies routing decision | `dispatch_node` |

- **Edge flow:**
  1. `START → router → dispatch` — first turn goes to router, then fan-in
  2. `dispatch → sub_agent` (if `routed_to`) or `dispatch → direct_answer` (if null)
  3. `sub_agent → human_interrupt` (if answered) or `sub_agent → router` (if out-of-scope, re-route)
  4. `direct_answer → human_interrupt`
  5. `human_interrupt` **fans out to 3 parallel branches:** `router`, `long_term_memory`, `summarizer`
  6. All three converge at `dispatch` before the next agent call

- **Checkpointer:** When running via FastAPI, a `MemorySaver` is passed for multi-turn persistence. For LangGraph Studio, left as `None` (platform manages persistence).

#### Scope Check (`ai/graph/nodes.py`)
- `_is_in_scope(query, agent_doc, model, history)` — asks LLM "is this message in-scope for this agent?"
- Short follow-ups like "yes", "ok", "correct" are always considered in-scope
- Returns `True` on check failure (fail-open)
- Used in `sub_agent_node` before invoking the agent; if out-of-scope, re-routes by adding agent to `excluded` list

#### Studio Entry Point (`ai/graph/studio.py`)
- Loads agent summaries from MongoDB at import time via `_load_agent_summaries()`
- Creates `LocalMemory`, `MainAgent`, and calls `build_graph()`
- Configurable via `STUDIO_USER_ID` / `STUDIO_ORG_ID` env vars
- Uses `sync_db` (PyMongo) for agent loading at startup

### MainAgent (`ai/agents/main_agent.py`)

**Class:** `MainAgent` — Orchestrator that answers generic queries directly or routes specialized ones to SubAgents.

**Constructor parameters:** `agent_summaries`, `db` (pymongo), `model`, `memory` (LocalMemory), `user_id`, `organization_id`, `session_id`, `tracing_context`

**Key methods:**

| Method | Purpose |
|---|---|
| `invoke(query)` | Public entry: route → delegate or direct-answer, stores trace |
| `_route(query, excluded, history, memory_summary)` | LLM-based routing: system prompt lists agents, responds with `{"agent_id": "<id or null>", "reason": "..."}` as JSON. Validates returned ID against known agents. Returns `None` for direct answer. |
| `_delegate(query, agent_id)` | Lazy-creates SubAgent, calls `sub.load_agent()`, `sub.load_tools()`, `sub.load_mcp_servers()`, caches in `_sub_agents` dict, invokes |
| `_answer_directly(query, memory_summary)` | Generic LLM completion with conversation history, stores result in memory |
| `_build_history()` | Reconstructs `[user, assistant]` message pairs from LocalMemory |

**Routing prompt features:**
- Lists all available agents with `id`, `name`, `description`, and `guardrails`
- Last 3 memory entries passed as context for follow-up handling
- Excluded agent IDs filtered out (for re-routing after scope failure)
- Memory summary injected when available
- Responds with JSON only — `{"agent_id": "<id or null>", "reason": "<one sentence>"}`

### SubAgent (`ai/agents/sub_agent.py`)

**Class:** `SubAgent` — Loads an agent from MongoDB and invokes it with tools.

**Constructor parameters:** `agent_id`, `db` (pymongo), `model`, `memory` (LocalMemory), `tracer` (AgentTracer), `mongo_store`

**Key methods:**

| Method | Purpose |
|---|---|
| `load_agent()` | Fetches agent document from MongoDB (filters `is_active != False`, `is_deleted != True`) |
| `load_tools()` | Reads `tool_ids` from agent doc, fetches tool docs, resolves handlers from `_TOOL_REGISTRY`, builds LiteLLM tool specs + callables |
| `load_mcp_servers()` | Reads `mcp_server_ids`, fetches active server docs, calls `build_mcp_tools()` from `backend.mcp_server.services` |
| `invoke(query, user_id, organization_id, memory_summary)` | Builds system prompt, history, runs LLM with tool loop, stores result in memory |
| `_run(system, messages)` | LLM completion loop: calls `litellm.completion`, handles `tool_calls` finish_reason, invokes tool callables, appends results, loops until final text response |
| `_build_system_prompt(memory_summary)` | Assembles: agent prompt + guardrails + tool instructions + MCP tool note + memory summary |

**Tool execution loop in `_run()`:**
- Iterates while `finish_reason == "tool_calls"`
- For each tool call: resolves callable from `_tool_callables` dict, invokes `fn(input)`, appends `{role: "tool", tool_call_id, content}` to messages
- Each tool call wrapped in a Langfuse span (`tool:{tool_name}`)
- Returns `(output, last_tool_name, last_tool_output)`

**`_TOOL_REGISTRY` — Code-level tool registration:**
- **File:** `ai/agents/sub_agent.py` (line 369)
- `_TOOL_REGISTRY: Dict[str, callable] = {}` — maps handler name strings to callables
- `@register_tool(handler_name)` decorator adds functions to the registry
- This is separate from the MongoDB-backed `tool_registry` collection — it maps the `handler` field stored on MongoDB tool documents to actual Python functions
- Currently empty in production (`_TOOL_REGISTRY = {}`) — tool execution in the standalone path relies on MongoDB tool docs whose `handler` field must match a registered key

### LLM Call Retry Logic (`ai/agents/sub_agent.py`)

**Function:** `_completion_with_retry(lf_metadata, **kwargs)`
- Wraps `litellm.completion()` with exponential-backoff retry on transient errors
- **Retryable errors:** `RateLimitError`, `ServiceUnavailableError`, `Timeout`
- **Non-retryable (raised immediately):** `AuthenticationError`, `BadRequestError`
- **Max retries:** 3
- **Backoff:** 2 seconds, doubling each attempt (2s → 4s → 8s)
- Merges `lf_metadata` into kwargs so Langfuse links the call to the active trace/span

### Summarizer Agent (`ai/agents/summarizer/`)

**Class:** `Summarizer_Agent` in `ai/agents/summarizer/agent.py`

**Purpose:** Sliding-window compression of conversation history.

**Algorithm:**
1. Triggered when `len(messages) > 10`
2. Splits messages into `to_summarize = messages[:-10]` and `recent = messages[-10:]`
3. Formats `to_summarize` including any `[Previous summary]` blocks from earlier compression
4. Calls LLM with summarizer system prompt to generate a compressed summary (max 300 words)
5. Returns `{messages: [summary_message] + recent, memory_summary: summary_text}`

**Summarizer System Prompt** (`ai/agents/summarizer/prompt.py`):
- Maximum 300 words
- Factual only — no inference
- Incorporates previous summary content faithfully
- Preserves key decisions, data points, outcomes
- Third-person narrative

**Summarizer Tools** (`ai/agents/summarizer/tools.py`):
- `Summarizer_Tools.as_list()` returns empty list — no tools needed

### Memory Systems (Two Separate Implementations)

#### System 1: `ai/memory/` — Used by Standalone LangGraph Path

| Component | File | Purpose |
|---|---|---|
| `LocalMemory` | `ai/memory/memory.py` | In-process list-based memory. Methods: `append_memory()`, `get_memory()`, `get_memory_by_user()`, `get_memory_by_agent()`, `get_memory_by_session(user_id, agent_id)`, `clear()`. Traced via optional `AgentTracer`. |
| `MemorySchema` | `ai/memory/memory_schema.py` | Pydantic model for memory entries: `user_id`, `organization_id`, `agent_id`, `agent_name`, `user_query`, `agents_output`, `tool_called` (bool), `tool_name`, `tool_output`, `timestamp` (UTC) |
| `MongoMemoryStore` | `ai/memory/mongo_store.py` | Persistent MongoDB-backed store. Collection: `conversation_logs`. Methods: `write(entry)`, `get_by_user(user_id, limit=50)`, `get_by_session(user_id, org_id, limit=20)`. Creates compound index on `(user_id, organization_id, timestamp)`. Used by `long_term_memory_node` in the standalone graph. |

**Flow:** `LocalMemory` stores turns in-process during a session. `MongoMemoryStore` persists turns to MongoDB for cross-session retrieval. Both run in parallel — `LocalMemory` for immediate context, `MongoMemoryStore` for durability.

**Memory dump debugging:** `_dump_agent_memory()` writes memory entries to `memory_dumps/` directory as JSON files for debugging (e.g., `memory_dumps/memory_agent_name_pre_invoke.json`).

#### System 2: `backend/memory/` — Used by Backend FastAPI Path

| Component | File | Purpose |
|---|---|---|
| `ConversationStore` | `backend/memory/conversation_store.py` | Async MongoDB CRUD for conversation logs. Stores `TurnEntry` and `SummaryEntry` objects in a document per `(session_id, user_id, agent_id)`. |
| `SubAgentMemory` | `backend/memory/sub_agent_memory.py` | Per-agent memory with fetch, append, compress, seed. Threshold-based compression (20 turns → compress, keep last 10). Uses `Summarizer_Agent` for compression. |

**Key difference:** System 1 uses a flat list per user+agent pair with separate `MongoMemoryStore` for persistence. System 2 uses structured documents with `TurnEntry`/`SummaryEntry` arrays and threshold-based compression built into the memory layer.

### Built-in Tool Implementations (`ai/tools/tools.py`)

#### `build_fetch_schema_tool(org_id, db_conn_ids)`
- Builds a synthetic tool doc for `fetch_schema`
- Shaped like per-agent tool docs from `tools_collection` so the runtime handles it without special-casing
- Injected automatically for agents with DB tools
- Carries `_is_search_schema` flag to route to RAG execution path

#### `Tools.query_db(tool_doc, args)` (async static method)
- Executes read-only queries against organization databases
- **Org-scoped connection resolution:** Always filters `db_connections_collection` by `organization_id` (tenant isolation)
- Supports explicit `db_conn_id` or falls back to first connection for the org
- Decrypts connection string via `backend.core.encryption.decrypt()`
- Runs query via `backend.core.query_runner.run_query()` in a threadpool
- **30-second timeout** via `asyncio.wait_for()`
- Logs every execution to `query_audit_logs` via `log_query_execution()` (async, fire-and-forget)

#### `Tools.search_internet(input)` (static method)
- Searches the internet using **DuckDuckGo** (`ddgs` library)
- Input: `{"query": "...", "max_results": 5}` (default 5 results)
- Returns formatted results with title, URL, and snippet
- Error-tolerant: catches all exceptions and returns error string

### LiteLLM Usage
- **Model-agnostic:** All LLM calls go through `litellm.completion()` (sync, standalone path), `litellm.acompletion()` (async, backend path), and `litellm.aembedding()` (for RAG)
- **Default model:** `gpt-5.4-mini` (configurable via `DEFAULT_MODEL`)
- **Title model:** `gpt-5.4-nano` (cheap model for session titles and prompt generation)
- **Tracing:** LiteLLM callbacks configured for Langfuse via `litellm.success_callback = ["langfuse"]`
- **Model enum:** `ai/models.py:Model` — `GPT_4_1 = "gpt-4.1"`, `GPT_5_4_MINI = "gpt-5.4-mini"`, `GPT_5_4_NANO = "gpt-5.4-nano"`

### Qdrant Usage
- **Collection:** `schema_tables` (1536-dim vectors, cosine distance)
- **Multi-tenant:** `org_id` as tenant key with HNSW payload indexing
- **Used for:** Semantic search over DB schema (tables/columns) so agents find correct table names

### RAG / Schema Search

#### Schema Indexing (`ai/rag/schema_indexer.py`)
- Embeds table schemas into Qdrant on DB connection creation/update
- Process: extract tables → generate LLM descriptions (batched) → embed with `text-embedding-3-small` → upsert to Qdrant
- Isolation: points carry `org_id` and `db_conn_id` payload fields for tenant filtering

#### Schema Retrieval (`ai/rag/schema_retriever.py`)
- **Function:** `get_relevant_schema(query, db_conn_ids, org_id, top_k=20)`
- Embeds the query via `litellm.aembedding()` with `settings.EMBEDDING_MODEL`
- Searches Qdrant with `Filter(must=[org_id match, db_conn_id in list])`
- Returns formatted schema: table name, purpose, columns (up to 30), primary keys, foreign keys
- Falls back gracefully if Qdrant is unavailable

#### Search Schema Tool (`ai/rag/search_schema_tool.py`)
- Synthetic tool injected at runtime for agents with `db_conn_ids`
- Calls `get_relevant_schema()` and returns formatted result

### Langfuse Tracing

#### Setup (`ai/tracing/__init__.py`)
- `setup_tracing()` — activates `litellm.success_callback = ["langfuse"]`
- Config: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`

#### AgentTracer (`ai/tracing/tracer.py`)
- Wraps Langfuse SDK with org/agent tagging
- `start_trace(name, input)` / `end_trace(output)` — one trace per user turn
- `span(name, input, metadata)` — nested spans for routing, delegation, tool calls
- `tag_agent(agent_id, agent_name)` — tags trace for per-agent filtering
- `litellm_metadata()` — returns dict that links LiteLLM calls to active trace/span
- `event(name, metadata)` — records discrete events (memory reads/writes)

#### Tag Helpers (`ai/tracing/tags.py`)
- `org_tag(org_id)` → `"org:{org_id}"`
- `agent_tag(agent_name)` → `"agent:{slugified_name}"`

#### TracingContext (`ai/tracing/context.py`)
- DTO carrying `org_id`, `user_id`, `session_id` from JWT boundary to AI layer

### How Backend Connects to AI Runtime
Backend directly imports and uses AI modules:
- `from ai.tools.tools import Tools` (in `backend/chat/graph.py`)
- `from ai.rag.search_schema_tool import ...` (in `backend/chat/graph.py`)
- `from ai.tracing.tracer import AgentTracer` (in `backend/chat/services.py`)
- `from ai.agents.summarizer.agent import Summarizer_Agent` (in `backend/memory/sub_agent_memory.py`)
- `from backend.mcp_server.services import build_mcp_tools` (in `ai/agents/sub_agent.py` — reverse dependency from AI to backend)

---

## 13. Database Connections and RAG

### DB connection model
- **Collection:** `db_connections`
- **Key fields:** `organization_id`, `connection_string` (encrypted), `schema` (or `schema_gridfs_id`), `schema_indexed`, `schema_table_count`

### Encryption of connection strings
- **File:** `backend/core/encryption.py`
- **Algorithm:** Fernet (AES-128-CBC + HMAC-SHA256)
- **Key source:** `ENCRYPTION_KEY` env var, or derived from `JWT_SECRET_KEY` via SHA-256
- **Functions:** `encrypt(plaintext) -> str`, `decrypt(token) -> str`, `mask_connection_string(plaintext) -> str`
- Connection strings are encrypted before storage and decrypted only when needed for query execution

### Schema introspection
- **File:** `backend/core/db_introspect.py`
- **Function:** `fetch_schema(connection_string) -> dict`
- Runs synchronously (called via `run_in_threadpool`)
- Supports: PostgreSQL, MySQL, SQLite (via SQLAlchemy `inspect()`), MongoDB (via PyMongo sampling), Supabase (auto-detected)
- Returns: `{kind: "sql"|"mongo", tables/databases: {...}, dialect, enums, views}`

### Supported databases
1. PostgreSQL (+ Supabase)
2. MySQL
3. SQLite
4. SQL Server (via pyodbc)
5. MongoDB

### GridFS usage
- **File:** `backend/dbconnection/services.py`
- **Constants file:** `backend/dbconnection/constants.py`
- **Bucket:** `SCHEMA_GRIDFS_BUCKET = "db_schemas"`
- **Inline size limit:** `SCHEMA_INLINE_MAX_BYTES = 15 * 1024 * 1024` (15 MB) — schemas larger than this are stored in GridFS instead of inline in the document (stays under MongoDB's 16 MB document limit with margin)
- On read, transparently loads from GridFS when `schema_gridfs_id` is set on the document

### Qdrant indexing
- **File:** `ai/rag/schema_indexer.py`
- **Trigger:** Background task on DB connection create/update/description-save
- **Process:** Extract tables → generate LLM descriptions (batched) → embed with `text-embedding-3-small` → upsert to Qdrant
- **Isolation:** Points filtered by `org_id` (tenant index) and `db_conn_id`

### search_schema tool
- **File:** `ai/rag/search_schema_tool.py`
- Auto-injected at runtime for agents that have `db_conn_ids`
- Calls `get_relevant_schema()` which does vector search in Qdrant → returns matching table schemas

### How agents query databases
1. Agent calls `search_schema` tool → gets relevant table/column names
2. Agent calls `query_db` tool with a SQL/MongoDB query
3. `Tools.query_db()` decrypts connection string, runs read-only query via `backend/core/query_runner.py`
4. Query audit logged to `query_audit_logs` collection
5. Results capped at 100 rows, 6000 chars
6. Write queries blocked by regex pattern matching

---

## 14. Security Review

### JWT secret handling
- **Default:** `"change-me-in-production"` — **MUST be changed in production**
- **Algorithm:** HS256
- **No refresh tokens** — single access token with 24h expiry
- **No token blacklist** — tokens valid until expiry

### Fernet encryption
- **Key:** `ENCRYPTION_KEY` env var (preferred) or derived from `JWT_SECRET_KEY` via SHA-256
- **Used for:** DB connection strings, MCP OAuth tokens, OAuth client info, PKCE code verifiers
- **Risk:** If `ENCRYPTION_KEY` is not set, encryption key is derived from JWT secret — a single secret compromise exposes everything

### Secret storage
- DB connection strings: Fernet-encrypted in MongoDB
- MCP OAuth tokens: Fernet-encrypted in `mcp_oauth_tokens` collection
- MCP OAuth client info: Fernet-encrypted
- Passwords: bcrypt-hashed (not reversible)
- OTPs: bcrypt-hashed

### OAuth security
- PKCE (S256) used for authorization code flow
- State parameter for CSRF protection
- Flow TTL: 900 seconds (configurable)
- Tokens encrypted at rest
- Token refresh implemented with expiry check

### Token handling
- Bearer tokens stored in HTTP headers (not cookies)
- MCP OAuth tokens: `Authorization: Bearer` header resolved at connection time
- Token refresh via `_refresh_sync()` — no mutex, potential race under concurrency

### Rate limiting
- Per-IP, fixed-window, in-memory counter
- Default: 600 requests/60 seconds
- Configurable live from admin panel
- Excluded paths: `/admin`, `/docs`, `/redoc`, `/openapi.json`, `/favicon`
- **Limitation:** In-memory only — does not work across multiple processes/instances

### Quotas
- `max_orgs_per_day`: 10 per user (daily)
- `max_tools_per_org`: 10 per org
- Configurable live from admin panel

### Admin panel exposure
- Accessible at `/admin` — authenticated via user/password against MongoDB
- Uses `SessionMiddleware` with `JWT_SECRET_KEY` as session secret
- No CSRF protection beyond session cookie
- Password field hidden from all views

### Logging of sensitive data
- Connection strings never logged (encrypted values stored)
- Queries logged in audit trail (intentional)
- Stack traces never leaked to clients
- MongoDB errors sanitized before client response

### Multi-tenant access risks
- Minor gap in direct_agent session lookup (see Section 5)
- No row-level security in MongoDB — relies entirely on application-level filtering

### Missing security protections before external integrations
1. **No webhook signature verification infrastructure**
2. **No API key authentication** (only JWT) — external services often use API keys
3. **No IP allowlisting** for incoming webhooks
4. **No CSRF protection** on non-admin routes
5. **No request signing** for outgoing webhook/API calls
6. **No secrets vault integration** (HashiCorp Vault, AWS Secrets Manager)
7. **No audit logging** for admin panel actions
8. **Rate limiting is per-process only** — needs Redis for multi-instance

---

## 15. Observability

### Langfuse integration
- **Setup:** `ai/tracing/__init__.py:setup_tracing()` — activates `litellm.success_callback = ["langfuse"]`
- **Tracer:** `ai/tracing/tracer.py:AgentTracer` — wraps Langfuse SDK with org/agent tagging
- **Config:** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- **Coverage:** All LiteLLM calls are traced; manual spans for chat turns

### Cost tracking
- `GET /traces/stats` → aggregates `totalCost` from Langfuse traces
- Per-agent breakdown: `agent_breakdown` in `TraceStats`
- Batch fetches GENERATION observations to sum input/output tokens

### Token tracking
- `total_input_tokens` and `total_output_tokens` from Langfuse GENERATION observations
- Aggregated per-org and per-agent

### Org-level stats
- Traces filtered by `org:{org_id}` tag
- Cost and token totals across all agents

### Agent-level stats
- Traces filtered by `agent:{agent_name}` tag
- `GET /agents/{id}/stats` and `GET /agents/{id}/traces`

### Tracing Schemas (`backend/tracing/schemas.py`)

| Schema | Purpose | Key Fields |
|---|---|---|
| `ObservationItem` | Individual LLM call or span within a trace | `id`, `trace_id`, `type`, `name`, `start_time`, `end_time`, `input`, `output`, `model`, `usage` (dict), `calculated_total_cost`, `latency`, `parent_observation_id` |
| `TraceListItem` | Summary of a single trace for list views | `id`, `timestamp`, `name`, `session_id`, `user_id`, `metadata`, `tags[]`, `latency`, `total_cost`, `agent_name` |
| `TraceDetail` | Full trace with nested observations | Extends `TraceListItem` + `observations: List[ObservationItem]` |
| `TracesResponse` | Paginated trace list | `items[]`, `total`, `page`, `page_size`, `total_pages` |
| `AgentBreakdown` | Per-agent cost/token summary | `agent_name`, `trace_count`, `total_cost`, `total_tokens` |
| `TraceStats` | Aggregate statistics | `total_traces`, `total_cost`, `total_input_tokens`, `total_output_tokens`, `agent_breakdown[]` |
| `SessionItem` | Langfuse session summary | `id`, `created_at`, `user_id`, `trace_count`, `bookmarked` |
| `SessionsResponse` | Paginated session list | `items[]`, `total`, `page`, `page_size`, `total_pages` |

### Error logging
- Python `logging` module throughout
- Structured log messages with context (thread, agent, tool, etc.)
- Unhandled exceptions caught at app level and logged

### Missing observability for integrations
1. **No webhook event logging** — no collection for incoming/outgoing webhook events
2. **No integration health dashboard** — no monitoring of external service connectivity
3. **No token refresh failure alerting** — OAuth refresh errors only logged, not surfaced
4. **No per-integration cost tracking** — Langfuse traces don't distinguish by integration source
5. **No request/response logging** for external API calls
6. **No latency metrics** for external service calls
7. **No circuit breaker metrics** — no tracking of failures per external service

---

## 16. Integration Readiness Assessment

### Slack

| Aspect | Assessment |
|---|---|
| **Best fit** | MCP server (existing slack MCP servers available) OR native webhook connector |
| **Architecture** | Hybrid: MCP for tool execution (send messages, read channels) + native webhook receiver for real-time events (slash commands, mentions) |
| **Reusable components** | MCP server infrastructure, tool registry, agent binding, OAuth storage |
| **Missing components** | Webhook receiver endpoint, Slack app manifest, event routing, bot token storage, channel-to-org mapping |
| **OAuth requirements** | Slack OAuth 2.0 (bot token + user token). Existing MCP OAuth flow could be adapted but Slack's non-standard flow may need custom implementation |
| **Webhook requirements** | `POST /webhooks/slack` endpoint for Events API, slash commands, interactive components. Slack requires URL verification challenge. |
| **Token storage** | Extend `mcp_oauth_tokens` or create `integration_tokens` collection |
| **Complexity** | **Medium** — existing MCP infra covers tool execution; webhook receiver is new |

### Microsoft Teams

| Aspect | Assessment |
|---|---|
| **Best fit** | Native connector (Teams Bot Framework requires specific request/response format) |
| **Architecture** | New `backend/integrations/teams/` module with Bot Framework SDK adapter |
| **Reusable components** | Agent runtime, tool execution, conversation memory, Fernet encryption |
| **Missing components** | Bot Framework adapter, activity handler, Teams app manifest, proactive messaging, adaptive card support |
| **OAuth requirements** | Azure AD OAuth 2.0 with bot registration |
| **Webhook requirements** | `POST /api/messages` endpoint for Bot Framework activities |
| **Token storage** | New `integration_tokens` collection with Azure AD token format |
| **Complexity** | **High** — Teams Bot Framework has complex activity model, requires Azure registration |

### Jira

| Aspect | Assessment |
|---|---|
| **Best fit** | MCP server (Atlassian MCP servers exist) + optional native webhook receiver |
| **Architecture** | MCP server for tool execution (create issues, query, transition) + webhook receiver for issue events |
| **Reusable components** | Full MCP OAuth flow (already supports remote http MCP servers with OAuth), tool binding, agent binding |
| **Missing components** | Jira-specific MCP server registration in catalog, webhook event handler, issue-to-notification mapping |
| **OAuth requirements** | Atlassian OAuth 2.0 (3LO). **Existing MCP OAuth flow directly applicable** |
| **Webhook requirements** | `POST /webhooks/jira` for issue/comment events |
| **Token storage** | Existing `mcp_oauth_tokens` (MCP path) or new `integration_tokens` |
| **Complexity** | **Low-Medium** — MCP path is well-established; webhook receiver is straightforward |

### ClickUp

| Aspect | Assessment |
|---|---|
| **Best fit** | Native API connector (no major MCP server available) or extend MCP with custom adapter |
| **Architecture** | New `backend/integrations/clickup/` module with REST API client |
| **Reusable components** | Tool registry (register ClickUp actions as tools), agent binding, OAuth storage, Fernet encryption |
| **Missing components** | ClickUp API client, OAuth 2.0 implementation, webhook handler, task model mapping |
| **OAuth requirements** | ClickUp OAuth 2.0 |
| **Webhook requirements** | `POST /webhooks/clickup` for task/space events |
| **Token storage** | New `integration_tokens` collection |
| **Complexity** | **Medium** — clean REST API but needs full connector implementation |

### Gmail

| Aspect | Assessment |
|---|---|
| **Best fit** | Native API connector OR MCP server (Google MCP servers emerging) |
| **Architecture** | New `backend/integrations/gmail/` with Google API client + optional push notifications |
| **Reusable components** | OAuth storage, Fernet encryption, tool registry, agent binding |
| **Missing components** | Google OAuth 2.0 flow, Gmail API client, email parsing, push notification handler (Pub/Sub), email-to-chat routing |
| **OAuth requirements** | Google OAuth 2.0 with restricted scopes (gmail.readonly, gmail.send) |
| **Webhook requirements** | Google Pub/Sub push endpoint for real-time email notifications |
| **Token storage** | New `integration_tokens` with Google refresh token support |
| **Complexity** | **Medium-High** — Google API complexity, scope management, Pub/Sub setup |

### Outlook

| Aspect | Assessment |
|---|---|
| **Best fit** | Native API connector (Microsoft Graph API) |
| **Architecture** | New `backend/integrations/outlook/` with Microsoft Graph client |
| **Reusable components** | OAuth storage, Fernet encryption, tool registry, agent binding |
| **Missing components** | Azure AD OAuth 2.0, Microsoft Graph API client, email model, change notifications (webhooks) |
| **OAuth requirements** | Azure AD OAuth 2.0 with delegated/application permissions |
| **Webhook requirements** | Microsoft Graph change notifications endpoint |
| **Token storage** | New `integration_tokens` |
| **Complexity** | **Medium-High** — similar to Gmail but with Azure AD OAuth complexity |

### SharePoint

| Aspect | Assessment |
|---|---|
| **Best fit** | Native API connector (Microsoft Graph API — same auth as Outlook) |
| **Architecture** | Extend `backend/integrations/microsoft/` to share Azure AD auth with Outlook |
| **Reusable components** | Azure AD OAuth from Outlook integration, tool registry, agent binding |
| **Missing components** | SharePoint-specific Graph API client, document indexing pipeline, RAG integration for documents |
| **OAuth requirements** | Azure AD OAuth 2.0 (shared with Outlook) |
| **Webhook requirements** | Graph change notifications for document changes |
| **Token storage** | Shared with Outlook via Azure AD |
| **Complexity** | **Medium** — if Outlook is built first, SharePoint shares most infrastructure |

### Google Drive

| Aspect | Assessment |
|---|---|
| **Best fit** | Native API connector (shares Google OAuth with Gmail) |
| **Architecture** | Extend `backend/integrations/google/` to share Google OAuth with Gmail |
| **Reusable components** | Google OAuth from Gmail integration, RAG/Qdrant indexing pipeline, tool registry |
| **Missing components** | Drive API client, file indexing pipeline, document parsing (PDF, Docs, Sheets), RAG integration |
| **OAuth requirements** | Google OAuth 2.0 (shared with Gmail, add drive.readonly scope) |
| **Webhook requirements** | Drive push notifications via Pub/Sub |
| **Token storage** | Shared with Gmail |
| **Complexity** | **Medium** — if Gmail is built first, Drive shares auth; document parsing is the main effort |

### OneDrive

| Aspect | Assessment |
|---|---|
| **Best fit** | Native API connector (Microsoft Graph — shares auth with Outlook/SharePoint) |
| **Architecture** | Extend `backend/integrations/microsoft/` module |
| **Reusable components** | Azure AD OAuth (shared), RAG/Qdrant pipeline, tool registry |
| **Missing components** | OneDrive-specific Graph API client, file indexing, document parsing |
| **OAuth requirements** | Azure AD OAuth 2.0 (shared with Outlook/SharePoint) |
| **Webhook requirements** | Graph change notifications |
| **Token storage** | Shared with Outlook/SharePoint |
| **Complexity** | **Low-Medium** — if SharePoint is built first, OneDrive is a subset |

---

## 17. Recommended Backend Connector Architecture

### Create `backend/integrations/` module

```
backend/integrations/
├── __init__.py
├── base.py                    # Abstract IntegrationProvider base class
├── models.py                  # IntegrationConnection, IntegrationToken, WebhookEvent models
├── schemas.py                 # Connection create/update/public, webhook event schemas
├── routes.py                  # Shared webhook router, connection management
├── services.py                # Connection lifecycle, token management
├── oauth.py                   # Generic OAuth 2.0 flow (reuse patterns from MCP OAuth)
├── token_store.py             # Encrypted token storage (extends Fernet pattern)
├── webhook_handler.py         # Webhook signature verification + event dispatch
├── providers/
│   ├── slack/
│   │   ├── provider.py        # SlackProvider(IntegrationProvider)
│   │   ├── oauth.py           # Slack-specific OAuth
│   │   └── tools.py           # Slack actions as agent tools
│   ├── microsoft/             # Shared Azure AD auth
│   │   ├── oauth.py           # Azure AD OAuth 2.0
│   │   ├── teams/
│   │   │   ├── provider.py
│   │   │   └── tools.py
│   │   ├── outlook/
│   │   │   ├── provider.py
│   │   │   └── tools.py
│   │   ├── sharepoint/
│   │   │   ├── provider.py
│   │   │   └── tools.py
│   │   └── onedrive/
│   │       ├── provider.py
│   │       └── tools.py
│   ├── google/                # Shared Google OAuth
│   │   ├── oauth.py           # Google OAuth 2.0
│   │   ├── gmail/
│   │   │   ├── provider.py
│   │   │   └── tools.py
│   │   └── drive/
│   │       ├── provider.py
│   │       └── tools.py
│   ├── atlassian/
│   │   ├── oauth.py           # Atlassian OAuth 2.0
│   │   └── jira/
│   │       ├── provider.py
│   │       └── tools.py
│   └── clickup/
│       ├── provider.py
│       ├── oauth.py
│       └── tools.py
```

### Extend tool registry
- Add new tool types: `slack_action`, `jira_action`, `gmail_action`, etc.
- Each integration registers its actions as tool registry entries
- Org tools reference these entries, binding actions to agents

### Whether to extend MCP
- **Use MCP where MCP servers already exist** (Jira via Atlassian MCP, Slack via existing MCP servers)
- **Use native connectors where MCP is insufficient** (Teams Bot Framework, Gmail push notifications, webhook receivers)
- **Hybrid approach recommended:** MCP for tool execution, native connectors for event reception

### How to store OAuth connections
New `integration_connections` collection:

```
{
  _id: ObjectId,
  organization_id: string,           // tenant scope
  provider: string,                   // "slack" | "teams" | "jira" | etc.
  connection_name: string,           // user-friendly label
  status: string,                     // "active" | "expired" | "error"
  oauth_token_id: string,            // reference to integration_tokens
  scopes: string[],                   // granted OAuth scopes
  metadata: dict,                     // provider-specific (workspace_id, team_id, etc.)
  created_by: string,                 // user ID
  created_at: datetime,
  updated_at: datetime,
  is_deleted: bool
}
```

### How to encrypt tokens
- Reuse existing `backend/core/encryption.py` Fernet encrypt/decrypt
- Store in new `integration_tokens` collection following `mcp_oauth_tokens` pattern
- Fields: `connection_id`, `access_token` (encrypted), `refresh_token` (encrypted), `expires_at`, `token_endpoint`, `updated_at`

### How to assign integrations to orgs/users/agents
- `integration_connections` scoped by `organization_id`
- Agent binding: add `integration_ids: List[str]` field to agent model (parallel to `mcp_server_ids`)
- User-level overrides: optional `user_id` on connection for per-user OAuth tokens

### How webhook routes should work
```python
# backend/integrations/routes.py
webhook_router = APIRouter(prefix="/webhooks")

@webhook_router.post("/slack")     # Slack Events API
@webhook_router.post("/jira")     # Jira webhooks
@webhook_router.post("/clickup")  # ClickUp webhooks
# etc.
```
- No JWT auth (external services can't authenticate as users)
- Signature verification per provider (Slack signing secret, Jira JWT, etc.)
- Event dispatch to appropriate handler based on event type
- Events stored in `webhook_events` collection for audit/replay

### How external actions become tools for agents
1. Integration provider defines available actions (e.g., Slack: send_message, list_channels)
2. Actions registered in `tool_registry` with type = provider name
3. Org creates tool instances linking registry entries to agents
4. At runtime, `_execute_tool()` detects integration tool type and routes to provider's execute method
5. Provider resolves OAuth tokens and makes the external API call

### How background jobs/queues should work
- **Immediate need:** Token refresh scheduler, webhook retry queue
- **Recommended:** Add `arq` (Redis-backed async task queue) or `celery`
- **New dependency:** Redis for job queue + distributed rate limiting
- **Jobs:** Token refresh (periodic), webhook delivery retry (on failure), document indexing (for Drive/SharePoint/OneDrive)

### How audit logs should work
New `integration_audit_logs` collection:
```
{
  organization_id: string,
  provider: string,
  action: string,              // "oauth_start" | "oauth_complete" | "webhook_received" | "tool_executed" | "token_refreshed"
  connection_id: string,
  agent_id: string?,
  user_id: string?,
  input: dict?,                // sanitized request
  output: dict?,               // sanitized response
  error: string?,
  duration_ms: int,
  timestamp: datetime
}
```

---

## 18. Backend Implementation Tasks

### New Models

| Model | Collection | Fields | File |
|---|---|---|---|
| `IntegrationConnection` | `integration_connections` | organization_id, provider, connection_name, status, oauth_token_id, scopes, metadata, created_by, timestamps, is_deleted | `backend/integrations/models.py` |
| `IntegrationToken` | `integration_tokens` | connection_id, access_token (encrypted), refresh_token (encrypted), expires_at, token_endpoint, scopes, updated_at | `backend/integrations/models.py` |
| `WebhookEvent` | `webhook_events` | organization_id, provider, event_type, payload_hash, status, retry_count, timestamps | `backend/integrations/models.py` |
| `IntegrationAuditLog` | `integration_audit_logs` | organization_id, provider, action, connection_id, agent_id, input, output, error, duration_ms, timestamp | `backend/integrations/models.py` |

### New Schemas

| Schema | Purpose | File |
|---|---|---|
| `IntegrationConnectionCreate` | Create connection request | `backend/integrations/schemas.py` |
| `IntegrationConnectionPublic` | Connection response (tokens hidden) | `backend/integrations/schemas.py` |
| `IntegrationOAuthStartRequest` | Start OAuth for a provider | `backend/integrations/schemas.py` |
| `IntegrationOAuthStartResponse` | Returns authorization URL | `backend/integrations/schemas.py` |
| `WebhookEventPublic` | Webhook event response | `backend/integrations/schemas.py` |
| Per-provider action schemas | E.g., `SlackSendMessageInput`, `JiraCreateIssueInput` | `backend/integrations/providers/*/tools.py` |

### New Routes

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/integrations/providers` | List available providers | JWT |
| POST | `/integrations/connections` | Create connection (start OAuth) | JWT |
| GET | `/integrations/connections` | List org connections | JWT |
| GET | `/integrations/connections/{id}` | Get connection | JWT |
| DELETE | `/integrations/connections/{id}` | Disconnect | JWT |
| POST | `/integrations/connections/{id}/refresh` | Force token refresh | JWT |
| POST | `/webhooks/slack` | Slack event receiver | Signature |
| POST | `/webhooks/jira` | Jira event receiver | Signature |
| POST | `/webhooks/clickup` | ClickUp event receiver | Signature |
| POST | `/api/messages` | Teams Bot Framework | Azure AD |
| POST | `/webhooks/google` | Google Pub/Sub | Signature |
| POST | `/webhooks/microsoft` | Graph notifications | Signature |

### New Services

| Service | Purpose | File |
|---|---|---|
| `IntegrationConnectionService` | CRUD for connections, OAuth lifecycle | `backend/integrations/services.py` |
| `IntegrationTokenStore` | Encrypted token storage + refresh | `backend/integrations/token_store.py` |
| `GenericOAuthService` | Reusable OAuth 2.0 flow | `backend/integrations/oauth.py` |
| `WebhookDispatcher` | Route incoming webhooks to handlers | `backend/integrations/webhook_handler.py` |

### Provider Adapters (per integration)

| Provider | Adapter | Key actions |
|---|---|---|
| Slack | `SlackProvider` | send_message, list_channels, read_messages, search |
| Teams | `TeamsProvider` | send_message, list_teams/channels, adaptive cards |
| Jira | `JiraProvider` | create_issue, search_issues, transition, add_comment |
| ClickUp | `ClickUpProvider` | create_task, list_tasks, update_task, add_comment |
| Gmail | `GmailProvider` | send_email, search_emails, read_email, draft |
| Outlook | `OutlookProvider` | send_email, search_emails, read_email, calendar |
| SharePoint | `SharePointProvider` | list_files, download, upload, search |
| Google Drive | `GoogleDriveProvider` | list_files, download, upload, search |
| OneDrive | `OneDriveProvider` | list_files, download, upload, search |

### OAuth Flow Implementation
- Generic OAuth 2.0 service reusing patterns from `backend/mcp_server/services.py`
- Per-provider OAuth configuration (endpoints, scopes, client registration)
- PKCE support where applicable

### Token Refresh
- Background scheduler (arq/celery job) to refresh tokens before expiry
- Manual refresh endpoint for immediate refresh
- Failure alerting via notifications system

### Webhooks
- Per-provider signature verification
- Idempotent event processing (payload_hash dedup)
- Retry queue for failed deliveries
- Event-to-notification mapping

### Tool/Action Registration
- Seed scripts per provider to register actions in tool_registry
- Auto-inject integration tools for agents with linked connections

### Agent Binding
- Add `integration_ids` field to Agent model
- Build integration tools at runtime (parallel to MCP tool building)

### Tests
- Unit tests per provider adapter
- Integration tests with mock OAuth servers
- Webhook signature verification tests
- Token refresh lifecycle tests

### Migration Scripts
- `seed_integration_providers.py` — Register provider metadata
- `seed_integration_tools.py` — Register actions in tool_registry
- `migrate_mcp_to_integration.py` — Optional: migrate existing MCP-based integrations

### Environment Variables

| Variable | Purpose |
|---|---|
| `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET` | Slack OAuth |
| `SLACK_SIGNING_SECRET` | Webhook verification |
| `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` / `AZURE_TENANT_ID` | Microsoft (Teams/Outlook/SharePoint/OneDrive) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google (Gmail/Drive) |
| `JIRA_CLIENT_ID` / `JIRA_CLIENT_SECRET` | Atlassian OAuth |
| `CLICKUP_CLIENT_ID` / `CLICKUP_CLIENT_SECRET` | ClickUp OAuth |
| `REDIS_URL` | Background job queue (arq/celery) |
| `WEBHOOK_BASE_URL` | Public URL for webhook endpoints |

---

## 19. Backend Risks and Unknowns

### Code risks
1. **`mcp_server/services.py` is 1370 lines** — Should be split into separate modules (as the README originally intended)
2. **`tool/models.py` contains unrelated models** — ChatSession, Message, RagSource, DbConnection models are in the tool module
3. **No input validation on webhook payloads** — External data will need strict validation
4. **`_SESSIONS` process-level cache** — Unbounded MCP session accumulation
5. **In-memory rate limiter** — Will not work with multiple workers/instances

### Architecture risks
1. **No background job infrastructure** — Token refresh, webhook retry, document indexing all need async jobs
2. **No message queue** — Webhook events need reliable processing with retry
3. **No distributed locking** — Concurrent token refreshes may race
4. **Single-process state** — Graph cache, rate limiter, MCP sessions are all in-memory per-process
5. **Sync MongoDB client** — `mcp_oauth_tokens_sync` uses PyMongo because MCP sessions run on separate threads; this pattern will need extension for integration tokens

### Missing tests
1. No end-to-end tests for full chat → tool → response flow
2. No load/stress tests
3. No security tests (injection, auth bypass, tenant isolation)
4. No webhook processing tests
5. Limited MCP OAuth flow tests

### Missing documentation
1. No architecture decision records (ADRs)
2. No API versioning strategy
3. No deployment runbook
4. No monitoring/alerting playbook
5. No data retention policy

### Security gaps
1. CORS allows all origins (`allow_origins=["*"]`) — should be restricted in production
2. No API key authentication for service-to-service calls
3. No webhook signature verification infrastructure
4. No secrets rotation mechanism
5. Session middleware uses `JWT_SECRET_KEY` — separate secret recommended
6. `OTP_RETURN_IN_RESPONSE` defaults to env-driven — easy to accidentally enable in production

### Refactor suggestions
1. Split `mcp_server/services.py` into separate files as README describes
2. Move ChatSession, Message, RagSource, DbConnection out of `tool/models.py`
3. Add Redis for rate limiting, caching, and job queue
4. Introduce connection pooling/health checks for MCP sessions
5. Add API versioning (`/api/v1/...`) before adding integration endpoints
6. Create shared `backend/core/oauth.py` for reusable OAuth 2.0 logic

### Questions to ask before implementation
1. **Which integrations are highest priority?** (Recommend: Slack + Jira first)
2. **Should integrations use the existing MCP path where possible or build native connectors?**
3. **Is Redis acceptable as a new infrastructure dependency?**
4. **Should the webhook base URL be the same as the API or a separate subdomain?**
5. **What is the expected scale? (orgs, users, concurrent webhook events)**
6. **Should integration tokens be per-org or per-user?**
7. **Is there a frontend team ready to build the integration connection UI?**
8. **What is the compliance requirement for webhook event retention?**
9. **Should we support OAuth 2.0 for all integrations or also API key-based auth?**
10. **Does the platform need to support custom/self-hosted instances of Jira/GitLab/etc.?**

---

## 20. Final Summary

### Is backend integration-ready?
**Partially.** The backend has strong foundations — multi-tenancy, RBAC, encrypted secret storage, tool registry, MCP server integration with OAuth, and agent-tool binding. The MCP infrastructure specifically demonstrates that the team has already solved many of the patterns needed for integrations (OAuth flow, token storage, tool discovery, runtime execution). However, the backend lacks webhook infrastructure, background job processing, distributed state management, and a generic integration connector layer.

### Best backend path forward
1. **Phase 1 (Foundation):** Build `backend/integrations/` module with generic OAuth, token storage, webhook handler, and provider base class. Add Redis for job queue.
2. **Phase 2 (First integrations):** Implement Slack (MCP + webhook) and Jira (MCP OAuth). These leverage existing MCP infrastructure most directly.
3. **Phase 3 (Microsoft stack):** Azure AD OAuth + Teams + Outlook + SharePoint + OneDrive (shared auth).
4. **Phase 4 (Google stack):** Google OAuth + Gmail + Drive (shared auth).
5. **Phase 5 (Remaining):** ClickUp and any additional integrations.

### Top 10 backend files to understand first

| # | File | Why |
|---|---|---|
| 1 | `backend/main.py` | App factory, router registration, middleware, startup |
| 2 | `backend/dependencies.py` | Auth dependency injection pattern |
| 3 | `backend/auth/permissions.py` | RBAC resolution, org access guards |
| 4 | `backend/mcp_server/services.py` | OAuth flow, token storage, connection, discovery — the integration template |
| 5 | `backend/chat/graph.py` | LangGraph builder, tool execution, agent runtime — how tools are invoked |
| 6 | `backend/chat/services.py` | Chat lifecycle, MCP tool loading, memory management |
| 7 | `backend/core/encryption.py` | Fernet encryption for secrets at rest |
| 8 | `backend/tool/services.py` | Tool creation, registry validation, agent binding |
| 9 | `backend/db/database.py` | All MongoDB collection references |
| 10 | `backend/core/config.py` | All configuration settings |

### Top 10 backend files likely to change for integrations

| # | File | Change |
|---|---|---|
| 1 | `backend/main.py` | Register integration routers, webhook routers, startup tasks |
| 2 | `backend/db/database.py` | Add new collection references (integration_connections, integration_tokens, webhook_events, integration_audit_logs) |
| 3 | `backend/db/constants.py` | Add new collection name constants |
| 4 | `backend/agent/models.py` | Add `integration_ids: List[str]` field |
| 5 | `backend/agent/schemas.py` | Add `integration_ids` to create/update/public schemas |
| 6 | `backend/agent/services.py` | Load integration tools for agents (parallel to MCP tools) |
| 7 | `backend/chat/graph.py` | Bind integration tool callables to agent nodes |
| 8 | `backend/chat/services.py` | Load integration tools alongside MCP tools |
| 9 | `backend/core/config.py` | Add integration-specific settings (client IDs, secrets, webhook URLs) |
| 10 | `backend/admin.py` | Add admin views for integration connections and tokens |

---

*End of Backend Project Overview for Integrations*
