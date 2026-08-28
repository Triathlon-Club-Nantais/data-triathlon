/** Valeurs de `sort` acceptées par `GET /courses/events` (`Literal` côté backend, #711). */
const EVENT_SORT_VALUES = ["date_desc", "date_asc", "name", "imported_desc"] as const;

export type EventSort = (typeof EVENT_SORT_VALUES)[number];

/**
 * Convertit le paramètre d'URL `sort` en valeur acceptée par l'API.
 *
 * Le backend renvoie désormais 422 sur une valeur inconnue (#711, `Literal`
 * côté route) — mais l'URL, elle, reste du texte libre : un lien partagé
 * corrompu ou un `?sort=pertinence` tapé à la main ne doit pas planter tout
 * le rendu serveur de `/resultats`. `undefined` laisse l'API retomber sur
 * son propre défaut (`date_desc`).
 */
export function sortFromParam(sort?: string | null): EventSort | undefined {
  return (EVENT_SORT_VALUES as readonly string[]).includes(sort ?? "")
    ? (sort as EventSort)
    : undefined;
}
