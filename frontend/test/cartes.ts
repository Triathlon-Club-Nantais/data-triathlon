import { screen, within } from "@testing-library/react";
import type { Matcher } from "@testing-library/react";

/**
 * Requêtes portant sur l'**arbre carte** d'un écran (#461).
 *
 * `test/setup.ts` retire cet arbre des requêtes texte — sans quoi chaque valeur
 * y existerait en double, jsdom ne chargeant aucune feuille de style pour n'en
 * afficher qu'un. L'exclusion étant globale, `within` ne la lève pas : un test
 * qui veut justement lire les cartes doit passer `{ ignore: false }`, et
 * l'oubli ne se lit pas — la requête rend « unable to find an element », comme
 * si la carte n'existait pas. D'où cette porte d'entrée unique.
 *
 * Les requêtes de rôle et de testid ne sont pas concernées (`ignore` ne
 * s'applique qu'au texte) : elles sont rendues telles quelles.
 */
export function dansLesCartes(testId: string) {
  const scope = within(screen.getByTestId(testId));
  return {
    ...scope,
    /** `getByText` qui voit l'arbre carte. */
    texte: (matcher: Matcher) => scope.getByText(matcher, { ignore: false }),
  };
}
