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
