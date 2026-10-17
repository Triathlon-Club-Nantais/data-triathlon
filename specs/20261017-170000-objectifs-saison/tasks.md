# Tasks: Objectifs de saison de l'athlète rattaché

## Backend

- [ ] T001 Test migration `season_goals` (up/down) et table possédée (suppression du compte l'emporte)
- [ ] T002 Modèle, relation `User.season_goals`, migration, `_OWNED_TABLES`
- [ ] T003 Tests `season_goal_repository` (création, liste par compte et saison, lecture par compte, suppression, compte) et lectures de progression de `participation_repository` (meilleur temps avec exclusions, nombre avec relais)
- [ ] T004 Repositories
- [ ] T005 Tests service : création (rattachement exigé, plafond 10, validation sorte/cible), modification, suppression, 404 hors propriétaire, progression temps et nombre
- [ ] T006 `services/season_goals.py`
- [ ] T007 Tests API : `GET/POST /auth/me/goals`, `PUT/DELETE /auth/me/goals/{id}` (401, 201, 404 d'un autre compte, 409, 422)
- [ ] T008 Schémas et routes

## Frontend

- [ ] T009 Tests `SeasonGoals` : liste et progression, ajout temps et nombre, suppression, rien sans fiche rattachée
- [ ] T010 Types, client, hooks, `components/dashboard/SeasonGoals.tsx`, pose sur l'Accueil
- [ ] T011 Politique de confidentialité (test puis texte)

## Finitions

- [ ] T012 Docs `backend/app/models/AGENTS.md`
- [ ] T013 Suites complètes backend et frontend
