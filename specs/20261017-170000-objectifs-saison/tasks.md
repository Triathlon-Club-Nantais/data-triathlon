# Tasks: Objectifs de saison de l'athlète rattaché

## Backend

- [x] T001 Test migration `season_goals` (up/down) et table possédée (suppression du compte l'emporte)
- [x] T002 Modèle, relation `User.season_goals`, migration, `_OWNED_TABLES`
- [x] T003 Tests `season_goal_repository` (création, liste par compte et saison, lecture par compte, suppression, compte) et lectures de progression de `participation_repository` (meilleur temps avec exclusions, nombre avec relais)
- [x] T004 Repositories
- [x] T005 Tests service : création (rattachement exigé, plafond 10, validation sorte/cible), modification, suppression, 404 hors propriétaire, progression temps et nombre
- [x] T006 `services/season_goals.py`
- [x] T007 Tests API : `GET/POST /auth/me/goals`, `PUT/DELETE /auth/me/goals/{id}` (401, 201, 404 d'un autre compte, 409, 422)
- [x] T008 Schémas et routes

## Frontend

- [x] T009 Tests `SeasonGoals` : liste et progression, ajout temps et nombre, suppression, rien sans fiche rattachée
- [x] T010 Types, client, hooks, `components/dashboard/SeasonGoals.tsx`, pose sur l'Accueil
- [x] T011 Politique de confidentialité (test puis texte)

## Finitions

- [x] T012 Docs `backend/app/models/AGENTS.md`
- [x] T013 Suites complètes backend et frontend
