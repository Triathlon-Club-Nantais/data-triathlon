import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import type { VolunteerDeclarationCreate } from "@/lib/types";
import { queryKeys } from "./keys";

export function useMyVolunteerDeclarations() {
  return useQuery({
    queryKey: queryKeys.myVolunteerDeclarations(),
    queryFn: () => apiClient.listMyVolunteerDeclarations(),
  });
}

export function useCreateVolunteerDeclaration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: VolunteerDeclarationCreate) => apiClient.createVolunteerDeclaration(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.myVolunteerDeclarations() }),
  });
}

export function useDeleteMyVolunteerDeclaration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.deleteMyVolunteerDeclaration(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.myVolunteerDeclarations() }),
  });
}
