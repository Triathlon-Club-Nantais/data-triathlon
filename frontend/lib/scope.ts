/** Nom du paramètre d'URL pilotant la portée club (par page). */
export const SCOPE_PARAM = "scope";

/** Valeur du paramètre quand seul le club est affiché. */
export const SCOPE_CLUB = "club";

/**
 * Convertit le paramètre d'URL en valeur de `scope` pour l'API.
 * `?scope=club` → `"club"` ; sinon `undefined` (aucun filtre, tous les athlètes).
 *
 * Le front n'a plus d'opinion sur ce qu'est un membre du club : il transmet une
 * portée, le backend tranche (cf. `app/core/club.py`, issue #76).
 */
export function scopeFromParam(scope?: string | null): typeof SCOPE_CLUB | undefined {
  return scope === SCOPE_CLUB ? SCOPE_CLUB : undefined;
}

/** true si la portée club est active. */
export function isClubScope(scope?: string | null): boolean {
  return scope === SCOPE_CLUB;
}
