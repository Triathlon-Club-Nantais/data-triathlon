import type { ReactNode } from "react";
import Link from "next/link";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { RankTypeToggle } from "@/components/layout/RankTypeToggle";
import { SeasonSelector, SeasonTags } from "@/components/dashboard/SeasonSelector";
import { StatCardsRank } from "@/components/dashboard/StatCardsRank";
import { currentSeason, parseSeasonsParam, seasonSelectionLabel } from "@/lib/utils/season";
import { StatCard, Card, Eyebrow, FormatChip } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { EmptyState } from "@/components/ui/empty-state";
import { aggregateDisciplines, formatToken, pctFr } from "@/lib/utils/format";

/** Petit libellé visuel au-dessus d'un contrôle de filtrage (NAV-5, #483) —
 *  même style que les en-têtes de la table "Dernières épreuves" plus bas
 *  dans ce fichier, réutilisé ici pour la 3ᵉ fois plutôt qu'un nouveau
 *  token. */
function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 12,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: ".04em",
        color: "var(--tcn-text-faint)",
        marginBottom: 6,
      }}
    >
      {children}
    </div>
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

  // Fenêtre de revalidation courte (#352) : les trois appels rejouaient
  // l'intégralité du rendu serveur à chaque visite (`cache: "no-store"`),
  // pour un coût que le sondage du 2026-08-14 chiffre à 1,5-1,8 s une fois
  // les N+1 corrigés (#350/#351) — un `revalidate` masque ce coût pour
  // l'écrasante majorité des visites, sans retarder la visibilité d'un
  // import (batch) au-delà de ce qu'un visiteur tolère.
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };
  const [stats, eventsPage, seasons] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: selected, federal_only }, revalidateOpts),
    apiServer.listEvents(
      { scope: SCOPE_CLUB, seasons: selected, federal_only, page_size: 200 },
      revalidateOpts,
    ),
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }, revalidateOpts),
  ]);

  const disciplines = aggregateDisciplines(stats.by_type);
  const topEvents = [...eventsPage.items].sort((a, b) => b.total - a.total).slice(0, 6);

  return (
    <PageShell>
      {/* En-tête en colonne : titre + barre d'outils sur une ligne, tags sur la
          suivante (#445). L'empilement est déclaré au palier `lg` plutôt que
          laissé à un `flex-wrap` : la barre basculait alors sous le titre à une
          largeur qui dépendait du `max-content` de la description, donc à un
          point que rien ne pouvait suivre — et les tags, eux, restaient à
          droite. Même palier ici et sur `SeasonTags`, les deux bougent
          ensemble. */}
      <div className="space-y-3" style={{ marginBottom: 26 }}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Eyebrow>Participations aux épreuves</Eyebrow>
            <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(28px, 5vw, 40px)", fontWeight: 400, color: "var(--tcn-ink)", lineHeight: 1, margin: 0, marginTop: 6 }}>{seasonSelectionLabel(selected)}</h1>
            <div style={{ fontSize: 15, color: "var(--tcn-text-muted)", marginTop: 8, fontWeight: 500 }}>Vue d&apos;ensemble des performances des athlètes du club</div>
          </div>
          <div data-testid="dashboard-toolbar" style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
            <div>
              <FieldLabel>Disciplines</FieldLabel>
              <DisciplineToggle />
            </div>
            <div>
              <FieldLabel>Saisons</FieldLabel>
              <SeasonSelector seasons={seasons} />
            </div>
          </div>
        </div>
        {/* Hors de la barre d'outils, à dessein (#445) : les tags y élargissaient
            la barre jusqu'à la faire basculer sous le titre, tout à gauche. */}
        <SeasonTags seasons={seasons} className="justify-start lg:justify-end" />
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)] lg:items-start">
        <StatCard variant="hero" label="Dossards enregistrés" value={stats.total.toLocaleString("fr-FR")} delta={`${stats.athletes} athlètes · ${stats.events} épreuves`} />
        <div>
          <div className="mb-2 flex items-center justify-between">
            <FieldLabel>Type de rang</FieldLabel>
            <RankTypeToggle />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCardsRank rankCounters={stats.rank_counters} />
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2" style={{ gridTemplateColumns: undefined }}>
        <Card>
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 24, fontWeight: 400, color: "var(--tcn-ink)", margin: 0, marginBottom: 20 }}>Type d&apos;épreuves</h2>
          {disciplines.length === 0 ? (
            <EmptyState
              bare
              title="Aucune épreuve enregistrée"
              action={
                <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
                  Ajouter une épreuve →
                </Link>
              }
            />
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
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 24, fontWeight: 400, color: "var(--tcn-ink)", margin: 0, marginBottom: 18 }}>Épreuves préférées</h2>
          <div style={{ display: "grid", gridTemplateColumns: "24px 1fr auto auto", gap: "0 14px", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", paddingBottom: 10, borderBottom: "1px solid var(--tcn-border)" }}>
            <div>#</div><div>Épreuve</div><div>Format</div><div style={{ textAlign: "right" }}>Dossards</div>
          </div>
          {topEvents.map((e, i) => (
            // prefetch={false} (#425) : jusqu'à 6 liens au-dessus de la ligne
            // de flottaison, next/link les prefetch tous par défaut dès
            // l'atterrissage sur /dashboard — un coût réseau pour des épreuves
            // au hasard, rarement celle que le visiteur va effectivement ouvrir.
            <Link key={e.id} href={`/courses/${e.id}`} prefetch={false} className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: "24px 1fr auto auto", gap: "0 14px", alignItems: "center", padding: "12px 0", borderBottom: i < topEvents.length - 1 ? "1px solid var(--tcn-border-faint)" : "none", fontSize: 15 }}>
              <span style={{ fontFamily: "var(--tcn-font-display)", color: i === 0 ? "var(--tcn-orange-deeper)" : "var(--tcn-text-muted)" }}>{i + 1}</span>
              <span style={{ color: "var(--tcn-ink)", fontWeight: 600 }}>{e.event_name}</span>
              <FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip>
              <b style={{ textAlign: "right", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>{e.total}</b>
            </Link>
          ))}
          {topEvents.length === 0 && (
            <EmptyState
              bare
              className="py-6"
              title="Aucune épreuve à afficher"
              action={
                <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
                  Ajouter une épreuve →
                </Link>
              }
            />
          )}
        </Card>
      </div>
    </PageShell>
  );
}
