# Knowledge Base RAG — today's work log, and what's open for tomorrow

_Written 2026-08-20._

## Part 1 — Everything shipped today (complete pipeline)

### Ingestion pipeline
Upload → extract text (PDF/Office/text, OCR fallback via existing `backend/core/attachments.py`, now shared via a new `extract_document_text()` helper) → **identify document** (LLM-generated description + auto-classify into an existing KB, or auto-create a new KB if nothing fits) → structural+semantic chunking (flat, not hierarchical — heading/section split, then sentence-boundary windowing) → dense (`text-embedding-3-small`) + sparse (`fastembed` BM25) embedding → store:
- MongoDB: `knowledge_bases`, `kb_documents` (metadata, description, status)
- GridFS: **original raw file bytes** (fixed today — was storing extracted text instead, which meant re-extraction on reassignment was silently broken and the original file was unrecoverable)
- Qdrant: `kb_chunks` (dense + sparse vectors, chunk-adjacency links)

New files: `ai/rag/kb_llm.py`, `kb_indexer.py`, `kb_retriever.py`, `kb_identifier.py`, `kb_tool.py`; `backend/knowledgebase/` module (models/schemas/routes/services).

### Retrieval pipeline
Query → **rephrase** (last 6 turns of chat history resolve pronouns/follow-ups, LLM call, falls back to original query on failure) → hybrid dense+sparse search (Qdrant `Prefetch` + `FusionQuery(Fusion.RRF)`) → **chunk-adjacency graph expand** (one-hop, sequential links only, direct point-ID lookup — not a traversal algorithm) → **per-user KB visibility re-check** (`filter_visible_kb_ids` / `filter_visible_kb_ids_sync`, checked before a KB is ever baked into a searchable tool, not after) → formatted result → citations extracted and surfaced on the chat response (`sources` field, rendered as chips in both playgrounds).

**Verified live, not just claimed:** hybrid search actually uses both vector types (pulled a point back out of Qdrant and confirmed); graph-expand actually pulls in topically-unrelated neighbor chunks that pure similarity search could never surface (isolated 3-section test); the scope-check actually excludes a personal KB for an unrelated user (direct test); the whole thing works end-to-end through the real chat UI including citations.

### Wired into all four execution engines
Today's fixes (rephrase-history passing + KB visibility re-check) were applied consistently across every place an agent can run, not just the main path:
1. `backend/chat/graph.py` — supervisor + direct chat (FastAPI backend)
2. `ai/multi_orchestration/` (`graph_loader.py` + `agent_invoker.py`) — explicit orchestration graphs
3. `ai/agents/sub_agent.py` + `main_agent.py` — the actual LangGraph Studio "MainAgent+SubAgent" stack (this one previously had **no** KB tool injection at all until today)
4. `ai/graph/nodes.py` — the fourth call site that builds a `SubAgent`
5. `backend/scripts/verify_ai_subagent_mcp.py` — the standalone dev verification script, updated to exercise `load_rag_tools()` too, plus fixed an unrelated pre-existing bug (test password violated the current password-strength policy)

### Permissions
- `view/create/edit/delete_knowledge_base` added to the permission catalog and **granted to all four roles by default** (previously `org_manager` was view+edit only and plain `user` was view-only — now full CRUD for everyone, per your explicit ask).
- Synced via the real script (`migrate_role_permissions.py` — **not** `seed_roles.py`, which is a decoy that seeds a collection nothing reads; this cost real time to discover, now in memory).
- The Permissions admin page needed **no frontend change** — it's fully catalog-driven, so "Knowledge Base" already shows up there with full CRUD toggles automatically.

### Frontend
- Knowledge Bases list/detail/review pages, sidebar nav entry.
- Create-KB dialog with the standard **Visibility picker** (Organization/Selected users/Team/Personal), matching the exact pattern used for agents/projects — including backend validation reuse (`_validate_allowed_user_ids`/`_validate_team_id` from `backend/agent/services.py`, not reinvented).
- **UX pivot, per your direction**: originally built as a dedicated "Knowledge Bases" wizard step — reworked into a **"Knowledge Base" virtual tool inside the Tools step** instead, matching the existing Read/Write-database tool pattern exactly: checkbox → inline multi-select KB checklist → "Create new knowledge base" inline action. Wired into both the agent create page and the agent edit page (the create page never had KB attachment before at all).
- Citation chips under assistant replies in both the client and admin playgrounds.

