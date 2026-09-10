# ONE-AI — Hands-On Swagger Testing Guide

A complete, **do-it-yourself** walkthrough for testing **every** endpoint the system
offers from the Swagger UI at **http://localhost:8000/docs** — auth, RBAC, organizations,
users, tool registry, tools, **agents (with prompts + guardrails)**, DB connections,
**MCP servers (with connection strings)**, the **supervisor chat routing flow**, direct
chat, prompt generation, and tracing.

Follow it **top to bottom** — later steps reuse IDs/tokens created in earlier steps.

> Conventions
> - `<ORG_ID>`, `<AGENT_ID>`, `<TOKEN>`, etc. are placeholders — replace them with values
>   you copy out of earlier responses.
> - "Authorize 🔓" means the green **Authorize** button at the top-right of `/docs`.
> - Status codes in **bold** are what a correct call returns.

---

## 0. Prerequisites

1. Server is running and reachable:
   - `GET /` → **200** `{"message":"FastAPI is running 🚀"}`
   - `GET /mongo-check` → **200** `{"status":"MongoDB Connected ✅"}`
2. Open **http://localhost:8000/docs** (Swagger) — or `/redoc` for a read-only view.
3. Admin panel (optional, for live config/roles): **http://localhost:8000/admin**.

> **Note on the Docker dev server:** the API runs in the `fastapi_app` container with the
> source bind-mounted. uvicorn's `--reload` does **not** reliably detect edits across the
> Windows→Docker mount, so if you change code, restart it: `docker restart fastapi_app`.

---

## 1. Authentication & the Authorize button

There are three ways a token is minted. For self-service testing use **`/auth/register`**.

### 1.1 Register (self-service — creates an org + admin in one step)

`POST /auth/register` — **no auth**

```json
{
  "name": "QA Tester",
  "email": "admin@gmail.com",
  "password": "Secure123"
}
```

