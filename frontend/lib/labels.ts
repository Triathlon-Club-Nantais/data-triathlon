import type { RankType } from "@/lib/rank";
import type { PodiumScope } from "@/lib/podium-scope";

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

/**
 * Libellés des statuts de participation (#1084) : la saisie manuelle, le badge
 * de résultat et les compteurs de l'épreuve disent le même mot, dans la même
 * graphie. Les valeurs sont celles de l'API, jamais traduites côté backend.
 */
export const PARTICIPATION_STATUSES = ["finisher", "DNF", "DNS", "DSQ"] as const;
export type ParticipationStatus = (typeof PARTICIPATION_STATUSES)[number];

const STATUS_LABEL: Record<ParticipationStatus, { one: string; many: string }> = {
  finisher: { one: "Arrivé", many: "Arrivants" },
  DNF: { one: "Abandon", many: "Abandons" },
  DNS: { one: "Non partant", many: "Non-partants" },
  DSQ: { one: "Disqualifié", many: "Disqualifiés" },
};

export function participationStatusLabel(
  status: ParticipationStatus,
  opts?: { form?: "one" | "many" },
): string {
  return STATUS_LABEL[status][opts?.form ?? "one"];
}
