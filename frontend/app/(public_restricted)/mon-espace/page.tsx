import type { Metadata } from "next";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { SeasonSelector, SeasonTags } from "@/components/dashboard/SeasonSelector";
import { currentSeason, parseSeasonsParam, seasonSelectionLabel } from "@/lib/utils/season";
import { Eyebrow } from "@/components/tcn";
import { FieldLabel } from "@/components/layout/FieldLabel";
import { PageShell } from "@/components/layout/PageShell";
import { MonEspace } from "@/components/mon-espace/MonEspace";

export const metadata: Metadata = { title: "Mon espace" };

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  // Mon espace = vitrine du club : portée TCN forcée, pas de choix « Tous »
  // (validé par Vincent, issue #6). Le paramètre `?scope` est volontairement
  // ignoré, mais on lit `?seasons` pour le sélecteur de saison (issue #7) et
  // `?sports` pour le filtre fédéral/hors-fédération (issue #76).
  const sp = await searchParams;

  // Calcul de la sélection de saisons depuis l'URL, avec fallback sur la saison en cours
  const fromUrl = parseSeasonsParam(sp.seasons);
  const selected = fromUrl.length > 0 ? fromUrl : [currentSeason()];
  const federal_only = federalOnlyFromParam(sp.sports);

  // Les saisons proposées sont celles du club (revalidation courte, #352) ; les
  // chiffres, eux, viennent de la fiche rattachée, côté client.
  const seasons = await apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }, { revalidateSeconds: SHORT_REVALIDATE_SECONDS });

  return (
    <PageShell>
      {/* En-tête en colonne : titre + barre d'outils sur une ligne, tags sur la
          suivante (#445). L'empilement est déclaré au palier `lg` plutôt que
          laissé à un `flex-wrap` : la barre basculait alors sous le titre à une
          largeur qui dépendait du `max-content` de la description, donc à un
          point que rien ne pouvait suivre — et les tags, eux, restaient à
          droite. Même palier ici et sur `SeasonTags`, les deux bougent
          ensemble. */}
      <div className="space-y-3" style={{ marginBottom: 26 }}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Eyebrow>Mon espace</Eyebrow>
            <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(28px, 5vw, 40px)", fontWeight: 400, color: "var(--tcn-ink)", lineHeight: 1, margin: 0, marginTop: 6 }}>{seasonSelectionLabel(selected)}</h1>
          </div>
          <div data-testid="dashboard-toolbar" style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
            <div>
              <FieldLabel>Disciplines</FieldLabel>
              <DisciplineToggle />
            </div>
            <div>
              <FieldLabel>Saisons</FieldLabel>
              <SeasonSelector seasons={seasons} />
            </div>
          </div>
        </div>
        {/* Hors de la barre d'outils, à dessein (#445) : les tags y élargissaient
            la barre jusqu'à la faire basculer sous le titre, tout à gauche. */}
        <SeasonTags seasons={seasons} className="justify-start lg:justify-end" />
      </div>

      <MonEspace seasons={selected} federalOnly={federal_only ?? false} />
    </PageShell>
  );
}
