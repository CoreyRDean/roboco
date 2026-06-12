"use client";

import { useEffect, useState } from "react";
import { useGoals, useUpdateGoals } from "@/hooks/use-goals";
import {
  AutonomyLevel,
  ObjectiveStatus,
  StrategyCadence,
  type BusinessGoals,
  type Objective,
} from "@/types";
import { getErrorMessage } from "@/lib/api/client";
import { OfflineState } from "@/components/ui/offline-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2, Save } from "lucide-react";
import { toast } from "sonner";

// One blank objective for the "add" action.
function emptyObjective(priority: number): Objective {
  return {
    title: "",
    description: null,
    metric: null,
    target: null,
    horizon: null,
    priority,
    status: ObjectiveStatus.ACTIVE,
  };
}

// A multi-line text area drives constraints/gate_list (one entry per line) —
// the simplest editable surface for a string list.
function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function GoalsEditor({ goals }: { goals: BusinessGoals }) {
  const updateGoals = useUpdateGoals();

  // Local editable copy, seeded from the server and re-seeded when it changes.
  const [northStar, setNorthStar] = useState(goals.north_star);
  const [objectives, setObjectives] = useState<Objective[]>(goals.objectives);
  const [constraintsText, setConstraintsText] = useState(
    goals.constraints.join("\n"),
  );
  const [policy, setPolicy] = useState(goals.operating_policy);

  useEffect(() => {
    setNorthStar(goals.north_star);
    setObjectives(goals.objectives);
    setConstraintsText(goals.constraints.join("\n"));
    setPolicy(goals.operating_policy);
  }, [goals]);

  const setObjective = (index: number, patch: Partial<Objective>) => {
    setObjectives((prev) =>
      prev.map((o, i) => (i === index ? { ...o, ...patch } : o)),
    );
  };

  const addObjective = () => {
    setObjectives((prev) => [...prev, emptyObjective(prev.length + 1)]);
  };

  const removeObjective = (index: number) => {
    setObjectives((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSave = () => {
    updateGoals.mutate(
      {
        north_star: northStar,
        objectives,
        constraints: linesToList(constraintsText),
        operating_policy: policy,
      },
      {
        onSuccess: () => toast.success("Business goals updated"),
        onError: (error) => toast.error(getErrorMessage(error)),
      },
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Business Goals</h1>
          <p className="text-muted-foreground">
            The single CEO-owned charter every agent orients to — direction,
            objectives, and the operating-policy leash.
          </p>
        </div>
        <Button onClick={handleSave} disabled={updateGoals.isPending}>
          <Save className="h-4 w-4 mr-2" />
          {updateGoals.isPending ? "Saving…" : "Save"}
        </Button>
      </div>

      {/* Direction */}
      <Card>
        <CardHeader>
          <CardTitle>Direction</CardTitle>
          <CardDescription>
            The overarching mission and the inviolable boundaries the company
            must always respect.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="north-star">North star</Label>
            <Textarea
              id="north-star"
              value={northStar}
              onChange={(e) => setNorthStar(e.target.value)}
              placeholder="Become the default workbench for solo AI developers."
              rows={2}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="constraints">Constraints (one per line)</Label>
            <Textarea
              id="constraints"
              value={constraintsText}
              onChange={(e) => setConstraintsText(e.target.value)}
              placeholder={"B2B only\nno crypto\nRust + TypeScript preferred"}
              rows={4}
            />
          </div>
        </CardContent>
      </Card>

      {/* Objectives */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Objectives</CardTitle>
              <CardDescription>
                The prioritized goals. Metric, target, and horizon are optional —
                qualitative objectives are first-class.
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={addObjective}>
              <Plus className="h-4 w-4 mr-2" />
              Add objective
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {objectives.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No objectives yet. Add one to give the company a direction.
            </p>
          ) : (
            objectives.map((objective, index) => (
              <div
                key={index}
                className="rounded-lg border p-4 space-y-4"
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1 space-y-2">
                    <Label htmlFor={`obj-title-${index}`}>Title</Label>
                    <Input
                      id={`obj-title-${index}`}
                      value={objective.title}
                      onChange={(e) =>
                        setObjective(index, { title: e.target.value })
                      }
                      placeholder="Ship a usable v1 of one flagship product"
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="mt-7 text-muted-foreground hover:text-destructive"
                    onClick={() => removeObjective(index)}
                    title="Remove objective"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label htmlFor={`obj-desc-${index}`}>Description</Label>
                  <Textarea
                    id={`obj-desc-${index}`}
                    value={objective.description ?? ""}
                    onChange={(e) =>
                      setObjective(index, {
                        description: e.target.value || null,
                      })
                    }
                    placeholder="What success looks like"
                    rows={2}
                  />
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-2">
                    <Label htmlFor={`obj-metric-${index}`}>Metric</Label>
                    <Input
                      id={`obj-metric-${index}`}
                      value={objective.metric ?? ""}
                      onChange={(e) =>
                        setObjective(index, {
                          metric: e.target.value || null,
                        })
                      }
                      placeholder="(optional)"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`obj-target-${index}`}>Target</Label>
                    <Input
                      id={`obj-target-${index}`}
                      value={objective.target ?? ""}
                      onChange={(e) =>
                        setObjective(index, {
                          target: e.target.value || null,
                        })
                      }
                      placeholder="(optional)"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`obj-horizon-${index}`}>Horizon</Label>
                    <Input
                      id={`obj-horizon-${index}`}
                      value={objective.horizon ?? ""}
                      onChange={(e) =>
                        setObjective(index, {
                          horizon: e.target.value || null,
                        })
                      }
                      placeholder="Q3 2026"
                    />
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor={`obj-priority-${index}`}>Priority</Label>
                    <Input
                      id={`obj-priority-${index}`}
                      type="number"
                      min={1}
                      value={objective.priority}
                      onChange={(e) =>
                        setObjective(index, {
                          priority: Math.max(
                            1,
                            parseInt(e.target.value, 10) || 1,
                          ),
                        })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Status</Label>
                    <Select
                      value={objective.status}
                      onValueChange={(value) =>
                        setObjective(index, {
                          status: value as ObjectiveStatus,
                        })
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.values(ObjectiveStatus).map((status) => (
                          <SelectItem key={status} value={status}>
                            {status}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Operating policy */}
      <Card>
        <CardHeader>
          <CardTitle>Operating policy</CardTitle>
          <CardDescription>
            The leash — how much autonomy the company has and the hard limits it
            runs within.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Autonomy level</Label>
              <Select
                value={policy.autonomy_level}
                onValueChange={(value) =>
                  setPolicy((p) => ({
                    ...p,
                    autonomy_level: value as AutonomyLevel,
                  }))
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(AutonomyLevel).map((level) => (
                    <SelectItem key={level} value={level}>
                      {level}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Strategy cadence</Label>
              <Select
                value={policy.strategy_cadence}
                onValueChange={(value) =>
                  setPolicy((p) => ({
                    ...p,
                    strategy_cadence: value as StrategyCadence,
                  }))
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(StrategyCadence).map((cadence) => (
                    <SelectItem key={cadence} value={cadence}>
                      {cadence}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="monthly-budget">Monthly budget (USD)</Label>
              <Input
                id="monthly-budget"
                type="number"
                min={0}
                value={policy.monthly_budget_usd}
                onChange={(e) =>
                  setPolicy((p) => ({
                    ...p,
                    monthly_budget_usd: Math.max(
                      0,
                      parseInt(e.target.value, 10) || 0,
                    ),
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="max-products">Max active products</Label>
              <Input
                id="max-products"
                type="number"
                min={0}
                value={policy.max_active_products}
                onChange={(e) =>
                  setPolicy((p) => ({
                    ...p,
                    max_active_products: Math.max(
                      0,
                      parseInt(e.target.value, 10) || 0,
                    ),
                  }))
                }
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="gate-list">
              Gate list (one per line — always needs CEO approval)
            </Label>
            <Textarea
              id="gate-list"
              value={policy.gate_list.join("\n")}
              onChange={(e) =>
                setPolicy((p) => ({
                  ...p,
                  gate_list: linesToList(e.target.value),
                }))
              }
              placeholder={"spend\ngo_public\nnew_product_line\ncap_breach"}
              rows={4}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="github-org">Provisioning — GitHub org</Label>
              <Input
                id="github-org"
                value={policy.provisioning.github_org ?? ""}
                onChange={(e) =>
                  setPolicy((p) => ({
                    ...p,
                    provisioning: {
                      ...p.provisioning,
                      github_org: e.target.value || null,
                    },
                  }))
                }
                placeholder="(unset)"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="repo-visibility">Default repo visibility</Label>
              <Input
                id="repo-visibility"
                value={policy.provisioning.default_repo_visibility}
                onChange={(e) =>
                  setPolicy((p) => ({
                    ...p,
                    provisioning: {
                      ...p.provisioning,
                      default_repo_visibility: e.target.value,
                    },
                  }))
                }
                placeholder="private"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Derived (read-only — computed elsewhere, surfaced later) */}
      <Card>
        <CardHeader>
          <CardTitle>Derived</CardTitle>
          <CardDescription>
            Read-only, computed by the company. The CEO sets the charter above;
            these report against it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Per-objective progress, spend vs budget, goal-coverage, and drift
            land here once the work-generation engine (Phase 5) computes them.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function GoalsPage() {
  const { data: goals, isLoading, error, refetch } = useGoals();

  // Connection error (backend not running) — mirror the tasks page treatment.
  const isOffline =
    error &&
    (error.message?.includes("Network Error") ||
      error.message?.includes("ECONNREFUSED") ||
      (error as { code?: string })?.code === "ERR_NETWORK");

  if (isOffline) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Business Goals</h1>
          <p className="text-muted-foreground">
            The single CEO-owned charter every agent orients to.
          </p>
        </div>
        <OfflineState
          title="Cannot Load Business Goals"
          description="Start the RoboCo orchestrator to edit the company charter."
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  if (isLoading || !goals) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-9 w-48 mb-2" />
            <Skeleton className="h-5 w-96" />
          </div>
          <Skeleton className="h-10 w-24" />
        </div>
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  return <GoalsEditor goals={goals} />;
}
