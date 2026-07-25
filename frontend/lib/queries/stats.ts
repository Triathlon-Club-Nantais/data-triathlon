import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";

export function useStats(scope?: "club") {
  return useQuery({
    queryKey: queryKeys.stats(scope),
    queryFn: () => apiClient.getStats({ scope }),
  });
}

/** Feed live : participations récentes, rafraîchies toutes les 15 s. */
export function useLiveFeed(scope?: "club") {
  return useQuery({
    queryKey: ["live-feed", scope ?? null],
    queryFn: () => apiClient.listParticipations({ scope, page_size: 20 }),
    refetchInterval: 15000,
  });
}
