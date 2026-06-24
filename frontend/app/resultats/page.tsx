import { apiServer } from "@/lib/api/server";
import { clubFromScope } from "@/lib/scope";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { ScopeToggle } from "@/components/layout/ScopeToggle";
import { ResultsFilters } from "@/components/results/ResultsFilters";
import { EventList } from "@/components/results/EventList";
import { EVENTS_PAGE_SIZE } from "@/lib/queries/events";
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
    sort: sp.sort,
  };

  // Page 1 récupérée côté serveur : compteurs honnêtes + données initiales (pas de flash).
  const firstPage = await apiServer.listEvents({ ...filters, page: 1, page_size: EVENTS_PAGE_SIZE });
  const { total_events, total_participations } = firstPage;

  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Toutes les épreuves"
          title="Résultats"
          description={
            `${total_events} épreuve${total_events > 1 ? "s" : ""}` +
            ` · ${total_participations} résultat${total_participations > 1 ? "s" : ""}`
          }
          actions={<ScopeToggle />}
        />
        <ResultsFilters />
        <EventList filters={filters} initial={firstPage} />
      </div>
    </PageShell>
  );
}
