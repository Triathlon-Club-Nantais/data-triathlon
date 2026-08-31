import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import type { VolunteerActionSelfCreate } from "@/lib/types";

export function useCreateVolunteerAction() {
  return useMutation({
    mutationFn: (body: VolunteerActionSelfCreate) => apiClient.createVolunteerAction(body),
  });
}
