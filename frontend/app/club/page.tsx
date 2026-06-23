import { apiServer } from "@/lib/api/server";
import { TCN_CLUB_FILTER } from "@/lib/club-constants";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { ClubDashboard } from "@/components/club/ClubDashboard";

// La page Club est TOUJOURS filtrée sur le club, indépendamment de toute portée.
export default async function ClubPage() {
  const [stats, participations] = await Promise.all([
    apiServer.getStats(TCN_CLUB_FILTER),
    apiServer.listParticipations({ club: TCN_CLUB_FILTER, page_size: 1000 }),
  ]);

  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader
          eyebrow="Triathlon Club Nantais"
          title="Espace club"
          description="Synthèse, podiums et athlètes du Triathlon Club Nantais."
        />
        <ClubDashboard stats={stats} participations={participations} />
      </div>
    </PageShell>
  );
}
