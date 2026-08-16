"use client";
import type { ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { StatCard } from "@/components/tcn";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { rankTypeLabel } from "@/lib/labels";
import type { DashboardRankCounters } from "@/lib/types";

const TrophyIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 4h12v3a6 6 0 0 1-12 0V4z" /><path d="M6 5H3v2a3 3 0 0 0 3 3" /><path d="M18 5h3v2a3 3 0 0 1-3 3" /><path d="M9 17h6" /><path d="M12 13v4" /><path d="M8 21h8" /></svg>
);
const PodiumIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="4" width="6" height="17" /><rect x="2" y="10" width="6" height="11" /><rect x="16" y="8" width="6" height="13" /></svg>
);
const Top10Icon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="9" r="6" /><path d="M12 6v3l2 1" /><path d="M9 14l-2 7 5-3 5 3-2-7" /></svg>
);

// Rendu dédoublé F / H pour le mode gender (#104 US3). L'espacement passe par
// des marges plutôt que le `gap` du flex : le `gap` fait partie de la plage
// sélectionnable et peignait une bande orange dans le vide entre les libellés
// et leurs chiffres, une marge reste hors de la sélection (#375).
function GenderPair({ women, men }: { women: number; men: number }): ReactNode {
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", fontFamily: "var(--tcn-font-display)" }}>
      <span style={{ display: "inline-flex", alignItems: "baseline" }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: "var(--tcn-text-muted)", marginRight: 6 }}>F</span>
        <span>{women}</span>
      </span>
      <span style={{ display: "inline-flex", alignItems: "baseline", marginLeft: 18 }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: "var(--tcn-text-muted)", marginRight: 6 }}>H</span>
        <span>{men}</span>
      </span>
    </span>
  );
}

/**
 * Les 3 cartes « Victoires / Podiums / Top 10 » côté client.
 *
 * Les compteurs des 4 modes sont calculés **une fois** côté backend
 * (`stats_service.get_stats`, champ `rank_counters`) — ce composant ne fait
 * plus que choisir le bucket courant selon `?rank=…`, sans recalcul ni
 * re-fetch (#132/#328 restent vrais : aucun réseau au changement de mode).
 * Avant #376, ce composant recevait les participations brutes du club (jusqu'à
 * 5000 lignes) pour ce seul calcul — déplacé en backend, la page n'a plus à
 * les charger du tout.
 */
export function StatCardsRank({ rankCounters }: { rankCounters: DashboardRankCounters }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const rankLabel = rankTypeLabel(rankType, { form: "long" });

  if (rankType === "gender") {
    const { women, men } = rankCounters.gender;
    return (
      <>
        <StatCard label="Victoires" value={<GenderPair women={women.victories} men={men.victories} />} delta={rankLabel} icon={<TrophyIcon />} />
        <StatCard label="Podiums" value={<GenderPair women={women.podiums} men={men.podiums} />} delta={rankLabel} icon={<PodiumIcon />} />
        <StatCard label="Top 10" value={<GenderPair women={women.top10} men={men.top10} />} delta={rankLabel} icon={<Top10Icon />} />
      </>
    );
  }
  const counters = rankCounters[rankType];
  return (
    <>
      <StatCard label="Victoires" value={counters.victories} delta={rankLabel} icon={<TrophyIcon />} />
      <StatCard label="Podiums" value={counters.podiums} delta={rankLabel} icon={<PodiumIcon />} />
      <StatCard label="Top 10" value={counters.top10} delta={rankLabel} icon={<Top10Icon />} />
    </>
  );
}
