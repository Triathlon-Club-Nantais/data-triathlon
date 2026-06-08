import { apiServer } from "@/lib/api/server";
import { clubFromScope, isClubScope } from "@/lib/scope";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScopeToggle } from "@/components/layout/ScopeToggle";
import { Kpis } from "@/components/dashboard/Kpis";
import { LiveFeed } from "@/components/dashboard/LiveFeed";
import { MonthlyTrend } from "@/components/charts/MonthlyTrend";
import { BarList } from "@/components/charts/BarList";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { eventTypeLabel } from "@/lib/constants";
import { eventTypeColor } from "@/lib/sport-colors";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const club = clubFromScope(sp.scope);
  const clubScope = isClubScope(sp.scope);
  const stats = await apiServer.getStats(club);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Tableau de bord"
        description={
          clubScope
            ? "Vue d'ensemble des résultats des membres du club."
            : "Vue d'ensemble de tous les résultats importés."
        }
        actions={<ScopeToggle />}
      />

      <Kpis stats={stats} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Activité par mois</CardTitle>
          </CardHeader>
          <CardContent>
            <MonthlyTrend byMonth={stats.by_month} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Répartition par discipline</CardTitle>
          </CardHeader>
          <CardContent>
            <BarList
              entries={Object.entries(stats.by_type)}
              labeller={(k) => eventTypeLabel(k)}
              colorer={(k) => eventTypeColor(k)}
              emptyTitle="Aucune épreuve"
            />
          </CardContent>
        </Card>
      </div>

      <section className="space-y-4">
        <h2 className="font-heading text-lg font-semibold">Derniers résultats</h2>
        <LiveFeed club={club} />
      </section>
    </div>
  );
}
