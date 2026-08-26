"use client";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { BarList } from "@/components/charts/BarList";
import { disciplinePerformance } from "@/lib/utils/club-aggregate";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { eventTypeLabel } from "@/lib/constants";
import { eventTypeColor } from "@/lib/sport-colors";
import type { DisciplinePodiumCounts } from "@/lib/types";

/**
 * Performance du club par discipline (podiums), distincte du décompte
 * d'épreuves par discipline déjà rendu par l'onglet « Par discipline »
 * (volume) — US10, #466. Recalcule selon `?rank=…` sans re-fetch, même patron
 * que `ClubPodiumKpi`/`PodiumsList` : `podiumsByDiscipline`/`byType`
 * arrivent déjà agrégés côté serveur dans `ClubSummary`/`Stats` (#642),
 * `/club` les transporte tous deux au chargement.
 */
export function DisciplinePerformance({
  podiumsByDiscipline,
  byType,
}: {
  podiumsByDiscipline: Record<string, DisciplinePodiumCounts>;
  byType: Record<string, number>;
}) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const performance = useMemo(
    () => disciplinePerformance(podiumsByDiscipline, byType, rankType),
    [podiumsByDiscipline, byType, rankType],
  );

  const entries: [string, number][] = performance.map((d) => [d.discipline, d.podiums]);
  const countByDiscipline = new Map(performance.map((d) => [d.discipline, d.count]));

  return (
    <BarList
      entries={entries}
      labeller={(key) => {
        const count = countByDiscipline.get(key) ?? 0;
        return `${eventTypeLabel(key)} (${count} épreuve${count > 1 ? "s" : ""})`;
      }}
      colorer={eventTypeColor}
      emptyTitle="Aucun podium"
      subjectLabel="discipline, en podiums"
    />
  );
}
