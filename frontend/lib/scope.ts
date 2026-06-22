import { TCN_CLUB_FILTER } from "./club-constants";

/** Nom du paramètre d'URL pilotant la portée club (par page). */
export const SCOPE_PARAM = "scope";

/** Valeur du paramètre quand seul le club est affiché. */
export const SCOPE_CLUB = "club";

/**
 * Convertit le paramètre de portée d'URL en filtre `club` pour l'API.
 * `?scope=club` → filtre TCN ; sinon `undefined` (tous les athlètes).
 */
export function clubFromScope(scope?: string | null): string | undefined {
  return scope === SCOPE_CLUB ? TCN_CLUB_FILTER : undefined;
}

/** true si la portée club est active. */
export function isClubScope(scope?: string | null): boolean {
  return scope === SCOPE_CLUB;
}
