# RoboCo — Implementation Plans

Prescriptive, code-grounded plans for the phases specified in [`../specs/`](../specs/)
and the vision in [`../INTENT.md`](../INTENT.md). Where the specs say *what*, these
say *how* — with real file anchors — and are structured so a fleet of agents can
work them in parallel and know exactly where they block each other.

## How to read these

- One plan file per phase. Each plan groups **action items** into **tracks** that
  can run in parallel:
  - **Track A — Data/Backend** (models, tables, migrations, services)
  - **Track B — API** (routes, schemas, auth)
  - **Track C — Panel** (Next.js pages, hooks, components, types)
  - **Track D — Agent/Gateway/Prompt** (verbs, tools, MCP, prompts)
  - **Track E — Orchestrator** (loops, spawning, escalation)
- Every action item has an **ID**: `<phase>.<track><n>` — e.g. `1.A2`, `4.E1`.
- **Items are parallel-safe by default.** Order is constrained *only* by the
  explicit `→ Blocked by:` line on each item.

## Blocker convention

Each item carries one `→ Blocked by:` line. We surface only the non-obvious
blockers (a child completing its parent phase is implicit and never restated):

- `→ Blocked by: nothing — start immediately` — no prerequisite.
- `→ Blocked by: 1.A2` — another item, **same plan** (sequential within the plan).
- `→ Blocked by: Phase 1 complete` — a whole upstream **phase** must be done.
- `→ Blocked by: 1.A4 (cross-phase)` — a **specific item in another phase**.

If an item lists no blocker on a thing, you may assume it does **not** depend on
it and can proceed in parallel.

## Cross-phase dependency map (the DAG)

```
Phase 1  Business Goals ──────────────┬──────────────┬───────────────┐
  (foundation; everything reads it)   │              │               │
        │                             ▼              ▼               ▼
        │                        Phase 3        Phase 4          Phase 6
        │                        Secretary      Pitch→Approve→   Cockpit
        │                        (needs 1)      Provision        (needs 1; full
        ▼                                       (needs 1; soft 2) polish after 5)
Phase 2  Web Research ───────────────────────────►  │
  (soft-needs 1; else independent)                  ▼
                                              Phase 5  Autonomous Cadence
                                              (capstone — needs 1, 2, 4;
                                               drives 3 and 6)
```

**What can start immediately, in parallel:**
- Phase 1, **Track A** (the Goals model/service) — the critical path; start here.
- Phase 2, **Track A/D** (web-research tool + MCP) — independent of Goals.
- Phase 4, **Track A/E provisioning sub-track** (GitHub repo creation service) —
  independent of Goals; the pitch sub-track waits on Phase 1.
- Phase 6, read-only **Track C** scaffolding — but its data needs Phase 1.

**Hard gates (do not start until upstream done):**
- **Phase 3 (Secretary)** → blocked by **Phase 1 complete** (it edits goals and
  reads company state).
- **Phase 5 (Autonomous Cadence)** → blocked by **Phases 1, 2, and 4 complete**
  (it is the engine that drives them).

**Sequencing rationale** (from INTENT §12): prove pitch *quality* with the human
in the loop (Phase 4) before automating the trigger (Phase 5); never let an
autonomous loop mint products before the CEO has seen the quality.

## What these plans deliberately leave to the implementing agent

The plans say which file, which pattern to copy (with anchors), and the contract
to satisfy. They do not paste final code. Follow the cited exemplar, match the
surrounding conventions, and run the gates in [`../CLAUDE.md`](../CLAUDE.md)
(`ruff`/`mypy`/`pytest` for Python; `pnpm lint`/`typecheck`/`test` for the panel)
before calling an item done.

## Plans

| Phase | Plan | Tracks |
|---|---|---|
| 1 | [Business Goals](phase-1-goals.md) | A, B, C, D |
| 2 | [Web & Market Research](phase-2-web-research.md) | A, B, D |
| 3 | [The Secretary](phase-3-secretary.md) | A, B, C, D |
| 4 | [Pitch → Approve → Provision](phase-4-pitch-approve-provision.md) | A, B, C, D, E |
| 5 | [Autonomous Cadence & Caps](phase-5-autonomous-cadence.md) | A, D, E |
| 6 | [The Cockpit](phase-6-cockpit.md) | B, C |
