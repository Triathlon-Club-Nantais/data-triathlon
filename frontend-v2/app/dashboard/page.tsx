import { apiServer } from "@/lib/api/server";
import { isClubFilterActive, TCN_CLUB_FILTER } from "@/lib/club-cookie";
import { Kpis } from "@/components/dashboard/Kpis";
import { LiveFeed } from "@/components/dashboard/LiveFeed";

export default async function DashboardPage() {
  const clubActive = await isClubFilterActive();
  const club = clubActive ? TCN_CLUB_FILTER : undefined;
  const stats = await apiServer.getStats(club);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Tableau de bord</h1>
      <Kpis stats={stats} />
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Derniers résultats</h2>
        <LiveFeed club={club} />
      </section>
    </div>
  );
}
