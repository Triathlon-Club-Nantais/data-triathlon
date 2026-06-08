import { apiServer } from "@/lib/api/server";
import { isClubFilterActive, TCN_CLUB_FILTER } from "@/lib/club-cookie";
import { ResultsFilters } from "@/components/results/ResultsFilters";
import { ResultsList } from "@/components/results/ResultsList";
import type { ParticipationFilters } from "@/lib/types";

export default async function ResultatsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const clubActive = await isClubFilterActive();

  const filters: ParticipationFilters = {
    name: sp.name,
    event_type: sp.event_type,
    event_name: sp.event_name,
    date_from: sp.date_from,
    date_to: sp.date_to,
    club: clubActive ? TCN_CLUB_FILTER : undefined,
    page_size: 500,
  };

  const participations = await apiServer.listParticipations(filters);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Résultats</h1>
      <ResultsFilters />
      <ResultsList initial={participations} />
    </div>
  );
}
