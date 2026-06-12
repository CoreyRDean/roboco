import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { goalsApi } from "@/lib/api/goals";
import type { BusinessGoalsUpdate } from "@/types";

// Query keys
export const goalKeys = {
  all: ["goals"] as const,
  detail: () => [...goalKeys.all, "detail"] as const,
};

// Read the company charter (the singleton Business Goals artifact)
export function useGoals() {
  return useQuery({
    queryKey: goalKeys.detail(),
    queryFn: () => goalsApi.get(),
    staleTime: 30000, // 30 seconds
  });
}

// Revise the charter (CEO-only) and refresh the cached copy on success
export function useUpdateGoals() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (updates: BusinessGoalsUpdate) => goalsApi.update(updates),
    onSuccess: (goals) => {
      queryClient.setQueryData(goalKeys.detail(), goals);
      queryClient.invalidateQueries({ queryKey: goalKeys.all });
    },
  });
}
