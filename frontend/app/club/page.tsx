import { apiServer } from "@/lib/api/server";
import { SCOPE_CLUB } from "@/lib/scope";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { ClubDashboard } from "@/components/club/ClubDashboard";

// La page Club est TOUJOURS filtrée sur le club, indépendamment de toute portée.
export default async function ClubPage() {
  const [stats, participations] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB }),
    apiServer.listParticipations({ scope: SCOPE_CLUB, page_size: 1000 }),
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
