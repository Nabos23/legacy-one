# MCP Server Integration — Architecture Design

## Overview

This document covers the architectural decisions for integrating MCP (Model Context Protocol) servers into the One-AI platform at enterprise scale.

---

## Part 1: Enterprise-Level System Design

### The Core Problem

A raw `connect_mcp_server()` call per agent load works in development. At enterprise scale it breaks because:

- Every agent invocation reconnects — expensive for stdio servers where you spawn a process
- Credentials are flat strings in the DB — no rotation, no audit trail
- No visibility into which tools are being called, by whom, and whether they are healthy
- Any org can register any server — no governance

---

### The 5 Layers You Need

#### 1. Registry Layer — "What MCP servers exist?"

A two-tier registry separates platform concerns from org concerns:

- **Global catalog**: Curated, approved servers (e.g. "GitHub MCP", "Jira MCP", "Postgres MCP") managed by platform admins. Orgs pick from this list.
- **Org-level instances**: An org takes a server from the catalog and configures their own instance (their API key, their DB URL). This is what gets linked to agents.

This separation controls the attack surface — an org cannot register `command: "rm -rf /"`.

---

#### 2. Credential Layer — "How do secrets get there safely?"

Flat strings in MongoDB is a dev shortcut. Enterprise needs:

- **Secrets vault integration** (AWS Secrets Manager, HashiCorp Vault, Azure Key Vault) — the DB stores only a *reference key*, not the actual secret. At connection time, the system resolves the key to the real value.
- **Per-org encryption** — even inside the DB, secrets at rest are encrypted with org-scoped keys, not a global app key.
- **Secret rotation** — when an org rotates an API key, only the vault entry changes. Every existing MCP config auto-picks it up on next connection.

---

#### 3. Connection Pool Layer — "Don't reconnect on every request"

The biggest operational concern. Three approaches depending on server type:

- **stdio servers**: These are processes. You do not spawn them per-request. Maintain a **pool of warm processes** per (org, server) pair — check them out on demand, return them after.
- **SSE/WebSocket servers**: These are long-lived HTTP connections. Keep a **persistent connection per org instance**, reconnect with exponential backoff on drop.
- **Stateless HTTP/SSE with short TTL**: For servers where reconnection is cheap, a short-lived pool (e.g. 5-minute TTL) is sufficient.

The pool lives at the **application level** (a singleton per worker), not inside SubAgent. SubAgent borrows from it.

---

#### 4. Health & Observability Layer — "Is the server actually working?"

Without this you get silent failures — the LLM calls a tool, gets nothing back, and hallucinates.

- **Health checks**: Background task that calls `list_tools()` on each active server every N minutes. If it fails K times consecutively, mark the server `status: degraded` and stop routing to it.
- **Per-call tracing**: Every `call_tool()` gets a Langfuse span just like existing tools — latency, error rate, and which orgs are using which MCP servers are all visible.
- **Circuit breaker**: If a server fails 5 calls in 60 seconds, open the circuit — stop the agent from retrying. Close it again after a cooldown period.
- **Tool audit log**: For compliance, every MCP tool call writes an immutable record: which user, which agent, which server, which tool, what arguments, what result.

---

#### 5. Governance Layer — "Who can use what, and with what limits?"

- **Admin approval flow**: An org requests a server from the global catalog → platform admin reviews → approved or rejected. No self-service for external servers.
- **Tool-level allowlist**: An org gets the Jira MCP but you only allow them to call `create_issue` and `get_issue`, not `delete_project`.
- **Rate limiting per server**: An MCP server may have upstream rate limits. Enforce per-org quotas on top of the existing quota system.
- **Sandbox for stdio servers**: Do not run `npx` on the main application server. stdio MCP servers should run in isolated containers (per-org, network-restricted), with the connection bridging back to the app. Otherwise any org can run arbitrary code on your infrastructure.

---

### How It All Connects

```
Org admin → picks from Global Catalog → creates Org MCP Instance
                                              ↓
                                     Stores ref key (not secret)
                                              ↓
Agent linked to Instance via mcp_server_ids
                                              ↓
Agent load → pool manager checks out a warm connection
                                              ↓
Tool call → circuit breaker → call_tool() → Langfuse span → audit log
                                              ↓
                             result back to SubAgent._run() (unchanged)
```

The existing `connect_mcp_server()` stays as the **low-level connection primitive**. Everything above wraps it.

---

### Practical Build Order

| Step | What | Why first |
|------|------|-----------|
| 1 | Connection pool | Biggest immediate win, zero schema changes |
| 2 | Secrets vault reference | Swap secret fields for reference keys, resolve at runtime |
| 3 | Health checks + circuit breaker | Operational reliability |
| 4 | Global catalog + approval flow | Governance |
| 5 | stdio sandboxing | Security hardening |
| 6 | Tool-level allowlist + audit log | Compliance |

Each step is independent — you do not need step 5 to ship step 1.

---

## Part 2: Where Does the MCP Connection String Belong?

### Short Answer

**No — the connection string should not be part of the tool document itself.**

---

### The Right Mental Model

An MCP server is a **source** of tools, not a tool itself. One MCP server exposes many tools. Embedding the connection string inside the tool document means duplicating it across every tool that comes from that server. When the URL changes or the secret rotates, you update N documents instead of one.

Think of it like a database connection vs. a query:

| Concept | Analogy | In the system |
|---------|---------|---------------|
| MCP Server | Database connection | `mcp_servers` collection |
| MCP Tool | A stored procedure on that DB | entry in `tools` collection |

They have **different lifecycles**:
- The server config changes when credentials rotate or the URL moves
- The tool definition changes when you want to expose different capabilities to different agents

---

### The Clean Design

Keep `mcp_servers` as its own collection. Instead of linking servers directly to agents via `mcp_server_ids`, let individual **tools** reference an MCP server:

```json
{
  "type": "mcp",
  "mcp_server_id": "<id>",
  "tool_name": "read_file",
  "name": "Read File",
  "description": "Reads a file from the filesystem",
  "input_schema": { }
}
```

**Benefits of this approach:**

- Agents still only have `tool_ids` — no schema change on agents
- You pick exactly which MCP tools an agent can use, not the whole server
- Connection config lives in one place, referenced by many tools
- Existing quota, soft-delete, and tool allowlist logic applies automatically

---

### What Changes at Runtime

`SubAgent.load_tools()` already loops over tool docs. You add a branch:

- `type: "handler"` → look up `_TOOL_REGISTRY` (current behavior, unchanged)
- `type: "mcp"` → look up the server doc by `mcp_server_id`, connect, call the specific `tool_name`

No separate `load_mcp_servers()` step needed. Everything flows through the same `tool_ids` path agents already have.

---

### Summary

| Concern | Lives in |
|---------|----------|
| Connection config (URL, command, credentials) | `mcp_servers` collection |
| Which tool to expose from that server | `tools` collection (`mcp_server_id` + `tool_name`) |
| Which tools an agent can use | `agents.tool_ids` (unchanged) |

The connection string belongs in `mcp_servers`. The tool document holds a **reference** to the server plus the specific tool name to expose. The agent sees no difference — it just has `tool_ids` as always.
