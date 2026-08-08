import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";
import type { BatchRun, RescrapeLaunch } from "@/lib/types";

/** Cadence de rafraîchissement pendant qu'une exécution travaille. */
const RAFRAICHISSEMENT_MS = 15_000;

/**
 * Les derniers lancements (#47).
 *
 * `enabled` plutôt qu'un appel systématique : un porteur de `batch:run` seul
 * n'a pas `batch:read`, et l'interroger lui afficherait un bloc en 403 à la
 * place de l'état courant. L'appelant passe ce qu'il sait de la session.
 *
 * Le rafraîchissement ne tourne **que** tant qu'une exécution est en cours. Un
 * intervalle permanent ferait battre un onglet ouvert toute la journée contre
 * l'API de la plateforme, qui compte les appels.
 */
export function useBatchRuns(enabled = true) {
  return useQuery({
    queryKey: queryKeys.batchRuns(),
    queryFn: () => apiClient.listBatchRuns(),
    enabled,
    refetchInterval: (query) =>
      (query.state.data as BatchRun[] | undefined)?.some((run) =>
        ["pending", "running"].includes(run.state),
      )
        ? RAFRAICHISSEMENT_MS
        : false,
  });
}

/**
 * Les fournisseurs ciblables, tels que le registre backend les énumère.
 *
 * `staleTime: Infinity` : la liste ne bouge qu'au déploiement d'un nouveau
 * provider, un rechargement d'onglet suffit à la reprendre.
 */
export function useProviders() {
  return useQuery({
    queryKey: queryKeys.providers(),
    queryFn: () => apiClient.listProviders(),
    staleTime: Infinity,
  });
}

export function useLaunchBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (options: RescrapeLaunch) => apiClient.launchBatch(options),
    // La plateforme ne rend aucun identifiant au dispatch : c'est cette
    // invalidation qui fait apparaître l'exécution dans la liste, où on la
    // retrouve par son `correlation_id`.
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.batchRuns() }),
  });
}

/**
 * Le bilan d'un lancement — chargé à la demande, jamais avec la liste.
 *
 * `retry: false` : les trois refus possibles (404 pas de bilan, 410 expiré,
 * 503 plateforme) sont des réponses, pas des incidents réseau. Réessayer ne
 * ferait que retarder le message.
 */
export function useBatchReport(runId: number | null) {
  return useQuery({
    queryKey: queryKeys.batchReport(runId ?? 0),
    queryFn: () => apiClient.getBatchReport(runId as number),
    enabled: runId !== null,
    retry: false,
  });
}
