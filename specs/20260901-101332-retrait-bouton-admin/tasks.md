# Tasks: Retrait du bouton admin de déclaration de bénévolat

**Input**: Design documents from `specs/20260901-101332-retrait-bouton-admin/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/removed-endpoint.md, quickstart.md

**Tests**: feature de suppression pure — le TDD (Principe III) s'applique en
adaptant/retirant chaque test **avec** le code qu'il couvrait, jamais après ;
chaque étape se termine avec la suite verte (voir research.md D3/D4).

**Organization**: une seule user story (P1) — pas de phase Setup ni
Foundational, rien de nouveau à initialiser.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: User Story 1 - Le geste admin en un clic disparaît (Priority: P1) 🎯 MVP

**Goal**: plus aucun geste admin de déclaration de bénévolat sans titre ni
description ; `ValiderSaison` inchangé ; données historiques toujours
lisibles.

**Independent Test**: cf. quickstart.md scénarios 1-4.

### Tests — adapter avant de retirer le code qu'ils couvrent

- [ ] T001 [US1] Adapter `test_create_laisse_title_description_a_none_et_status_au_defaut` dans `backend/tests/test_repositories/test_volunteer_action_repository.py` pour construire `VolunteerAction` directement (research.md D3) ; lancer, confirmer vert avant toute suppression.
- [ ] T002 [US1] Réécrire `test_create_consigne_les_quatre_champs_du_contrat` et `test_create_autorise_plusieurs_declarations_pour_le_meme_athlete_et_la_meme_saison` (même fichier) sur `create_pending()` (research.md D3).
- [ ] T003 [US1] Basculer `test_exists_for_athlete_season_faux_pour_une_declaration_en_attente` et `test_exists_for_athlete_season_ne_traverse_pas_les_saisons` (même fichier) sur `create_pending(..., title=..., description=...)`.
- [ ] T004 [US1] Adapter les 2 usages de `volunteer_action_repository.create()` (lignes ~83, ~189) dans `backend/tests/test_api/test_admin_volunteer_actions_api.py` pour construire `VolunteerAction` directement (research.md D4).
- [ ] T005 [P] [US1] Adapter `test_season_quota_reflete_les_trois_signaux` dans `backend/tests/test_services/test_admin_actions.py` : remplacer l'appel `admin_actions.declare_volunteer_action(...)` par `volunteer_action_repository.create_pending(...)` (le chemin admin disparaît).
- [ ] T006 [P] [US1] Supprimer dans `backend/tests/test_services/test_admin_actions.py` : `test_declare_volunteer_action_consigne_le_geste`, `test_declare_volunteer_action_autorise_plusieurs_declarations`, `test_declare_volunteer_action_sur_athlete_inexistant_refuse_et_n_ecrit_rien`.
- [ ] T007 [P] [US1] Supprimer dans `backend/tests/test_api/test_admin_data_api.py` : `test_declarer_un_benevolat_rend_201`, `test_declarer_un_benevolat_deux_fois_de_suite_est_accepte`, `test_declarer_un_benevolat_sans_le_pouvoir_rend_403`, `test_declarer_un_benevolat_sans_session_rend_401`, `test_declarer_un_benevolat_sur_coureur_inconnu_rend_404`.
- [ ] T008 [P] [US1] Retirer `"athletes:volunteer_manage"` de `CODES_ATTENDUS` dans `backend/tests/test_core/test_permissions.py`.

**Checkpoint**: `uv run pytest -m "not integration"` toujours vert (code pas
encore retiré) — les tests ci-dessus couvrent désormais ce qui doit survivre.

### Implémentation backend — retrait, dans l'ordre des couches

- [ ] T009 [US1] Retirer `ATHLETES_VOLUNTEER_MANAGE` de la classe `P` et du tuple `ALL` dans `backend/app/core/permissions.py` ; ajuster les commentaires qui la référencent (lignes ~221, ~316).
- [ ] T010 [US1] Retirer la route `POST /admin/athletes/{athlete_id}/volunteer-actions` et les imports `VolunteerActionCreate`/`VolunteerActionOut` dans `backend/app/api/v1/admin_data.py` (dépend de T009).
- [ ] T011 [US1] Retirer `declare_volunteer_action()` dans `backend/app/services/admin_actions.py` (dépend de T010).
- [ ] T012 [US1] Retirer `VolunteerActionCreate`/`VolunteerActionOut` dans `backend/app/schemas/admin.py` (dépend de T010).
- [ ] T013 [US1] Retirer `create()` dans `backend/app/repositories/volunteer_action_repository.py` et sa mention dans le docstring du module (dépend de T011).
- [ ] T014 [US1] Vérifier : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` — suite verte, aucun symbole orphelin.

### Implémentation frontend — retrait

- [ ] T015 [US1] Retirer `DeclarerBenevolat`/`peutDeclarerBenevolat` de `frontend/components/athletes/SeasonValidationPanel.tsx` ; remplacer la garde externe par `if (!peutValiderSaison) return null;`.
- [ ] T016 [US1] Retirer le describe block « SeasonValidationPanel — déclarer un bénévolat (US2) » (4 tests) dans `frontend/components/athletes/SeasonValidationPanel.test.tsx` ; revérifier le cas « ne rend rien sans pouvoir » sur la garde externe modifiée.
- [ ] T017 [US1] Retirer `useDeclareVolunteerAction` de `frontend/lib/queries/admin.ts` et ses tests associés dans `frontend/lib/queries/admin.test.ts` (dépend de T015).
- [ ] T018 [US1] Retirer `declareVolunteerAction` de `frontend/lib/api/client.ts` (dépend de T017).
- [ ] T019 [US1] Grep `VolunteerAction` (interface) dans `frontend/lib/types.ts` — retirer si orpheline après T015-T018 (dépend de T018).
- [ ] T020 [US1] Retirer le mock `useDeclareVolunteerAction` du bloc `vi.mock("@/lib/queries/admin", ...)` dans `frontend/app/(public_restricted)/athletes/[id]/page.test.tsx` (dépend de T017).
- [ ] T021 [US1] Vérifier : `cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build` — suite verte.

**Checkpoint**: User Story 1 complète et testable de bout en bout.

---

## Phase 2: Polish

- [ ] T022 Dérouler manuellement les 4 scénarios de `quickstart.md` (bouton disparu, `ValiderSaison` intact, route retirée → 404, données historiques lisibles).

---

## Dependencies & Execution Order

- T001-T008 (tests) avant T009-T013 (retrait backend) — suite verte aux deux bornes.
- T009 → T010 → T011/T012 → T013 (ordre des couches : permission avant route, route avant service/schéma, service avant repository).
- T014 clôture le backend.
- T015 → T016/T017 → T018 → T019/T020 (frontend : composant avant hook, hook avant client, client avant nettoyage des types/mocks orphelins).
- T021 clôture le frontend.
- T022 après T014 et T021.

## Parallel Opportunities

- T005, T006, T007, T008 : fichiers de test distincts, aucune dépendance entre eux.
- Aucun autre parallélisme utile — le retrait backend et frontend s'enchaîne par couches dépendantes.

## Implementation Strategy

Story unique (P1 = MVP). Tests d'abord (T001-T008, suite verte sur le code
existant), puis retrait backend couche par couche (T009-T014), puis retrait
frontend (T015-T021), puis validation manuelle (T022).
