# Plan : badge de fiche revendiquée (#1693)

Objectif : sur la fiche athlète publique, une pastille « Fiche rattachée à l'athlète » quand un compte de membre y est rattaché (`users.athlete_id`). Pour le membre rattaché, sur sa propre fiche, un lien « Gérer ma fiche » vers `/mon-compte` (empilé sur #1737). Après revue UI/UX : ni infobulle ni arrêt de tabulation (inopérants au doigt), pastille non accentuée pour ne pas doubler « Votre fiche ». Décision utilisateur : la fiche athlète seulement (ni listes, ni palette ⌘K), à partir d'un booléen public. Aucun autre fait sur le compte n'est exposé. Pas de migration.

## Tâche 1 : contrat API (TDD)

- `backend/tests/test_api/test_athletes_api.py` : `claimed` vaut `false` sans compte rattaché ou avec une demande en attente, `true` dès qu'un compte vise la fiche ; la réponse ne porte ni adresse ni identifiant de compte.
- `AthleteDetail.claimed: bool = False` (`backend/app/schemas/participation.py`), ajout de champ, Principe IV respecté.
- Route `GET /athletes/{id}` : `claimed = bool(user_repository.ids_linked_to_athlete(db, athlete_id))`, helper existant.

## Tâche 2 : pastille (TDD)

- `frontend/lib/types.ts` : `AthleteDetail.claimed: boolean`.
- `page.tsx` : une `MetaPill` simple « Fiche rattachée à l'athlète » rejoint la rangée Catégorie/Genre quand `claimed`.
- Tests `page.test.tsx` : présente, hors de l'ordre de tabulation, non accentuée si `claimed`, absente sinon.
- Politique de confidentialité : la fiche rattachée l'indique aux visiteurs, sans montrer le compte.

## Tâche 3 : lien « Gérer ma fiche » (TDD)

- `LinkedAthleteMark` (`frontend/components/athletes/AthleteClaimAction.tsx`) : sur sa propre fiche, un lien vers `/mon-compte` à côté de « Votre fiche », cible tactile de 44 px.
- Test dans `AthleteHeaderActions.test.tsx` (cas « marque la fiche du compte rattaché »).

## Tâche 4 : vérification

- `pytest -m "not integration"`, `ruff`, `npm test`, `lint`, `build`.