### Bugs found and fixed along the way (not asked for directly, found during verification)
- `rag_ids` existed on `AgentPublic` but was **missing from `AgentCreate`/`AgentUpdate`** — every attempt to attach a KB to an agent was being silently dropped by the backend until this was caught and fixed.
- **Playground session-handoff bug**: switching from the supervisor's unpersisted "prewarmed" session to a specific agent reused that session id against the direct-chat endpoint, which requires the session to already exist in Mongo → 404. Fixed in `hooks/use-chat.ts` (`prewarmedSessionRef` tracking). Verified live by reproducing your exact repro steps — confirmed `POST /chat/stream` now returns 200, and the KB tool answers correctly with a citation.

### Repo hygiene / security
- Checked `origin/dev-Sufyan` on **both** repos against the known PolinRider trojan fingerprint (`.vscode/tasks.json` with `runOn:folderOpen` + `public/fonts/fa-solid-400.woff2`) — **both clean**, no cleanup needed. Also scanned both local working directories.
- Committed and pushed the full day's work on both repos, after pulling and merging each repo's one legitimate upstream commit first (verified clean, no conflicts, tests/type-check green after merge).
- `.claude/skills/` added to frontend `.gitignore` (local, machine-specific, shouldn't be tracked).
- `package-lock.json` synced and pushed — verified safe first (the added dependency was already declared in `package.json`, lockfile just hadn't caught up).

## Part 2 — What's explicitly NOT done (by design, disclosed, not oversight)

- **Not canonical GraphRAG.** No entity/relationship extraction, no knowledge graph, no community detection. What exists is a **chunk-adjacency graph** (sequential neighbor links within a document) — real and verified, but structural, not semantic. This is the subject of Part 3 below.
- Graph-expand scoring is a fixed placeholder, not "parent score × decay."
- No bounded timeout specifically on the graph-expand lookup (only general exception handling).
- Expansion cap takes the first N linked ids encountered, not "most-linked-first" ordered.
- No multi-tier merge/rerank — only the organization tier exists right now (user-level and agent-level KBs were explicitly deferred).
- Chunking is flat (structural then semantic split) — no parent/child hierarchy, no multi-level summary tree.

## Part 3 — Open ask: "true GraphRAG in every term" (deferred to tomorrow)

Canonical GraphRAG needs three things not built yet: entity/relationship extraction into an actual knowledge graph, community detection (clustering) over that graph, and per-community LLM summaries enabling a "global" query path (broad/thematic questions answered from summaries, not individual chunks) alongside the existing "local" chunk-level path.

**Three decisions asked today, answered "no preference," deferred to tomorrow:**

### 1. Where does the knowledge graph live?
No dedicated graph database exists in this stack (just MongoDB + Qdrant).
- **Option A (recommended)**: new MongoDB collections (`kb_entities`, `kb_relationships`, `kb_communities`) + build the graph in-memory with `networkx` at index/query time. No new infrastructure.
- **Option B**: add Neo4j (or similar) — better native traversal at scale, but a whole new service to run/operate/back up.

### 2. Entity/relationship ontology?
- **Option A (recommended)**: generic, loosely-typed — the LLM picks free-text type labels per document (e.g. "Policy", "governs"). Flexible across arbitrary document types, no upfront schema design.
- **Option B**: a fixed ontology defined up front (e.g. `Person`, `Policy`, `Department` / `governs`, `applies-to`, `supersedes`). More consistent, but only fits documents matching the schema.

### 3. Build community detection + global summarization now, or defer it?
The expensive, complex half: cluster entities (Leiden), write an LLM summary per cluster, re-run as documents change, add a query router that sends broad/thematic questions to summaries instead of chunk search.
- **Option A (recommended if we want "true GraphRAG in every term")**: build entity extraction + graph construction + community detection + summaries + the global query path all together.
- **Option B**: entity/relationship extraction and multi-hop **local** traversal first; add community detection and global summarization as a second phase once the entity graph is proven.

### Cost/scope note
Entity extraction means one (or more) LLM calls per document at ingest time, on top of the identify-document call and dense+sparse embedding already happening — a real, ongoing cost and latency increase, not a one-time build cost. Worth deciding the ontology + community-detection scope with that in mind.

## Next step
Resume with the three decisions above, then implement: extraction pipeline → graph construction → (if in scope) community detection + summaries → dual query routing (local vs. global) → wire into the existing `search_knowledge_base` tool across all four engines, same pattern as the current chunk-adjacency expand.
