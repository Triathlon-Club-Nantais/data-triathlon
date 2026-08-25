import Link from "next/link";
import { Avatar, StatCard } from "@/components/tcn";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/ui/empty-state";
import { ResultCard } from "@/components/results/ResultCard";
import { BarList } from "@/components/charts/BarList";
import { MonthlyTrend } from "@/components/charts/MonthlyTrend";
import { eventTypeLabel } from "@/lib/constants";
import { eventTypeColor } from "@/lib/sport-colors";
import {
  buildRoster,
  clubSummary,
  recentParticipations,
  type PodiumScope,
  type RosterEntry,
} from "@/lib/utils/club-aggregate";
import { PODIUM_SCOPE_META } from "@/lib/podium-scope";
import { CLUB_PARTICIPATIONS_PAGE_SIZE } from "@/lib/club";
import type { Participation, Stats } from "@/lib/types";
import { PodiumsList } from "./PodiumsList";
import { ClubPodiumKpi } from "./ClubPodiumKpi";

/**
 * Taille de l'aperçu du roster (#487). La liste complète — 350 fiches triées
 * par volume décroissant — vit sur `/club/athletes`, qui porte déjà la
 * recherche insensible aux accents et le tri. Ce que l'aperçu retire est le
 * **rendu** : 338 liens, autant d'`Avatar` et de badges, et leur hydratation.
 * Le transport, lui, ne bouge pas — voir le `ponytail:` de
 * `CLUB_PARTICIPATIONS_PAGE_SIZE`.
 */
export const APERCU_ROSTER = 12;

