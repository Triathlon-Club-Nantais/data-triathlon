/**
 * Libellés d'affichage du club — définition unique côté front (#200).
 *
 * Le back a le même libellé canonique dans `backend/app/core/club.TCN_CANONICAL_NAME`.
 * Deux définitions, même valeur : le front ne charge pas un endpoint pour un
 * texte statique qui apparaît dans l'aria-label du logo ou la meta description.
 * Si la valeur change, elle change des deux côtés (un test back verrouille
 * l'agrégat de « Top clubs »).
 */

/** Libellé complet, cas nominal. */
export const CLUB_NAME = "Triathlon Club Nantais";

/** Raccourci, pour les espaces contraints (badges, en-têtes de colonne, toggle). */
export const CLUB_NAME_SHORT = "TCN";
