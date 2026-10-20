import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import type { VolunteerActionSelfCreate } from "@/lib/types";
import { queryKeys } from "./keys";

export function useCreateVolunteerAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: VolunteerActionSelfCreate) => apiClient.createVolunteerAction(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.myVolunteerDeclarations() }),
  });
}
