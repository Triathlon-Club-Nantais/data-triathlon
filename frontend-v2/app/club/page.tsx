import { apiServer } from "@/lib/api/server";
import { isClubFilterActive, TCN_CLUB_FILTER } from "@/lib/club-cookie";
import { ClubStats } from "@/components/club/ClubStats";

export default async function ClubPage() {
  const clubActive = await isClubFilterActive();
  const stats = await apiServer.getStats(clubActive ? TCN_CLUB_FILTER : undefined);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Statistiques du club</h1>
      <ClubStats stats={stats} />
    </div>
  );
}
