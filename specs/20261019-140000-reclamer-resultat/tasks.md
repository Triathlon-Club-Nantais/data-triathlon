# Tasks: Réclamer un résultat rangé sur une autre fiche

## Backend

- [x] T001 Test migration `result_claims` (up/down) ; table possédée (suppression de compte)
- [x] T002 Modèle, relation `User.result_claims`, migration, `_OWNED_TABLES`
- [x] T003 Tests service : demande (rattachement exigé, propre fiche, en attente, relais, plafond 5, remise en attente d'une refusée), annulation, liste des siennes, file avec indices, validation (résultat déplacé, journal, conflit), refus, réclamation non en attente → 404
- [x] T004 `result_claim_repository`, `services/result_claims.py`
- [x] T005 Tests API utilisateur et back-office (401, 403, 201, 204, 404, 409) ; pastille `claims` comptant les deux sortes
- [x] T006 Schémas, routes, pastille

## Frontend

- [x] T007 Tests `ResultClaimAction` : bouton pour le compte rattaché sur le résultat d'une autre fiche, état en attente, rien sinon
- [x] T008 `ResultClaimAction`, pose sur la page détail
- [x] T009 Tests `ResultClaimsTable` et page : deux sections distinctes, pastille de sorte, verbes, valider/refuser
- [x] T010 `ResultClaimsTable`, refonte de `/admin/rattachements` (sections, explications), libellés du journal, guide

## Finitions

- [x] T011 Docs `backend/app/models/AGENTS.md`, politique de confidentialité si besoin
- [x] T012 Suites complètes
