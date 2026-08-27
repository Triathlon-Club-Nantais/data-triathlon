import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { RankTypeToggle } from "@/components/layout/RankTypeToggle";
import { ClubDashboard } from "@/components/club/ClubDashboard";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { CLUB_NAME } from "@/lib/club";
import { currentSeason } from "@/lib/utils/season";

// La page Club est TOUJOURS filtrée sur le club, indépendamment de toute portée.
export default async function ClubPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const federal_only = federalOnlyFromParam(sp.sports);

  // Fenêtre de revalidation courte (#352) — même raison qu'en page d'accueil.
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };
  const [stats, seasonStats, summary, recent] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, federal_only }, revalidateOpts),
    // #649 : le KPI « Résultats » doit refléter le même total que « Dossards
    // enregistrés » du dashboard — scopé à la saison en cours, jamais le
    // total toutes saisons que `stats` porte pour les autres KPI de la page.
    apiServer.getStats(
      { scope: SCOPE_CLUB, seasons: [currentSeason()], federal_only },
      revalidateOpts,
    ),
    apiServer.getClubSummary({ federal_only }, revalidateOpts),
    apiServer.listParticipations(
      { scope: SCOPE_CLUB, federal_only, page_size: 6 },
      revalidateOpts,
    ),
  ]);

  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader
          eyebrow={CLUB_NAME}
          title="Espace club"
          description={`Synthèse, podiums et athlètes du ${CLUB_NAME}.`}
          actions={
            <div className="flex flex-wrap items-center gap-3">
              <RankTypeToggle />
              <DisciplineToggle />
            </div>
          }
        />
        <ClubDashboard
          stats={stats}
          summary={summary}
          recent={recent}
          resultsTotal={seasonStats.total}
        />
      </div>
    </PageShell>
  );
}
