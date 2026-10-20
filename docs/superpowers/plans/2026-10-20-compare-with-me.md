# Plan : se comparer à un coéquipier en un geste (#1675)

Objectif : sur la fiche d'un autre athlète, un membre rattaché voit « Me comparer », qui ouvre sa propre fiche avec ce coéquipier déjà choisi dans la comparaison. Masqué sur sa propre fiche et pour un visiteur non rattaché. Aucun changement d'API.

## Interface réutilisée

- `?comparer=<id>` (#1701) : `AthleteComparisonChart` présélectionne le coéquipier ; c'est déjà le lien « Me comparer » de Mon espace (`/athletes/<ma fiche>?comparer=<coéquipier>`).
- La session est lue par `AthleteHeaderActions` avec `useHydratedSession` (page publique rendue côté serveur) ; `LinkedAthleteMark` ne s'affiche que pour un compte rattaché.

## Tâche 1 : lien « Me comparer » (TDD)

- Test `AthleteHeaderActions.test.tsx` : compte rattaché à une autre fiche, lien « Me comparer à Jean Dupont » vers `/athletes/99?comparer=12` ; absent sur sa propre fiche et pour un connecté sans rattachement.
- `LinkedAthleteMark` (`frontend/components/athletes/AthleteClaimAction.tsx`), branche « autre fiche » : le lien, en cible tactile (`tcn-cible-tactile`), même style que celui de Mon espace.

## Tâche 2 : vérification

- `npm test`, `lint`, `build`.
