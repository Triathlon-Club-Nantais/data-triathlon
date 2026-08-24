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

/**
 * Plafond de `page_size` de `GET /participations` (`le=5000`, cf.
 * `backend/app/api/v1/participations.py`). `/club` demande **le maximum**, et
 * non un rond arbitraire : sous le plafond, le roster et les quatre KPI se
 * tronquent sans que rien ne le dise. Au plafond, `ClubDashboard` le dit.
 *
 * ponytail: le plafond *servable* est plus bas que 5000. `ClubPodiumKpi` et
 * `PodiumsList` sont deux composants client qui reçoivent `participations`
 * **entier** (#132, pour recalculer sur `?rank=` sans re-fetch) : le tableau
 * est sérialisé dans la charge RSC, donc le poids de la page croît avec le
 * nombre de participations quel que soit ce qui est rendu. Sans effet
 * aujourd'hui (820 en base) ; la sortie est l'agrégation côté serveur
 * (#274, #382), pas un plafond plus bas qui tronquerait en silence.
 */
export const CLUB_PARTICIPATIONS_PAGE_SIZE = 5000;
