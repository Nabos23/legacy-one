# Supervisor Mode — Code Review Summary & Task List

Pushed to `dev-Sufyan` on both repos:
- **Backend** ([Legacy_AI](https://github.com/Allied-Intelligenza/Legacy_AI)) — commit [`75a8954`](https://github.com/Allied-Intelligenza/Legacy_AI/commit/75a8954) on top of `origin/dev-local` (merged in).
- **Frontend** ([Legacy_AI_UI](https://github.com/Allied-Intelligenza/Legacy_AI_UI)) — commits [`e7c3a82`](https://github.com/Allied-Intelligenza/Legacy_AI_UI/commit/e7c3a82), [`ecc2aac`](https://github.com/Allied-Intelligenza/Legacy_AI_UI/commit/ecc2aac) on top of `origin/staging` (merged in).

**What it is:** a new "Supervisor" orchestration mode alongside the existing sequential (`Start → Agent A → Agent B → End`) flow. A hardcoded Supervisor becomes the entry point, routes each user message to whichever connected agent's purpose fits, and regains control after every agent turn to decide the next hop or finish. Sequential mode is untouched — `mode` defaults to `"sequential"` on any document that predates this feature.

---

## 1. Backend — new module: `ai/multi_orchestration/supervisor/`

| File | Responsibility |
|---|---|
| `agent.py` (418 lines) | `SupervisorAgent` — candidate shortlisting at scale, routing decision, direct-answer guard, synthesis of multi-agent answers |
| `prompt.py` (214 lines) | All Supervisor and routed-agent prompt text — routing rules, handback rules, deadlock/forced-assignment rules, peer roster |
| `handback.py` (88 lines) | The control-transfer protocol an agent uses to hand a request back — `wrong_domain` vs `blocked` |
| `__init__.py` | Public surface — constants (`SUPERVISOR_AGENT_ID`, defaults), re-exports |

**Engine changes** (existing files, behind a `mode` check — sequential path is unchanged):
- `runtime_graph.py`, `graph_loader.py` — supervisor-mode graphs skip edge-building; every node gets its teammates' names/purposes injected into its prompt.
- `scheduler.py` (+642 lines) — the supervisor turn loop: route → run agent → return to Supervisor → repeat, with sticky continuity, handback/deadlock handling, and hop/visit/bounce bounds.
- `agent_invoker.py`, `memory_bus.py` — agents now receive prior turns as structured chat history instead of a flat text transcript.
- `backend/orchestration/schemas.py`, `services.py` — `SupervisorConfig`, mode-aware create/update validation, `get_run_status` filters internal handback steps out of what the UI sees.
- `backend/mcp_server/services.py` — MCP tool loader now also returns which server owns each tool (needed for the Supervisor's per-agent capability summary).

## 2. Frontend — `One-AI-UI`

- `components/orchestration/SupervisorNode.tsx` (new) — the non-deletable Supervisor node on the canvas.
- `OrchestrationCanvas.tsx` (+329/-?) — mode toggle (Sequential ↔ Supervisor), supervisor settings panel (max hops, max declines, sticky routing, direct-answer toggle, custom instructions), save payload branches by mode.
- `AgentNode.tsx`, `chat/page.tsx`, `types/index.ts` — supervised-node styling, new types (`OrchestrationMode`, `SupervisorConfig`), chat UI already renders supervisor steps via the existing status endpoint with no new wiring needed.

## 3. Test coverage

`backend/tests/test_supervisor_mode.py` — **66 tests**, all passing at push time. Covers: candidate shortlisting under load, per-agent capability rendering (connector/MCP tool collapsing), the full turn state machine, handback kind distinction (`wrong_domain` vs `blocked`), deadlock forcing, the "Supervisor never answers a specialist question" guard, and the "no path ends in a dead/failed run" guarantee. **Note: this file is covered by a repo-wide `tests/` rule in `.gitignore` and did not get pushed** — it exists only locally. Flagged as item 1 below.

---

## Task list for the team lead

### Must do before merging to a shared branch

1. **Commit and push the test file.** `backend/tests/test_supervisor_mode.py` (66 tests) is local-only — `.gitignore` has a broad `tests/` rule that's silently excluding it. Either add a narrow exception for this file, or move it, or fix the gitignore rule; right now no CI will ever run these tests.
2. **Delete the stray `ai/multi_orchestration copy/` directory** sitting untracked in the backend working tree (visible in `git status`, not part of any commit). Looks like an accidental editor/OS backup copy — confirm and remove before it gets added by mistake.
3. **Run `python -m backend.scripts.seed_function_tools` and `backfill_ask_human`** in every environment this deploys to. Any agent without `ask_human` seeded can't pause for missing input in supervisor mode and will guess instead (observed in testing: an agent picked an email recipient without confirming).

### Known limitations to review as a team, not blockers

4. **Routing quality depends on how agents are described**, not just on the code. Two agents with overlapping purposes (e.g. both querying the same database) can currently be mis-routed on the first hop, or — before the deadlock fix — bounce a request between each other. The deadlock case is now handled (Supervisor is forced to commit to the closest agent rather than fail the turn), but first-hop accuracy will improve with better agent `description`/`purpose` text, not more code.
5. **No usage-derived capability scoping yet.** Two agents sharing one tool (e.g. `query_db` on the same connection) look identical to the router. A follow-up idea, not built: derive each agent's actual table/data scope from its own successful tool calls over time, and surface that in routing instead of relying only on hand-written descriptions.
6. **Context growth is unbounded**, same as the existing sequential mode — `MemoryBus` is an uncapped, ever-growing log seeded from the previous turn. Supervisor mode reaches this ceiling faster because a multi-hop turn appends more agents' output per user message. Needs a windowing/summarization strategy; out of scope for this PR.
7. **`allow_direct_answer` config exists but is untested against a live model** — whether the Supervisor actually refuses to answer specialist questions depends on prompt compliance from the real LLM, not just the code guard. Worth a manual pass before enabling by default for a customer-facing orchestration.

### Suggested review focus (where to actually look)

8. `ai/multi_orchestration/scheduler.py` — the supervisor turn loop is the highest-risk piece (new state machine, bounds, forced-assignment escape hatch). Read `_run_supervised` and the `_commit_route`/`_report_supervised` helpers.
9. `ai/multi_orchestration/supervisor/prompt.py` — this is the actual routing/handback behavior; a prompt wording change here changes runtime behavior without touching any "logic" file.
10. `backend/orchestration/services.py::get_run_status` — confirm the `status != "handback"` filter is correct; handbacks must never reach the chat UI as if they were a real agent turn.

---

*No destructive or pushing actions were taken while producing this review — it's a read-only diff summary of what's already on `origin/dev-Sufyan` in both repos.*
