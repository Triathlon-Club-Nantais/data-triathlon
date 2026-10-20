import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import type { VolunteerActionSelfCreate } from "@/lib/types";
import { queryKeys } from "./keys";

export function useCreateVolunteerAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: VolunteerActionSelfCreate) => apiClient.createVolunteerAction(body),
    // La carte « Ma saison au club » compte l'action déclarée.
    onSuccess: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.myVolunteerDeclarations() }),
        qc.invalidateQueries({ queryKey: queryKeys.mySeasonQuota() }),
      ]),
  });
}
