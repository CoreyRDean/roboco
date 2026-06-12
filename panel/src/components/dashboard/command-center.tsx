"use client";

import { useCeoOverview, useAuditorFlags, useRecentActivity } from "@/hooks/use-dashboard";
import { useTasks } from "@/hooks/use-tasks";
import { TeamHealthCards } from "./team-health-cards";
import { KeyMetricsPanel } from "./key-metrics-panel";
import { AuditorAlertsPanel } from "./auditor-alerts-panel";
import { ActiveBlockersPanel } from "./active-blockers-panel";
import { RecentActivityFeed } from "./recent-activity-feed";
import { QuickActionsBar } from "./quick-actions-bar";
import { CeoApprovalQueue } from "./ceo-approval-queue";
import { PerformanceView, DriftSignal, StallSignal } from "./performance-view";
import type { Activity } from "./activity-item";
import { Button } from "@/components/ui/button";
import { UsageOverviewPanel } from "./usage-overview-panel";
import { RefreshCw, Settings } from "lucide-react";
import Link from "next/link";

export function CommandCenter() {
  const { data: overview, isLoading: loadingOverview, refetch: refetchOverview } = useCeoOverview();
  const { data: flags, isLoading: loadingFlags } = useAuditorFlags({ resolved: false });
  const { data: tasks, isLoading: loadingTasks } = useTasks();
  const { data: activity, isLoading: loadingActivity } = useRecentActivity(24);

  const handleRefresh = () => {
    refetchOverview();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">RoboCo Command Center</h1>
          <p className="text-muted-foreground">
            Complete visibility into all operations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Link href="/settings">
            <Button variant="ghost" size="icon">
              <Settings className="h-5 w-5" />
            </Button>
          </Link>
        </div>
      </div>

      {/* CEO Approval Queue — the focal point: what needs the CEO, top of the
          overview so a gated decision is impossible to miss (6.C2). */}
      <section>
        <CeoApprovalQueue />
      </section>

      {/* Drift & stall signals — surfaced above the fold, not buried (6.C3).
          Each renders only when it has something to say. */}
      <DriftSignal />
      <StallSignal tasks={tasks} />

      {/* Performance — "Is the business winning?" proxy metrics (6.C1). */}
      <section>
        <h2 className="text-lg font-semibold mb-4">
          Performance{" "}
          <span className="text-sm font-normal text-muted-foreground">
            (proxy until external launch)
          </span>
        </h2>
        <PerformanceView />
      </section>

      {/* Team Health */}
      <section>
        <h2 className="text-lg font-semibold mb-4">Team Health</h2>
        <TeamHealthCards
          teams={overview?.health_status}
          isLoading={loadingOverview}
        />
      </section>

      {/* Metrics, Alerts, and Usage Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <KeyMetricsPanel
          metrics={overview?.key_metrics}
          isLoading={loadingOverview}
        />
        <AuditorAlertsPanel alerts={flags} isLoading={loadingFlags} />
        <UsageOverviewPanel />
      </div>

      {/* Blockers and Activity Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ActiveBlockersPanel tasks={tasks} isLoading={loadingTasks} />
        <RecentActivityFeed
          activities={activity as Activity[] | undefined}
          isLoading={loadingActivity}
        />
      </div>

      {/* Quick Actions */}
      <section className="pt-4 border-t">
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <QuickActionsBar />
      </section>
    </div>
  );
}
