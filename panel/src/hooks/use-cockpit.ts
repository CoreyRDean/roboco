"use client";

import { useQuery } from "@tanstack/react-query";
import { cockpitApi } from "@/lib/api/cockpit";
import type { CockpitSummary } from "@/lib/api/cockpit";

export const cockpitKeys = {
  all: ["cockpit"] as const,
  summary: () => [...cockpitKeys.all, "summary"] as const,
};

/**
 * The derived "Is the business winning?" snapshot (6.B1): per-objective proxy
 * progress, goal-coverage + drift, spend vs budget, active products vs cap.
 * Polled like the other dashboard hooks so the cockpit stays current.
 */
export function useCockpitSummary() {
  return useQuery<CockpitSummary>({
    queryKey: cockpitKeys.summary(),
    queryFn: () => cockpitApi.summary(),
    refetchInterval: 60000, // Refetch every minute
  });
}
