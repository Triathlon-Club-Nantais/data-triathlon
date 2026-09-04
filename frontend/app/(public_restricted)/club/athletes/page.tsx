import { apiServer } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { AthleteSeasonList } from "@/components/club/AthleteSeasonList";
import { SeasonSelector, SeasonTags } from "@/components/dashboard/SeasonSelector";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { Alert } from "@/components/tcn";
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

  // Gardée par `pages:preview` (#811) : l'API refuse déjà `listAthleteSeasonActivity`
  // sans ce pouvoir, mais l'y laisser tomber rendrait l'écran d'erreur générique
  // plutôt qu'un message explicite — d'où la vérification avant le
  // `Promise.all` des deux fetchs de données, jamais en parallèle avec eux.
  //
  // Rendue en place, jamais par `redirect("/club")` (#831) : la redirection
  // silencieuse laissait un compte à qui il ne manquait que ce pouvoir — un
  // rôle jamais migré vers #811/#825 par exemple — sans aucun diagnostic
  // possible. Même idiome que `SiteAccessGate`
  // (`app/(public_restricted)/layout.tsx`) : un écran gardé rend son message
  // à la place du contenu plutôt que de faire disparaître la destination.
  const session = await apiServer.getSession();
  if (!session?.permissions.includes("pages:preview")) {
    return (
      <PageShell>
        <div className="space-y-8">
          <PageHeader
            backHref="/club"
            backLabel="Espace club"
            eyebrow={CLUB_NAME}
            title="Athlètes par saison"
            description={`Nombre d'épreuves faites par les athlètes du ${CLUB_NAME}, saison par saison.`}
          />
          <Alert status="error" title="Vous n'avez pas la permission nécessaire">
            Cette page est réservée aux comptes disposant du pouvoir « Voir les pages en
            avant-première ». Si vous pensez qu&apos;il devrait figurer sur votre rôle,
            contactez un administrateur du club.
          </Alert>
        </div>
      </PageShell>
    );
  }

  const [athletes, availableSeasons] = await Promise.all([
    apiServer.listAthleteSeasonActivity({ scope: SCOPE_CLUB, seasons, federal_only }),
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }),
  ]);

  return (
    <PageShell>
      <div className="space-y-8">
        {/* Groupé avec l'en-tête, au pas resserré : enfant direct du
            `space-y-8`, la ligne de tags se retrouvait à 32 px de l'en-tête
            **et** 32 px de la liste, donc rattachée à rien. L'alignement suit
            le slot d'actions de `PageHeader`, qui bascule au palier `sm`. */}
        <div className="space-y-3">
          <PageHeader
            backHref="/club"
            backLabel="Espace club"
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
          <SeasonTags seasons={availableSeasons} className="justify-start sm:justify-end" />
        </div>
        <AthleteSeasonList athletes={athletes} />
      </div>
    </PageShell>
  );
}
