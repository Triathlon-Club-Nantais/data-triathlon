# Tasks: Ouvrir le formulaire de crédit d'un athlète au mot de passe du site

**Input**: Design documents from `specs/20260901-141216-formulaire-mot-de-passe-site/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/volunteer-actions-api-change.md, quickstart.md

**Tests**: TDD non-négociable (Principe III) — chaque test qui doit changer
de verdict (401→201) est écrit/adapté **avant** l'implémentation et confirmé
rouge, puis vert après le changement de couche correspondant.

**Organization**: une seule user story (P1) — pas de phase Setup ni
Foundational, le changement porte sur une chaîne verticale déjà en place.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: User Story 1 - Le formulaire s'ouvre au mot de passe du site (Priority: P1) 🎯 MVP

**Goal**: `POST /volunteer-actions` accepte une requête sans session SSO
(mot de passe du site seul) ; une session SSO, si présente, reste tracée.

**Independent Test**: cf. quickstart.md scénarios 1-4.

### Tests — écrire/adapter avant l'implémentation, confirmer rouge

- [X] T001 [US1] Adapter `test_sans_session_rend_401` dans `backend/tests/test_api/test_volunteer_actions_api.py` : renommer `test_sans_session_rend_201_et_sans_auteur`, attendre `201` et `declared_by_user_id` à `null` dans la réponse ; lancer, confirmer rouge (toujours 401 avec le code actuel).
- [X] T002 [US1] Étendre `test_creer_une_declaration_pour_lathlete_choisi` (même fichier) pour asserter que `declared_by_user_id` vaut l'id de l'utilisateur de la session ouverte par `session_de_saisie` — verrouille le cas connecté (spec.md FR-005), passe déjà (pas de rouge attendu ici, juste une assertion renforcée).
- [X] T003 [P] [US1] Retirer `ROUTES_VOLUNTEER_ACTIONS_FERMEES` (et son usage dans `ROUTES_FERMEES`) de `backend/tests/test_auth/test_public_routes_still_open.py`, avec son commentaire devenu faux ; lancer, confirmer rouge (la route répond encore 401 sans session).
- [X] T004 [P] [US1] Ajouter un test dans `backend/tests/test_repositories/test_volunteer_action_repository.py` : `create_pending(..., declared_by_user_id=None, ...)` réussit, la ligne stockée porte `declared_by_user_id=None` ; confirmer rouge (signature actuelle exige un `int`).
- [X] T005 [P] [US1] Ajouter un test dans `backend/tests/test_services/test_volunteer_action_service.py` : `create_pending(db, declared_by_user_id=None, athlete_id=..., title=..., description=...)` rend une action avec `declared_by_user_id=None` ; confirmer rouge.

**Checkpoint**: les 5 tests ci-dessus sont rouges, le reste de la suite est
vert (code pas encore modifié).

### Implémentation backend — dans l'ordre des couches

- [X] T006 [US1] Rendre `VolunteerAction.declared_by_user_id` nullable dans `backend/app/models/volunteer_action.py` (`Mapped[int | None]`), mettre à jour le docstring du modèle.
- [X] T007 [US1] Générer la migration Alembic (`uv run alembic revision --autogenerate -m "declared_by_user_id nullable sur volunteer_actions"`), relire manuellement la révision générée (dépend de T006).
- [X] T008 [US1] Élargir `create_pending()` dans `backend/app/repositories/volunteer_action_repository.py` : `declared_by_user_id: int | None` (dépend de T006).
- [X] T009 [US1] Élargir `create_pending()` dans `backend/app/services/volunteer_action_service.py` : `declared_by_user_id: int | None` (dépend de T008).
- [X] T010 [US1] Élargir `VolunteerActionSelfOut.declared_by_user_id` et `AdminVolunteerActionOut.declared_by_user_id` dans `backend/app/schemas/volunteer_action.py` : `int` → `int | None` (dépend de T006).
- [X] T011 [US1] Basculer `backend/app/api/v1/volunteer_actions.py` sur `Depends(optional_user)` (`user: User | None`), passer `user.id if user else None` au service (dépend de T009, T010).
- [X] T012 [US1] Vérifier : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` — suite verte, T001-T005 passent désormais.

### Implémentation frontend

- [X] T013 [US1] Dans `frontend/app/(public_restricted)/benevolat/page.tsx`, sortir la section « Créditer un athlète pour le quota de saison » (`VolunteerActionForm`) du bloc conditionné par `useSession()` ; la section d'auto-déclaration (#751, `VolunteerDeclarationForm`/`VolunteerDeclarationList`) reste dans ce bloc.
- [X] T014 [US1] Créer `frontend/app/(public_restricted)/benevolat/page.test.tsx` : sans session, la section de crédit d'athlète s'affiche et la section d'auto-déclaration affiche l'invite « Se connecter » ; avec session, les deux s'affichent (écrit avant T013, confirmer rouge — le fichier n'existe pas encore donc le test échoue par absence, la précédence documente juste l'ordre logique).
- [X] T015 [US1] Vérifier : `cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build` — suite verte.

**Checkpoint**: User Story 1 complète et testable de bout en bout.

---

## Phase 2: Polish

- [X] T016 Dérouler manuellement les 4 scénarios de `quickstart.md` (formulaire accessible sans SSO, appel direct 201, traçabilité si connecté, validation admin toujours fermée).

---

## Dependencies & Execution Order

- T001-T005 (tests) avant T006-T012 (implémentation backend) — rouge puis vert.
- T006 → T007/T008/T010 → T009/T011 → T012 (modèle avant migration/repository/schéma, repository avant service, service+schéma avant route).
- T013/T014 avant T015 (composant avant vérification ; T014 peut être écrit en parallèle de T013, l'un documente l'attendu, l'autre l'implémente).
- T016 après T012 et T015.

## Parallel Opportunities

- T003, T004, T005 : fichiers de test distincts, aucune dépendance entre eux.
- T010 (schémas) est indépendant de T008/T009 (repository/service) — même dépendance commune (T006), pas l'un de l'autre.

## Implementation Strategy

Story unique (P1 = MVP). Tests d'abord (T001-T005, rouge confirmé), puis
retrait de la garde couche par couche côté backend (T006-T012), puis
ajustement d'affichage côté frontend (T013-T015), puis validation manuelle
(T016).
