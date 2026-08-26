/**
 * Colonnes des tableaux en grille (listes d'épreuves, de participations…).
 *
 * Une piste est soit une largeur fixe en px, soit la piste souple qui absorbe
 * la place restante — déclarée par sa largeur *minimale* (`{ flexMin }`), pas
 * par un `1fr` nu : sous cette largeur elle serait écrasée à zéro et son
 * contenu déborderait sur la colonne voisine (issue #78).
 *
 * `gridColumns` et `gridMinWidth` dérivent de la même liste de pistes : la
 * largeur minimale du conteneur scrollable ne peut plus se désynchroniser de
 * la définition des colonnes.
 */
export type Track = number | { flexMin: number };

const trackMin = (t: Track) => (typeof t === "number" ? t : t.flexMin);

/** Valeur CSS `grid-template-columns` correspondant aux pistes. */
export function gridColumns(tracks: Track[]): string {
  return tracks
    .map((t) => (typeof t === "number" ? `${t}px` : `minmax(${t.flexMin}px, 1fr)`))
    .join(" ");
}

/**
 * Largeur en dessous de laquelle la grille ne tient plus : somme des pistes,
 * gouttières et padding latéral. À poser en `min-width` sur le conteneur
 * scrollable, pour que la fenêtre étroite scrolle au lieu de comprimer.
 */
export function gridMinWidth(
  tracks: Track[],
  { gap, paddingX }: { gap: number; paddingX: number },
): number {
  const total = tracks.reduce<number>((sum, t) => sum + trackMin(t), 0);
  const gutters = Math.max(0, tracks.length - 1);
  return total + gap * gutters + paddingX * 2;
}

/**
 * Chrome entre la largeur de viewport et la largeur réellement offerte à une
 * grille sous `app/(public_restricted)`, rail de navigation **replié** compris
 * (revue UI/UX #461) : 76px (`--tcn-nav-rail`) + 1px de bordure + 80px de
 * gouttières (`PageShell`, `md:px-10`, actif à partir de 768px — la seule
 * plage où ce chrome est consulté). Un seuil de bascule grille/cartes qui
 * ignore ce chrome affiche la grille avant qu'elle n'ait la place de tenir :
 * elle défile alors à l'horizontale dans sa propre carte, sans que rien ne
 * l'indique — exactement le défilement bidirectionnel que #461 corrige.
 *
 * Ne couvre pas le rail **déplié** (`--tcn-nav-panel`, 288px, mémorisé par
 * cookie, #482) : sur cette largeur-là, la bande de défilement réapparaît,
 * plus étroite. Accepté — la majorité des sessions démarrent repliées — et
 * atténué par un conteneur `tabIndex`/`role="region"` sur la grille, pour
 * qu'elle reste au moins atteignable au clavier si la bande existe.
 */
export const CHROME_RAIL_REPLIE = 157;
