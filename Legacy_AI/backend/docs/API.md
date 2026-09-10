# Legacy AI — API Reference

FastAPI backend backed by MongoDB (motor). This document covers **Authentication**,
**Roles & Permissions**, and CRUD endpoints for organizations, agents, tools, DB
connections, tool registry, connectors, chat, and tracing.

- Base URL (local): `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs` (Swagger), `http://localhost:8000/redoc`
- Auth scheme: **Bearer JWT** — send `Authorization: Bearer <access_token>` on protected routes.
- **Role-based access control (RBAC)** — every protected route checks the caller's role
  for a permission flag (see [Roles & Permissions](#roles--permissions)). Generic flags
  (`view`, `create`, `edit`, `delete`) cover most operations; resource-specific flags
  (`create_org`, `create_user`, `create_tool`, `create_agent`, `create_db_connection`) gate the
  creation of each top-level resource and are **dynamically assignable to any role** via the admin panel.
- **Deletes are soft deletes**: a `DELETE` marks the record with `is_deleted=true` and a
  `deleted_at` timestamp instead of removing it. Soft-deleted records are excluded from all
  list/get/update responses (and `404` on a second delete). Applies to organizations, agents,
  tools, and DB connections.
- **List endpoints are paginated** (organizations, agents, tools, DB connections).
- **Rate limiting** is applied per client IP and is configurable live from the admin panel
  (see [Rate Limiting](#rate-limiting)).

## Rate Limiting

A fixed-window, per-IP rate limit is enforced on all API routes (the `/admin`, `/docs`,
`/redoc`, and `/openapi.json` paths are exempt so you can never lock yourself out).

- Limits are stored in MongoDB (`rate_limit_config`) and **edited live from the admin
  dashboard** at `/admin` → **Rate Limit** — changes apply within ~5 seconds, no restart.
- Configurable fields: `enabled`, `max_requests`, `window_seconds`.
- Successful responses include `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers.
- When exceeded, the API returns **`429 Too Many Requests`** with a `Retry-After` header:

  ```json
  { "detail": "Rate limit exceeded. Try again later." }
  ```

> Counters are in-memory (per process). For multiple workers/instances, back them with Redis.

## Quotas

Business quotas are stored in MongoDB (`quota_config`) and **edited live from the admin
dashboard** at `/admin` → **Quotas / Limits** (changes apply immediately).

| Setting | Meaning | Enforced on | Error |
|---|---|---|---|
| `enabled` | turn all quotas on/off | — | — |
| `max_orgs_per_day` | a single user may create at most this many organizations per (UTC) day | `POST /organizations` | `429` |
| `max_tools_per_org` | an organization may have at most this many tools | `POST /tools` | `403` |

When a quota is hit, the response body explains the limit, e.g.:

```json
{ "detail": "Daily limit reached: you can create at most 10 organizations per day." }
```

## Pagination

All list (`GET` collection) endpoints accept these query parameters:

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` | int | `1` | 1-based page number (`>= 1`) |
| `page_size` | int | `20` | Items per page (`1`–`100`) |

They return a **paginated envelope** instead of a bare array:

```json
{
  "items": [ /* array of the resource objects */ ],
  "total": 137,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

Example: `GET /organizations?page=2&page_size=50`

## Roles & Permissions

Protected API routes enforce **role-based access control**. Each user carries a
`role` string on their JWT-backed profile. The role maps to a set of boolean permission
flags. Permissions are stored in MongoDB (`roles` collection) and **seeded automatically
on startup**. They can also be edited live from the admin dashboard at `/admin` → **Roles**
(changes apply within ~5 seconds, no restart). Built-in roles start from code defaults;
per-flag overrides from the database are merged on top.

### Permission flags

Every resource has four granular flags — **view**, **create**, **edit**, **delete** —
dynamically assignable to any role via the admin panel:

| Resource | view | create | edit | delete |
|---|---|---|---|---|
| Organization | `view_org` | `create_org` | `edit_org` | `delete_org` |
| User | `view_user` | `create_user` | `edit_user` | `delete_user` |
| Agent | `view_agent` | `create_agent` | `edit_agent` | `delete_agent` |
| Tool | `view_tool` | `create_tool` | `edit_tool` | `delete_tool` |
| DB Connection | `view_db_connection` | `create_db_connection` | `edit_db_connection` | `delete_db_connection` |

Additional standalone flags:

| Flag | Gates |
|---|---|
| `create_chat` | `POST /chat/session`, `POST /chat/message`, `GET /chat/sessions`, `GET /chat/sessions/{thread_id}/history` |
| `view_trace` | All `GET /traces`, `GET /sessions` endpoints |
| `view_tool_registry` | `GET /tool-registry` |

### Built-in roles

| Role | Label | org<br/>v c e d | user<br/>v c e d | agent<br/>v c e d | tool<br/>v c e d | db_conn<br/>v c e d | chat<br/>c | trace<br/>v | reg<br/>v | Scope |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `user` | User | ✅❌❌❌ | ✅❌❌❌ | ✅❌❌❌ | ✅❌❌❌ | ✅❌❌❌ | ❌ | ✅ | ✅ | Own org |
| `org_manager` | Org Manager | ✅❌✅❌ | ✅❌❌❌ | ✅❌✅❌ | ✅❌✅❌ | ✅❌❌❌ | ❌ | ✅ | ✅ | Own org |
| `org_admin` | Org Admin | ✅❌✅✅ | ✅✅✅✅ | ✅✅✅✅ | ✅✅✅✅ | ✅✅✅✅ | ✅ | ✅ | ✅ | Own org |
| `super_admin` | Super Admin | ✅✅✅✅ | ✅✅✅✅ | ✅✅✅✅ | ✅✅✅✅ | ✅✅✅✅ | ✅ | ✅ | ✅ | **All orgs** |

### Legacy role aliases

Older user documents may still use these values; they are normalized at runtime:

| Stored role | Treated as |
|---|---|
| `member` | `user` |
| `admin` | `org_admin` |

### Special cases

| Endpoint | Permission required |
|---|---|
| `POST /organizations` | `create_org` (only `super_admin` by default) |
| `POST /auth/users` | `create_user` (`org_admin`, `super_admin`, or any role with this flag) |
| `POST /tools` | `create_tool` (`org_admin`, `super_admin`, or any role with this flag) |
| `POST /agents` | `create_agent` (`org_admin`, `super_admin`, or any role with this flag) |
| `POST /db-connections` | `create_db_connection` (`org_admin`, `super_admin`, or any role with this flag) |
| `POST /chat/session`, `POST /chat/message` | `create_chat` |
| `GET /traces`, `GET /sessions`, etc. | `view_trace` |
| `POST /tool-registry`, `PUT /tool-registry/{id}`, `DELETE /tool-registry/{id}` | **`super_admin` only** (global catalog) |
| `GET /tool-registry` | `view_tool_registry` |
| `GET /users` | **`super_admin` only** (global user list) |
| `GET /organizations/{org_id}/users` | `view_user` + org access |

### Organization scoping

- **`super_admin`** — can list and access resources in **any** organization.
- **All other roles** — list/get/update/delete only resources belonging to their
  `organization_id`. Nested routes such as `GET /organizations/{org_id}/tools` return
  **`403 Forbidden`** when `org_id` does not match the caller's organization (unless
  the caller is `super_admin`).
- **`POST /organizations`** — on success, the creator's `organization_id` is updated to
  the new organization's `_id`.

### Dynamic permission assignment

Any permission flag (`view_org`, `create_org`, `edit_org`, `delete_org`, `view_user`,
`create_user`, `edit_user`, `delete_user`, `view_agent`, `create_agent`, `edit_agent`,
`delete_agent`, `view_tool`, `create_tool`, `edit_tool`, `delete_tool`,
`view_db_connection`, `create_db_connection`, `edit_db_connection`, `delete_db_connection`,
`create_chat`, `view_trace`, `view_tool_registry`) can be toggled on or off for
**any role** from the admin panel at `/admin` → **Roles**.
For example, to let `org_manager` create tools without full `org_admin` access, set
`create_tool: true` on the `org_manager` role — the change takes effect within ~5 seconds.

### Error responses

| Status | When |
|---|---|
| `403 Forbidden` | Missing permission, e.g. `{ "detail": "Missing 'create_agent' permission for your role." }` |
| `403 Forbidden` | Cross-organization access denied, e.g. `{ "detail": "You do not have access to this organization." }` |
| `403 Forbidden` | Tool registry mutation by non–super-admin, e.g. `{ "detail": "Super admin privileges required." }` |

### Seed roles

```bash
uv run python -m backend.scripts.seed_roles
```

Re-running is safe: built-in roles are upserted by `name`.

## Admin Panel

A web admin UI (starlette-admin, backed by MongoDB via ODMantic) is mounted at **`/admin`**.

- Login at `http://localhost:8000/admin` — users with role `super_admin`, `org_admin`,
  or legacy `admin` may sign in (credentials are the same email/password as the API).
- Manage Organizations, Users, Agents, Tools, DB Connections, Tool Registry, and **Roles**
  (permission flags per role).
- Sensitive fields are hidden from the UI: user `password` hashes and the encrypted
  `connection_string`.
- Seed the first admin (needed before you can log in):

  ```bash
  uv run python -m backend.scripts.seed_admin admin@example.com "StrongPass123" <org_id> "Site Admin"
  ```

Run locally:

```bash
uv run uvicorn main:app --reload
```

Environment variables (optional, see `.env`):

| Variable | Default | Purpose |
|---|---|---|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DATABASE_NAME` | `aiddb` | Database name |
| `JWT_SECRET_KEY` | `change-me-in-production` | **Set this in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) | Token lifetime |
| `ENCRYPTION_KEY` | derived from `JWT_SECRET_KEY` | Fernet key for encrypting secrets at rest |
| `OTP_EXPIRE_MINUTES` | `10` | Password-reset OTP lifetime |
| `OTP_RETURN_IN_RESPONSE` | `true` | Return OTP in API response (set `false` in prod) |

---

## Authentication

### POST `/auth/register`

Self-service registration. This endpoint creates a new organization (named after the user)
and a new admin user within that organization. Returns a JWT and the created user.

**Auth required:** No

**Request body**

```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "Secure123"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | |
| `email` | string (email) | yes | Must be unique |
| `password` | string | yes | Min length 6 |

**Response `201 Created`** — a `TokenResponse`: `access_token`, `token_type` (`"bearer"`),
the created `user`, and `db_conn_ids`.

---

### POST `/auth/logout`

Stateless logout. The server returns a success message; the client is responsible for
discarding the token.

**Auth required:** Yes

**Response `200 OK`**

```json
{ "message": "Logged out successfully." }
```

---

> **Note:** there is no `POST /auth/signup`. Self-service signup is `POST /auth/register`
> (above), and provisioning a user inside an existing org is `POST /auth/users` (below).

### POST `/auth/login`

Authenticate an existing user.

**Auth required:** No

**Request body**

```json
{
  "email": "jane@example.com",
  "password": "Secure123"
}
```

**Response `200 OK`** — the same `TokenResponse` shape as `/auth/register`.

**Errors**

| Status | When |
|---|---|
| `401 Unauthorized` | Invalid email or password |

---

### POST `/auth/users`

**Provisioner only.** Create a user against an organization and return a JWT for the new
user (alongside the created user and the org's DB-connection ids).

**Auth required:** Yes — caller must have the **`create_user`** permission (`org_admin`,
`super_admin`, or any role granted this flag; else `403`).

**Request body** — `SignupRequest`

```json
{
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "name": "New Teammate",
  "email": "teammate@example.com",
  "password": "Secure123",
  "role": "user"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `organization_id` | string | yes | The org the new user belongs to |
| `name` | string | yes | |
| `email` | string (email) | yes | Must be unique; trimmed and normalized to lowercase |
| `password` | string | yes | Must meet the password rules below |
| `role` | string | no | Defaults to `"user"` (read-only). Assign `org_admin`, `org_manager`, etc. as needed. |

**Password rules** (enforced on signup):

| Rule | Requirement |
|---|---|
| Length | At least **8** characters |
| Uppercase | At least one `A`–`Z` |
| Lowercase | At least one `a`–`z` |
| Digit | At least one `0`–`9` |

Example valid password: `Secure123`

**Response `201 Created`** — `TokenResponse` (same shape as `/auth/register` and `/auth/login`)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "665f1d9a8a3b4c0012a9d4e3",
    "organization_id": "665f1c2e8a3b4c0012a9d4e1",
    "name": "New Teammate",
    "email": "teammate@example.com",
    "role": "user",
    "created_at": "2026-06-04T14:00:00Z"
  },
  "db_conn_ids": []
}
```

**Errors**

| Status | When |
|---|---|
| `401 Unauthorized` | Missing/invalid token |
| `403 Forbidden` | Caller lacks `create_user` permission |
| `409 Conflict` | Email already exists |
| `422 Unprocessable Entity` | Validation failed (invalid email, weak password, missing field) |

---

### GET `/auth/me`

Return the currently authenticated user.

**Auth required:** Yes (`Authorization: Bearer <token>`)

**Response `200 OK`**

```json
{
  "id": "665f1d9a8a3b4c0012a9d4e2",
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "user",
  "created_at": "2026-06-03T10:15:00Z"
}
```

**Errors**

| Status | When |
|---|---|
| `401 Unauthorized` | Missing/invalid/expired token, or user no longer exists |

> `/auth/me` requires authentication only — no specific permission flag.

---

### GET `/auth/me/permissions`

Debug: return the current user's role and resolved permissions.

**Auth required:** Yes

**Response `200 OK`**

```json
{
  "user_id": "665f1d9a8a3b4c0012a9d4e2",
  "role_stored": "user",
  "is_super_admin": false,
  "resolved_permissions": {
    "view": true,
    "create": false,
    "edit": false,
    "delete": false,
    "create_org": false,
    "create_user": false,
    "create_tool": false,
    "create_agent": false,
    "create_db_connection": false
  }
}
```

---

### POST `/auth/forgot-password`

Request a password-reset OTP. To avoid leaking which emails exist, the response is
always a generic success message. The OTP expires after `OTP_EXPIRE_MINUTES` (default 10).

**Auth required:** No

> **Dev mode:** when `OTP_RETURN_IN_RESPONSE=true` (default), the OTP is returned in the
> `otp` field *and* logged to the server console. In production set it to `false` and send
> the OTP by email — the `otp` field will be `null`.

**Request body**

```json
{ "email": "jane@example.com" }
```

**Response `200 OK`**

```json
{
  "message": "If the email exists, an OTP has been sent.",
  "otp": "233605"
}
```

---

### POST `/auth/verify-otp`

Verify an OTP without consuming it (useful for a "check code" step in the UI).

**Auth required:** No

**Request body**

```json
{ "email": "jane@example.com", "otp": "233605" }
```

**Response `200 OK`**

```json
{ "message": "OTP verified.", "otp": null }
```

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | OTP is invalid |
| `400 Bad Request` | OTP has expired |

---

### POST `/auth/reset-password`

Set a new password using a valid OTP. On success the OTP is invalidated (single use).

**Auth required:** No

**Request body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `email` | string (email) | yes | |
| `otp` | string | yes | |
| `new_password` | string | yes | Min length 6 |

```json
{
  "email": "jane@example.com",
  "otp": "233605",
  "new_password": "newpass456"
}
```

**Response `200 OK`**

```json
{ "message": "Password has been reset successfully.", "otp": null }
```

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | OTP is invalid or expired |
| `422 Unprocessable Entity` | `new_password` shorter than 6 chars |

---

## Organizations (CRUD)

All organization routes require a valid Bearer token and the matching
[permission](#permission--http-method) for each operation. Non–super-admins are
scoped to their own organization (see [Organization scoping](#organization-scoping)).

| Method | Permission |
|---|---|
| `GET` | `view` |
| `POST` | `create_org` |
| `PUT` | `edit` |
| `DELETE` | `delete` |

### POST `/organizations`

Create an organization. Requires **`create_org`** permission (only `super_admin` by default;
assignable to other roles via the admin panel). On success, the caller's
`organization_id` is updated to the new organization's `_id`.

**Request body**

```json
{
  "name": "Acme Corp",
  "description": "Manufacturer of everything"
}
```

| Field | Type | Required |
|---|---|---|
| `name` | string | yes |
| `description` | string | no |

**Response `201 Created`**

```json
{
  "id": "665f1c2e8a3b4c0012a9d4e1",
  "name": "Acme Corp",
  "description": "Manufacturer of everything",
  "created_at": "2026-06-03T10:00:00Z",
  "updated_at": "2026-06-03T10:00:00Z"
}
```

---

### GET `/organizations`

List organizations. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)).
Requires **`view`** permission.

- **`super_admin`** — returns all organizations (paginated).
- **Other roles** — returns only the caller's own organization (or an empty page if
  their `organization_id` does not match a stored organization).

**Response `200 OK`** — `Page` envelope of `OrganizationPublic`

```json
{
  "items": [
    {
      "id": "665f1c2e8a3b4c0012a9d4e1",
      "name": "Acme Corp",
      "description": "Manufacturer of everything",
      "created_at": "2026-06-03T10:00:00Z",
      "updated_at": "2026-06-03T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

### GET `/organizations/{org_id}`

Fetch a single organization by id.

**Path params:** `org_id` — the organization's `_id` (string).

**Response `200 OK`** — single `OrganizationPublic` object (see above).

**Errors**

| Status | When |
|---|---|
| `403 Forbidden` | `org_id` is not the caller's organization (non–super-admin) |
| `404 Not Found` | No organization with that id (or malformed id) |

---

### PUT `/organizations/{org_id}`

Update an organization. Only the provided fields are changed; `updated_at` is refreshed automatically.

**Request body** (all fields optional)

```json
{
  "name": "Acme Corporation",
  "description": "Updated description"
}
```

**Response `200 OK`** — updated `OrganizationPublic` object.

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | No fields provided to update |
| `404 Not Found` | No organization with that id |

---

### DELETE `/organizations/{org_id}`

Soft-delete an organization (marks `is_deleted=true`; not physically removed).

**Response `204 No Content`** — empty body.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No organization with that id |

---

### GET `/organizations/{org_id}/agents`

List agents belonging to a specific organization. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)). Requires **`view`** permission and access to `org_id`.

**Auth required:** Yes (`Authorization: Bearer <token>`)

**Path params:** `org_id` — the organization's `_id` (string).

**Query params:** `page`, `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `AgentPublic` objects.

```json
{
  "items": [
    {
      "id": "665f2a118a3b4c0012a9d4f0",
      "organization_id": "665f1c2e8a3b4c0012a9d4e1",
      "name": "Support Bot",
      "prompt": "You are a helpful customer support assistant.",
      "guardrails": "Never share internal pricing or customer PII.",
      "description": null,
      "user_description": null,
      "instructions": null,
      "tool_ids": [],
      "rag_ids": [],
      "mcp_server_ids": [],
      "created_by": "665f1d9a8a3b4c0012a9d4e2",
      "created_at": "2026-06-03T11:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

Example: `GET /organizations/665f1c2e8a3b4c0012a9d4e1/agents?page=1&page_size=10`

---

### GET `/organizations/{org_id}/tools`

List tools belonging to a specific organization. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)). Requires **`view`** permission and access to `org_id`.

**Auth required:** Yes (`Authorization: Bearer <token>`)

**Path params:** `org_id` — the organization's `_id` (string).

**Query params:** `page`, `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `ToolPublic` objects.

```json
{
  "items": [
    {
      "id": "6a2180119c1f2a3b4c5d6e7f",
      "organization_id": "665f1c2e8a3b4c0012a9d4e1",
      "agent_id": "665f2a118a3b4c0012a9d4f0",
      "name": "Customer DB Query",
      "user_description": "Looks up a customer's recent orders",
      "tool_id": "665fdeadbeef000000000001",
      "created_at": "2026-06-04T13:40:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

Example: `GET /organizations/665f1c2e8a3b4c0012a9d4e1/tools?page=1&page_size=10`

---

### GET `/organizations/{org_id}/db-connections`

List DB connections belonging to a specific organization. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)). Connection strings are masked in every item. Requires **`view`** permission and access to `org_id`.

**Auth required:** Yes (`Authorization: Bearer <token>`)

**Path params:** `org_id` — the organization's `_id` (string).

**Query params:** `page`, `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `DbConnectionPublic` objects.

```json
{
  "items": [
    {
      "id": "6a217c707dc7370a4b7d825e",
      "organization_id": "665f1c2e8a3b4c0012a9d4e1",
      "connection_string": "postgresql://****",
      "created_at": "2026-06-04T13:24:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

Example: `GET /organizations/665f1c2e8a3b4c0012a9d4e1/db-connections?page=1&page_size=10`

---

## Users

User query endpoints. Both require a valid Bearer token.

### GET `/users`

List **all** users across every organization. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)). **Super admin only.**

**Auth required:** Yes — caller must have the **`super_admin`** role; else `403`.

**Response `200 OK`** — `Page` envelope whose `items` are `UserPublic` objects.

```json
{
  "items": [
    {
      "id": "665f1d9a8a3b4c0012a9d4e2",
      "organization_id": "665f1c2e8a3b4c0012a9d4e1",
      "name": "Jane Doe",
      "email": "jane@example.com",
      "role": "user",
      "created_at": "2026-06-03T10:15:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

**Errors**

| Status | When |
|---|---|
| `403 Forbidden` | Caller is not a super admin |

---

### GET `/organizations/{org_id}/users`

List users belonging to a specific organization. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)). Requires **`view`** permission and access to `org_id`.

**Auth required:** Yes (`Authorization: Bearer <token>`)

**Path params:** `org_id` — the organization's `_id` (string).

**Query params:** `page`, `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `UserPublic` objects (same shape as above).

**Errors**

| Status | When |
|---|---|
| `403 Forbidden` | `org_id` is not the caller's org (non–super-admin) |

Example: `GET /organizations/665f1c2e8a3b4c0012a9d4e1/users?page=1&page_size=10`

---

## Agents (CRUD)

All agent routes require a valid Bearer token and the matching permission. On create,
`organization_id` is required in the request body (RBAC-checked against the caller's org);
`created_by` comes from the token. Non–super-admins only see and mutate agents in their
own organization.

### POST `/agents`

Create an agent. Requires **`create_agent`** permission (`org_admin`, `super_admin`, or
any role granted this flag).
`organization_id` must be provided in the request body and must be a valid, non-deleted organization.

**Request body**

```json
{
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "name": "Support Bot",
  "prompt": "You are a helpful customer support assistant.",
  "guardrails": "Never share internal pricing or customer PII.",
  "mcp_server_ids": ["665f3b228a3b4c0012a9d5a1"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `organization_id` | string | **yes** | must be a valid, non-deleted org; RBAC-checked against caller's org |
| `name` | string | **yes** | |
| `prompt` | string | **yes** | |
| `guardrails` | string | **yes** | |
| `mcp_server_ids` | string[] | no | Omit or pass `null` if not applicable; only stored when provided |

**Response `201 Created`**

```json
{
  "id": "665f2a118a3b4c0012a9d4f0",
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "name": "Support Bot",
  "prompt": "You are a helpful customer support assistant.",
  "guardrails": "Never share internal pricing or customer PII.",
  "description": null,
  "user_description": null,
  "instructions": null,
  "tool_ids": [],
  "rag_ids": [],
  "mcp_server_ids": [],
  "created_by": "665f1d9a8a3b4c0012a9d4e2",
  "created_at": "2026-06-03T11:00:00Z"
}
```

**Errors**

| Status | When |
|---|---|
| `403 Forbidden` | `organization_id` does not match the caller's org (non–super-admin) |
| `404 Not Found` | `organization_id` is not a valid or existing organization |

---

### GET `/agents`

List agents. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `AgentPublic` objects.

---

### GET `/agents/org/{org_id}`

List agents belonging to a specific organization. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)). Requires **`view`** permission and access to `org_id`.

**Auth required:** Yes (`Authorization: Bearer <token>`)

**Path params:** `org_id` — the organization's `_id` (string).

**Query params:** `page`, `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `AgentPublic` objects.

**Errors**

| Status | When |
|---|---|
| `403 Forbidden` | `org_id` is not the caller's organization (non–super-admin) |

Example: `GET /agents/org/665f1c2e8a3b4c0012a9d4e1?page=1&page_size=10`

---

### GET `/agents/{agent_id}`

Fetch a single agent by id.

**Path params:** `agent_id` — the agent's `_id` (string).

**Response `200 OK`** — single `AgentPublic` object.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No agent with that id (or malformed id) |

---

### PUT `/agents/{agent_id}`

Update an agent. Only provided fields are changed.

**Request body** (all fields optional)

```json
{
  "name": "Support Bot v2",
  "prompt": "You are a concise customer support assistant.",
  "guardrails": "Never share internal pricing, secrets, or customer PII."
}
```

**Response `200 OK`** — updated `AgentPublic` object.

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | No fields provided to update |
| `404 Not Found` | No agent with that id |

---

### DELETE `/agents/{agent_id}`

Soft-delete an agent (marks `is_deleted=true`; not physically removed).

**Response `204 No Content`** — empty body.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No agent with that id |

---

## DB Connections

All routes require a valid Bearer token and the matching permission
(`view` / `create` / `edit` / `delete`). On create, `organization_id` is provided in the
request body. Non–super-admins are scoped to their own organization's connections.

> **Security:** the `connection_string` is **encrypted at rest** (Fernet) and
> **never returned in plaintext**. All responses mask it (e.g. `postgresql://****`).
> The plaintext is only decrypted server-side when the connection is actually used.

> **Supported databases:**
> - **PostgreSQL / MySQL / SQLite** — tables (columns, types, nullable, defaults),
>   indexes, foreign keys, views, and PostgreSQL enums
> - **MongoDB** (`mongodb://` / `mongodb+srv://`) — databases, collections, field
>   types across sampled documents, document counts, and indexes
> - **Supabase** — detected automatically by hostname (`*.supabase.co`);
>   introspected as PostgreSQL with the full schema above plus PostgreSQL enums
>
> **Large schemas never fail:** if the stored schema exceeds MongoDB's 16 MB document
> limit it is transparently offloaded to GridFS and re-assembled on read.

### Standard flow — 2 calls

The intended flow for connecting a new database is exactly **two API calls**:

```
Step 1 — POST /db-connections/preview
  → Connect to the DB, fetch schema, generate LLM descriptions for every table.
  → Return schema + descriptions to the user for review. Nothing is saved.

Step 2 — POST /db-connections
  → Send connection string + the reviewed descriptions in one request.
  → Saves to MongoDB, then indexes schema + descriptions to Qdrant in the background.
```

The `table_descriptions` field on the create endpoint is how the two calls are
linked — pass back the descriptions (edited or as-is) from the preview response.

---

### POST `/db-connections/preview` — Step 1

Connect to the database, introspect the schema, and generate an LLM description
for every table or collection. **Nothing is saved.** Use this to show the user
their database before they commit.

Requires **`create_db_connection`** permission.

> **Large-DB safety:** descriptions are generated for at most **100**
> tables per call. All tables still appear in the response — the `truncated`
> field signals when the limit was hit. Descriptions are generated in parallel
> batches of 10 (max 3 concurrent LLM calls) so large schemas complete quickly.

**Request body**

```json
{
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "connection_string": "postgresql://user:secret@dbhost:5432/mydb"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `organization_id` | string | yes | RBAC-checked against caller's org |
| `connection_string` | string | yes | must be reachable; never stored |

**Response `200 OK`**

Same shape as `GET /db-connections/{conn_id}/schema` with a `description` field
added inside every table/collection entry, plus three top-level metadata fields.

```json
{
  "kind": "sql",
  "dialect": "postgresql",
  "table_count": 12,
  "described_count": 12,
  "truncated": false,
  "tables": {
    "users": {
      "description": "Stores registered user accounts and authentication credentials.",
      "columns": [
        { "name": "id",    "type": "INTEGER", "nullable": false, "default": "" },
        { "name": "email", "type": "VARCHAR", "nullable": false, "default": "" }
      ],
      "indexes": [{ "name": "users_pkey", "columns": ["id"], "unique": true }],
      "foreign_keys": []
    },
    "orders": {
      "description": "Tracks customer purchase orders and their fulfilment status.",
      "columns": [
        { "name": "id",      "type": "INTEGER", "nullable": false, "default": "" },
        { "name": "user_id", "type": "INTEGER", "nullable": false, "default": "" }
      ],
      "indexes": [],
      "foreign_keys": [{ "column": ["user_id"], "references_table": "users", "references_column": ["id"] }]
    }
  },
  "views": {},
  "enums": []
}
```

For **MongoDB**, `description` is added inside each collection entry under
`databases.{db_name}.{collection_name}`. MongoDB keys for `table_descriptions`
are `db.collection` (e.g. `"mydb.users"`).

| Metadata field | Type | Meaning |
|---|---|---|
| `table_count` | int | Total tables/collections found in the database |
| `described_count` | int | How many received an LLM-generated description |
| `truncated` | bool | `true` when `table_count > 100`; only the first 100 were described |

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | Database is unreachable or credentials are wrong |

---

### POST `/db-connections` — Step 2

Save the database connection. The schema is re-fetched from the live database to
confirm the connection is still valid. Pass `table_descriptions` (from the
preview response) to persist descriptions in the same request — no extra call needed.

After saving to MongoDB, schema + descriptions are indexed to Qdrant in a
background task. The Qdrant indexer uses descriptions already present in the
schema and only calls the LLM for any tables that are still missing one.

Requires **`create_db_connection`** permission.

**Request body**

```json
{
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "connection_string": "postgresql://user:secret@dbhost:5432/mydb",
  "table_descriptions": {
    "users":  "Stores registered user accounts and authentication credentials.",
    "orders": "Tracks customer purchase orders and their fulfilment status."
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `organization_id` | string | yes | must be a valid, non-deleted organization; RBAC-checked against caller's org |
| `connection_string` | string | yes | encrypted at rest; must be reachable |
| `table_descriptions` | object | no | `{table_name: description}` from the preview response; merged into the stored schema before Qdrant indexing. For MongoDB use `db.collection` keys. |

**Response `201 Created`** — connection string masked; schema not included here,
read it via `GET /db-connections/{conn_id}/schema`.

```json
{
  "id": "6a217c707dc7370a4b7d825e",
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "connection_string": "postgresql://****",
  "created_at": "2026-06-04T13:24:00Z"
}
```

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | Database is unreachable or credentials are wrong |

---

### GET `/db-connections`

List all DB connections for the caller's org (connection strings masked).
**Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `DbConnectionPublic` objects.

---

### GET `/db-connections/{conn_id}`

Fetch a single DB connection by id (connection string masked).

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No connection with that id (or malformed id) |

---

### GET `/db-connections/{conn_id}/schema`

Return the stored database schema. If `table_descriptions` were saved on create
(or updated via `POST /db-connections/{conn_id}/descriptions`), each table entry
includes a `description` field.

**Response `200 OK`** — shape depends on the database kind:

```json
// SQL (PostgreSQL / MySQL / SQLite) — description present when saved
{
  "kind": "sql",
  "dialect": "postgresql",
  "tables": {
    "users": {
      "description": "Stores registered user accounts and authentication credentials.",
      "columns": [
        { "name": "id",    "type": "INTEGER", "nullable": false, "default": "" },
        { "name": "email", "type": "VARCHAR", "nullable": false, "default": "" }
      ],
      "indexes":      [{ "name": "users_pkey", "columns": ["id"], "unique": true }],
      "foreign_keys": []
    }
  },
  "views": {
    "active_users": {
      "columns": [
        { "name": "id",    "type": "INTEGER" },
        { "name": "email", "type": "VARCHAR" }
      ]
    }
  },
  "enums": [{ "name": "user_role", "values": ["admin", "manager", "user"] }],
  "supabase": true
}

// MongoDB — description present when saved
{
  "kind": "mongo",
  "databases": {
    "mydb": {
      "users": {
        "description": "Stores user documents including profile and preferences.",
        "fields": {
          "_id":   { "types": ["object"] },
          "email": { "types": ["string"] },
          "age":   { "types": ["int", "null"] }
        },
        "document_count": 1500,
        "indexes": [{ "name": "_id_", "keys": [["_id", 1]], "unique": true }]
      }
    }
  }
}
```

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No connection with that id |

---

### PUT `/db-connections/{conn_id}`

Update a DB connection. If `connection_string` is provided it is re-encrypted
**and the schema is re-fetched** (rejected with `400` if the new connection is
unreachable). Existing `description` fields on tables are preserved unless
overwritten by `POST /db-connections/{conn_id}/descriptions`.

**Request body** (all fields optional)

```json
{ "connection_string": "mysql://root:pw@host:3306/db" }
```

**Response `200 OK`** — updated `DbConnectionPublic` (masked).

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | No fields provided, or new connection is unreachable |
| `404 Not Found` | No connection with that id |

---

### DELETE `/db-connections/{conn_id}`

Soft-delete a DB connection (marks `is_deleted=true`; not physically removed).
Also removes the connection's vectors from Qdrant in a background task.

**Response `204 No Content`** — empty body.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No connection with that id |

---

### POST `/db-connections/{conn_id}/descriptions`

Update table descriptions on an **already-saved** connection. Use this when
descriptions need to be added or corrected after the connection was created.

For the initial creation flow, prefer passing `table_descriptions` directly to
`POST /db-connections` — this endpoint is for post-creation updates only.

After merging into the stored schema, re-indexes Qdrant in the background using
the updated descriptions.

Requires **`edit_db_connection`** permission.

**Request body**

```json
{
  "table_descriptions": {
    "users":  "Stores registered user accounts and authentication credentials.",
    "orders": "Tracks customer purchase orders and their fulfilment status."
  }
}
```

For **MongoDB** use `db.collection` composite keys:

```json
{
  "table_descriptions": {
    "mydb.users":  "Stores user documents including profile and preferences.",
    "mydb.events": "Append-only log of application-level events."
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `table_descriptions` | object | yes | `{table_name: description}` — SQL: plain table name, MongoDB: `db.collection`. Unknown keys are silently ignored. |

**Response `204 No Content`** — empty body on success.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No connection with that id |

---

## Tools (CRUD)

All routes require a valid Bearer token and the matching permission. Non–super-admins are
scoped to their own organization's tools.

> Note: `tool_id` references a `tool_registry` entry (the global catalog).

### POST `/tools`

Create a tool. Requires **`create_tool`** permission (`org_admin`, `super_admin`, or
any role granted this flag).
`organization_id` is required in the request body. `tool_id` is validated against the tool registry — it must be a valid ObjectId referencing an **active**, non-deleted registry entry.

**Request body**

```json
{
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "agent_id": "665f2a118a3b4c0012a9d4f0",
  "user_description": "Looks up a customer's recent orders",
  "tool_id": "6a22a84202b6e3106b600a9d",
  "name": "Customer DB Query"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `organization_id` | string | **yes** | must be a valid, non-deleted org; RBAC-checked against caller's org |
| `agent_id` | string | **yes** | the agent this tool belongs to |
| `user_description` | string | **yes** | |
| `tool_id` | string | **yes** | ObjectId of an active `tool_registry` entry — validated on create |
| `name` | string | no | only stored when provided |

**Response `201 Created`**

```json
{
  "id": "6a2180119c1f2a3b4c5d6e7f",
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "agent_id": "665f2a118a3b4c0012a9d4f0",
  "name": "Customer DB Query",
  "user_description": "Looks up a customer's recent orders",
  "tool_id": "6a22a84202b6e3106b600a9d",
  "created_at": "2026-06-04T13:40:00Z"
}
```

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | `tool_id` is not an active tool registry entry |
| `422 Unprocessable Entity` | `tool_id` is not a valid ObjectId |

---

### GET `/tools`

List tools. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `ToolPublic` objects.

---

### GET `/tools/org/{org_id}`

List tools belonging to a specific organization. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)). Requires **`view`** permission and access to `org_id`.

**Auth required:** Yes (`Authorization: Bearer <token>`)

**Path params:** `org_id` — the organization's `_id` (string).

**Query params:** `page`, `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `ToolPublic` objects.

**Errors**

| Status | When |
|---|---|
| `403 Forbidden` | `org_id` is not the caller's organization (non–super-admin) |

Example: `GET /tools/org/665f1c2e8a3b4c0012a9d4e1?page=1&page_size=10`

---

### GET `/tools/{tool_id}`

Fetch a single tool by id.

> `tool_id` here is the tool document's own `_id`, not the registry reference.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No tool with that id (or malformed id) |

---

### PUT `/tools/{tool_id}`

Update a tool. Only provided fields are changed.

**Request body** (all fields optional)

```json
{
  "name": "Customer DB Query v2",
  "user_description": "Updated description",
  "tool_id": "665fdeadbeef000000000002"
}
```

**Response `200 OK`** — updated `ToolPublic` object.

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | No fields provided to update |
| `404 Not Found` | No tool with that id |

---

### DELETE `/tools/{tool_id}`

Soft-delete a tool (marks `is_deleted=true`; not physically removed).

**Response `204 No Content`** — empty body.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No tool with that id |

---

## Tool Registry (CRUD)

The tool registry is the global **catalog** of tool types. All routes require a valid
Bearer token. List is paginated; delete is a soft delete.

| Method | Who can call |
|---|---|
| `GET` | Any role with **`view`** permission |
| `POST`, `PUT`, `DELETE` | **`super_admin` only** |

### POST `/tool-registry`

Create a registry entry. **`super_admin` only.**

**Request body**

```json
{
  "name": "HTTP Request",
  "type": "http",
  "description": "Generic outbound HTTP call",
  "is_active": true,
  "tool_schema": {
    "type": "object",
    "properties": { "query": { "type": "string" } },
    "required": ["query"]
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | **yes** | |
| `type` | string | **yes** | e.g. `http`, `db`, `rag` |
| `description` | string | no | |
| `is_active` | bool | no | Defaults to `true` |
| `tool_schema` | object (JSON) | no | Arbitrary JSON schema describing the tool's inputs |

**Response `201 Created`**

```json
{
  "id": "6a22a84202b6e3106b600a9d",
  "name": "HTTP Request",
  "type": "http",
  "description": "Generic outbound HTTP call",
  "is_active": true,
  "tool_schema": {
    "type": "object",
    "properties": { "query": { "type": "string" } },
    "required": ["query"]
  },
  "created_at": "2026-06-05T12:00:00Z"
}
```

---

### GET `/tool-registry`

List registry entries. **Paginated** — accepts `page` and `page_size` (see [Pagination](#pagination)).

**Response `200 OK`** — `Page` envelope whose `items` are `ToolRegistryPublic` objects.

---

### GET `/tool-registry/{registry_id}`

Fetch a single registry entry by id.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No entry with that id (or malformed id) |

---

### PUT `/tool-registry/{registry_id}`

Update a registry entry. **`super_admin` only.** Only provided fields are changed.

**Request body** (all fields optional)

```json
{
  "name": "HTTP Request v2",
  "type": "http",
  "description": "Updated",
  "is_active": false
}
```

**Response `200 OK`** — updated `ToolRegistryPublic` object.

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | No fields provided to update |
| `404 Not Found` | No entry with that id |

---

### DELETE `/tool-registry/{registry_id}`

Soft-delete a registry entry. **`super_admin` only** (marks `is_deleted=true`; not physically removed).

**Response `204 No Content`** — empty body.

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No entry with that id |

---

## Connectors

The connector registry is the global **catalog** of connector types (Slack, Gmail, Jira, …).
Each user/org can connect their own instance of a catalog entry (OAuth, bot token, or API key),
tracked separately from the catalog itself. Unlike most other resources, connector routes are
mounted at `/api/connectors/**` (note the `/api` prefix) instead of at the root.

| Method | Who can call |
|---|---|
| `GET /registry`, `GET /{connector_id}/setup\|configure\|auth-url\|status`, `POST /{connector_id}/configure`, `DELETE /{connector_id}/configure`, `POST /{connector_id}/disconnect`, `GET /{connector_id}/actions/{action}` | Any authenticated user |
| `GET /registry/admin`, `PATCH /registry/{connector_id}/visibility`, `PATCH /registry/{connector_id}/active` | **`super_admin` only** |
| `GET /api/auth/connector/callback`, `POST /api/connectors/slack/webhook` | Public (no auth — OAuth redirect / Slack HMAC-verified webhook) |

### GET `/api/connectors/registry`

List **visible** connector catalog entries (client-facing). Returns a bare array of
`ConnectorRegistryItem`.

---

### GET `/api/connectors/registry/admin`

List **all** connector catalog entries, including hidden ones. **`super_admin` only.**
Paginated (see [Pagination](#pagination)) with extra filters:

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` | int | `1` | 1-based |
| `page_size` | int | `10` | `1`–`200` |
| `q` | string | `""` | Search term (name, description, category) |
| `category` | string | `""` | Filter by exact category name |

**Response `200 OK`** — `ConnectorRegistryPage` envelope.

---

### PATCH `/api/connectors/registry/{connector_id}/visibility`

Show or hide a connector in the catalog. **`super_admin` only.**

**Request body**

```json
{ "is_visible": false }
```

**Response `200 OK`** — updated `ConnectorRegistryItem`.

---

### PATCH `/api/connectors/registry/{connector_id}/active`

Enable or disable a connector in the catalog. **`super_admin` only.** This only flips the
catalog-level `is_active` flag on `connector_registry` — it does **not** affect any user's
existing connection (see `connected` status under `GET /{connector_id}/status` below).

**Request body**

```json
{ "is_active": false }
```

**Response `200 OK`** — updated `ConnectorRegistryItem`.

**Errors**

| Status | When |
|---|---|
| `400 Bad Request` | Malformed `connector_id` |
| `404 Not Found` | No entry with that id |

---

### GET `/api/connectors/{connector_id}/setup`

Return setup info needed by the client to configure this connector (whether credentials
already exist, the OAuth redirect URI to register with the provider, etc.).

**Response `200 OK`** — `ConnectorSetupInfo`:

```json
{
  "has_credentials": false,
  "client_id": null,
  "redirect_uri": "https://api.example.com/api/auth/connector/callback",
  "provider_id": "slack",
  "auth_type": "oauth2"
}
```

---

### POST `/api/connectors/{connector_id}/configure`

Save credentials for this connector (client_id/secret for OAuth2, or a bot token / API key).
For `bot_token`/`api_key` connectors this immediately marks the connection as `connected`
(no OAuth redirect needed).

**Request body** — fields depend on `auth_type` (`oauth2` needs `client_id`/`client_secret`,
`bot_token` needs `bot_token`, `api_key` needs `api_key`; `subdomain`/`signing_secret` optional):

```json
{
  "client_id": "...",
  "client_secret": "...",
  "signing_secret": "...",
  "bot_token": "...",
  "api_key": "...",
  "subdomain": "..."
}
```

**Response `200 OK`** — `{ "message": "Credentials saved successfully." }`

---

### DELETE `/api/connectors/{connector_id}/configure`

Remove stored credentials for this connector.

**Response `200 OK`** — `{ "message": "Credentials removed." }`

---

### GET `/api/connectors/{connector_id}/auth-url`

Build the OAuth authorization URL to redirect the user to. If already connected, returns
`already_connected: true` and an empty `url` instead.

**Response `200 OK`** — `AuthUrlResponse`:

```json
{ "url": "https://slack.com/oauth/v2/authorize?...", "already_connected": false }
```

---

### GET `/api/auth/connector/callback`

Public. Universal OAuth redirect target — the `state` query param links back to the
connector + owner. Not called directly by clients; the provider redirects the user's
browser here after authorization, and it redirects onward to
`{FRONTEND_URL}/client/connectors?connector=connected&provider=...` (or `...=error&reason=...`
on failure).

---

### GET `/api/connectors/{connector_id}/status`

Get the live connection status for the caller's connector instance. Re-validates the stored
token (refreshing if expired) — if the token can no longer be refreshed, the connection is
demoted to disconnected on the fly.

**Response `200 OK`** — `ConnectorStatus`:

```json
{ "connected": true, "connection_id": "6a22a84202b6e3106b600a9d", "metadata": {} }
```

---

### POST `/api/connectors/{connector_id}/disconnect`

Disconnect the caller's connector instance (deletes stored tokens, marks disconnected).

**Response `200 OK`** — `{ "message": "Connector disconnected." }`

---

### GET `/api/connectors/{connector_id}/actions/{action}`

Run a connector-defined action (e.g. list channels, send a message) using the caller's
stored credentials. Response shape is action-specific.

---

### POST `/api/connectors/slack/webhook`

Public. Slack Events API ingress. Verifies the `X-Slack-Signature` HMAC-SHA256 header before
processing. Requires `connector_id` and `owner_id` query params (set when registering the
webhook URL with Slack). Handles the `url_verification` challenge automatically.

**Errors**

| Status | When |
|---|---|
| `403 Forbidden` | Invalid Slack signature |

---

## Chat

LangGraph-backed conversational endpoints. Require authentication; the supervisor
session/message endpoints need **`create_chat`** permission (`user` and `org_manager`
roles cannot start sessions or send messages). The **direct** endpoint below
(`POST /chat`) only requires authentication.

### POST `/chat`

Send a message **directly to a single agent**, bypassing the supervisor/router. The
agent runs on its own; no session needs to be created first (a session is created/reused
internally and its id is returned). Requires authentication only (any authenticated role).

**Request body** — `DirectChatRequest`

```json
{
  "agent_id": "665f2a118a3b4c0012a9d4f0",
  "message": "What are my open tickets?"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `agent_id` | string | yes | The agent to talk to directly |
| `message` | string | yes | The user message |

**Response `200 OK`** — `DirectChatResponse`

```json
{
  "reply": "You have 3 open tickets: ...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "trace_id": null
}
```

| Field | Type | Notes |
|---|---|---|
| `reply` | string | The agent's response text |
| `session_id` | string | The session the turn was recorded under (created/reused internally) |
| `trace_id` | string \| null | Langfuse trace id when tracing is enabled |

---

### POST `/chat/session`

Initialize a LangGraph session for the caller's organization. Requires **`create_chat`**.

**Response `201 Created`** — `SessionPublic` with `thread_id`, `organization_id`, `name`, and agent list.

```json
{
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "name": null,
  "available_agents": [
    {
      "agent_id": "665f2a118a3b4c0012a9d4f0",
      "name": "Support Bot",
      "description": "You are a helpful customer support assistant.",
      "tool_count": 2
    }
  ],
  "created_at": "2026-06-16T10:00:00Z"
}
```

> `name` is `null` on creation and is automatically generated by the LLM after the first message is sent.

**Errors**

| Status | When |
|---|---|
| `403 Forbidden` | Missing `create_chat` permission |
| `404 Not Found` | Organization has no agents |

### POST `/chat/message`

Send a message into an existing session. Requires **`create_chat`**.

**Request body**

```json
{
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "What are my open tickets?"
}
```

**Response `200 OK`**

```json
{
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "response": "You have 3 open tickets: ...",
  "messages_count": 6
}
```

---

### GET `/chat/sessions`

List all chat sessions for the authenticated user in their organization, ordered newest first. Requires **`create_chat`**.

**Auth required:** Yes

**Response `200 OK`** — array of `SessionListItem`

```json
[
  {
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "organization_id": "665f1c2e8a3b4c0012a9d4e1",
    "user_id": "665f1d9a8a3b4c0012a9d4e2",
    "name": "Open Tickets Overview",
    "epoch": 1,
    "agent_ids": ["665f2a118a3b4c0012a9d4f0"],
    "created_at": "2026-06-16T10:00:00Z"
  }
]
```

| Field | Type | Notes |
|---|---|---|
| `thread_id` | string | UUID — pass to `/chat/message` and `/chat/sessions/{thread_id}/history` |
| `organization_id` | string | The session's org |
| `user_id` | string | The owning user |
| `name` | string \| null | LLM-generated title set after the first message; `null` for sessions with no messages yet |
| `epoch` | int | Current LangGraph epoch (increments when conversation is compressed) |
| `agent_ids` | string[] | Agent IDs available in this session |
| `created_at` | datetime | Session creation time |

> Sessions are scoped to the caller's `organization_id` and `user_id` from the JWT — a user can only see their own sessions.

---

### GET `/chat/sessions/{thread_id}/history`

Return the full conversation history for a session, broken down per agent. Requires **`create_chat`**.

**Auth required:** Yes

**Path params:** `thread_id` — UUID returned when the session was created.

**Response `200 OK`** — `SessionHistoryResponse`

```json
{
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "user_id": "665f1d9a8a3b4c0012a9d4e2",
  "name": "Open Tickets Overview",
  "epoch": 2,
  "agents": [
    {
      "agent_id": "665f2a118a3b4c0012a9d4f0",
      "total_messages": 12,
      "total_summaries": 1,
      "conversations": [
        {
          "type": "summary",
          "content": "The user asked about open tickets. Agent listed 3 tickets.",
          "timestamp": "2026-06-16T10:05:00Z"
        },
        {
          "type": "turn",
          "human_message": "Can you close ticket #42?",
          "agent_message": "Ticket #42 has been closed.",
          "timestamp": "2026-06-16T10:10:00Z",
          "tool_called": true,
          "tool_name": "close_ticket"
        }
      ],
      "created_at": "2026-06-16T10:00:00Z",
      "updated_at": "2026-06-16T10:10:00Z"
    }
  ],
  "created_at": "2026-06-16T10:00:00Z"
}
```

**Conversation entry types**

Each item in `conversations` is one of:

| Type | Fields | Notes |
|---|---|---|
| `"turn"` | `human_message`, `agent_message`, `timestamp`, `tool_called`, `tool_name` | One Q&A exchange |
| `"summary"` | `content`, `timestamp` | Compressed summary of earlier turns (replaces them when the compression threshold is reached) |

**Errors**

| Status | When |
|---|---|
| `404 Not Found` | No session with that `thread_id` in the caller's org |

---

## MCP Servers

Register Model Context Protocol (MCP) servers and attach them to an agent so their tools
are available at the **sub-agent level**. MCP instances are **agent-scoped** — every
instance belongs to both an `organization_id` and an `agent_id`. All endpoints require
authentication and are scoped to the caller's organization; the permission column reuses
the **tool** flags (`view_tool` / `create_tool` / `edit_tool` / `delete_tool`).

A connection target is specified by **either** a `connection_string` (a URL/command for an
stdio / SSE / WebSocket transport) **or** a `registry_key` referencing a catalog entry. The
field name is `connection_string`, **not** `url`.

### POST `/mcp-servers`

Connect an MCP server to an agent: probes the connection, discovers and caches its tools.
Requires **`create_tool`**.

**Request body** — `McpServerCreate`

```json
{
  "organization_id": "665f1c2e8a3b4c0012a9d4e1",
  "agent_id": "665f2a118a3b4c0012a9d4f0",
  "connection_string": "https://mcp.example.com/sse"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `organization_id` | string | **yes** | Must match the caller's org (super_admin may cross) |
| `agent_id` | string | **yes** | The agent the MCP tools attach to |
| `connection_string` | string \| null | one of | Transport URL/command — **use this, not `url`** |
| `registry_key` | string \| null | one of | Catalog key (from `GET /mcp-servers/catalog`) instead of a raw connection string |
| `placeholders` | object\<string,string\> \| null | no | Substitutions injected into a catalog template |
| `user_description` | string \| null | no | Free-text label |
| `token` | string \| null | no | Bearer token for the server, if it needs one |
| `headers` | object\<string,string\> \| null | no | Extra connection headers |
| `timeout` | number | no | Connection timeout (seconds) |

> Provide **`connection_string` OR `registry_key`** — supplying neither (or only
> `organization_id`/`agent_id`) is the most common mistake; both `organization_id` and
> `agent_id` are mandatory.

**Response `201 Created`** — `McpServerPublic` (`id`, `organization_id`, `agent_id`,
`name`, `transport`, `tools`, `tool_count`, `status`, `last_error`, `discovered_at`,
`is_active`, `created_at`, …).

### GET `/mcp-servers`

List MCP instances for the caller's org (paginated). Requires **`view_tool`**.

### GET `/mcp-servers/agent/{agent_id}`

List MCP instances attached to a specific agent (paginated). Requires **`view_tool`**.

### GET `/mcp-servers/{server_id}`

Get a single MCP instance. Requires **`view_tool`**.

### PUT `/mcp-servers/{server_id}`

Update an instance (`McpServerUpdate`: `user_description`, `connection_string`, `token`,
`headers`, `timeout`, `is_active`). Changing `connection_string` re-probes the server.
Requires **`edit_tool`**.

### POST `/mcp-servers/{server_id}/discover`

Re-connect to the server and refresh its cached tool list. Requires **`edit_tool`**.

### DELETE `/mcp-servers/{server_id}`

Soft-delete an MCP instance. Requires **`delete_tool`**. Returns `204 No Content`.

### GET `/mcp-servers/catalog`

Browse connectable MCP servers (curated seed + official registry). Requires **`view_tool`**.
Optional `?q=` search term. Returns `McpCatalogEntry[]` (`key`, `name`, `description`,
`transport`, `connection_string`, `requires`, …).

### POST `/mcp-servers/test-connection`

Probe a connection **without saving anything** and report the tools it exposes. Requires
**`view_tool`**.

**Request body** — `McpTestConnectionRequest`

```json
{ "connection_string": "https://mcp.example.com/sse" }
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `connection_string` | string | **yes** | Target to probe — **not `url`** |
| `token` | string \| null | no | Bearer token if required |
| `headers` | object\<string,string\> \| null | no | Extra headers |
| `timeout` | number | no | Connection timeout (seconds) |

**Response `200 OK`** — `McpTestConnectionResult`: `{ "ok": bool, "transport": str|null,
"tools": [...], "tool_count": int, "error": str|null }`. A reachable server returns
`ok: true`; an unreachable one returns `ok: false` with `error` populated (still `200`).

### POST `/mcp-servers/oauth/start`

Begin OAuth authorization for an OAuth-protected remote MCP server (e.g. Jira). Requires
**`create_tool`**. Body — `McpOAuthStartRequest` (`organization_id`, `agent_id`,
`connection_string` required; optional `user_description`, `scope`). Returns
`{ "authorization_url": "...", "state": "..." }`; open the URL in a browser to consent.

### GET `/mcp-servers/oauth/callback`

OAuth redirect target (**no auth** — the opaque `state` is the CSRF protection). The
provider redirects here with `?code=&state=`; it finalizes the connection and returns an
HTML page (or redirects to `MCP_OAUTH_SUCCESS_REDIRECT` if configured).

---

## Prompt Generator

Generate optimized system prompts for agents using LLM (`gpt-5.4-nano`).

### POST `/generate-prompt`

Generates an optimized system prompt for an agent given its name and description.

**Auth required:** No

**Request body**

```json
{
  "agent_name": "Support Bot",
  "agent_description": "Helps users troubleshoot common issues and escalates complex problems"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `agent_name` | string | yes | The name of the agent |
| `agent_description` | string | yes | Description of the agent's purpose and behavior |

**Response `200 OK`**

```json
{
  "prompt": "You are Support Bot, an AI assistant specialized in troubleshooting...",
  "model": "gpt-5.4-nano"
}
```

**Errors**

| Status | When |
|---|---|
| `500 Internal Server Error` | LLM call failed (e.g. invalid API key, network error) |

---

## Tracing

Langfuse observability endpoints. All require authentication and **`view`** permission.
Results are scoped to the caller's `organization_id`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/traces` | List traces for the org |
| `GET` | `/traces/stats` | Aggregate cost/token stats |
| `GET` | `/traces/{trace_id}` | Trace detail with observation waterfall |
| `GET` | `/sessions` | List conversation sessions |
| `GET` | `/agents/{agent_id}/traces` | Traces for one agent |
| `GET` | `/agents/{agent_id}/stats` | Stats for one agent |

---

## Endpoint summary

Permission column uses shorthand: **V** = `view`, **C** = `create`, **E** = `edit`,
**D** = `delete`, **SA** = `super_admin` only.
Suffix denotes the resource, e.g. **V-org** = `view_org`, **C-user** = `create_user`,
**E-agent** = `edit_agent`, **D-tool** = `delete_tool`.
See [Roles & Permissions](#roles--permissions).

| Method | Path | Auth | Permission | Description |
|---|---|---|---|---|
| POST | `/auth/register` | No | — | Self-service registration (auto-org/admin) |
| POST | `/auth/login` | No | — | Log in, return JWT |
| POST | `/auth/logout` | Yes | — | Stateless logout |
| POST | `/auth/users` | Yes | C-user | Provision a user against an org, return JWT |
| GET | `/auth/me` | Yes | — | Current user |
| GET | `/auth/me/permissions` | Yes | — | Resolved permissions (debug) |
| POST | `/auth/forgot-password` | No | — | Request a password-reset OTP |
| POST | `/auth/verify-otp` | No | — | Verify a password-reset OTP |
| POST | `/auth/reset-password` | No | — | Reset password with a valid OTP |
| POST | `/organizations` | Yes | C-org | Create organization (super_admin by default) |
| GET | `/organizations` | Yes | V-org | List organizations |
| GET | `/organizations/{org_id}` | Yes | V-org | Get one organization |
| PUT | `/organizations/{org_id}` | Yes | E-org | Update organization |
| DELETE | `/organizations/{org_id}` | Yes | D-org | Delete organization |
| GET | `/organizations/{org_id}/agents` | Yes | V-org | List agents for an organization |
| GET | `/organizations/{org_id}/tools` | Yes | V-org | List tools for an organization |
| GET | `/organizations/{org_id}/db-connections` | Yes | V-org | List DB connections for an organization |
| GET | `/organizations/{org_id}/users` | Yes | V-org | List users for an organization |
| GET | `/users` | Yes | SA | List all users (paginated, super admin only) |
| POST | `/agents` | Yes | C-agent | Create agent (org_id in body) |
| GET | `/agents` | Yes | V-agent | List agents |
| GET | `/agents/org/{org_id}` | Yes | V-agent | List agents for a specific org |
| GET | `/agents/{agent_id}` | Yes | V-agent | Get one agent |
| PUT | `/agents/{agent_id}` | Yes | E-agent | Update agent |
| DELETE | `/agents/{agent_id}` | Yes | D-agent | Delete agent |
| POST | `/db-connections/preview` | Yes | C-db | **Step 1** — fetch schema + LLM descriptions, nothing saved |
| POST | `/db-connections` | Yes | C-db | **Step 2** — save connection + descriptions to MongoDB, index to Qdrant |
| GET | `/db-connections` | Yes | V-db | List DB connections (paginated, strings masked) |
| GET | `/db-connections/{conn_id}` | Yes | V-db | Get one DB connection |
| GET | `/db-connections/{conn_id}/schema` | Yes | V-db | Get stored schema (includes descriptions if saved) |
| PUT | `/db-connections/{conn_id}` | Yes | E-db | Update connection string (re-fetches schema) |
| DELETE | `/db-connections/{conn_id}` | Yes | D-db | Soft-delete connection, removes Qdrant vectors |
| POST | `/db-connections/{conn_id}/descriptions` | Yes | E-db | Post-creation: update descriptions + re-index Qdrant |
| POST | `/tools` | Yes | C-tool | Create tool (org_id in body) |
| GET | `/tools` | Yes | V-tool | List tools |
| GET | `/tools/org/{org_id}` | Yes | V-tool | List tools for a specific org |
| GET | `/tools/{tool_id}` | Yes | V-tool | Get one tool |
| PUT | `/tools/{tool_id}` | Yes | E-tool | Update tool |
| DELETE | `/tools/{tool_id}` | Yes | D-tool | Delete tool |
| POST | `/tool-registry` | Yes | SA | Create tool registry entry |
| GET | `/tool-registry` | Yes | V-reg | List tool registry entries |
| GET | `/tool-registry/{registry_id}` | Yes | V-reg | Get one registry entry |
| PUT | `/tool-registry/{registry_id}` | Yes | SA | Update registry entry |
| DELETE | `/tool-registry/{registry_id}` | Yes | SA | Delete registry entry |
| GET | `/api/connectors/registry` | Yes | — | List visible connector catalog entries |
| GET | `/api/connectors/registry/admin` | Yes | SA | List all connector catalog entries (paginated) |
| PATCH | `/api/connectors/registry/{connector_id}/visibility` | Yes | SA | Show/hide a connector in the catalog |
| PATCH | `/api/connectors/registry/{connector_id}/active` | Yes | SA | Enable/disable a connector in the catalog |
| GET | `/api/connectors/{connector_id}/setup` | Yes | — | Get setup info (credentials present?, redirect URI) |
| POST | `/api/connectors/{connector_id}/configure` | Yes | — | Save credentials (OAuth client, bot token, or API key) |
| DELETE | `/api/connectors/{connector_id}/configure` | Yes | — | Remove stored credentials |
| GET | `/api/connectors/{connector_id}/auth-url` | Yes | — | Build OAuth authorization URL |
| GET | `/api/auth/connector/callback` | No | — | OAuth redirect target (state = connector + owner) |
| GET | `/api/connectors/{connector_id}/status` | Yes | — | Get live connection status (re-validates token) |
| POST | `/api/connectors/{connector_id}/disconnect` | Yes | — | Disconnect caller's connector instance |
| GET | `/api/connectors/{connector_id}/actions/{action}` | Yes | — | Run a connector-defined action |
| POST | `/api/connectors/slack/webhook` | No | — | Slack Events API ingress (HMAC-verified) |
| POST | `/generate-prompt` | No | — | Generate agent system prompt via LLM |
| POST | `/chat` | Yes | — | Direct 1:1 chat with a single agent (no supervisor) |
| POST | `/chat/session` | Yes | C-chat | Start LangGraph chat session |
| POST | `/chat/message` | Yes | C-chat | Send chat message |
| GET | `/chat/sessions` | Yes | C-chat | List caller's chat sessions (newest first) |
| GET | `/chat/sessions/{thread_id}/history` | Yes | C-chat | Full per-agent conversation history for a session |
| POST | `/mcp-servers` | Yes | C-tool | Attach an MCP server to an agent (probe + cache tools) |
| GET | `/mcp-servers` | Yes | V-tool | List MCP instances for the org |
| GET | `/mcp-servers/agent/{agent_id}` | Yes | V-tool | List MCP instances for one agent |
| GET | `/mcp-servers/{server_id}` | Yes | V-tool | Get one MCP instance |
| PUT | `/mcp-servers/{server_id}` | Yes | E-tool | Update an MCP instance (re-probes on connection change) |
| POST | `/mcp-servers/{server_id}/discover` | Yes | E-tool | Refresh an instance's cached tool list |
| DELETE | `/mcp-servers/{server_id}` | Yes | D-tool | Soft-delete an MCP instance |
| GET | `/mcp-servers/catalog` | Yes | V-tool | Browse connectable MCP servers |
| POST | `/mcp-servers/test-connection` | Yes | V-tool | Probe a connection without saving |
| POST | `/mcp-servers/oauth/start` | Yes | C-tool | Begin OAuth authorization for a remote MCP server |
| GET | `/mcp-servers/oauth/callback` | No | — | OAuth redirect target (state = CSRF protection) |
| GET | `/traces` | Yes | V-trace | List traces |
| GET | `/traces/stats` | Yes | V-trace | Trace aggregate stats |
| GET | `/traces/{trace_id}` | Yes | V-trace | Trace detail |
| GET | `/sessions` | Yes | V-trace | List sessions |
| GET | `/agents/{agent_id}/traces` | Yes | V-trace | Agent traces |
| GET | `/agents/{agent_id}/stats` | Yes | V-trace | Agent stats |

---

## Example flow (curl)

Self-service `/auth/register` creates an organization and an admin user in one step, so the
returned token already has full CRUD in that org. (To add more users to an existing org, an
authorized caller uses `POST /auth/users` with a `create_user` token.)

```bash
# 1. Register (auto-creates an org + admin user, returns a JWT)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Jane","email":"jane@example.com","password":"Secure123"}'

# 2. Log in (grab access_token from response)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"jane@example.com","password":"Secure123"}' | jq -r .access_token)

# 3. Create an organization (requires create permission; updates your organization_id)
curl -X POST http://localhost:8000/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","description":"Manufacturer of everything"}'

# 4. Create an agent (organization_id & created_by come from the token)
curl -X POST http://localhost:8000/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Support Bot","prompt":"You are a helpful assistant.","guardrails":"Never share PII."}'

# 5. List tools in your org (view permission — all roles except unauthenticated)
curl -X GET "http://localhost:8000/organizations/<org_id>/tools?page=1" \
  -H "Authorization: Bearer $TOKEN"
```
