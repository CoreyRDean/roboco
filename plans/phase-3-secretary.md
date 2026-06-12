# Plan — Phase 3: The Secretary

Implements [`../specs/03-secretary.md`](../specs/03-secretary.md). Expands the
intake agent into the CEO's two-way chief-of-staff: set goals, brief status, walk
the action queue, relay intent, remind proactively.

**Phase dependencies:** **Blocked by Phase 1 complete** — the Secretary's first job
is editing the Goals artifact and reading company state, both of which Phase 1
provides. Reuses the existing intake SDK agent + live relay.

**Critical path:** `3.D1 → 3.D2 → 3.A1 → 3.D3` (read-state tools → goal-edit tool →
side-effect executor → status/reminder behaviors).

---

## Track D — Agent/Gateway (the core)

**3.D1 — Rename + rescope intake → Secretary, with read access to company state.**
Build on the intake SDK agent (`roboco/agent_sdk/intake_main.py:98-163`,
`intake_driver.py:220-349`). Add read-only MCP tools so the Secretary can see the
company: `read_goals`, `read_status` (tasks/queue/spend summary), `read_queue`
(pending CEO actions). Follow the MCP pattern in `roboco/mcp/flow_server.py` and add
them to the Secretary's tool allowlist in
`intake_driver.py:_INTAKE_BASE_TOOLS`/`_gate` (291-349).
→ Blocked by: Phase 1 complete.

**3.D2 — Goal-editing capability.**
Give the Secretary a way to propose/commit goal changes. Because the SDK agent has
no lifecycle verbs, route the edit through a confirmed side-effect (the existing
`propose_draft`→confirm seam, `roboco/api/routes/prompter*.py`) OR a dedicated
CEO-authenticated tool that calls `BusinessGoalsService.update` (1.A4). Goal changes
the CEO makes conversationally must land in the same artifact the Panel edits.
→ Blocked by: 3.D1, 1.A4 (cross-phase).

**3.D3 — Status, action-queue walkthrough, and reminders behaviors.**
Update the Secretary's role prompt (`agents/prompts/roles/prompter.md`, renamed/
extended) so it: synthesizes status from `read_status`; for each queue item explains
what/why/tradeoffs/recommendation; and obeys the same gate list (acts on in-bounds
relays, brings gated actions back). Keep it a *non-strategist* interface per the spec.
→ Blocked by: 3.D1.

---

## Track A — Data/Backend

**3.A1 — Downward relay + side-effect executor.**
A small service path so the Secretary can carry CEO directives down (e.g., create a
note/notification to the Board/Main PM, or apply a confirmed goal edit). Reuse
`ContentActions`/`NotificationService` (`roboco/services/notification.py`) rather
than new machinery. Enforce the gate list here — gated actions become CEO action
items, not silent executions.
→ Blocked by: 3.D2.

**3.A2 — Proactive feed source.**
Provide what the proactive channel needs: a periodic digest of "what needs the CEO"
(pending approvals, stale decisions, drift, fresh pitches). Source it from existing
notifications + the goals/derived metrics. (Delivery cadence is wired in Phase 5's
loop; here, expose the data.)
→ Blocked by: Phase 1 complete.

---

## Track B — API / Track C — Panel

**3.B1 — Secretary session + relay endpoints.**
Reuse the live intake endpoints (`roboco/api/routes/prompter_live.py`) — the
two-way chat surface already exists. Add only what new tools/relays require.
→ Blocked by: 3.D1.

**3.C1 — Secretary chat surface in the panel.**
The intake live-chat UI already exists; relabel to "Secretary" and surface it as a
persistent, always-available panel entry (not just a task-draft modal). Add the
proactive feed (3.A2) as a notifications-style strip.
→ Blocked by: 3.B1, 3.A2.

---

## Parallelization summary

- **Nothing here starts until Phase 1 is complete** (hard gate).
- **Then:** `3.D1` first (read tools), enabling `3.D2`, `3.D3`, `3.B1` in parallel;
  `3.A1` after `3.D2`; `3.A2` can start as soon as Phase 1 is done; `3.C1` last.
