# Plan — Phase 6: The Cockpit

Implements [`../specs/06-cockpit.md`](../specs/06-cockpit.md). The Panel matured
into a watch-and-act surface: performance vs goals, what's happening, and the CEO
action queue as the focal point.

**Phase dependencies:** **Blocked by Phase 1 complete** (metrics/objectives to show).
Richest after **Phase 5** (activity + caps to render), but the read-only views can
ship incrementally. The action queue + Approve & Start surface already exist.

**Critical path:** `6.B1 → 6.C1 → 6.C2` (derived-metrics endpoint → performance view
→ unified action queue).

---

## Track B — API

**6.B1 — Derived-metrics endpoint.**
Add a read-only `GET /api/cockpit/summary` (new `roboco/api/routes/cockpit.py`,
mounted in `app.py`) that returns the derived state: per-objective progress, goal
coverage, drift, spend vs budget, active products vs cap. Compute from Goals (1.A4)
+ existing task/usage data (the token-usage rollups already exist per CLAUDE.md).
Read-only; any authenticated agent.
→ Blocked by: Phase 1 complete.

---

## Track C — Panel

**6.C1 — Performance view.**
Add a performance section to the dashboard (extend the command center,
`panel/src/components/dashboard/command-center.tsx`) rendering 6.B1: objective
progress, goal-coverage, spend vs budget, active vs cap. Use the existing chart dep
(`recharts`) and the data-hook pattern (`panel/src/hooks/use-tasks.ts`). Honor the
proxy-metrics boundary (spec §"On winning") — label these as proxy until external
launches are greenlit.
→ Blocked by: 6.B1.

**6.C2 — Action queue as the focal point.**
Make the CEO action queue the centerpiece of the overview, consolidating both
gated stages (Approve & Start *and* final approval) already built in
`panel/src/components/dashboard/ceo-approval-queue.tsx`. Carry the
"impossible-to-miss" lesson (a buried gate is a gate that never gets seen) — give it
top placement and a live count.
→ Blocked by: Phase 1 complete (can start as soon as goals exist; richer with 5).

**6.C3 — Drift & stall signals.**
Surface drift (work/spend tied to no objective, from 6.B1) and stalls (from Phase 5
`5.A1`) as visible signals on the cockpit, not buried. If Phase 5 isn't done yet,
ship the drift half from 6.B1 and add stalls when `5.A1` lands.
→ Blocked by: 6.B1; the stall half additionally → Blocked by: 5.A1 (cross-phase).

---

## Parallelization summary

- **Start after Phase 1:** `6.B1`, then `6.C1` + `6.C2` in parallel; `6.C3`'s drift
  half after `6.B1`.
- **Defer to after Phase 5:** the activity/caps richness in `6.C1` and the stall
  half of `6.C3` (`5.A1`).
- **Lowest-risk early win:** `6.C2` (queue as focal point) needs only the existing
  queue surface + Phase 1 — ship it early so the CEO never misses a gated decision.
