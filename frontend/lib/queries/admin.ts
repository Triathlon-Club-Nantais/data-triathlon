import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";

export function usePendingProviders() {
  return useQuery({
    queryKey: queryKeys.pendingProviders(),
    queryFn: () => apiClient.listPendingProviders(),
  });
}

export function useMarkProviderHandled() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.markProviderHandled(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.pendingProviders() }),
  });
}
