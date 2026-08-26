import Link from "next/link";
import { StatCard } from "@/components/tcn";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/ui/empty-state";
import { ResultCard } from "@/components/results/ResultCard";
import { BarList } from "@/components/charts/BarList";
import { MonthlyTrend } from "@/components/charts/MonthlyTrend";
import { eventTypeLabel } from "@/lib/constants";
import { eventTypeColor } from "@/lib/sport-colors";
import type { ClubSummary, Participation, Stats } from "@/lib/types";
import { PodiumsList } from "./PodiumsList";
import { ClubPodiumKpi } from "./ClubPodiumKpi";
import { RosterApercu } from "./RosterApercu";
import { DisciplinePerformance } from "./DisciplinePerformance";
import { ClubComposition } from "./ClubComposition";

export function ClubDashboard({
  stats,
  summary,
  recent,
}: {
  stats: Stats;
  summary: ClubSummary;
  recent: Participation[];
}) {
  const roster = summary.roster;

  if (stats.total === 0) {
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
      {/* Synthèse — les 3 premiers KPI ne dépendent pas du rank et restent SSR.
          Le KPI Podiums, lui, suit `?rank=…` via un composant client (#132). */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Résultats" value={stats.total} accent />
        <KpiCard label="Athlètes" value={stats.athletes} />
        <KpiCard label="Épreuves" value={stats.events} />
        <ClubPodiumKpi rankCounters={stats.rank_counters} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Podiums / top performers */}
        <Card>
          <CardHeader>
            <CardTitle>Podiums & performances</CardTitle>
          </CardHeader>
          <CardContent>
            <PodiumsList podiums={summary.podiums} />
          </CardContent>
        </Card>

        {/* Répartition & tendances */}
        <Card>
          <CardHeader>
            <CardTitle>Répartition & tendances</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="type">
              <div className="overflow-x-auto">
                <TabsList className="w-full">
                  <TabsTrigger value="type">Par discipline</TabsTrigger>
                  <TabsTrigger value="performance">Performance</TabsTrigger>
                  <TabsTrigger value="month">Par mois</TabsTrigger>
                  <TabsTrigger value="composition">Composition</TabsTrigger>
                </TabsList>
              </div>
              <TabsContent value="type" className="pt-4">
                <BarList
                  entries={Object.entries(stats.by_type)}
                  labeller={(k) => eventTypeLabel(k)}
                  colorer={(k) => eventTypeColor(k)}
                  emptyTitle="Aucune épreuve"
                  subjectLabel="type d'épreuve"
                />
              </TabsContent>
              {/* « Où le club performe-t-il ? » (US10, #466) — podiums par
                  discipline, à ne pas confondre avec le volume ci-dessus. */}
              <TabsContent value="performance" className="pt-4">
                <DisciplinePerformance
                  podiumsByDiscipline={summary.podiums_by_discipline}
                  byType={stats.by_type}
                />
              </TabsContent>
              <TabsContent value="month" className="pt-4">
                <MonthlyTrend byMonth={stats.by_month} />
              </TabsContent>
              {/* « À quoi ressemble le club ? » (US9, #466) — genre et
                  catégorie d'âge, agrégés côté serveur (#642,
                  `ClubSummary.composition`) mais jamais affichés (le fait le
                  plus structurant du jeu de données selon l'audit UX). Un
                  athlète compte une fois, pas une fois par épreuve : la
                  composition porte sur des personnes. */}
              <TabsContent value="composition" className="pt-4">
                <ClubComposition composition={summary.composition} />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      {/* Roster */}
      <section className="space-y-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-heading text-lg font-semibold">
            {stats.athletes > roster.length ? "Les athlètes les plus actifs" : "Athlètes du club"}
          </h2>
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
        {/* #488 (PROF-3, revue UI/UX) : `club_roster` (backend) compte les
            podiums sur les trois portées sans condition, quand le KPI « Podiums » plus
            haut suit `?rank=`. Les deux nombres sont justes et incomparables ;
            sans cette légende, basculer le toggle faisait bouger l'un et pas
            l'autre, sans explication à l'écran. Déplacée du bloc de titre (où
            elle qualifiait le `h2`, pas les cartes) vers ici, juste au-dessus
            de la grille qu'elle décrit, et reformulée avec le vocabulaire déjà
            posé par le KPI et les badges plutôt que « portée », un mot de
            `PodiumScope` que l'utilisateur ne lit nulle part ailleurs. La
            condition d'affichage et la grille elle-même vivent dans
            `RosterApercu` (#504), qui porte aussi la mise en avant de
            l'athlète retenu et le rappel générique quand il est hors de
            l'aperçu, lu côté client uniquement. */}
        <RosterApercu roster={roster} />
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
