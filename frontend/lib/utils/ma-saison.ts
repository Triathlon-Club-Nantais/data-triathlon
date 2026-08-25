import type { RankType } from "@/lib/rank";
import type { Participation } from "@/lib/types";
import { isPodium } from "@/lib/utils/club-aggregate";

/** Les deux chiffres de la bande « Ma saison » (#502). */
export type CompteursMaSaison = { epreuves: number; podiums: number };

/**
 * Épreuves courues et podiums d'un athlète sur les participations reçues.
 *
 * Trois règles reprises du club, sans quoi la comparaison serait bancale :
 * les résultats **en attente de validation** sont exclus (comme
 * `for_stats`, #270/FR-021), les épreuves se comptent en **courses
 * distinctes** — un athlète inscrit en solo *et* en relais sur la même course
 * y compterait sinon pour deux, là où `stats.events` la compte une fois — et
 * le podium délègue la règle de rang à `isPodium` (`club-aggregate.ts`,
 * miroir de `stats_service._rank_counters`) plutôt que d'en tenir une
 * troisième copie ici.
 *
 * Asymétrie assumée avec les compteurs club (#502, à charge pour #503/#504
 * de ne pas la prendre pour réglée) : le club se calcule sur
 * `for_stats(club_only=True)` (`tcn_clause(Participation.club)`), quand
 * `list_for_athlete` n'a délibérément aucune clause de club (FR-019,
 * `backend/app/api/AGENTS.md`) — une participation dont le club diffère ou est
 * vide compte donc ici sans compter côté club.
 */
export function compteMaSaison(
  participations: Participation[],
  mode: RankType,
): CompteursMaSaison {
  const validees = participations.filter((p) => !p.is_pending_validation);
  const podiums = validees.filter((p) => isPodium(p, mode)).length;
  return { epreuves: new Set(validees.map((p) => p.course.id)).size, podiums };
}
