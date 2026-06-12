# Plan — Phase 2: Web & Market Research

Implements [`../specs/02-web-research.md`](../specs/02-web-research.md). A real,
cited external-research capability exposed to the Board (and research-tasked
agents) as gateway tools.

**Phase dependencies:** none hard. **Soft:** stronger once Phase 1 lands (research
aimed at objectives), but the tooling is independent and can be built in parallel
with Phase 1. **Blocks:** the *quality* of Phase 4 pitches; Phase 5 relies on it.

**Critical path:** `2.A1 → 2.B1 → 2.D1 → 2.D2` (backend search service → endpoint →
MCP tool → role wiring).

---

## Track A — Data/Backend

**2.A1 — External research service.**
New `roboco/services/research.py` (`BaseService` pattern,
`roboco/services/base.py:116`) wrapping a web-search + fetch capability. Use the
harness/web provider available in the deployment; return normalized, **cited**
results (title, url, snippet). Cost-bound the breadth (top-k, max fetches). This is
the only place external HTTP for research lives.
→ Blocked by: nothing — start immediately.

**2.A2 — Persist research artifacts (optional but recommended).**
So findings are durable and reusable, store research outputs as notes/evidence on
the originating task using the existing journal/evidence path
(`roboco/services/gateway/content_actions.py`, `note`/`evidence`). No new table
required if you reuse evidence; add one only if findings must outlive the task.
→ Blocked by: 2.A1.

---

## Track B — API

**2.B1 — Research endpoints (gateway-internal).**
Add `POST /api/v1/.../web_search` and `.../web_fetch` handlers (follow the
`do`-server route pattern under `roboco/api/routes/v1/`) that call `2.A1` and return
an `Envelope`. Gate to roles allowed to research (Board, PMs). These are the bridge
the MCP tool posts to (mirrors how `roboco/mcp/flow_server.py:71-113` posts to the
orchestrator).
→ Blocked by: 2.A1.

---

## Track D — Agent/Gateway

**2.D1 — Web-research MCP server/tools.**
New `roboco/mcp/search_server.py` following `roboco/mcp/flow_server.py:51-265`
(FastMCP instance, `_post` bridge, thin tool wrappers `web_search`, `web_fetch`).
Respect the per-agent allowlist from `/app/tool-manifest.json` like the other
servers.
→ Blocked by: 2.B1.

**2.D2 — Grant the tools to the right roles.**
Add the new tools to the appropriate role configs in
`roboco/services/gateway/role_config.py:40-111` (Board roles, and main/cell PM for
research tasks) so they appear in the spawn manifest
(`roboco/runtime/spawn_manifest.py:57-79`). Mount the new MCP server in the agent
container spawn (alongside `roboco-optimal` etc.).
→ Blocked by: 2.D1.

**2.D3 — Teach the roles to use it.**
Update `agents/prompts/roles/board.md` (and the research guidance in PM prompts) to
require grounding market/competitive claims in `web_search`/`web_fetch` results with
citations — never asserting an unsourced market fact.
→ Blocked by: 2.D2.

---

## Parallelization summary

- **Start now:** `2.A1` (fully independent of Phase 1).
- **Chain:** `2.A1 → 2.B1 → 2.D1 → 2.D2 → 2.D3`; `2.A2` parallel after `2.A1`.
- **Runs alongside Phase 1** — no cross-blockers. Land it before Phase 4 so pitches
  are grounded; Phase 5 assumes it exists.
