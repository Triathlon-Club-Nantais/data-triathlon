"use client";
import { useSearchParams } from "next/navigation";
import { BarList } from "@/components/charts/BarList";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { rankTypeLabel } from "@/lib/labels";
import type { DashboardRankCounters, RankCountersBucket } from "@/lib/types";

const LABELS: Record<string, string> = {
  victories: "Victoires",
  podiums: "Podiums",
  top10: "Top 10",
};

function sumBuckets(a: RankCountersBucket, b: RankCountersBucket): RankCountersBucket {
  return {
    victories: a.victories + b.victories,
    podiums: a.podiums + b.podiums,
    top10: a.top10 + b.top10,
  };
}

/**
 * Performance collective du club (victoires/podiums/top10) en graphique,
 * complémentaire des cartes chiffrées de `StatCardsRank` — même source
 * (`rank_counters`, `GET /stats`), même lecture autonome de `?rank=`, pour
 * réagir au même geste sans re-fetch ni duplication de state (#132/#328). La
 * saison est déjà filtrée côté serveur : un changement de `SeasonSelector`
 * fait naviguer la page et renouvelle `rankCounters` en entier (US8, #466).
 * En mode `gender`, femmes et hommes sont agrégés — la ventilation par sexe
 * reste la responsabilité de `StatCardsRank` (`GenderPair`), ce composant ne
 * la duplique pas.
 */
export function ClubPerformanceChart({ rankCounters }: { rankCounters: DashboardRankCounters }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const rankLabel = rankTypeLabel(rankType, { form: "long" });
  const counters =
    rankType === "gender"
      ? sumBuckets(rankCounters.gender.women, rankCounters.gender.men)
      : rankCounters[rankType];

  const entries: [string, number][] = [
    ["victories", counters.victories],
    ["podiums", counters.podiums],
    ["top10", counters.top10],
  ];

  return (
    <BarList
      entries={entries}
      labeller={(key) => LABELS[key]}
      subjectLabel={`classement ${rankLabel}`}
      emptyTitle="Aucun classement sur cette sélection"
    />
  );
}
