import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import type { ScrapedPreview } from "@/lib/types";

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
