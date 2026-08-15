import Link from "next/link";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { RankTypeToggle } from "@/components/layout/RankTypeToggle";
import { SeasonSelector } from "@/components/dashboard/SeasonSelector";
import { StatCardsRank } from "@/components/dashboard/StatCardsRank";
import { currentSeason, parseSeasonsParam, seasonSelectionLabel } from "@/lib/utils/season";
import { StatCard, Card, Eyebrow, FormatChip } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { aggregateDisciplines, formatToken, pctFr } from "@/lib/utils/format";

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

  // Fenêtre de revalidation courte (#352) : les quatre appels rejouaient
  // l'intégralité du rendu serveur à chaque visite (`cache: "no-store"`),
  // pour un coût que le sondage du 2026-08-14 chiffre à 1,5-1,8 s une fois
  // les N+1 corrigés (#350/#351) — un `revalidate` masque ce coût pour
  // l'écrasante majorité des visites, sans retarder la visibilité d'un
  // import (batch) au-delà de ce qu'un visiteur tolère.
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };
  const [stats, eventsPage, participations, seasons] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: selected, federal_only }, revalidateOpts),
    apiServer.listEvents(
      { scope: SCOPE_CLUB, seasons: selected, federal_only, page_size: 200 },
      revalidateOpts,
    ),
    apiServer.listParticipations(
      { scope: SCOPE_CLUB, seasons: selected, federal_only, page_size: 5000 },
      revalidateOpts,
    ),
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }, revalidateOpts),
  ]);

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
        <StatCardsRank participations={participations} />
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
