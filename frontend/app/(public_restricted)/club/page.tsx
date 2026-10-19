import type { Metadata } from "next";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { FieldLabel } from "@/components/layout/FieldLabel";
import { PageShell } from "@/components/layout/PageShell";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { RankTypeToggle } from "@/components/layout/RankTypeToggle";
import { ClubBestTimesCard } from "@/components/club/ClubBestTimesCard";
import { ClubDashboard } from "@/components/club/ClubDashboard";
import { SexeToggle } from "@/components/layout/SexeToggle";
import { SCOPE_CLUB, SEXE_PARAM, federalOnlyFromParam, genderFromSexeParam } from "@/lib/scope";
import { CLUB_NAME } from "@/lib/club";
import { SeasonSelector, SeasonTags } from "@/components/dashboard/SeasonSelector";
import { currentSeason, parseSeasonsParam, seasonLabel } from "@/lib/utils/season";

export const metadata: Metadata = { title: "Espace club" };

// La page Club est TOUJOURS filtrée sur le club, indépendamment de toute portée.
export default async function ClubPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const federal_only = federalOnlyFromParam(sp.sports);
  const gender = genderFromSexeParam(sp[SEXE_PARAM]);
  const fromUrl = parseSeasonsParam(sp.seasons);
  const selected = fromUrl.length > 0 ? fromUrl : [currentSeason()];

  // Fenêtre de revalidation courte (#352) — même raison qu'en page d'accueil.
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };
  const [stats, summary, recent, seasonBestTimes, allBestTimes, seasonList] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: selected, federal_only, gender }, revalidateOpts),
    // Aperçu seul : la liste complète pesait 215 ko de la page (#1354).
    apiServer.getClubSummary({ federal_only, podiums: "preview", seasons: selected, gender }, revalidateOpts),
    apiServer.listParticipations(
      { scope: SCOPE_CLUB, federal_only, seasons: selected, page_size: 6, gender },
      revalidateOpts,
    ),
    // Quelques dizaines de lignes au plus : les deux onglets partent avec la page (#1588).
    // L'onglet « saison » suit la plus récente de la sélection.
    apiServer.getClubBestTimes({ season: Math.max(...selected), federal_only }, revalidateOpts),
    apiServer.getClubBestTimes({ federal_only }, revalidateOpts),
    // Sélecteur décoratif : sa panne ne doit pas emporter la page.
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }, revalidateOpts).catch(() => []),
  ]);

  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader
          eyebrow={CLUB_NAME}
          title="Espace club"
          description={`Synthèse, podiums et athlètes du ${CLUB_NAME}.`}
          actions={
            <div className="flex flex-wrap items-end gap-3">
              <RankTypeToggle />
              <SexeToggle />
              <DisciplineToggle />
              <div>
                <FieldLabel>Saisons</FieldLabel>
                <SeasonSelector seasons={seasonList} />
              </div>
            </div>
          }
        />
        {/* Sous l'en-tête, jamais dans le slot d'actions (#445). */}
        <SeasonTags seasons={seasonList} className="justify-start sm:justify-end" />
        <ClubDashboard
          stats={stats}
          summary={summary}
          recent={recent}
          seasons={selected}
          gender={gender}
        />
        <ClubBestTimesCard
          seasonLines={seasonBestTimes}
          allLines={allBestTimes}
          seasonLabel={seasonLabel(Math.max(...selected))}
          gender={gender}
        />
      </div>
    </PageShell>
  );
}
