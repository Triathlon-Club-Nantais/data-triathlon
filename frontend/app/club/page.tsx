import { apiServer } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { RankTypeToggle } from "@/components/layout/RankTypeToggle";
import { ClubDashboard } from "@/components/club/ClubDashboard";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { CLUB_NAME } from "@/lib/club";

// La page Club est TOUJOURS filtrée sur le club, indépendamment de toute portée.
export default async function ClubPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const federal_only = federalOnlyFromParam(sp.sports);

  const [stats, participations] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, federal_only }),
    apiServer.listParticipations({ scope: SCOPE_CLUB, federal_only, page_size: 1000 }),
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
        <ClubDashboard stats={stats} participations={participations} />
      </div>
    </PageShell>
  );
}
