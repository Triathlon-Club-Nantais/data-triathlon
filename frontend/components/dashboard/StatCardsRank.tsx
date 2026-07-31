"use client";
import type { ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { StatCard } from "@/components/tcn";
import { rankCounters } from "@/lib/utils/club-aggregate";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { rankTypeLabel } from "@/lib/labels";
import type { Participation } from "@/lib/types";

const TrophyIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 4h12v3a6 6 0 0 1-12 0V4z" /><path d="M6 5H3v2a3 3 0 0 0 3 3" /><path d="M18 5h3v2a3 3 0 0 1-3 3" /><path d="M9 17h6" /><path d="M12 13v4" /><path d="M8 21h8" /></svg>
);
const PodiumIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="4" width="6" height="17" /><rect x="2" y="10" width="6" height="11" /><rect x="16" y="8" width="6" height="13" /></svg>
);
const Top10Icon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="9" r="6" /><path d="M12 6v3l2 1" /><path d="M9 14l-2 7 5-3 5 3-2-7" /></svg>
);

// Rendu dédoublé F / H pour le mode gender (#104 US3).
function GenderPair({ women, men }: { women: number; men: number }): ReactNode {
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", gap: 18, fontFamily: "var(--tcn-font-display)" }}>
      <span style={{ display: "inline-flex", alignItems: "baseline", gap: 6 }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: "var(--tcn-text-muted)" }}>F</span>
        <span>{women}</span>
      </span>
      <span style={{ display: "inline-flex", alignItems: "baseline", gap: 6 }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: "var(--tcn-text-muted)" }}>H</span>
        <span>{men}</span>
      </span>
    </span>
  );
}

/**
 * Les 3 cartes « Victoires / Podiums / Top 10 » côté client.
 *
 * Les participations sont chargées **une fois** par le RSC parent, puis
 * `rankCounters` recalcule localement au changement de `?rank=…` — sans
 * re-fetch, sans re-render du reste du dashboard. Résout la latence observée
 * en dev quand chaque bascule du toggle déclenchait un cycle RSC complet
 * (voir issue #132).
 */
export function StatCardsRank({ participations }: { participations: Participation[] }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const counters = useMemo(() => rankCounters(participations, rankType), [participations, rankType]);
  const rankLabel = rankTypeLabel(rankType, { form: "long" });

  if (counters.kind === "scalar") {
    return (
      <>
        <StatCard label="Victoires" value={counters.victories} delta={rankLabel} icon={<TrophyIcon />} />
        <StatCard label="Podiums" value={counters.podiums} delta={rankLabel} icon={<PodiumIcon />} />
        <StatCard label="Top 10" value={counters.top10} delta={rankLabel} icon={<Top10Icon />} />
      </>
    );
  }
  return (
    <>
      <StatCard label="Victoires" value={<GenderPair women={counters.women.victories} men={counters.men.victories} />} delta={rankLabel} icon={<TrophyIcon />} />
      <StatCard label="Podiums" value={<GenderPair women={counters.women.podiums} men={counters.men.podiums} />} delta={rankLabel} icon={<PodiumIcon />} />
      <StatCard label="Top 10" value={<GenderPair women={counters.women.top10} men={counters.men.top10} />} delta={rankLabel} icon={<Top10Icon />} />
    </>
  );
}
