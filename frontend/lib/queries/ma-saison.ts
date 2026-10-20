import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { compteMaSaison } from "@/lib/utils/ma-saison";
import { serializeSeasons } from "@/lib/utils/season";
import { queryKeys } from "./keys";

/** Épreuves des saisons sélectionnées d'un athlète (même fetch et même règle de compte que Mon espace). `undefined` tant que le compte charge ou si le fetch échoue. */
export function useEpreuvesSaison(athleteId: number | undefined, selected: number[], federalOnly = true) {
  const seasons = serializeSeasons(selected);
  const { data } = useQuery({
    queryKey: queryKeys.epreuvesSaison(athleteId ?? 0, seasons, federalOnly),
    queryFn: async () => {
      const detail = await apiClient.getAthlete(athleteId!, { seasons, federal_only: federalOnly });
      return compteMaSaison(detail.participations, "all").epreuves;
    },
    enabled: athleteId !== undefined,
    retry: false,
  });
  return data;
}
