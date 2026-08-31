import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { scopeFromParam } from "@/lib/scope";
import { sortFromParam } from "@/lib/sort";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { ScopeToggle } from "@/components/layout/ScopeToggle";
import { ResultsFilters } from "@/components/results/ResultsFilters";
import { EventList } from "@/components/results/EventList";
import { CoverageTimeline } from "@/components/charts/CoverageTimeline";
import { SeasonSelector, SeasonTags } from "@/components/dashboard/SeasonSelector";
import { EVENTS_PAGE_SIZE } from "@/lib/queries/events";
import { monthlyCoverage } from "@/lib/utils/coverage";
import { currentSeason, parseSeasonsParam } from "@/lib/utils/season";
import type { EventOut, ParticipationFilters } from "@/lib/types";

// Plafond de la route /courses/events (`page_size`, `le=200`) : pas de
// `page_size=all` pour les épreuves (contrairement au classement d'une
// épreuve unique). Quelques requêtes suffisent à l'échelle actuelle
// (~300 épreuves) — à revoir si le volume grossit d'un ordre de grandeur.
const COVERAGE_PAGE_SIZE = 200;

/** Toutes les épreuves de la sélection, indépendamment de la recherche en
 * cours — la couverture est une vue d'ensemble qui précède le filtrage, pas
 * un résumé du résultat filtré (US11, #466). `scope` (portée club/toutes) et
 * `seasons` (défaut : saison en cours, #772) restent respectés : ce sont des
 * réglages de page, pas des filtres de recherche ponctuels. */
async function fetchAllEventsForCoverage(
  scope: ParticipationFilters["scope"],
  seasons: number[],
): Promise<EventOut[]> {
  const items: EventOut[] = [];
  let page = 1;
  for (;;) {
    const batch = await apiServer.listEvents({ scope, seasons, page, page_size: COVERAGE_PAGE_SIZE });
    items.push(...batch.items);
    if (items.length >= batch.total_events || batch.items.length === 0) break;
    page += 1;
  }
  return items;
}

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
    scope: scopeFromParam(sp.scope),
    sort: sortFromParam(sp.sort),
  };

  // Couverture scopée sur la saison en cours par défaut (#772) — un choix qui
  // inverse celui de #466 (historique complet) : `?seasons` retenu s'il porte
  // une valeur, la saison en cours sinon, même défaut que `SeasonSelector`.
  const coverageSeasons = (() => {
    const fromUrl = parseSeasonsParam(sp.seasons);
    return fromUrl.length > 0 ? fromUrl : [currentSeason()];
  })();

  // Page 1 récupérée côté serveur : compteurs honnêtes + données initiales (pas de flash).
  const [firstPage, coverageEvents, seasons] = await Promise.all([
    apiServer.listEvents(
      { ...filters, page: 1, page_size: EVENTS_PAGE_SIZE },
      { revalidateSeconds: SHORT_REVALIDATE_SECONDS },
    ),
    fetchAllEventsForCoverage(filters.scope, coverageSeasons),
    apiServer.listSeasons({ scope: filters.scope }, { revalidateSeconds: SHORT_REVALIDATE_SECONDS }),
  ]);
  const { total_events, total_participations } = firstPage;
  const coverage = monthlyCoverage(coverageEvents);

  return (
    <PageShell>
      <div className="space-y-6">
        <div className="space-y-3">
          <PageHeader
            eyebrow="Toutes les épreuves"
            title="Résultats"
            description={
              `${total_events} épreuve${total_events > 1 ? "s" : ""}` +
              ` · ${total_participations} résultat${total_participations > 1 ? "s" : ""}`
            }
            actions={
              <>
                <ScopeToggle />
                <SeasonSelector seasons={seasons} />
              </>
            }
          />
          <SeasonTags seasons={seasons} className="justify-start sm:justify-end" />
        </div>
        <CoverageTimeline months={coverage} />
        <ResultsFilters />
        <EventList filters={filters} initial={firstPage} />
      </div>
    </PageShell>
  );
}
