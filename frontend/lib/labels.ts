import type { RankType } from "@/lib/rank";
import type { PodiumScope } from "@/lib/utils/club-aggregate";

/**
 * Libellés utilisateur du vocabulaire de rang. Une seule source pour les trois
 * sites d'affichage — toggle (RankTypeToggle), delta des StatCard (StatCardsRank),
 * badge de podium (PodiumsList) — cf. #133. Un renommage (« Genre » → « Sexe »)
 * ne touche plus qu'ici.
 *
 * `scratch` (mode du toggle) et `overall` (scope résultant d'un podium) désignent
 * la même chose vue de deux côtés : le rang général. Ils rendent donc **le même
 * libellé** (« Général »).
 */

const RANK_LABEL_SHORT: Record<RankType, string> = {
  scratch: "Général",
  category: "Catégorie",
  gender: "Genre",
  all: "Tous",
};

// Forme minuscule utilisée en `delta` sous les compteurs (« 12 · général »).
const RANK_LABEL_LONG: Record<RankType, string> = {
  scratch: "général",
  category: "catégorie",
  gender: "genre",
  all: "général, genre ou catégorie",
};

export function rankTypeLabel(
  t: RankType,
  opts?: { form?: "short" | "long" },
): string {
  return opts?.form === "long" ? RANK_LABEL_LONG[t] : RANK_LABEL_SHORT[t];
}

const SCOPE_LABEL: Record<PodiumScope, string> = {
  overall: RANK_LABEL_SHORT.scratch,
  gender: RANK_LABEL_SHORT.gender,
  category: RANK_LABEL_SHORT.category,
};

export function podiumScopeLabel(s: PodiumScope): string {
  return SCOPE_LABEL[s];
}
