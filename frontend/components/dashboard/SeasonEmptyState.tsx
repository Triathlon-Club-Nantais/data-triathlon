import Link from "next/link";
import { EmptyState } from "@/components/ui/empty-state";
import { currentSeason, seasonAbsenceLabel } from "@/lib/utils/season";

const LIEN = "tcn-cible-tactile inline-flex items-center gap-1 text-sm font-semibold text-accent-ink hover:underline";

/**
 * Sélection de saisons sans aucun résultat, partagée par le tableau de bord et
 * `/resultats` (#1404, #1409). Une sélection vide vaut la saison en cours.
 */
export function SeasonEmptyState({ seasons, currentSeasonHref }: { seasons: number[]; currentSeasonHref: string }) {
  const saisonEnCoursSeule = seasons.length <= 1 && (seasons[0] ?? currentSeason()) === currentSeason();
  return (
    <EmptyState
      title={`Aucun résultat enregistré pour ${seasonAbsenceLabel(seasons)}`}
      description="Changez de saison ou ajoutez les premiers résultats du club."
      action={
        <div className="flex flex-wrap items-center justify-center gap-4">
          {!saisonEnCoursSeule && (
            <Link href={currentSeasonHref} className={LIEN}>
              Voir la saison en cours
            </Link>
          )}
          <Link href="/ajouter" className={LIEN}>
            Ajouter une épreuve<span aria-hidden="true">→</span>
          </Link>
        </div>
      }
    />
  );
}