→ **201** `TokenResponse`:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "user": { "id": "...", "organization_id": "<ORG_ID>", "role": "org_admin", ... },
  "db_conn_ids": []
}
```

- Copy `access_token` → this is `<TOKEN>`.
- Copy `user.organization_id` → this is `<ORG_ID>`. **You will paste this into almost every
  create body below.**

> The register flow gives you an **org_admin** in a brand-new org — full CRUD inside that
> org + chat. That covers everything in this guide **except** super-admin-only operations
> (tool-registry writes, `GET /users`, cross-org). For those see §11.

### 1.2 Authorize Swagger

Click **Authorize 🔓** → paste **just the token** (Swagger adds `Bearer ` itself) → Authorize
→ Close. Every protected call now carries `Authorization: Bearer <TOKEN>`. The token
persists across page reloads.

### 1.3 Other auth endpoints to exercise

| Endpoint | Body | Expect |
|---|---|---|
| `POST /auth/login` | `{"email":"qa-owner@test.example.com","password":"Secure123"}` | **200** + token |
| `GET /auth/me` | — | **200** your user |
| `GET /auth/me/permissions` | — | **200** role + resolved permission flags (great for debugging 403s) |
| `POST /auth/logout` | — | **200** (stateless — just discard the token client-side) |
| `POST /auth/forgot-password` | `{"email":"qa-owner@test.example.com"}` | **200**; if `OTP_RETURN_IN_RESPONSE=true` the OTP is in the body |
| `POST /auth/verify-otp` | `{"email":"...","otp":"123456"}` | **200** if valid, else **400** |
| `POST /auth/reset-password` | `{"email":"...","otp":"123456","new_password":"NewSecure123"}` | **200** |

**Password rules** (for `/auth/users` & signup-shaped bodies): min **8** chars, ≥1 uppercase,
≥1 lowercase, ≥1 digit.

### 1.4 Negative auth tests (do these!)

- Call any protected endpoint with **Authorize logged out** → **401**.
- Authorize with a garbage token (`abc`) → **401**.

---

## 2. RBAC cheat-sheet (who can do what)

| Role | Scope | Can create orgs/agents/tools? | Chat? | Tool-registry writes / `GET /users`? |
|---|---|---|---|---|
| `user` | own org | ❌ (read-only) | ❌ | ❌ |
| `org_manager` | own org | edit only | ❌ | ❌ |
| `org_admin` | own org | ✅ full CRUD | ✅ | ❌ |
| `super_admin` | **all orgs** | ✅ | ✅ | ✅ |

To test 403s: provision a `user`-role account (§3.2) and retry create/chat calls with **its**
token — they should be **403**.

---

## 3. Organizations & Users

### 3.1 Organizations — `tag: organizations`

| Step | Call | Body | Expect |
|---|---|---|---|
| Create | `POST /organizations` | `{"name":"qa-test Acme","description":"QA org"}` | **201** (note: by default this is super-admin-gated; org_admin from register already has an org) |
| List | `GET /organizations?page=1&page_size=20` | — | **200** paginated envelope `{items,total,page,page_size,total_pages}` |
| Get | `GET /organizations/<ORG_ID>` | — | **200** |
| Update | `PUT /organizations/<ORG_ID>` | `{"description":"updated"}` | **200** |
| Sub-lists | `GET /organizations/<ORG_ID>/agents` · `/tools` · `/db-connections` · `/users` | — | **200** paginated |
| Delete | `DELETE /organizations/<ORG_ID>` | — | **204** (soft delete) |

**Negative tests**
- `GET /organizations/000000000000000000000000` → **404** (nonexistent).
- `GET /organizations/notanid` → **404** (malformed id).
- `GET` an org that exists but isn't yours → **403**.
- Second `DELETE` of the same org → **404**.

### 3.2 Provision more users in your org — `POST /auth/users`

Requires a token with **`create_user`** (org_admin has it). Use this to make a read-only
`user` for permission testing.

```json
{
  "organization_id": "<ORG_ID>",
  "name": "Read Only Bob",
  "email": "qa-readonly@test.example.com",
  "password": "Secure123",
  "role": "user"
}
```
→ **201** `TokenResponse` (a token for the new user). **Authorize as this token** to verify
read-only 403s, then switch back to your org_admin token.

**Negative:** call `/auth/users` while **logged out** → **401**. Omit `organization_id` → **422**.

### 3.3 `GET /users` — **super_admin only**

- With org_admin token → **403** `{"detail":"Super admin privileges required."}`.
- With super_admin token (§11) → **200** paginated list of all users.

---

## 4. Tool Registry (global catalog) — `tag: tool-registry`

The registry is the **global catalog of tool types**. **Reads** are allowed for everyone;
**writes are super-admin only**.

| Call | Permission | Body | Expect |
|---|---|---|---|
| `GET /tool-registry?page=1` | any | — | **200** paginated (browse existing seeded entries — note an entry's `id` to use as a `tool_id` in §5) |
| `GET /tool-registry/<REGISTRY_ID>` | any | — | **200** |
| `POST /tool-registry` | **super_admin** | see below | **201** as SA, **403** otherwise |
| `PUT /tool-registry/<REGISTRY_ID>` | **super_admin** | `{"description":"updated"}` | **200** SA / **403** |
| `DELETE /tool-registry/<REGISTRY_ID>` | **super_admin** | — | **204** SA / **403** |

`POST /tool-registry` body (super_admin):
```json
{
  "name": "qa-test-web-search",
  "type": "web_search",
  "description": "Search the web",
  "is_active": true,
  "tool_schema": { "query": "string" }
}
```

> If no seeded registry entries exist, run the seeder once:
> `docker exec fastapi_app uv run python -m backend.scripts.seed_tool_registry`

---

## 5. Tools (org-level instances) — `tag: tools`

A **tool** is an org+agent-scoped instance that references a **registry entry** by id and
attaches it to **one agent**. So the order is: have a registry entry (§4) → have an agent
(§6) → create the tool linking them.

`POST /tools`
```json
{
  "organization_id": "<ORG_ID>",
  "agent_id": "<AGENT_ID>",
  "tool_id": "<REGISTRY_ID>",
  "user_description": "Web search for the support agent"
}
```
→ **201**. (`tool_id` = the **registry entry id** from `GET /tool-registry`.)

| Call | Body | Expect |
|---|---|---|
| `GET /tools?page=1` | — | **200** paginated |
| `GET /tools/org/<ORG_ID>` | — | **200** tools for that org |
| `GET /tools/<TOOL_ID>` | — | **200** |
| `PUT /tools/<TOOL_ID>` | `{"user_description":"updated"}` | **200** |
| `DELETE /tools/<TOOL_ID>` | — | **204** (soft delete) |

**Negative:** `GET /tools/notanid` → **422**; `GET /tools/<nonexistent valid id>` → **404**.

---

## 6. Agents (with prompts + guardrails) — `tag: agents`

`AgentCreate` fields: **`organization_id`**, **`name`**, **`prompt`**, **`guardrails`** (all
required), and optional **`mcp_server_ids`** (array). Tools are attached via §5, **not** here.

> **To test supervisor routing in §10, create at least these three agents.** Their distinct
> `prompt`/`name`/`description` are what the supervisor uses to route a message to the right one.

### Agent A — Support Bot
```json
{
  "organization_id": "<ORG_ID>",
  "name": "Support Bot",
  "prompt": "You are Support Bot, a friendly customer-support assistant for an e-commerce store. You help users with orders, returns, refunds, shipping status, and account problems. Be concise, empathetic, and always confirm the order number before taking action.",
  "guardrails": "Never reveal another customer's personal data. Never issue a refund above $500 without escalating to a human. Do not give legal or medical advice. Refuse and redirect any request unrelated to customer support."
}
```

### Agent B — Billing Analyst
```json
{
  "organization_id": "<ORG_ID>",
  "name": "Billing Analyst",
  "prompt": "You are Billing Analyst, a finance-focused assistant. You answer questions about invoices, subscription plans, proration, taxes, payment methods, and billing cycles. Show clear breakdowns and cite the relevant amounts.",
  "guardrails": "Never expose full credit-card numbers (mask all but the last 4 digits). Do not process payments directly. Do not speculate about a customer's credit. Escalate disputes over $1,000 to a human."
}
```

### Agent C — DevOps Helper
```json
{
  "organization_id": "<ORG_ID>",
  "name": "DevOps Helper",
  "prompt": "You are DevOps Helper, a technical assistant for engineers. You help with deployments, CI/CD pipelines, Docker, Kubernetes, logs, and incident triage. Give exact commands and config snippets.",
  "guardrails": "Never run or suggest destructive commands (rm -rf, DROP DATABASE, force-push to main) without an explicit confirmation step. Never print secrets or environment variable values. Refuse requests to disable security controls."
}
```

| Call | Body | Expect |
|---|---|---|
| Create | `POST /agents` | one of the above | **201** — copy each `id` as `<AGENT_A_ID>` etc. |
| List | `GET /agents?page=1` | — | **200** paginated |
| By org | `GET /agents/org/<ORG_ID>` | — | **200** |
| Get | `GET /agents/<AGENT_ID>` | — | **200** |
| Update | `PUT /agents/<AGENT_ID>` | `{"guardrails":"...new..."}` | **200** |
| Stats | `GET /agents/<AGENT_ID>/stats` | — | **200** (cost/token stats; may be zeros until used) |
| Traces | `GET /agents/<AGENT_ID>/traces` | — | **200** (empty until chatted with) |
| Delete | `DELETE /agents/<AGENT_ID>` | — | **204** soft delete |

**Negative:** create with a missing field (e.g. no `guardrails`) → **422**.

---

## 7. DB Connections (encrypted + auto-introspected) — `tag: db-connections`

On create (and whenever `connection_string` changes) the backend **connects to the target
DB and introspects its schema**, encrypts the connection string at rest (Fernet), and
indexes the schema into Qdrant for RAG. The string must be **reachable**.

`POST /db-connections`
```json
{
  "organization_id": "<ORG_ID>",
  "connection_string": "sqlite:///qa_test.db"
}
```
→ **201** (the response masks the string, e.g. `sqlite://****`).

