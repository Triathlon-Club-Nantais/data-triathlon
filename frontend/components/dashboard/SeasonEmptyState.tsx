import Link from "next/link";
import { EmptyState } from "@/components/ui/empty-state";
import { currentSeason, seasonAbsenceLabel } from "@/lib/utils/season";

const LINK_CLASS = "tcn-cible-tactile inline-flex items-center text-sm font-semibold text-accent-ink hover:underline";

/** Sortie « Ajouter une épreuve » des états vides publics (#1415, #1421, #1511). */
export function AddEventLink() {
  return (
    <Link href="/ajouter" className={LINK_CLASS}>
      <span>
        Ajouter une épreuve <span aria-hidden="true">→</span>
      </span>
    </Link>
  );
}

/**
 * Sélection de saisons sans aucun résultat, partagée par le tableau de bord et
 * `/resultats` (#1404, #1409). Une sélection vide vaut la saison en cours.
 */
export function SeasonEmptyState({ seasons, currentSeasonHref }: { seasons: number[]; currentSeasonHref: string }) {
  const onlyCurrentSeason = seasons.length <= 1 && (seasons[0] ?? currentSeason()) === currentSeason();
  return (
    <EmptyState
      title={`Aucun résultat enregistré pour ${seasonAbsenceLabel(seasons)}`}
      description="Changez de saison ou ajoutez les premiers résultats du club."
      action={
        <div className="flex flex-wrap items-center justify-center gap-4">
          {!onlyCurrentSeason && (
            <Link href={currentSeasonHref} className={LINK_CLASS}>
              Voir la saison en cours
            </Link>
          )}
          <AddEventLink />
        </div>
      }
    />
  );
}
