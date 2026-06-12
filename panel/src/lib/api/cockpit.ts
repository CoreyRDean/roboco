import api from "./client";

// ---------------------------------------------------------------------------
// Cockpit — the CEO watch-surface derived state (Phase 6, specs/06-cockpit.md).
//
// A single read-only `GET /cockpit/summary` that answers "Is the business
// winning?" — composed server-side from already-built services (Business Goals,
// the Secretary's drift signal, UsageService spend projection, ProductService).
// Mirrors `roboco/api/schemas/cockpit.py`.
//
// Honest boundary (spec §"On winning"): every performance number is `basis:
// "proxy"` until real external launches are greenlit. The panel labels these as
// PROXY on screen — the cockpit does not pretend to measure revenue that isn't
// there.
// ---------------------------------------------------------------------------

/** One active objective with its proxy coverage signal. */
export interface ObjectiveProgress {
  title: string;
  priority: number;
  metric?: string | null;
  target?: string | null;
  horizon?: string | null;
  /** Proxy coverage: True when work is in flight that can serve the objectives. */
  has_work_behind_it: boolean;
}

/** Are the active objectives covered by work, and is work tied to a goal? */
export interface GoalCoverage {
  active_objectives: number;
  in_flight_tasks: number;
  work_without_objectives: boolean;
  objectives_without_work: boolean;
}

/** Projected monthly spend against the operating-policy budget cap. */
export interface SpendVsBudget {
  monthly_budget_usd: number;
  spend_30d_usd: number;
  projected_monthly_usd: number;
  projected_pct_of_budget?: number | null;
  over_budget: boolean;
}

/** Registered (active) products against the operating-policy concurrency cap. */
export interface ActiveProductsVsCap {
  active_products: number;
  max_active_products: number;
  at_cap: boolean;
}

/** Derived cockpit state — "Is the business winning?" at a glance. */
export interface CockpitSummary {
  /** Honest-boundary label; "proxy" until real external launches are greenlit. */
  basis: string;
  objectives: ObjectiveProgress[];
  goal_coverage: GoalCoverage;
  spend: SpendVsBudget;
  products: ActiveProductsVsCap;
  generated_at: string;
}

export const cockpitApi = {
  // The derived "winning?" snapshot: per-objective progress, goal-coverage +
  // drift, spend vs budget, active products vs cap. Read-only.
  summary: async (): Promise<CockpitSummary> => {
    const { data } = await api.get<CockpitSummary>("/cockpit/summary");
    return data;
  },
};
