"use client";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import { isPodium } from "@/lib/utils/club-aggregate";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
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
  return (
    <Card>
      <CardContent>
        <Stat value={count} label="Podiums" />
      </CardContent>
    </Card>
  );
}
