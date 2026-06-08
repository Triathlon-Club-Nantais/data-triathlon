import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";
import type { ParticipationFilters, ScrapedPreview } from "@/lib/types";

export function useParticipations(filters: ParticipationFilters = {}, enabled = true) {
  return useQuery({
    queryKey: queryKeys.participations(filters),
    queryFn: () => apiClient.listParticipations(filters),
    enabled,
  });
}

export function useSaveParticipation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<ScrapedPreview>) => apiClient.saveParticipation(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["participations"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useDeleteParticipation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.deleteParticipation(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["participations"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}
