import { apiServer } from "@/lib/api/server";
import { clubFromScope } from "@/lib/scope";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScopeToggle } from "@/components/layout/ScopeToggle";
import { ResultsFilters } from "@/components/results/ResultsFilters";
import { ResultsList } from "@/components/results/ResultsList";
import type { ParticipationFilters } from "@/lib/types";

export default async function ResultatsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;

  const filters: ParticipationFilters = {
    name: sp.name,
    event_type: sp.event_type,
    event_name: sp.event_name,
    date_from: sp.date_from,
    date_to: sp.date_to,
    club: clubFromScope(sp.scope),
    page_size: 500,
  };

  const participations = await apiServer.listParticipations(filters);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Résultats"
        description={`${participations.length} résultat${participations.length > 1 ? "s" : ""}`}
        actions={<ScopeToggle />}
      />
      <ResultsFilters />
      <ResultsList initial={participations} />
    </div>
  );
}
