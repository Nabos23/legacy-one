# Legacy AI — API Reference

FastAPI backend backed by MongoDB (motor). This document covers Authentication, Roles & Permissions, and CRUD endpoints for organizations, agents, tools, DB connections, tool registry, chat, and tracing.

**Base URL (local):** `http://localhost:8000`  
**Interactive docs:** `http://localhost:8000/docs` (Swagger), `http://localhost:8000/redoc`  
**Auth scheme:** Bearer JWT — send `Authorization: Bearer <access_token>` on protected routes.

---

## Architecture & Concepts

### Roles & Permissions (RBAC)
Every protected route checks the caller's role for a permission flag. Generic flags (`view`, `create`, `edit`, `delete`) cover most operations; resource-specific flags (`create_org`, `create_user`, `create_tool`, `create_agent`, `create_db_connection`) gate the creation of each top-level resource and are dynamically assignable to any role via the admin panel.

### Soft Deletes
Deletes are soft deletes: a `DELETE` marks the record with `is_deleted=true` and a `deleted_at` timestamp instead of removing it. Soft-deleted records are excluded from all list/get/update responses (and 404 on a second delete). Applies to organizations, agents, tools, and DB connections.

### Pagination
List endpoints are paginated (organizations, agents, tools, DB connections).
All list (GET collection) endpoints accept these query parameters:
- `page`: 1-based page number (>= 1, default: 1)
- `page_size`: Items per page (1–100, default: 20)

**Response Envelope Format:**
```json
{
  "items": [ /* array of the resource objects */ ],
  "total": 137,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

### Rate Limiting & Quotas
- **Rate Limits:** Fixed-window, per-IP rate limit. Returns `429 Too Many Requests` with a `Retry-After` header when exceeded. Responses include `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers.
- **Quotas:** Returns `429` (e.g., `max_orgs_per_day`) or `403` (e.g., `max_tools_per_org`) when business limits are reached.

### Organization Scoping
- `super_admin` — can list and access resources in any organization.
- All other roles — list/get/update/delete only resources belonging to their `organization_id`. Nested routes such as `GET /organizations/{org_id}/tools` return `403 Forbidden` when `org_id` does not match the caller's organization.

---

## Authentication

### `POST /auth/register`
Self-service registration. Creates a new organization and admin user.
- **Auth required:** No
- **Request:** `{ "name": "...", "email": "...", "password": "..." }`
- **Response:** `201 Created` with JWT and user.

### `POST /auth/signup`
Register a new user to an existing organization.
- **Auth required:** No
- **Request:** `{ "organization_id": "...", "name": "...", "email": "...", "password": "...", "role": "user" }`
- **Response:** `201 Created` with JWT.

### `POST /auth/login`
Authenticate an existing user.
- **Request:** `{ "email": "...", "password": "..." }`
- **Response:** `200 OK` with JWT.

### `POST /auth/logout`
Stateless logout. Client is responsible for discarding the token.
- **Auth required:** Yes
- **Response:** `200 OK`

### `POST /auth/users` (Provisioner only)
Create a user in the caller's own organization.
- **Auth required:** Yes (requires `create_user` permission).
- **Request:** `{ "name": "...", "email": "...", "password": "...", "role": "user" }`
- **Response:** `201 Created` with User object (no token).

### `GET /auth/me`
Return the currently authenticated user.
- **Auth required:** Yes

### Password Reset Flow
- `POST /auth/forgot-password`: Request a password-reset OTP (Request: `{ "email": "..." }`).
- `POST /auth/verify-otp`: Verify an OTP (Request: `{ "email": "...", "otp": "..." }`).
- `POST /auth/reset-password`: Set new password (Request: `{ "email": "...", "otp": "...", "new_password": "..." }`).

---

## Organizations

- `POST /organizations`: Create organization (requires `create_org`).
- `GET /organizations`: List organizations.
- `GET /organizations/{org_id}`: Fetch a single organization.
- `PUT /organizations/{org_id}`: Update an organization.
- `DELETE /organizations/{org_id}`: Soft-delete an organization.
- `GET /organizations/{org_id}/agents`: List agents in org.
- `GET /organizations/{org_id}/tools`: List tools in org.
- `GET /organizations/{org_id}/db-connections`: List DB connections in org.
- `GET /organizations/{org_id}/users`: List users in org.

---

## Agents

- `POST /agents`: Create agent (requires `create_agent`).
- `GET /agents`: List agents.
- `GET /agents/org/{org_id}`: List agents belonging to a specific org.
- `GET /agents/{agent_id}`: Fetch single agent.
- `PUT /agents/{agent_id}`: Update agent.
- `DELETE /agents/{agent_id}`: Soft-delete agent.

---

## Tools

- `POST /tools`: Create tool (requires `create_tool`).
- `GET /tools`: List tools.
- `GET /tools/org/{org_id}`: List tools for a specific org.
- `GET /tools/{tool_id}`: Fetch single tool.
- `PUT /tools/{tool_id}`: Update tool.
- `DELETE /tools/{tool_id}`: Soft-delete tool.

---

## DB Connections
*Security note: `connection_string` is encrypted at rest and always returned masked (e.g. `postgresql://****`).*

- `POST /db-connections`: Create DB connection (requires `create_db_connection`).
- `GET /db-connections`: List DB connections.
- `GET /db-connections/{conn_id}`: Fetch single DB connection.
- `GET /db-connections/{conn_id}/schema`: Get the auto-fetched DB schema.
- `PUT /db-connections/{conn_id}`: Update connection (re-encrypts and re-fetches schema).
- `DELETE /db-connections/{conn_id}`: Soft-delete DB connection.

---

## Chat (LangGraph)

All chat endpoints require authentication. Write operations require `create_chat` permission.

### `POST /chat/session`
Initialize a LangGraph session for the caller's organization.
- **Response:**
```json
{
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "name": null,
  "available_agents": [
    {
      "agent_id": "...",
      "name": "Support Bot",
      "description": "...",
      "tool_count": 2
    }
  ],
  "created_at": "2026-06-16T10:00:00Z"
}
```

### `POST /chat/message`
Send a message into an existing session.
- **Request:** `{ "thread_id": "...", "message": "..." }`
- **Response:** `{ "thread_id": "...", "response": "...", "messages_count": 6 }`

### `GET /chat/sessions`
List all chat sessions for the authenticated user (newest first).
- **Response Envelope:** Array of items containing `thread_id`, `organization_id`, `user_id`, `name`, `epoch`, `agent_ids`, `created_at`.

### `GET /chat/sessions/{thread_id}/history`
Return full conversation history per agent.
- **Response:** Contains array of `agents` where each has `conversations` containing `"turn"` or `"summary"` entries.

---

## Tool Registry (Global Catalog)
- `POST /tool-registry` (Super Admin)
- `GET /tool-registry`
- `GET /tool-registry/{registry_id}`
- `PUT /tool-registry/{registry_id}` (Super Admin)
- `DELETE /tool-registry/{registry_id}` (Super Admin)

---

## Prompt Generator
- `POST /generate-prompt`: Generates system prompts (no auth required).
  - Request: `{ "agent_name": "...", "agent_description": "..." }`

---

## Tracing (Langfuse)
All trace endpoints require `view_trace` permission and are scoped to the caller's organization.
- `GET /traces`
- `GET /traces/stats`
- `GET /traces/{trace_id}`
- `GET /sessions`
- `GET /agents/{agent_id}/traces`
- `GET /agents/{agent_id}/stats`
