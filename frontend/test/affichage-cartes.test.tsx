// frontend/test/affichage-cartes.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { dansLesCartes } from "./cartes";

/**
 * Verrou de la configuration posée dans `test/setup.ts`.
 *
 * Les écrans à tableau rendent deux arbres — la grille et les cartes — dont un
 * seul est affiché, par CSS. jsdom ne charge aucune feuille de style : sans
 * cette configuration, chaque valeur existerait en double pour Testing Library
 * et toute requête texte singulière lèverait « found multiple elements ». La
 * règle est globale, donc invisible à la lecture d'un fichier de test : ce test
 * est ce qui la rend visible le jour où elle disparaît.
 */
describe("data-affichage=cartes", () => {
  // Le texte d'une carte est porté par un DESCENDANT du conteneur marqué, et
  // `defaultIgnore` filtre par `node.matches()` : c'est le `*` du sélecteur,
  // et lui seul, qui fait tenir cette assertion.
  it("sort les descendants de l'arbre carte des requêtes texte", () => {
    render(
      <>
        <div data-affichage="grille">
          <span>Jean DUPONT</span>
        </div>
        <div data-affichage="cartes">
          <article>
            <span>Jean DUPONT</span>
          </article>
        </div>
      </>,
    );

    expect(screen.getByText("Jean DUPONT")).toBeInTheDocument();
  });

  it("laisse `dansLesCartes` lire l'arbre carte", () => {
    render(
      <div data-testid="cartes" data-affichage="cartes">
        <span>Jean DUPONT</span>
      </div>,
    );

    expect(dansLesCartes("cartes").texte("Jean DUPONT")).toBeInTheDocument();
  });

  // Le piège que `dansLesCartes` existe pour désamorcer : `within` n'annule pas
  // une exclusion globale, et l'échec ne dit pas pourquoi.
  it("ne laisse pas `within` seul y entrer", () => {
    render(
      <div data-testid="cartes" data-affichage="cartes">
        <span>Jean DUPONT</span>
      </div>,
    );

    expect(within(screen.getByTestId("cartes")).queryByText("Jean DUPONT")).toBeNull();
  });
});
