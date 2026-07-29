import Link from "next/link";
import { apiServer } from "@/lib/api/server";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { rankTypeFromParam, type RankType } from "@/lib/rank";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { RankTypeToggle } from "@/components/layout/RankTypeToggle";
import { SeasonSelector } from "@/components/dashboard/SeasonSelector";
import { currentSeason, parseSeasonsParam, seasonSelectionLabel } from "@/lib/utils/season";
import { StatCard, Card, Eyebrow, FormatChip } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { aggregateDisciplines, formatToken, pctFr } from "@/lib/utils/format";
import { rankCounters } from "@/lib/utils/club-aggregate";
import type { ReactNode } from "react";

// Libellés secondaires des cartes selon le mode de rang courant (FR-008).
// Le mode gender aura son propre rendu dédoublé F/H en Phase 5 ; en attendant
// on prépare l'étiquette scalaire « genre ».
const RANK_LABEL: Record<RankType, string> = {
  scratch: "scratch",
  category: "catégorie",
  gender: "genre",
  all: "scratch, genre ou catégorie",
};

const TrophyIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 4h12v3a6 6 0 0 1-12 0V4z" /><path d="M6 5H3v2a3 3 0 0 0 3 3" /><path d="M18 5h3v2a3 3 0 0 1-3 3" /><path d="M9 17h6" /><path d="M12 13v4" /><path d="M8 21h8" /></svg>
);
const PodiumIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="4" width="6" height="17" /><rect x="2" y="10" width="6" height="11" /><rect x="16" y="8" width="6" height="13" /></svg>
);
const Top10Icon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="9" r="6" /><path d="M12 6v3l2 1" /><path d="M9 14l-2 7 5-3 5 3-2-7" /></svg>
);

// Rendu dédoublé F / H pour le mode gender (#104 US3) : deux valeurs séparées
// dans une même carte, chacune préfixée par son label. `<StatCard>` accepte un
// `ReactNode` en `value`, on branche donc directement ce fragment.
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

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  // Page d'accueil = vitrine du club : portée TCN forcée, pas de choix « Tous »
  // (validé par Vincent, issue #6). Le paramètre `?scope` est volontairement
  // ignoré, mais on lit `?seasons` pour le sélecteur de saison (issue #7) et
  // `?sports` pour le filtre fédéral/hors-fédération (issue #76).
  const sp = await searchParams;

  // Calcul de la sélection de saisons depuis l'URL, avec fallback sur la saison en cours
  const fromUrl = parseSeasonsParam(sp.seasons);
  const selected = fromUrl.length > 0 ? fromUrl : [currentSeason()];
  const federal_only = federalOnlyFromParam(sp.sports);
  const rankType = rankTypeFromParam(sp.rank);

  const [stats, eventsPage, participations, seasons] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: selected, federal_only }),
    apiServer.listEvents({ scope: SCOPE_CLUB, seasons: selected, federal_only, page_size: 200 }),
    apiServer.listParticipations({ scope: SCOPE_CLUB, seasons: selected, federal_only, page_size: 5000 }),
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }),
  ]);

  const counters = rankCounters(participations, rankType);
  const rankLabel = RANK_LABEL[rankType];

  const disciplines = aggregateDisciplines(stats.by_type);
  const topEvents = [...eventsPage.items].sort((a, b) => b.total - a.total).slice(0, 6);

  return (
    <PageShell>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 26 }}>
        <div>
          <Eyebrow>Participations aux courses</Eyebrow>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(28px, 5vw, 40px)", color: "var(--tcn-ink)", lineHeight: 1, marginTop: 6 }}>{seasonSelectionLabel(selected)}</div>
          <div style={{ fontSize: 15, color: "var(--tcn-text-muted)", marginTop: 8, fontWeight: 500 }}>Vue d&apos;ensemble des performances des athlètes du club</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <RankTypeToggle />
          <DisciplineToggle />
          <SeasonSelector seasons={seasons} />
        </div>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard variant="hero" label="Dossards enregistrés" value={stats.total.toLocaleString("fr-FR")} delta={`${stats.athletes} athlètes · ${stats.events} épreuves`} />
        {counters.kind === "scalar" ? (
          <>
            <StatCard label="Victoires" value={counters.victories} delta={rankLabel} icon={<TrophyIcon />} />
            <StatCard label="Podiums" value={counters.podiums} delta={rankLabel} icon={<PodiumIcon />} />
            <StatCard label="Top 10" value={counters.top10} delta={rankLabel} icon={<Top10Icon />} />
          </>
        ) : (
          <>
            <StatCard label="Victoires" value={<GenderPair women={counters.women.victories} men={counters.men.victories} />} delta={rankLabel} icon={<TrophyIcon />} />
            <StatCard label="Podiums" value={<GenderPair women={counters.women.podiums} men={counters.men.podiums} />} delta={rankLabel} icon={<PodiumIcon />} />
            <StatCard label="Top 10" value={<GenderPair women={counters.women.top10} men={counters.men.top10} />} delta={rankLabel} icon={<Top10Icon />} />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2" style={{ gridTemplateColumns: undefined }}>
        <Card>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 24, color: "var(--tcn-ink)", marginBottom: 20 }}>Type d&apos;épreuves</div>
          {disciplines.length === 0 ? (
            <div style={{ color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucune épreuve enregistrée.</div>
          ) : (
            <>
              <div style={{ display: "flex", height: 20, borderRadius: 999, overflow: "hidden", marginBottom: 24 }}>
                {disciplines.map((d) => <div key={d.name} style={{ width: d.pct + "%", background: d.color }} />)}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {disciplines.map((d) => (
                  <div key={d.name} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 15, color: "var(--tcn-text-body)" }}>
                    <span style={{ width: 12, height: 12, borderRadius: 3, background: d.color }} />{d.name}
                    <b style={{ marginLeft: "auto", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>{pctFr(d.pct)}%</b>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 24, color: "var(--tcn-ink)", marginBottom: 18 }}>Épreuves préférées</div>
          <div style={{ display: "grid", gridTemplateColumns: "24px 1fr auto auto", gap: "0 14px", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", paddingBottom: 10, borderBottom: "1px solid var(--tcn-border)" }}>
            <div>#</div><div>Épreuve</div><div>Format</div><div style={{ textAlign: "right" }}>Dossards</div>
          </div>
          {topEvents.map((e, i) => (
            <Link key={e.id} href={`/courses/${e.id}`} className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: "24px 1fr auto auto", gap: "0 14px", alignItems: "center", padding: "12px 0", borderBottom: i < topEvents.length - 1 ? "1px solid var(--tcn-border-faint)" : "none", fontSize: 15 }}>
              <span style={{ fontFamily: "var(--tcn-font-display)", color: i === 0 ? "var(--tcn-orange)" : "var(--tcn-text-muted)" }}>{i + 1}</span>
              <span style={{ color: "var(--tcn-ink)", fontWeight: 600 }}>{e.event_name}</span>
              <FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip>
              <b style={{ textAlign: "right", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>{e.total}</b>
            </Link>
          ))}
          {topEvents.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucune épreuve.</div>}
        </Card>
      </div>
    </PageShell>
  );
}
