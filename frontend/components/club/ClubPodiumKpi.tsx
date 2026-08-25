"use client";
import { useSearchParams } from "next/navigation";
import { StatCard } from "@/components/tcn";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { rankTypeLabel } from "@/lib/labels";
import type { DashboardRankCounters } from "@/lib/types";

/**
 * KPI « Podiums » côté client — recalcule selon `?rank=…` sans re-fetch RSC.
 * Lit `rankCounters` (déjà calculé côté backend, #376) au lieu de recompter
 * sur les participations brutes (#581) : même source que `StatCardsRank`.
 * Les autres KPI (Résultats / Athlètes / Épreuves) ne dépendent pas du rank
 * et restent SSR dans `ClubDashboard`. Miroir du couple `StatCardsRank` +
 * `PodiumsList` (issue #132).
 */
export function ClubPodiumKpi({ rankCounters }: { rankCounters: DashboardRankCounters }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const count =
    rankType === "gender"
      ? rankCounters.gender.women.podiums + rankCounters.gender.men.podiums
      : rankCounters[rankType].podiums;
  return (
    <StatCard
      label="Podiums"
      value={count}
      accent={false}
      delta={rankTypeLabel(rankType, { form: "long" })}
    />
  );
}
