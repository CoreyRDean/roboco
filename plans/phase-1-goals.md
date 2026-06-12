# Plan — Phase 1: Business Goals

Implements [`../specs/01-business-goals.md`](../specs/01-business-goals.md). The
CEO-editable charter persisted once, served via API, edited in the panel, and
injected into every agent's briefing.

**Phase dependencies:** none — this is the foundation. **Blocks:** Phases 3, 4, 5, 6.

**Critical path:** `1.A1 → 1.A2 → 1.A4 → 1.A5` (model → table → service → briefing
injection). Everything else hangs off those.

---

## Track A — Data/Backend

**1.A1 — Define the Goals domain model.**
New `roboco/models/business_goals.py`. Mirror the model + DTO split in
`roboco/models/product.py:38-69` (inherit `RobocoBase`/`TimestampMixin` from
`roboco/models/base.py:220`). Shape: `north_star: str`, `objectives: list[Objective]`
(each: title, description, optional metric/target/horizon, priority, status),
`operating_policy` (autonomy_level enum, gate_list, monthly_budget_usd,
max_active_products, strategy_cadence, provisioning target), `constraints: list[str]`.
Add the enums (`AutonomyLevel`, `ObjectiveStatus`, `StrategyCadence`) as `StreEnum`s
in `roboco/models/base.py` alongside the existing ones.
→ Blocked by: nothing — start immediately.

**1.A2 — Add the ORM table (single-row).**
Append `BusinessGoalsTable` to `roboco/db/tables.py` following `ProjectTable`
(`tables.py:419-485`). Use `JSON` columns for `objectives`, `operating_policy`,
`constraints`; `Text` for `north_star`; standard `created_at`/`updated_at`; a fixed
singleton primary key (`00000000-0000-0000-0000-000000000001`).
→ Blocked by: 1.A1.

**1.A3 — Alembic migration.**
New `alembic/versions/027_add_business_goals.py` following
`alembic/versions/026_token_usage_tables.py`. `upgrade()` creates the table and
seeds the singleton row with sane defaults (empty north star, `autonomy_level=gated`,
budget/caps from INTENT §9 illustration). Auto-runs on boot via
`roboco/db/base.py:141-177`. Provide `downgrade()`.
→ Blocked by: 1.A2.

**1.A4 — BusinessGoalsService.**
New `roboco/services/business_goals.py` extending `BaseService`
(`roboco/services/base.py:116`); follow `roboco/services/product.py`. Methods:
`get_or_initialize()` (singleton fetch-or-create) and `update(data, updated_by)`.
Add `get_business_goals_service(session)` factory at the file end.
→ Blocked by: 1.A2.

**1.A5 — Inject goals into every agent briefing.**
Add `company_goals` to `BriefingInputs` and `build_context_briefing` in
`roboco/services/gateway/evidence_builder.py:35-49,125-136`; fetch the singleton in
`_briefing_for` at `roboco/services/gateway/choreographer/_impl.py:703-732` and pass
it through. Wire `BusinessGoalsService` into the Choreographer's deps. Keep the
injected payload compact (north star + active objectives + gate list + caps).
→ Blocked by: 1.A4.

---

## Track B — API

**1.B1 — Request/response schemas.**
New `roboco/api/schemas/business_goals.py` following `roboco/api/schemas/product.py`
(`ConfigDict(from_attributes=True)` response, validated update request).
→ Blocked by: 1.A1.

**1.B2 — Goals endpoints + mount.**
New `roboco/api/routes/business_goals.py`: `GET /api/goals` (any authenticated
agent — they read it) and `PUT /api/goals` (CEO-only — copy the
`agent.role != AgentRole.CEO → 403` gate from `roboco/api/routes/tasks.py:1321`).
Mount under prefix `/api/goals` in `roboco/api/app.py` (see the `include_router`
block ~`app.py:201-309`).
→ Blocked by: 1.A4, 1.B1.

---

## Track C — Panel

**1.C1 — Shared types.**
Add `BusinessGoals`, `Objective`, `OperatingPolicy`, and the new enums to
`panel/src/types/index.ts`, mirroring the backend model from 1.A1.
→ Blocked by: 1.A1.

**1.C2 — API client + data hook.**
New `panel/src/lib/api/goals.ts` (follow `panel/src/lib/api/tasks.ts`) with
`get()`/`update()`; new `panel/src/hooks/use-goals.ts` (follow
`panel/src/hooks/use-tasks.ts`) with a `useGoals()` query and `useUpdateGoals()`
mutation that invalidates on success.
→ Blocked by: 1.B2, 1.C1.

**1.C3 — Goals editor page + nav.**
New page `panel/src/app/(dashboard)/goals/page.tsx` (follow the structure of
`panel/src/app/(dashboard)/tasks/page.tsx`) letting the CEO edit north star,
objectives, operating policy, and constraints; show derived read-only fields as
placeholders for now. Add a sidebar nav item in
`panel/src/components/layout/sidebar.tsx:30-56`.
→ Blocked by: 1.C2.

---

## Track D — Prompt

**1.D1 — Make agents goal-aware.**
Update the universal prompt `agents/prompts/base.md` to instruct every agent to
read `context_briefing.company_goals` and align its work to the active objectives
and constraints. Reinforce in the Board and PM role prompts
(`agents/prompts/roles/board.md`, `main_pm.md`, `cell_pm.md`) that work should
serve a stated objective. No verb/spec change needed for this phase.
→ Blocked by: 1.A5 (the briefing must actually carry goals first).

---

## Parallelization summary

- **Start now, in parallel:** `1.A1`, and (after it) `1.B1` + `1.C1` immediately.
- **Backend chain:** `1.A1 → 1.A2 → {1.A3, 1.A4} → 1.A5 → 1.D1`.
- **API:** `1.B2` once `1.A4` + `1.B1` land — unblocks all of Track C's data.
- **Panel:** `1.C2 → 1.C3` once `1.B2` is up.
- **Phase is "complete"** (the gate Phases 3/4/5/6 wait on) when `1.A5` (briefing)
  and `1.B2` (API) are merged — model, service, injection, and CEO editing all live.
