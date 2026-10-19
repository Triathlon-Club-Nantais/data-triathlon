import type { Metadata } from "next";
import { BandeauDirect } from "@/components/home/BandeauDirect";
import { TuilesEspaces } from "@/components/home/TuilesEspaces";
import { PageShell } from "@/components/layout/PageShell";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { sortEventsByDateDesc } from "@/lib/utils/event";
import { SeasonSelector, SeasonTags } from "@/components/dashboard/SeasonSelector";
import { selectedSeasonsOrCurrent } from "@/lib/utils/season";

export const metadata: Metadata = { title: "Accueil" };

export default async function HomePage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const federal_only = federalOnlyFromParam(sp.sports);
  const seasons = selectedSeasonsOrCurrent(sp.seasons);
  const query = new URLSearchParams(Object.entries({ seasons: sp.seasons, sports: sp.sports }).filter(([, v]) => v) as [string, string][]).toString();
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };

  const [stats, eventsPage, sortie, seasonList] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons, federal_only }, revalidateOpts),
    apiServer.listEvents({ scope: SCOPE_CLUB, federal_only, page_size: 1 }, revalidateOpts),
    // Décor de l'accueil : sa panne ne doit pas emporter la page.
    apiServer.getClubLastOuting({ federal_only, seasons }, revalidateOpts).catch(() => null),
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }, revalidateOpts),
  ]);
  const derniere = sortEventsByDateDesc(eventsPage.items)[0];

  return (
    <PageShell>
      <div className="mb-4 space-y-2">
        <div className="flex flex-wrap items-end gap-3 lg:justify-end">
          <div>
            <div className="micro-label mb-1.5">Saisons</div>
            <SeasonSelector seasons={seasonList} />
          </div>
        </div>
        <SeasonTags seasons={seasonList} className="justify-start lg:justify-end" />
      </div>
      <BandeauDirect sortie={sortie} stats={stats} seasons={seasons} today={new Date()} />
      <TuilesEspaces
        derniereEpreuve={derniere ? { nom: derniere.event_name, date: derniere.event_date } : null}
        podiumsSaison={stats.rank_counters.all.podiums}
        seasons={seasons}
        query={query ? `?${query}` : ""}
      />
    </PageShell>
  );
}
