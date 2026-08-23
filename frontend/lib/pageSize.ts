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

/** Libellé d'une option dans le sélecteur. */
export function pageSizeLabel(taille: PageSize): string {
  return taille === "all" ? "Tout" : `${taille} lignes`;
}
