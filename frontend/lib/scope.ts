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

/**
 * Filtres du classement venus des cartes de synthèse (#486, RES-11).
 *
 * Distincts de `SCOPE_PARAM` : celui-ci porte la sémantique **TCN**, arbitrée par le
 * backend (`app/core/club.py`, dépositaire unique depuis #76). `CLUB_PARAM` porte un
 * club **quelconque**, en égalité exacte sur le libellé que la carte a proposé. Les
 * deux se cumulent, et leur intersection peut légitimement être vide.
 */
export const CLUB_PARAM = "club";
export const CATEGORY_PARAM = "category";

/** Nom du paramètre d'URL ouvrant les compteurs aux disciplines hors fédération. */
export const SPORTS_PARAM = "sports";

/** Valeur du paramètre quand toutes les disciplines sont affichées. */
export const SPORTS_ALL = "all";

/**
 * Traduit le paramètre d'URL en filtre pour l'API.
 *
 * L'URL est en positif (`?sports=all` = tout montrer), l'API en négatif
 * (`federal_only=true` = retirer trail, course à pied et cyclisme) : l'URL dit
 * ce qu'on voit, l'API ce qu'elle enlève. Le défaut — filtrer — est un défaut
 * d'écran, pas d'API ; c'est ici qu'il est décidé.
 */
export function federalOnlyFromParam(sports?: string | null): true | undefined {
  return sports === SPORTS_ALL ? undefined : true;
}
