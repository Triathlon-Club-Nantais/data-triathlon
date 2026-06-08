import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";

export function useStats(club?: string) {
  return useQuery({
    queryKey: queryKeys.stats(club),
    queryFn: () => apiClient.getStats(club),
  });
}

/** Feed live : participations récentes, rafraîchies toutes les 15 s. */
export function useLiveFeed(club?: string) {
  return useQuery({
    queryKey: ["live-feed", club ?? null],
    queryFn: () => apiClient.listParticipations({ club, page_size: 20 }),
    refetchInterval: 15000,
  });
}