export function ClubDashboard({
  stats,
  participations,
}: {
  stats: Stats;
  participations: Participation[];
}) {
  const summary = clubSummary(participations);
  const roster = buildRoster(participations);
  const apercu = roster.slice(0, APERCU_ROSTER);
  const tronque = participations.length >= CLUB_PARTICIPATIONS_PAGE_SIZE;
  const recent = recentParticipations(participations, 6);

  if (participations.length === 0) {
    return (
      <EmptyState
        title="Aucun résultat de club"
        description="Importez une épreuve : les membres du club apparaîtront automatiquement ici."
        action={
          <Link
            href="/ajouter"
            className="text-sm font-semibold text-accent-ink hover:underline"
          >
            Ajouter une épreuve →
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-8">
      {tronque && (
        // « importés », et non « les plus récents » : `list_participations`
        // trie par `created_at desc` hors détail d'épreuve — la date d'import,
        // pas celle de la course. Une épreuve de 2019 importée hier est dans
        // la tranche. Pas de `role="status"` : rendue au SSR, une région live
        // n'annonce que ce qui change **après** son entrée dans l'arbre. Pas
        // de `bg-muted` non plus — il vaut exactement `--background`
        // (cf. frontend/AGENTS.md, le piège des squelettes).
        <p className="rounded-xl bg-[var(--tcn-surface)] p-3 text-sm text-[var(--tcn-text-faint)] ring-1 ring-[var(--tcn-border-strong)]">
          Cette synthèse porte sur les {CLUB_PARTICIPATIONS_PAGE_SIZE.toLocaleString("fr-FR")}{" "}
          derniers résultats importés. Les résultats importés avant n&apos;y figurent pas.
        </p>
      )}

      {/* Synthèse — les 3 premiers KPI ne dépendent pas du rank et restent SSR.
          Le KPI Podiums, lui, suit `?rank=…` via un composant client (#132). */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Résultats" value={summary.results} accent />
        <KpiCard label="Athlètes" value={summary.athletes} />
        <KpiCard label="Épreuves" value={summary.events} />
        <ClubPodiumKpi participations={participations} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Podiums / top performers */}
        <Card>
          <CardHeader>
            <CardTitle>Podiums & performances</CardTitle>
          </CardHeader>
          <CardContent>
            <PodiumsList participations={participations} />
          </CardContent>
        </Card>

        {/* Répartition & tendances */}
        <Card>
          <CardHeader>
            <CardTitle>Répartition & tendances</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="type">
              <TabsList>
                <TabsTrigger value="type">Par discipline</TabsTrigger>
                <TabsTrigger value="month">Par mois</TabsTrigger>
              </TabsList>
              <TabsContent value="type" className="pt-4">
                <BarList
                  entries={Object.entries(stats.by_type)}
                  labeller={(k) => eventTypeLabel(k)}
                  colorer={(k) => eventTypeColor(k)}
                  emptyTitle="Aucune épreuve"
                  subjectLabel="type d'épreuve"
                />
              </TabsContent>
              <TabsContent value="month" className="pt-4">
                <MonthlyTrend byMonth={stats.by_month} />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      {/* Roster */}
      <section className="space-y-4">
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h2 className="font-heading text-lg font-semibold">
              {roster.length > APERCU_ROSTER ? "Les athlètes les plus actifs" : "Athlètes du club"}
            </h2>
            {/* #488 (PROF-3) : `buildRoster` compte les podiums sur les trois
                portées sans condition, quand le KPI « Podiums » plus haut suit
                `?rank=`. Les deux nombres sont justes et incomparables ; sans
                cette ligne, basculer le toggle faisait bouger l'un et pas
                l'autre, sans explication à l'écran. Rendue seulement si
                l'aperçu montre au moins un podium : les cartes elles-mêmes ne
                rendent leur décompte que sous cette condition (`r.podiums > 0`
                ci-dessous) — sur un club sans podium, la légende qualifiait
                des nombres absents de l'écran (revue finale). */}
            {apercu.some((r) => r.podiums > 0) && (
              <p className="text-sm text-[var(--tcn-text-faint)]">
                podiums toutes portées confondues
              </p>
            )}
          </div>
          {/* Inconditionnel : « les deux écrans reliés dans les deux sens »
              est une garantie de navigation, elle ne peut pas s'éteindre sous
              13 athlètes. Le libellé dit la destination et non un décompte —
              /club/athletes ouvre sur la saison en cours seule, quand
              `roster.length` agrège toutes les saisons ; le total du club vit
              dans le KPI « Athlètes », qui le tient déjà. */}
          <Link
            href="/club/athletes"
            className="shrink-0 text-sm font-medium text-accent-ink hover:underline"
          >
            Voir saison par saison →
          </Link>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {apercu.map((r) => (
            <Link
              key={r.athleteId}
              href={`/athletes/${r.athleteId}`}
              className="flex items-center gap-3 rounded-xl bg-card p-3 ring-1 ring-foreground/10 transition-colors hover:bg-muted/50"
            >
              <Avatar name={r.name} size={40} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold">{r.name}</div>
                <div className="text-xs text-[var(--tcn-text-faint)]">
                  {r.count} épreuve{r.count > 1 ? "s" : ""}
                  {r.podiums > 0 && ` · ${r.podiums} podium${r.podiums > 1 ? "s" : ""}`}
                </div>
              </div>
              {r.podiums > 0 && <RosterPodiumBadges roster={r} />}
            </Link>
          ))}
        </div>
      </section>

      {/* Résultats récents */}
      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="font-heading text-lg font-semibold">Résultats récents</h2>
          <Link
            href="/resultats?scope=club"
            className="text-sm font-medium text-accent-ink hover:underline"
          >
            Tout voir →
          </Link>
        </div>
        <div className="space-y-3">
          {recent.map((p) => (
            <ResultCard key={p.id} result={p} />
          ))}
        </div>
      </section>
    </div>
  );
}

/**
 * Podiums d'un athlète du roster, ventilés par scope (#128). Une icône +
 * décompte par scope non nul, chacun avec le tooltip natif partagé — permet
 * de distinguer « 3 podiums scratch » de « 3 podiums de catégorie » là où
 * l'ancien `🏅3` amalgamait tout.
 */
function RosterPodiumBadges({ roster }: { roster: RosterEntry }) {
  const scopes: PodiumScope[] = ["overall", "gender", "category"];
  return (
    <span className="flex shrink-0 items-center gap-1.5">
      {scopes.map((scope) => {
        const n = roster.podiumsByScope[scope];
        if (n === 0) return null;
        const { Icon, label, title } = PODIUM_SCOPE_META[scope];
        return (
          <span
            key={scope}
            className="num inline-flex items-center gap-0.5 text-sm font-bold text-accent-ink"
            title={`${n} ${title.toLowerCase()}`}
            aria-label={`${n} ${label.toLowerCase()}`}
          >
            <Icon size={14} strokeWidth={2.5} aria-hidden="true" />
            {n}
          </span>
        );
      })}
    </span>
  );
}

function KpiCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  // `StatCard` **est** la carte : pas de `Card`/`CardContent` autour, ils
  // doubleraient le chrome. `accent` y désigne le trait orange sous la valeur,
  // là où l'`ui/Stat` qu'il remplace colorait la valeur elle-même. Le `?? false`
  // n'est pas décoratif : `StatCard` a `accent = true` par défaut, l'omettre
  // mettrait le trait sur les quatre tuiles et rendrait ce paramètre inerte.
  return <StatCard label={label} value={value} accent={accent ?? false} />;
}
