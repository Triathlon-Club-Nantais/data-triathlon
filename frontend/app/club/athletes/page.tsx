import { apiServer } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { AthleteSeasonList } from "@/components/club/AthleteSeasonList";
import { SeasonSelector, SeasonTags } from "@/components/dashboard/SeasonSelector";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { CLUB_NAME } from "@/lib/club";
import { currentSeason, parseSeasonsParam } from "@/lib/utils/season";

// Page dédiée, distincte de /club (#274) : toujours scopée club, saison en
// cours par défaut. `?seasons=` est lu ici (rendu serveur), comme sur
// /dashboard — c'est ce qui impose `router.push` plutôt que `pushState` dans
// `SeasonSelector` (cf. frontend/AGENTS.md).
export default async function AthletesSeasonPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const fromUrl = parseSeasonsParam(sp.seasons);
  const seasons = fromUrl.length > 0 ? fromUrl : [currentSeason()];
  const federal_only = federalOnlyFromParam(sp.sports);

  const [athletes, availableSeasons] = await Promise.all([
    apiServer.listAthleteSeasonActivity({ scope: SCOPE_CLUB, seasons, federal_only }),
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }),
  ]);

  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader
          eyebrow={CLUB_NAME}
          title="Athlètes par saison"
          description={`Nombre d'épreuves faites par les athlètes du ${CLUB_NAME}, saison par saison.`}
          actions={
            <div className="flex flex-wrap items-center gap-3">
              <DisciplineToggle />
              <SeasonSelector seasons={availableSeasons} />
            </div>
          }
        />
        {/* Sous l'en-tête, jamais dans le slot d'actions (#445) : dans la barre
            d'outils, les tags la poussaient à déborder et déplaçaient les
            boutons de sélection. */}
        <SeasonTags seasons={availableSeasons} />
        <AthleteSeasonList athletes={athletes} />
      </div>
    </PageShell>
  );
}
