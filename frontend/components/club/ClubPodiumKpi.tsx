"use client";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { StatCard } from "@/components/tcn";
import { isPodium } from "@/lib/utils/club-aggregate";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { rankTypeLabel } from "@/lib/labels";
import type { Participation } from "@/lib/types";

/**
 * KPI « Podiums » côté client — recalcule selon `?rank=…` sans re-fetch RSC.
 * Les autres KPI (Résultats / Athlètes / Épreuves) ne dépendent pas du rank
 * et restent SSR dans `ClubDashboard`. Miroir du couple `StatCardsRank` +
 * `PodiumsList` (issue #132).
 */
export function ClubPodiumKpi({ participations }: { participations: Participation[] }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const count = useMemo(
    () => participations.reduce((n, p) => n + (isPodium(p, rankType) ? 1 : 0), 0),
    [participations, rankType],
  );
  // `accent={false}` comme les trois KPI SSR de `ClubDashboard` : le trait
  // orange reste à la seule tuile mise en avant (« Résultats »).
  // Le `delta` nomme la portée du décompte (#488, PROF-3) : le roster deux
  // blocs plus bas compte sur les trois portées cumulées, sans condition. Les
  // deux nombres sont justes et incomparables — chacun porte donc le sien.
  // Même geste que `StatCardsRank`, qui écrit déjà « 12 · général ».
  return (
    <StatCard
      label="Podiums"
      value={count}
      accent={false}
      delta={rankTypeLabel(rankType, { form: "long" })}
    />
  );
}
