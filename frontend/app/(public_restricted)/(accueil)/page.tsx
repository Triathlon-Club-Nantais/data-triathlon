import type { Metadata } from "next";
import { BandeauDirect } from "@/components/home/BandeauDirect";
import { TuilesEspaces } from "@/components/home/TuilesEspaces";
import { PageShell } from "@/components/layout/PageShell";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { sortEventsByDateDesc } from "@/lib/utils/event";
import { currentSeason } from "@/lib/utils/season";

export const metadata: Metadata = { title: "Accueil" };

export default async function HomePage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const federal_only = federalOnlyFromParam(sp.sports);
  const season = currentSeason();
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };

  const [stats, eventsPage, sortie] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: [season], federal_only }, revalidateOpts),
    apiServer.listEvents({ scope: SCOPE_CLUB, federal_only, page_size: 1 }, revalidateOpts),
    // Décor de l'accueil : sa panne ne doit pas emporter la page.
    apiServer.getClubLastOuting({ federal_only }, revalidateOpts).catch(() => null),
  ]);
  const derniere = sortEventsByDateDesc(eventsPage.items)[0];

  return (
    <PageShell>
      <BandeauDirect sortie={sortie} stats={stats} season={season} today={new Date()} />
      <TuilesEspaces
        derniereEpreuve={derniere ? { nom: derniere.event_name, date: derniere.event_date } : null}
        podiumsSaison={stats.rank_counters.all.podiums}
      />
    </PageShell>
  );
}
