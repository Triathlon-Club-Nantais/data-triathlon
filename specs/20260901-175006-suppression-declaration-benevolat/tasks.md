# Tasks: Suppression d'une déclaration de crédit de bénévolat

**Input**: Design documents from `specs/20260901-175006-suppression-declaration-benevolat/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/delete-volunteer-action.md, quickstart.md

**Tests**: Principe III (non-négociable) — les tâches de test précèdent
l'implémentation dans chaque story, écrites pour échouer d'abord.

**Organization**: Deux user stories indépendantes (P1 file d'attente, P2
fiche athlète) partageant le même socle backend (Phase 2), posé une seule
fois.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallélisable (fichiers différents, aucune dépendance non résolue)
- **[Story]**: US1 ou US2, uniquement en Phase 3+

## Path Conventions

Web app existante : `backend/app/...`, `backend/tests/...`,
`frontend/lib/...`, `frontend/components/...`. Chemins tirés de plan.md
§Project Structure.

---

## Phase 1: Setup

Aucune tâche — la feature s'insère dans des fichiers déjà en place
(`volunteer_action_repository.py`, `volunteer_action_service.py`,
`admin_volunteer_actions.py`, `client.ts`, `admin.ts`, les deux composants).
Aucune dépendance nouvelle, aucune migration.

---

## Phase 2: Foundational (bloquant pour US1 et US2)

**Purpose** : le trio repository → service → route est partagé par les deux
écrans ; aucune des deux stories n'est testable sans lui.

### Tests (Phase 2)

> Écrire ces tests d'abord, les voir échouer (Principe III).

- [ ] T001 [P] Test repository `delete()` — retire la ligne, `db.get` renvoie
      `None` ensuite — dans `backend/tests/test_repositories/test_volunteer_action_repository.py`
- [ ] T002 [P] Tests service `delete()` : succès sur les trois statuts
      (`en_attente`/`validee`/`refusee`), `NotFoundError` sur id inexistant,
      écriture d'une ligne `AdminActionLog` (`action="athlete.volunteer_action.delete"`,
      `entity_type="athlete"`, `entity_id=athlete_id`, payload avec `season`/`action_id`/`status`)
      — dans `backend/tests/test_services/test_volunteer_action_service.py`
- [ ] T003 [P] Tests API `DELETE /admin/volunteer-actions/{id}` : `204` sur
      succès (vérifier la ligne absente en base après), `404` sur id
      inexistant ou déjà supprimé (double suppression), `401` sans session,
      `403` sans `athletes:volunteer_validate` (via `_session_etroite`) —
      dans `backend/tests/test_api/test_admin_volunteer_actions_api.py`

### Implementation (Phase 2)

- [ ] T004 Ajouter `delete(db: Session, action: VolunteerAction) -> None`
      dans `backend/app/repositories/volunteer_action_repository.py`
      (`db.delete(action)` + `db.flush()`, patron
      `course_source_repository.remove`) — fait passer T001
- [ ] T005 Ajouter `delete(db: Session, *, admin_user_id: int, action_id: int) -> None`
      dans `backend/app/services/volunteer_action_service.py` : `_action_ou_404`,
      capture du payload avant suppression, appel au repository (T004),
      `admin_action_log_repository.create(...)` (dépend de T004) — fait
      passer T002
- [ ] T006 Ajouter la route `DELETE /admin/volunteer-actions/{action_id}`
      (`status_code=204`) dans `backend/app/api/v1/admin_volunteer_actions.py`,
      gardée par `require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)`, déléguant
      à `volunteer_action_service.delete` (dépend de T005) — fait passer T003
- [ ] T007 Lancer `uv run pytest tests/test_repositories/test_volunteer_action_repository.py tests/test_services/test_volunteer_action_service.py tests/test_api/test_admin_volunteer_actions_api.py -k delete`
      et `uv run pytest -m "not integration"` (suite complète, aucune
      régression) — depuis `backend/`

**Checkpoint** : le geste de suppression existe et est gardé côté API — les
deux stories front peuvent commencer, indépendamment l'une de l'autre.

---

## Phase 3: User Story 1 - Supprimer depuis la file d'attente (Priority: P1) 🎯 MVP

**Goal** : un admin supprime une déclaration en attente directement depuis
`/admin/benevolat`, avec confirmation.

**Independent Test** : depuis la file d'attente, déclencher puis confirmer
la suppression d'une ligne en attente → elle disparaît de la liste sans
rechargement manuel ; annuler la confirmation → elle reste.

### Tests for User Story 1

- [ ] T008 [P] [US1] Test client `apiClient.deleteVolunteerAction(id)` —
      appelle `DELETE /admin/volunteer-actions/{id}` — ajouté au bloc de
      test existant de `frontend/lib/api/client.test.ts` (ou fichier jumeau
      s'il existe déjà pour ce client)
- [ ] T009 [P] [US1] Tests `AdminVolunteerActionsTable` : bouton de
      suppression par ligne ouvre `DangerConfirm` (`useDangerConfirm`) ;
      confirmer appelle la mutation et retire la ligne (via invalidation de
      `queryKeys.pendingVolunteerActions()`) ; annuler laisse la ligne
      intacte — dans `frontend/components/benevolat/AdminVolunteerActionsTable.test.tsx`

### Implementation for User Story 1

- [ ] T010 [US1] Ajouter `deleteVolunteerAction: (id: number) => request<void>(...)`
      dans `frontend/lib/api/client.ts` (contracts/delete-volunteer-action.md)
      — fait passer T008
- [ ] T011 [US1] Ajouter `useDeleteVolunteerAction()` dans
      `frontend/lib/queries/admin.ts`, invalidant
      `queryKeys.pendingVolunteerActions()` sur succès (dépend de T010)
- [ ] T012 [US1] Ajouter le geste de suppression dans
      `AdminVolunteerActionsTable.tsx` : bouton par ligne (couleur
      destructive), `useDangerConfirm()` pour la confirmation, `toast`
      succès/erreur sur le patron d'`onAccept`/`onReject` (dépend de T011)
      — fait passer T009
- [ ] T013 [US1] Lancer `npm test -- AdminVolunteerActionsTable client` depuis
      `frontend/`

**Checkpoint** : US1 fonctionnelle et testable seule — MVP livrable.

---

## Phase 4: User Story 2 - Supprimer depuis la fiche athlète (Priority: P2)

**Goal** : un admin supprime une déclaration validée depuis la liste des
actions validées de la fiche athlète, avec confirmation et recalcul du
quota affiché.

**Independent Test** : depuis la fiche d'un athlète, déclencher puis
confirmer la suppression d'une déclaration validée → elle disparaît de la
liste et le quota de saison affiché se recalcule sans elle, sans
rechargement manuel ; annuler → rien ne change.

### Tests for User Story 2

- [ ] T014 [P] [US2] Tests `VolunteerActionsList` : bouton de suppression par
      ligne ouvre le `<DangerConfirm>` déclaratif (pas de
      `DangerConfirmProvider` monté dans le test, cf. research.md D2) ;
      confirmer appelle la mutation et invalide
      `["validated-volunteer-actions", athleteId]` **et**
      `["season-quota", athleteId, season]` ; annuler laisse la ligne
      intacte — dans `frontend/components/athletes/VolunteerActionsList.test.tsx`

### Implementation for User Story 2

- [ ] T015 [US2] Ajouter `useDeleteValidatedVolunteerAction()` (ou réutiliser
      `useDeleteVolunteerAction` de T011 en lui passant `athleteId`/`season`
      pour l'invalidation ciblée) dans `frontend/lib/queries/admin.ts`,
      invalidant `["validated-volunteer-actions", athleteId]` et
      `["season-quota", athleteId, season]` sur succès (dépend de T010)
- [ ] T016 [US2] Ajouter le geste de suppression dans
      `VolunteerActionsList.tsx` : bouton par ligne, `<DangerConfirm>`
      déclaratif géré en state local du composant (pas de
      `useDangerConfirm`, cf. research.md D2), `toast` succès/erreur
      (dépend de T015) — fait passer T014
- [ ] T017 [US2] Lancer `npm test -- VolunteerActionsList` depuis `frontend/`

**Checkpoint** : US1 et US2 fonctionnelles indépendamment.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T018 [P] `uv run ruff check backend/` et `npm run lint` (frontend) —
      aucune régression de lint
- [ ] T019 Rejouer `quickstart.md` en entier (scénarios manuels US1, US2,
      refus de pouvoir, double suppression)
- [ ] T020 `uv run pytest -m "not integration"` et `npm test` — suites
      complètes vertes avant `requesting-code-review`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)** : aucune dépendance — bloque US1 et US2.
- **US1 (Phase 3)** : dépend de Phase 2 uniquement. MVP.
- **US2 (Phase 4)** : dépend de Phase 2 uniquement (T010 partagé avec US1,
  mais T015/T016 n'attendent pas T012/T013 — les deux stories touchent des
  fichiers front distincts et sont livrables dans n'importe quel ordre une
  fois T010 posé).
- **Polish (Phase 5)** : dépend de US1 et US2.

### Parallel Opportunities

- T001/T002/T003 en parallèle (fichiers de test distincts).
- Une fois T007 vert, US1 (Phase 3) et US2 (Phase 4) peuvent avancer en
  parallèle par deux développeurs — seul T010 (client API) est un point de
  jonction, à poser une fois avant que T011 et T015 s'en servent chacun.
- T008/T009 en parallèle entre eux ; T014 est seule dans sa story.

---

## Parallel Example: Phase 2

```bash
Task: "Test repository delete() dans backend/tests/test_repositories/test_volunteer_action_repository.py"
Task: "Tests service delete() dans backend/tests/test_services/test_volunteer_action_service.py"
Task: "Tests API DELETE /admin/volunteer-actions/{id} dans backend/tests/test_api/test_admin_volunteer_actions_api.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 2 (Foundational) — trio backend + ses tests.
2. Phase 3 (US1) — geste de suppression sur la file d'attente.
3. **STOP et valider** : `quickstart.md` §US1 manuellement.
4. US1 seule est un MVP livrable et démontrable.

### Incremental Delivery

1. Phase 2 → Phase 3 (US1) → valider → PR/démo possible.
2. Phase 4 (US2) → valider → complète la feature #818.
3. Phase 5 (Polish) → `requesting-code-review`.
