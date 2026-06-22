import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Stat } from "@/components/ui/stat";
import { Medal } from "@/components/ui/medal";
import { InitialsAvatar } from "@/components/ui/initials-avatar";
import { EmptyState } from "@/components/ui/empty-state";
import { SportBadge } from "@/components/results/SportBadge";
import { ResultCard } from "@/components/results/ResultCard";
import { BarList } from "@/components/charts/BarList";
import { MonthlyTrend } from "@/components/charts/MonthlyTrend";
import { eventTypeLabel } from "@/lib/constants";
import { eventTypeColor } from "@/lib/sport-colors";
import {
  buildRoster,
  clubSummary,
  listPodiums,
  recentParticipations,
  type PodiumScope,
} from "@/lib/utils/club-aggregate";
import type { Participation, Stats } from "@/lib/types";

const SCOPE_LABEL: Record<PodiumScope, string> = {
  overall: "Général",
  gender: "Genre",
  category: "Catégorie",
};

export function ClubDashboard({
  stats,
  participations,
}: {
  stats: Stats;
  participations: Participation[];
}) {
  const summary = clubSummary(participations);
  const podiums = listPodiums(participations).slice(0, 6);
  const roster = buildRoster(participations);
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
      {/* Synthèse */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Résultats" value={summary.results} accent />
        <KpiCard label="Athlètes" value={summary.athletes} />
        <KpiCard label="Épreuves" value={summary.events} />
        <KpiCard label="Podiums" value={summary.podiums} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Podiums / top performers */}
        <Card>
          <CardHeader>
            <CardTitle>Podiums & performances</CardTitle>
          </CardHeader>
          <CardContent>
            {podiums.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Pas encore de podium enregistré.
              </p>
            ) : (
              <ul className="divide-y">
                {podiums.map(({ participation: p, best }) => {
                  const name =
                    [p.athlete?.prenom, p.athlete?.nom].filter(Boolean).join(" ") ||
                    "Athlète";
                  return (
                    <li key={p.id} className="flex items-center gap-3 py-2.5">
                      <Medal rank={best.rank} size={28} />
                      <div className="min-w-0 flex-1">
                        <Link
                          href={`/athletes/${p.athlete?.id}`}
                          className="font-semibold hover:underline"
                        >
                          {name}
                        </Link>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span className="truncate">{p.course?.name}</span>
                          <SportBadge type={p.course?.event_type} />
                          <span className="micro-label text-[9px]">
                            {SCOPE_LABEL[best.scope]}
                          </span>
                        </div>
                      </div>
                      {p.total_time && (
                        <span className="num text-sm font-bold">{p.total_time}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
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
        <div className="flex items-baseline justify-between">
          <h2 className="font-heading text-lg font-semibold">Athlètes du club</h2>
          <span className="text-sm text-muted-foreground">{roster.length} membres</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {roster.map((r) => (
            <Link
              key={r.athleteId}
              href={`/athletes/${r.athleteId}`}
              className="flex items-center gap-3 rounded-xl bg-card p-3 ring-1 ring-foreground/10 transition-colors hover:bg-muted/50"
            >
              <InitialsAvatar name={r.name} size={40} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold">{r.name}</div>
                <div className="text-xs text-muted-foreground">
                  {r.count} course{r.count > 1 ? "s" : ""}
                  {r.podiums > 0 && ` · ${r.podiums} podium${r.podiums > 1 ? "s" : ""}`}
                </div>
              </div>
              {r.podiums > 0 && (
                <span className="num text-sm font-bold text-accent-ink">
                  🏅{r.podiums}
                </span>
              )}
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

function KpiCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <Card>
      <CardContent>
        <Stat value={value} label={label} accent={accent} />
      </CardContent>
    </Card>
  );
}
