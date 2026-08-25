import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

// `useSession` (#427) n'appelle `/auth/me` que si ce cookie est présent —
// posé par défaut ici pour que les tests existants, qui simulent une session
// via `apiClient.getSession`, gardent leur comportement sans le poser
// individuellement. Un test du visiteur anonyme l'efface explicitement.
if (typeof document !== "undefined") {
  beforeEach(() => {
    document.cookie = "tcn_logged_in=1; path=/";
  });
}

// jsdom ne fournit pas ResizeObserver, requis par les primitives `@base-ui/react`.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom n'implémente pas scrollIntoView (appelé au montage par `select`/`popover`).
// Garde `typeof Element` : les tests d'outillage (scripts/) tournent en environnement
// node, où le DOM n'existe pas et où ce setup s'exécute quand même.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

import { configure } from "@testing-library/react";

// Les écrans à tableau rendent deux arbres — la grille et les cartes — dont la
// CSS n'en affiche qu'un (#461). jsdom ne charge aucune feuille de style, donc
// les deux sont là pour Testing Library, et chaque nom, chaque temps, chaque
// badge existerait en double : tout `getByText` singulier lèverait « found
// multiple elements ». `defaultIgnore` s'applique aux requêtes **texte** et
// retire l'arbre carte de leur portée — les 159 requêtes singulières des quatre
// fichiers de test concernés passent donc sans être touchées.
//
// `[data-affichage="cartes"] *` n'est pas décoratif : `defaultIgnore` est
// appliqué par `node.matches(ignore)` (@testing-library/dom, queries/text.js),
// donc il n'écarte que les nœuds qui matchent EUX-MÊMES. `script, style`
// fonctionne parce que le texte y est porté par la balise ; le texte d'une
// carte, lui, est porté par un descendant du conteneur marqué. Sans le `*`,
// cette configuration ne filtre rien.
//
// Deux conséquences à connaître :
// - `getByRole` n'utilise pas `ignore` : une requête de rôle visant l'intérieur
//   d'une ligne doit être scopée à la main, avec `within`.
// - `within` ne lève PAS l'exclusion, qui est globale : l'arbre carte est
//   invisible aux requêtes texte, y compris à celles qui le visent. Un test qui
//   porte sur les cartes passe par `dansLesCartes` (`test/cartes.ts`), qui porte
//   le `{ ignore: false }`.
//
// `test/affichage-cartes.test.tsx` verrouille cette configuration.
configure({
  defaultIgnore: 'script, style, [data-affichage="cartes"], [data-affichage="cartes"] *',
});
