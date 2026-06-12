"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useCockpitSummary } from "@/hooks/use-cockpit";
import { TaskStatus, type Task } from "@/types";
import Link from "next/link";
import {
  Target,
  Coins,
  Boxes,
  CircleAlert,
  CircleDot,
  Activity,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";

function fmtCost(n: number): string {
  return "$" + n.toFixed(n >= 100 ? 0 : 2);
}

// Honest-boundary label (spec §"On winning"): every cockpit performance number
// is a proxy until real external launches are greenlit. Stamp it on the section
// so the CEO never reads these as measured revenue.
function ProxyBadge() {
  return (
    <Badge
      variant="outline"
      className="border-amber-400/60 text-amber-600 dark:text-amber-400 text-[10px] uppercase tracking-wide"
      title="Proxy metrics — honest until real external launches are greenlit (spec §'On winning')"
    >
      Proxy
    </Badge>
  );
}

/** Spend vs budget — headlines ACTUAL spend (30d) against the cap; the projected
 *  run-rate is a secondary forecast (amber when it would exceed the cap), never
 *  shown as money already spent. */
function SpendCard({
  monthlyBudget,
  spend30d,
  projectedMonthly,
  overBudget,
}: {
  monthlyBudget: number;
  spend30d: number;
  projectedMonthly: number;
  // True when the *projection* would exceed the cap — a forecast caution, not a
  // breach of actual spend.
  overBudget: boolean;
}) {
  const actualPct = monthlyBudget > 0 ? (spend30d / monthlyBudget) * 100 : 0;
  const actualOver = spend30d > monthlyBudget;
  const chartData = [{ name: "Spend", value: spend30d, budget: monthlyBudget }];
  const barColor = actualOver ? "var(--destructive)" : "var(--chart-2)";

  return (
    <Card className={actualOver ? "border-destructive/50" : undefined}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Coins className="h-4 w-4" />
            Spend vs Budget
          </CardTitle>
          <ProxyBadge />
        </div>
        <CardDescription>Actual spend (30d) against the cap</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline justify-between">
          <span
            className={
              "text-2xl font-bold " + (actualOver ? "text-destructive" : "")
            }
          >
            {fmtCost(spend30d)}
          </span>
          <span className="text-sm text-muted-foreground">
            of {fmtCost(monthlyBudget)} cap
          </span>
        </div>
        <ResponsiveContainer width="100%" height={56}>
          <BarChart
            layout="vertical"
            data={chartData}
            margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
          >
            <CartesianGrid horizontal={false} strokeDasharray="3 3" className="opacity-20" />
            <XAxis
              type="number"
              domain={[0, Math.max(monthlyBudget, spend30d)]}
              hide
            />
            <YAxis type="category" dataKey="name" hide />
            <Tooltip
              formatter={(value) => [fmtCost(typeof value === "number" ? value : 0), "Spent (30d)"]}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="value" radius={[3, 3, 3, 3]} barSize={18}>
              <Cell fill={barColor} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Activity className="h-3 w-3" />
            {actualPct.toFixed(0)}% of budget used
          </span>
          <span
            className={
              "flex items-center gap-1 " +
              (overBudget ? "text-amber-600 dark:text-amber-500" : "")
            }
            title="Projected monthly cost at the current usage rate"
          >
            ~{fmtCost(projectedMonthly)}/mo projected
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

/** Active products vs the concurrency cap. */
function ProductsCard({
  active,
  cap,
  atCap,
}: {
  active: number;
  cap: number;
  atCap: boolean;
}) {
  const pct = cap > 0 ? Math.min(100, (active / cap) * 100) : 0;
  return (
    <Card className={atCap ? "border-amber-400/50" : undefined}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Boxes className="h-4 w-4" />
            Active Products
          </CardTitle>
          <ProxyBadge />
        </div>
        <CardDescription>Registered products against the cap</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-bold">
            {active}
            <span className="text-base font-normal text-muted-foreground"> / {cap}</span>
          </span>
          {atCap && (
            <Badge variant="secondary" className="text-amber-600 dark:text-amber-400">
              At cap
            </Badge>
          )}
        </div>
        <Progress
          value={pct}
          className={atCap ? "[&_[data-slot=progress-indicator]]:bg-amber-500" : undefined}
        />
        <p className="text-xs text-muted-foreground">
          {atCap
            ? "Concurrency cap reached — new product generation is held."
            : `Room for ${Math.max(0, cap - active)} more active product${cap - active === 1 ? "" : "s"}.`}
        </p>
      </CardContent>
    </Card>
  );
}

/** Per-objective proxy progress: the standing objectives and whether work is in
 *  flight behind them (the coverage proxy — no per-objective task linkage). */
function ObjectivesCard({
  objectives,
  inFlight,
}: {
  objectives: {
    title: string;
    priority: number;
    metric?: string | null;
    target?: string | null;
    horizon?: string | null;
    has_work_behind_it: boolean;
  }[];
  inFlight: number;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Target className="h-4 w-4" />
            Objective Progress
          </CardTitle>
          <ProxyBadge />
        </div>
        <CardDescription>
          Coverage proxy — whether work is in flight behind each active objective
        </CardDescription>
      </CardHeader>
      <CardContent>
        {objectives.length === 0 ? (
          <div className="text-center py-4 text-sm text-muted-foreground">
            <Target className="h-8 w-8 mx-auto mb-2 opacity-50" />
            No active objectives set
          </div>
        ) : (
          <ul className="space-y-3">
            {objectives.map((o, i) => (
              <li key={i} className="space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium line-clamp-2">{o.title}</span>
                  {o.has_work_behind_it ? (
                    <Badge variant="secondary" className="shrink-0 text-xs gap-1">
                      <TrendingUp className="h-3 w-3" />
                      Work in flight
                    </Badge>
                  ) : (
                    <Badge
                      variant="outline"
                      className="shrink-0 text-xs gap-1 border-amber-400/60 text-amber-600 dark:text-amber-400"
                    >
                      <CircleDot className="h-3 w-3" />
                      No work yet
                    </Badge>
                  )}
                </div>
                {(o.metric || o.target || o.horizon) && (
                  <p className="text-xs text-muted-foreground">
                    {[o.metric, o.target && `→ ${o.target}`, o.horizon]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 pt-3 border-t text-xs text-muted-foreground">
          {inFlight} task{inFlight === 1 ? "" : "s"} in flight company-wide (no
          per-objective task linkage today).
        </p>
      </CardContent>
    </Card>
  );
}

/**
 * Performance view (6.C1) — renders GET /api/cockpit/summary so the CEO can
 * answer "Is the business winning?" at a glance: spend vs budget, active vs cap,
 * per-objective progress, goal-coverage. The drift signal (6.C3) rides on the
 * same payload (goal_coverage) and is surfaced separately in the command center.
 * Every metric is labelled PROXY per the honest boundary (spec §"On winning").
 */
export function PerformanceView() {
  const { data: summary, isLoading } = useCockpitSummary();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-48 w-full" />
        ))}
      </div>
    );
  }

  if (!summary) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Performance summary unavailable.
        </CardContent>
      </Card>
    );
  }

  const { spend, products, objectives, goal_coverage } = summary;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
      <SpendCard
        monthlyBudget={spend.monthly_budget_usd}
        spend30d={spend.spend_30d_usd}
        projectedMonthly={spend.projected_monthly_usd}
        overBudget={spend.over_budget}
      />
      <ProductsCard
        active={products.active_products}
        cap={products.max_active_products}
        atCap={products.at_cap}
      />
      <div className="md:col-span-2">
        <ObjectivesCard
          objectives={objectives}
          inFlight={goal_coverage.in_flight_tasks}
        />
      </div>
    </div>
  );
}

/**
 * DRIFT signal (6.C3, drift half) — work or spend not tied to an active
 * objective, surfaced as a visible banner rather than buried. Derives from the
 * same cockpit summary (goal_coverage). Renders nothing when there is no drift,
 * so it only appears when it earns the CEO's attention.
 */
export function DriftSignal() {
  const { data: summary } = useCockpitSummary();
  const coverage = summary?.goal_coverage;
  if (!coverage) return null;

  const workNoGoal = coverage.work_without_objectives;
  const goalNoWork = coverage.objectives_without_work;
  if (!workNoGoal && !goalNoWork) return null;

  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-400/60 bg-amber-50 dark:bg-amber-950/30 p-4">
      <CircleAlert className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-amber-700 dark:text-amber-300">
            Drift detected
          </p>
          <ProxyBadge />
        </div>
        <ul className="text-sm text-amber-800/90 dark:text-amber-200/90 space-y-0.5">
          {workNoGoal && (
            <li>
              {coverage.in_flight_tasks} task
              {coverage.in_flight_tasks === 1 ? " is" : "s are"} in flight with no
              active objective behind them.
            </li>
          )}
          {goalNoWork && (
            <li>
              {coverage.active_objectives} active objective
              {coverage.active_objectives === 1 ? " has" : "s have"} no work in
              flight.
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}

/**
 * STALL signal (6.C3, stall half) — stranded work that needs the CEO, surfaced
 * as a visible banner above the fold rather than buried in the lower blockers
 * grid. Stalls land as blocked tasks (Phase 5 stall surfacing also routes them
 * into the action queue / notifications); this banner makes them impossible to
 * miss at a glance. Renders nothing when there is no stalled work.
 */
export function StallSignal({ tasks }: { tasks: Task[] | undefined }) {
  const stalled = (tasks ?? []).filter((t) => t.status === TaskStatus.BLOCKED);
  if (stalled.length === 0) return null;

  return (
    <Link href="/tasks?status=blocked" className="block">
      <div className="flex items-center gap-3 rounded-lg border border-red-300 bg-red-50 dark:bg-red-950/30 dark:border-red-900 p-4 hover:bg-red-100 dark:hover:bg-red-950/50 transition-colors">
        <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-700 dark:text-red-300">
            {stalled.length} task{stalled.length === 1 ? "" : "s"} stalled
          </p>
          <p className="text-sm text-red-800/90 dark:text-red-200/90 truncate">
            Work has stranded and needs attention — review the blocked queue.
          </p>
        </div>
        <ArrowRight className="h-4 w-4 text-red-600 dark:text-red-400 shrink-0" />
      </div>
    </Link>
  );
}
