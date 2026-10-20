import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { serializeSeasons } from "@/lib/utils/season";
import type { Gender } from "@/lib/scope";
import { queryKeys } from "./keys";

/**
 * Rang exact d'un athlète dans le roster club, au-delà de l'aperçu de 12
 * (#504, #641) — chargé à la demande, seulement quand `RosterApercu` en a
 * besoin (`enabled`). `null` si l'athlète n'a aucune participation validée au
 * club : un état normal (rappel générique), pas une panne.
 */
export function useClubRosterRank(
  athleteId: number,
  { federalOnly = false, seasons, gender, enabled }: { federalOnly?: boolean; seasons: number[]; gender?: Gender; enabled: boolean },
) {
  return useQuery({
    queryKey: queryKeys.clubRosterRank(athleteId, federalOnly, serializeSeasons(seasons), gender),
    queryFn: () => apiClient.getClubRosterRank(athleteId, { federal_only: federalOnly, seasons, gender }),
    enabled,
  });
}
