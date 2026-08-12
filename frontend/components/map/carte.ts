/**
 * Ce que la carte et sa légende doivent partager — et rien de plus.
 *
 * Module **sans Leaflet** délibérément : `app/carte/page.tsx` charge `MapView`
 * par `dynamic()` (`ssr: false`), donc son libellé d'attente ne peut pas venir
 * de `MapView` sans annuler ce chargement différé.
 */

/**
 * Couleurs des cercles, en littéraux : `pathOptions` de Leaflet alimente un
 * attribut SVG, où `var()` n'est pas fiable. Le défaut n'était pas le littéral
 * mais sa **duplication** — la légende de l'écran portait sa propre copie, et un
 * changement de token désynchronisait les deux (#299). `app/globals.test.ts`
 * garde l'égalité avec les tokens nommés en commentaire.
 *
 * `pointilles` porte la distinction **non colorée** exigée par WCAG 1.4.1 : les
 * deux familles ne se séparaient que par leur remplissage, le seul indice non
 * coloré étant une épaisseur de trait de 2 contre 1.
 */
export const COULEURS_CARTE = {
  avecTcn: {
    remplissage: "#E9530E", // --tcn-orange
    // --tcn-orange-deeper, et non `-deep` : celui-ci est désormais trop proche du
    // remplissage pour se lire comme un trait.
    trait: "#b83a00",
    epaisseur: 2,
    pointilles: undefined,
  },
  sansTcn: {
    // --tcn-text-muted, et non l'ancien --tcn-grey-400 (#b0aaa0) qui ne tenait
    // que 2,08:1 sur papier pour les 3:1 de WCAG 1.4.11.
    remplissage: "#857f74",
    trait: "#3a3833", // --tcn-text-body
    epaisseur: 1,
    pointilles: "4 3",
  },
} as const;

/**
 * Un seul libellé d'attente. L'écran en enchaînait trois — « Chargement… » du
 * `Suspense`, « Chargement de la carte… » du `dynamic()`, « Géolocalisation des
 * courses… » de `MapView` —, soit trois façons de dire la même seconde d'attente,
 * dont une qui parlait de courses là où tout le reste parle d'épreuves.
 */
export const LIBELLE_CHARGEMENT = "Chargement de la carte…";
