# Plan — Phase 5: Autonomous Cadence & Caps

Implements [`../specs/05-autonomous-cadence.md`](../specs/05-autonomous-cadence.md).
The work-generation engine runs on its own cadence, generates the full breadth of
goal-aligned work, respects budget/concurrency caps, idles honestly, and surfaces
stalls. This is the capstone.

**Phase dependencies:** **Blocked by Phases 1, 2, and 4 complete** — it drives them
(goals to pursue, research to see, the pitch/provision path to act on). It also
feeds Phase 3 (the Secretary narrates it) and Phase 6 (the cockpit shows it).

**Critical path:** `5.E1 → 5.D1 → 5.E2 → 5.E3 → 5.A1` (loop → generation logic →
caps enforcement → honest idle → stall surfacing).

---

## Track E — Orchestrator (the loop)

**5.E1 — The strategy/work-generation loop.**
Add a new background loop in `Orchestrator.start()` parallel to `_dispatcher_loop`
(`roboco/runtime/orchestrator.py:618-643`, loop template at `5265-5292`). On its
cadence it runs one decision cycle. Make the interval configurable
(`strategy_cadence` from the Goals operating policy, 1.A1) including an `off` value
for human-triggered-only.
→ Blocked by: Phases 1, 2, 4 complete.

**5.E2 — Caps enforcement.**
Before generating/spawning, enforce the operating-policy caps (monthly budget,
max-active-products) read from Goals. Reuse the budget-kill plumbing in the sweeper
(`roboco/runtime/orchestrator.py:3855` sweeper loop) and count active product lines.
A cycle that would breach a cap surfaces to the CEO instead of proceeding.
→ Blocked by: 5.D1.

**5.E3 — Honest idle.**
When a cycle finds no value-adding, in-bounds work against the standing goals, it
stops and emits a single "need direction" signal to the CEO
(`NotificationService`, `services/notification.py`) rather than generating busywork.
Guard against false idle (don't stop while real backlog exists).
→ Blocked by: 5.E2.

---

## Track D — Agent/Gateway (generation logic)

**5.D1 — Decision logic: assess → find gap → generate.**
The cycle body: read goals + derived metrics (coverage, drift, per-objective
progress), pick the highest-leverage gap, and generate work. Generation creates
tasks via `TaskService.create` (`roboco/services/task.py:537`) across the full
taxonomy (new products → via the Phase 4 pitch path; plus maintenance, research,
marketing, ops, meta). Prioritize by objective priority/leverage. This may itself be
an agent (a "strategist") spawned per cycle rather than hard-coded heuristics — reuse
the spawn path (`orchestrator.py:1484-1547`).
→ Blocked by: 5.E1.

**5.D2 — Route generated work correctly.**
New-product work flows through the Phase 4 pitch→approve→provision path (stays
gated). In-bounds work (maintenance, research) flows straight to the delivery engine.
Respect the autonomy line from Goals: gated kinds surface; the rest run.
→ Blocked by: 5.D1.

---

## Track A — Orchestrator (stall surfacing — the INTENT §10 gap)

**5.A1 — Surface stalls and failures to the CEO queue.**
Generalize the existing stuck-task / respawn-loop / SLA detectors
(`roboco/runtime/orchestrator.py:6909-7057`, `_detect_stuck_tasks`,
`_pm_respawn_should_gate`, `_detect_sla_exceeded`) so any stranded work (a failed
step like the merge-405 we hit, a hard error, a stuck state) reaches the CEO action
queue and is recoverable — never silently idle. Use the notification path
(`services/notification.py:90-124`).
→ Blocked by: 5.E3.

---

## Parallelization summary

- **Nothing starts until Phases 1, 2, and 4 are complete** (hard gate — it drives
  all three).
- **Then:** `5.E1 → 5.D1` first; `5.D2`, `5.E2` branch off `5.D1`; `5.E3` after
  `5.E2`; `5.A1` last (and is independently valuable — the stall-surfacing gap can
  ship even ahead of the full loop if needed).
- **This phase makes the company walk-away-able** — treat caps, honest idle, and
  stall surfacing (`5.E2`, `5.E3`, `5.A1`) as non-negotiable before enabling a
  non-`off` cadence.
