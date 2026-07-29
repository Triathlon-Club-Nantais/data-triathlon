/** Nom du paramètre d'URL pilotant le type de rang des cartes de stats. */
export const RANK_PARAM = "rank";

/** Type de rang appliqué aux cartes « Victoires / Podiums / Top 10 ». */
export type RankType = "scratch" | "category" | "gender" | "all";

/**
 * Défaut du toggle : rang scratch. Le cas d'usage nominal cité dans #104 est la
 * comparaison avec les stats présentées à l'AG, qui étaient toutes au scratch.
 * Ce défaut n'est pas neutre — c'est explicite (voir plan.md §Complexity Tracking).
 */
export const RANK_DEFAULT: RankType = "scratch";

const CANONICAL: readonly RankType[] = ["scratch", "category", "gender", "all"];

/**
 * Traduit le paramètre d'URL en `RankType`. Whitelist stricte : les 4 valeurs
 * canoniques, tout le reste (absent, vide, casse non canonique, alias) retombe
 * silencieusement sur le défaut — pas d'erreur, pas de redirection.
 */
export function rankTypeFromParam(v: string | undefined): RankType {
  return (CANONICAL as readonly string[]).includes(v ?? "")
    ? (v as RankType)
    : RANK_DEFAULT;
}
