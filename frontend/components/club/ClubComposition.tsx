import { BarList } from "@/components/charts/BarList";
import type { ClubComposition as ClubCompositionData } from "@/lib/types";

/** Codes normalisés par le scraping (`backend/app/scrapers/*.py` : "H" alias de "M"). */
function genderLabel(code: string): string {
  if (code === "M") return "Hommes";
  if (code === "F") return "Femmes";
  return "Non renseigné";
}

/**
 * « À quoi ressemble le club ? » (US9, #466) — genre et catégorie d'âge sur
 * l'ensemble du club, pas seulement le top 12 de `ClubSummary.roster` (#581).
 * Un athlète compte une fois, pas une fois par épreuve : la composition porte
 * sur des personnes. Agrégée côté serveur (#642, `ClubSummary.composition`) —
 * `/club` la transporte déjà, aucun fetch ici.
 */
export function ClubComposition({ composition }: { composition: ClubCompositionData }) {
  const genderEntries = Object.entries(composition.gender);
  const categoryEntries = Object.entries(composition.category);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-2 text-sm font-semibold text-[var(--tcn-text-faint)]">Par genre</h3>
        <BarList
          entries={genderEntries}
          labeller={genderLabel}
          emptyTitle="Aucun athlète"
          subjectLabel="genre"
        />
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-[var(--tcn-text-faint)]">Par catégorie</h3>
        <BarList
          entries={categoryEntries}
          labeller={(k) => k || "Non renseignée"}
          emptyTitle="Aucune catégorie renseignée"
          subjectLabel="catégorie"
        />
      </div>
    </div>
  );
}
