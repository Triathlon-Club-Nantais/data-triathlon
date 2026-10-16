/** Nom du paramètre d'URL portant la taille de tranche du classement. */
export const PAGE_SIZE_PARAM = "page_size";

/**
 * Tailles proposées par le sélecteur du classement.
 *
 * `all` est l'échappatoire **contractuelle** de l'API (`backend/app/api/AGENTS.md`) :
 * c'est elle qui rend le tri client exact et le Ctrl+F du navigateur utilisable
 * sur une grosse épreuve.
 */
export const PAGE_SIZE_OPTIONS = [20, 50, 200, "all"] as const;

export type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];

/** Taille par défaut, alignée sur celle du backend. */
export const PAGE_SIZE_DEFAUT: PageSize = 20;

/**
 * Liste blanche : toute valeur hors des options vaut le défaut.
 *
 * Le backend accepte 1 à 200, mais le sélecteur ne sait représenter que ces
 * quatre valeurs — une URL bricolée le désaccorderait sinon, affichant une
 * taille qu'aucune option ne porte.
 */
export function parsePageSize(raw: string | null | undefined): PageSize {
  if (raw === "all") return "all";
  const n = Number(raw);
  const connue = PAGE_SIZE_OPTIONS.find((o) => o === n);
  return connue ?? PAGE_SIZE_DEFAUT;
}

/**
 * Au-delà, « Tout » n'est plus proposé (#1355) : les 3 003 lignes d'une grosse
 * épreuve rendaient 17 Mo de HTML (grille, cartes et charge RSC) et 10 s de
 * flux. Mesuré sur l'épreuve entière, pas sur la sélection filtrée.
 */
export const PAGE_SIZE_ALL_MAX = 500;

export function pageSizeOptions(totalEpreuve: number): readonly PageSize[] {
  return totalEpreuve > PAGE_SIZE_ALL_MAX ? PAGE_SIZE_OPTIONS.filter((o) => o !== "all") : PAGE_SIZE_OPTIONS;
}

/** La taille réellement servie : « Tout » retombe sur la plus grande tranche au-delà du seuil. */
export function boundPageSize(taille: PageSize, totalEpreuve: number): PageSize {
  return taille === "all" && totalEpreuve > PAGE_SIZE_ALL_MAX ? 200 : taille;
}

/** Libellé d'une option dans le sélecteur. */
export function pageSizeLabel(taille: PageSize): string {
  return taille === "all" ? "Tout" : `${taille} lignes`;
}
