import type { RankType } from "@/lib/rank";
import type { Participation } from "@/lib/types";

/**
 * Rang à lire pour un mode du toggle du tableau de bord.
 *
 * **Miroir littéral de `stats_service._rank_counters`** (backend) : c'est ce
 * qui rend « mon » podium comparable à celui du club affiché juste dessous. Le
 * mode `all` prend le meilleur des trois rangs, comme `_meilleur_rang`. Toute
 * divergence ici rendrait la mise en regard fausse sans qu'elle se voie.
 */
export function rangPourMode(p: Participation, mode: RankType): number | null {
  if (mode === "scratch") return p.rank_overall;
  if (mode === "category") return p.rank_category;
  if (mode === "gender") return p.rank_gender;
  const connus = [p.rank_overall, p.rank_gender, p.rank_category].filter(
    (r): r is number => r != null && r >= 1,
  );
  return connus.length > 0 ? Math.min(...connus) : null;
}

/** Les deux chiffres de la bande « Ma saison » (#502). */
export type CompteursMaSaison = { epreuves: number; podiums: number };

/**
 * Épreuves courues et podiums d'un athlète sur les participations reçues.
 *
 * Deux règles reprises du club, sans quoi la comparaison serait bancale :
 * les résultats **en attente de validation** sont exclus (comme
 * `for_stats`, #270/FR-021), et les épreuves se comptent en **courses
 * distinctes** — un athlète inscrit en solo *et* en relais sur la même course
 * y compterait sinon pour deux, là où `stats.events` la compte une fois.
 */
export function compteMaSaison(
  participations: Participation[],
  mode: RankType,
): CompteursMaSaison {
  const validees = participations.filter((p) => !p.is_pending_validation);
  const podiums = validees.filter((p) => {
    const rang = rangPourMode(p, mode);
    return rang != null && rang >= 1 && rang <= 3;
  }).length;
  return { epreuves: new Set(validees.map((p) => p.course.id)).size, podiums };
}