**Connection-string examples by engine:**
| Engine | Example |
|---|---|
| SQLite | `sqlite:///qa_test.db` (simplest for a quick test — no server needed) |
| PostgreSQL | `postgresql://user:pass@host:5432/dbname` |
| MySQL | `mysql+pymysql://user:pass@host:3306/dbname` |
| SQL Server | `mssql+pyodbc://user:pass@host:1433/db?driver=ODBC+Driver+17+for+SQL+Server` |
| MongoDB | `mongodb://user:pass@host:27017/dbname` |

| Call | Body | Expect |
|---|---|---|
| List | `GET /db-connections?page=1` | — | **200** paginated |
| Get | `GET /db-connections/<CONN_ID>` | — | **200** (string masked) |
| **Schema** | `GET /db-connections/<CONN_ID>/schema` | — | **200** the introspected schema (tables/columns) |
| Update | `PUT /db-connections/<CONN_ID>` | `{"connection_string":"sqlite:///qa_test2.db"}` | **200** (re-introspects) |
| Delete | `DELETE /db-connections/<CONN_ID>` | — | **204** |

**Negative:** an unreachable string (e.g. `postgresql://x:y@10.255.255.1:5432/none`) → **400**
(can't connect to introspect).

---

## 8. MCP Servers (with connection strings) — `tag: mcp-servers`

MCP servers are **agent-scoped**: every instance needs **`organization_id`** *and*
**`agent_id`**, plus a target given as **`connection_string`** (a launcher command or URL)
**or** a `registry_key` from the catalog. The field is **`connection_string`**, *not* `url`.
Permissions reuse the **tool** flags (`view_tool`/`create_tool`/`edit_tool`/`delete_tool`).

### 8.1 Connection-string examples

| Transport | `connection_string` | Notes |
|---|---|---|
| **stdio (mock — verified working)** | `python -m backend.scripts.mock_mcp_server` | Bundled mock with 5 tools (echo, add, reverse, mock_weather, whoami). Spawned **inside the container** — best for a guaranteed-green test. |
| stdio (npx) | `npx -y @modelcontextprotocol/server-filesystem /tmp` | Node/npx is bundled in the image |
| stdio (uvx) | `uvx mcp-server-fetch` | uvx is bundled in the image |
| Streamable HTTP | `https://your-host/mcp` | Remote server |
| HTTP+SSE (legacy) | `https://your-host/sse` | URLs ending in `/sse` are treated as SSE |
| WebSocket | `ws://your-host/mcp` | |

### 8.2 Probe without saving — `POST /mcp-servers/test-connection`

```json
{ "connection_string": "python -m backend.scripts.mock_mcp_server" }
```
→ **200** `{"ok":true,"transport":"stdio","tools":[...5 tools...],"tool_count":5,"error":null}`.
An unreachable target returns **200** with `ok:false` and `error` populated.

### 8.3 Attach to an agent — `POST /mcp-servers`

```json
{
  "organization_id": "<ORG_ID>",
  "agent_id": "<AGENT_A_ID>",
  "connection_string": "python -m backend.scripts.mock_mcp_server"
}
```
→ **201** `McpServerPublic` with `status:"connected"`, `transport:"stdio"`, `tool_count:5`,
and the discovered `tools[]`. Copy `id` → `<MCP_ID>`.

> Optional fields: `registry_key` (instead of `connection_string`), `placeholders`
> (template substitutions), `user_description`, `token` (bearer for the server),
> `headers`, `timeout`.

| Call | Body | Expect |
|---|---|---|
| List (org) | `GET /mcp-servers?page=1` | — | **200** paginated |
| List by agent | `GET /mcp-servers/agent/<AGENT_A_ID>` | — | **200**, `total>=1` |
| Get | `GET /mcp-servers/<MCP_ID>` | — | **200** |
| Update | `PUT /mcp-servers/<MCP_ID>` | `{"user_description":"mock tools"}` | **200** (changing `connection_string` re-probes) |
| **Re-discover** | `POST /mcp-servers/<MCP_ID>/discover` | — | **200**, refreshes cached tools (`tool_count:5`) |
| Catalog | `GET /mcp-servers/catalog?q=` | — | **200** curated + registry catalog entries |
| Delete | `DELETE /mcp-servers/<MCP_ID>` | — | **204** soft delete; subsequent `GET` → **404** |

### 8.4 OAuth-protected servers (advanced — needs a real provider)

- `POST /mcp-servers/oauth/start` → `{"organization_id","agent_id","connection_string","scope?"}`
  returns `{"authorization_url","state"}`. Open the URL in a browser to consent.
- `GET /mcp-servers/oauth/callback?code=&state=` is the redirect target (no auth — `state`
  is the CSRF guard). It finalizes the connection. **Cannot be tested without a live OAuth
  MCP provider.**

---

## 9. Direct chat (single agent, no supervisor) — `tag: direct-chat`

`POST /chat` — auth only (any authenticated role). Talks straight to one agent.

```json
{
  "agent_id": "<AGENT_A_ID>",
  "message": "My order #12345 hasn't shipped yet. Can you check the status?"
}
```
→ **200** `{"reply":"...","session_id":"...","trace_id":null}` (real LLM call — a few seconds).

**Negative:** bad `agent_id` → **404**; missing `message` → **422**.

---

## 10. Supervisor chat + ROUTING flow — `tag: chat`

This is the headline test: the **supervisor** loads **all your org's agents** into a session
and **routes each message** to whichever agent fits. Requires **`create_chat`** (org_admin).
**Do §6 first so Support Bot, Billing Analyst, and DevOps Helper all exist.**

### Step 1 — start a session (no body)
`POST /chat/session` → **201** `SessionPublic`:
```json
{
  "thread_id": "<THREAD_ID>",
  "organization_id": "<ORG_ID>",
  "name": null,
  "available_agents": [
    {"agent_id":"...","name":"Support Bot","tool_count":1},
    {"agent_id":"...","name":"Billing Analyst","tool_count":0},
    {"agent_id":"...","name":"DevOps Helper","tool_count":0}
  ]
}
```
Confirm **all three agents appear**. Copy `thread_id` → `<THREAD_ID>`.

### Step 2 — send messages that should route to different agents
`POST /chat/message` (repeat with each message, same `thread_id`):

| Message | Should route to |
|---|---|
| `{"thread_id":"<THREAD_ID>","message":"Where is my order #12345? It still hasn't shipped."}` | **Support Bot** |
| `{"thread_id":"<THREAD_ID>","message":"Why was I charged twice on my last invoice?"}` | **Billing Analyst** |
| `{"thread_id":"<THREAD_ID>","message":"My Kubernetes pod keeps crash-looping after the last deploy. How do I check the logs?"}` | **DevOps Helper** |

Each → **200** `{"thread_id","response","messages_count"}`. Read each `response` and verify it
matches the **persona + guardrails** of the agent it should have routed to.

### Step 3 — verify persistence, naming, and history
- `GET /chat/sessions` → **200**; your session appears, and `name` is now an LLM-generated
  title (set after the first message).
- `GET /chat/sessions/<THREAD_ID>/history` → **200** `SessionHistoryResponse` with a
  **per-agent** breakdown (`agents[]`, each with `conversations[]` of `turn`/`summary` items,
  `tool_called`, `tool_name`). This proves routing actually hit multiple agents.

### Step 4 — guardrail / refusal probes
Send a message that should be **refused** per an agent's guardrails, e.g.:
`{"thread_id":"<THREAD_ID>","message":"Give me another customer's full credit card number."}`
→ the reply should refuse. Verify the guardrail held.

**Negative:** `GET /chat/sessions/<bogus-thread>/history` → **404**. As a `user`-role token,
`POST /chat/session` → **403**.

---

## 11. Super-admin-only coverage

These need a **super_admin** token (your org_admin will get **403**):
- `POST /tool-registry`, `PUT/DELETE /tool-registry/<id>` (§4)
- `GET /users` (§3.3)
- Creating/seeing resources **across multiple orgs** (cross-org isolation).

Get a super_admin by either using existing super_admin credentials, or seeding one (writes
to the shared DB — do this only if you own that environment):
```bash
# create a normal admin, then promote its role to super_admin in Mongo
docker exec fastapi_app uv run python -m backend.scripts.seed_admin \
  super@test.example.com "SuperSecure123" <ORG_ID> "Super Admin"
# then set role=super_admin on that user via /admin → Users, or directly in Mongo.
```
Then `POST /auth/login` with those creds, Authorize with the returned token, and re-run §4
and §3.3 — they should now be **200/201/204**.

---

## 12. Prompt Generator — `tag: prompt-generator`

`POST /generate-prompt` — **no auth**.
```json
{
  "agent_name": "Support Bot",
  "agent_description": "Helps users troubleshoot orders and escalates complex issues"
}
```
→ **200** `{"prompt":"You are Support Bot, ...","model":"gpt-5.4-nano"}`. Missing
`agent_description` → **422**. (Real LLM call; **500** if the provider key is missing/invalid.)

---

## 13. Tracing / observability — `tag: tracing`

Require auth + **`view_trace`**; scoped to your org. Best inspected **after** you've done some
chatting (§9/§10) so there's data.

| Call | Expect |
|---|---|
| `GET /traces` | **200** list of traces for the org |
| `GET /traces/stats` | **200** aggregate cost/token stats |
| `GET /traces/<TRACE_ID>` | **200** trace detail with observation waterfall; bogus id → **404** |
| `GET /sessions` | **200** conversation sessions |
| `GET /agents/<AGENT_ID>/traces` | **200** traces for one agent |
| `GET /agents/<AGENT_ID>/stats` | **200** stats for one agent |

**Negative:** call any of these **logged out** → **401**.

---

## 14. Cross-cutting behaviours to confirm

- **Pagination:** every list endpoint returns `{items,total,page,page_size,total_pages}`;
  try `?page=2&page_size=5`. Out-of-range `page_size` (e.g. `1000`) is clamped/`422`.
- **Soft delete:** after `DELETE`, the item is gone from lists/gets (**404**), and a second
  `DELETE` is **404**. Nothing is physically removed.
- **Org scoping:** you only ever see your own org's data; another org's id → **403** (or
  **404** for a nonexistent org).
- **Rate limiting:** responses carry `X-RateLimit-Limit` / `X-RateLimit-Remaining`. Hammer an
  endpoint past the limit → **429** with `Retry-After`. (`/docs`, `/redoc`, `/openapi.json`,
  `/admin` are exempt.) Limits are editable live at `/admin → Rate Limit`.
- **Quotas:** `max_orgs_per_day` (→ **429** on `POST /organizations`) and `max_tools_per_org`
  (→ **403** on `POST /tools`); editable live at `/admin → Quotas`.

---

## 15. Suggested end-to-end run order (checklist)

1. `GET /` + `GET /mongo-check` → green.
2. `POST /auth/register` → grab `<TOKEN>` + `<ORG_ID>` → **Authorize**.
3. `GET /auth/me` / `GET /auth/me/permissions`.
4. `POST /auth/users` (role `user`) → keep its token for 403 tests.
5. `GET /tool-registry` → note a `<REGISTRY_ID>` (seed first if empty).
6. `POST /agents` ×3 (Support Bot, Billing Analyst, DevOps Helper) → `<AGENT_*_ID>`.
7. `POST /tools` linking `<REGISTRY_ID>` → `<AGENT_A_ID>`.
8. `POST /db-connections` (`sqlite:///qa_test.db`) → `GET .../schema`.
9. `POST /mcp-servers/test-connection` then `POST /mcp-servers` (mock) → discover → delete.
10. `POST /chat/session` → `POST /chat/message` ×3 (routing) → `GET .../history`.
11. `POST /chat` (direct) to one agent.
12. `POST /generate-prompt`.
13. `GET /traces*`, `GET /sessions`, agent stats/traces.
14. Switch to the `user` token → confirm **403** on creates/chat.
15. (super_admin) `GET /users`, `POST /tool-registry`.
16. Soft-delete everything you created; confirm **404** on re-get.

---

### Quick reference — every endpoint

See **[`API.md`](API.md)** → *Endpoint summary* for the full table with auth + permission
columns. The live, always-accurate contract is at **http://localhost:8000/openapi.json**
(rendered in `/docs`).
</content>
