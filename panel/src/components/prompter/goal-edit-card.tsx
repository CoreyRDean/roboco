"use client";

import { Target, Check, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { BusinessGoalsUpdate, Objective, OperatingPolicy } from "@/types";

interface GoalEditCardProps {
  patch: BusinessGoalsUpdate;
  onConfirm: () => void;
  onDismiss: () => void;
  /** The PUT /goals call is in flight — disable the actions. */
  isConfirming?: boolean;
}

function policyLines(policy: OperatingPolicy): string[] {
  const out: string[] = [];
  if (policy.autonomy_level) out.push(`Autonomy: ${policy.autonomy_level}`);
  if (policy.gate_list?.length) out.push(`Gates: ${policy.gate_list.join(", ")}`);
  if (policy.monthly_budget_usd != null)
    out.push(`Budget: $${policy.monthly_budget_usd}/mo`);
  if (policy.max_active_products != null)
    out.push(`Max active products: ${policy.max_active_products}`);
  if (policy.strategy_cadence) out.push(`Cadence: ${policy.strategy_cadence}`);
  return out;
}

function ObjectiveRow({ obj }: { obj: Objective }) {
  return (
    <li className="flex items-start gap-2 text-xs">
      <span className="mt-0.5 h-3 w-3 shrink-0 rounded-full border border-primary/50" />
      <span className="text-foreground">
        <span className="font-medium">{obj.title}</span>
        {obj.description ? (
          <span className="text-muted-foreground"> — {obj.description}</span>
        ) : null}
        {obj.target ? (
          <span className="text-muted-foreground"> ({obj.target})</span>
        ) : null}
      </span>
    </li>
  );
}

/**
 * Inline confirm-card for a Secretary-proposed Business Goals edit. The agent
 * only PROPOSES the patch (it has no goal-write authority); the CEO confirms it
 * here and the panel applies it (PUT /goals) — landing in the same singleton
 * charter the Panel goals editor writes. Mirrors the draft card's confirm seam.
 */
export function GoalEditCard({
  patch,
  onConfirm,
  onDismiss,
  isConfirming = false,
}: GoalEditCardProps) {
  return (
    <Card className="border-violet-500/40 bg-violet-500/5">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-violet-500" />
          <CardTitle className="text-sm font-semibold leading-tight">
            Proposed goal change
          </CardTitle>
          <Badge variant="outline" className="ml-auto text-xs">
            needs your confirm
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 pb-3">
        {patch.north_star != null && (
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              North star
            </p>
            <p className="text-sm text-foreground">{patch.north_star}</p>
          </div>
        )}

        {patch.objectives != null && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">
              Objectives ({patch.objectives.length})
            </p>
            <ul className="space-y-1">
              {patch.objectives.map((obj, i) => (
                <ObjectiveRow key={`${obj.title}-${i}`} obj={obj} />
              ))}
            </ul>
          </div>
        )}

        {patch.constraints != null && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              Constraints:
            </span>
            {patch.constraints.length === 0 ? (
              <span className="text-xs text-muted-foreground">(cleared)</span>
            ) : (
              patch.constraints.map((c) => (
                <Badge key={c} variant="outline" className="text-xs">
                  {c}
                </Badge>
              ))
            )}
          </div>
        )}

        {patch.operating_policy != null && (
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Operating policy
            </p>
            <ul className="space-y-0.5">
              {policyLines(patch.operating_policy).map((line) => (
                <li key={line} className="text-xs text-foreground">
                  {line}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex-wrap gap-2 pt-0">
        <Button
          variant="outline"
          size="sm"
          onClick={onDismiss}
          disabled={isConfirming}
        >
          <X className="mr-1.5 h-3.5 w-3.5" />
          Dismiss
        </Button>
        <Button size="sm" onClick={onConfirm} disabled={isConfirming}>
          {isConfirming ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Check className="mr-1.5 h-3.5 w-3.5" />
          )}
          Confirm change
        </Button>
      </CardFooter>
    </Card>
  );
}
