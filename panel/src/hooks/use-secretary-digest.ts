import { useQuery } from "@tanstack/react-query";
import { secretaryApi } from "@/lib/api/secretary";

// Query keys
export const secretaryKeys = {
  all: ["secretary"] as const,
  digest: () => [...secretaryKeys.all, "digest"] as const,
};

// The Secretary proactive feed (3.A2). Polls on a slow cadence so the strip
// stays current without the CEO refreshing; cadence/channel are matured in
// Phase 5, this just keeps the panel view fresh.
export function useSecretaryDigest() {
  return useQuery({
    queryKey: secretaryKeys.digest(),
    queryFn: () => secretaryApi.digest(),
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // re-pull every minute
  });
}
