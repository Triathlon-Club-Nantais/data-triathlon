# Plan : badge de fiche revendiquée (#1693)

Objectif : sur la fiche athlète publique, une pastille « Fiche tenue par l'athlète » quand un compte de membre y est rattaché (`users.athlete_id`), avec une infobulle accessible. Pour le membre rattaché, sur sa propre fiche, un lien « Gérer dans Mon espace ». Décision utilisateur : la fiche athlète seulement (ni listes, ni palette ⌘K), à partir d'un booléen public. Aucun autre fait sur le compte n'est exposé. Pas de migration.

## Tâche 1 : contrat API (TDD)

- `backend/tests/test_api/test_athletes_api.py` : `claimed` vaut `false` sans compte rattaché, `true` dès qu'un compte vise la fiche ; la réponse ne porte ni adresse ni identifiant de compte.
- `AthleteDetail.claimed: bool = False` (`backend/app/schemas/participation.py`), ajout de champ, Principe IV respecté.
- Route `GET /athletes/{id}` : `claimed = bool(user_repository.ids_linked_to_athlete(db, athlete_id))`, helper existant.

## Tâche 2 : pastille (TDD)

- `frontend/lib/types.ts` : `AthleteDetail.claimed: boolean`.
- `frontend/components/athletes/ClaimedAthleteBadge.tsx` : `MetaPill` accentuée dans un `TooltipTrigger` focusable, explication liée par `aria-describedby` (toujours dans le DOM) et reprise dans l'infobulle.
- `page.tsx` : la pastille rejoint la rangée Catégorie/Genre quand `claimed`.
- Tests `page.test.tsx` : présente avec nom et description accessibles si `claimed`, absente sinon.

## Tâche 3 : lien « Gérer dans Mon espace » (TDD)

- `LinkedAthleteMark` (`frontend/components/athletes/AthleteClaimAction.tsx`) : sur sa propre fiche, un lien vers `/mon-espace` à côté de « Votre fiche ».
- Test dans `AthleteHeaderActions.test.tsx` (cas « marque la fiche du compte rattaché »).

## Tâche 4 : vérification

- `pytest -m "not integration"`, `ruff`, `npm test`, `lint`, `build`.
