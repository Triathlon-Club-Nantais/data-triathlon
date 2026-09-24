# Tasks: Rattacher un résultat de relais à plusieurs athlètes

**Input**: Design documents from `specs/20260924-171341-relay-multi-athletes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: obligatoires (Principe III, TDD non négociable). Chaque tâche d'implémentation est précédée de sa tâche de test, qui doit **échouer** avant l'implémentation. Tests backend sans réseau.

**Organization**: par user story. Chemins relatifs à la racine du dépôt.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers distincts, pas de dépendance sur une tâche inachevée)
- **[Story]** : US1, US2, US3 (spec.md)

---

## Phase 1: Setup

- [X] T001 Vérifier la base de départ dans le worktree : `backend/.env` présent, `cd backend && uv sync && uv run alembic upgrade head && uv run pytest -m "not integration"` vert (hors `test_cors_origins_defaut`, déjà rouge sur main), `cd frontend && npm install && npm test` vert

---

## Phase 2: Foundational (bloque toutes les stories)

**Purpose**: la table de liaison, son exposition en lecture et les lectures par athlète qui doivent la connaître (research R1, R2, R5).

- [X] T002 Écrire les tests du modèle `ParticipationTeammate` dans `backend/tests/test_repositories/test_participation_repository.py` : PK composite (un athlète une fois par résultat), cascade à la suppression de la participation, refus de suppression d'un athlète encore lié, relation `Participation.teammates` ordonnée par insertion
- [X] T003 Créer le modèle `ParticipationTeammate` (table `participation_teammates`, FK `participations.id` `ON DELETE CASCADE`, FK `athletes.id` `ON DELETE RESTRICT`, index `ix_participation_teammates_athlete_id`) et la relation `Participation.teammates` dans `backend/app/models/participation.py` ; l'exporter depuis `backend/app/models/__init__.py`
- [X] T004 Générer la migration `cd backend && uv run alembic revision --autogenerate -m "participation teammates"`, la relire à la main (seule la nouvelle table et son index), puis `uv run alembic upgrade head` ; vérifier `backend/tests/test_migrations.py` vert
- [X] T005 Écrire les tests de dépôt dans `backend/tests/test_repositories/test_participation_repository.py` : `replace_teammates(db, participation, athlete_ids)` remplace la composition ; `list_for_athlete` renvoie aussi un résultat où l'athlète n'est qu'équipier ; `exists_for_athlete_on_course` vrai pour un équipier présent seulement dans la liaison ; `teammate_athlete_ids(db, participation_id)`
- [X] T006 Implémenter `replace_teammates`, `teammate_athlete_ids` et étendre `list_for_athlete` (~l. 420-438), `exists_for_athlete_on_course` (~l. 59) et `count_for_athlete` avec la liaison dans `backend/app/repositories/participation_repository.py`
- [X] T007 [P] Écrire les tests dans `backend/tests/test_repositories/test_athlete_repository.py` : `delete_orphans_among` et `only_on_course` ne considèrent pas orphelin un athlète présent seulement dans la liaison ; roster, `club_rank` et `club_composition` créditent chaque équipier d'un relais attribué
- [X] T008 Étendre `delete_orphans_among` (~l. 278), `only_on_course` (~l. 251), `_club_roster_requete` (~l. 478-503), `club_rank` (~l. 521) et `club_composition` (~l. 538) avec la liaison dans `backend/app/repositories/athlete_repository.py`
- [X] T009 [P] Écrire le test de sérialisation dans `backend/tests/test_api/test_participations_api.py` : un résultat non attribué rend `teammates: []` ; un résultat attribué rend la liste des `AthleteBrief` dans l'ordre
- [X] T010 Ajouter `teammates: list[AthleteBrief] = []` à `ParticipationOut` dans `backend/app/schemas/participation.py`
- [X] T011 [P] Ajouter `teammates: AthleteBrief[]` au type `Participation` dans `frontend/lib/types.ts` en champ optionnel, comme `team_name` : les fabriques de test existantes n'ont pas à le porter

**Checkpoint**: la liaison existe, se lit par athlète et s'expose ; aucun comportement visible ne change encore.

---

## Phase 3: User Story 1 - Attribuer un relais à ses équipiers (Priority: P1) 🎯 MVP

**Goal**: un administrateur attribue un résultat de relais à 2 à 8 athlètes existants en un geste ; la fiche d'équipe vide est purgée ; le rescrape ne défait rien.

**Independent Test**: sur un relais porté par une fiche d'équipe, `PUT .../teammates` avec deux athlètes existants ; les deux fiches listent le résultat, la fiche d'équipe n'existe plus, un rescrape de l'épreuve ne change rien.

### Tests for User Story 1

- [X] T012 [US1] Écrire les tests de service dans `backend/tests/test_services/test_admin_actions.py` pour `set_teammates(db, participation_id, teammates, user_id)` : succès avec deux athlètes existants (porteur = premier, `team_name` = nom de la fiche d'origine s'il était vide, fiche d'origine purgée si orpheline, une ligne de journal `participation.set_teammates` avec la charge de data-model.md) ; fiche d'origine conservée si elle porte d'autres résultats ou si elle figure parmi les équipiers ; requête identique rejouée sans effet ni journal ; refus `DuplicateError` si un équipier a déjà un résultat sur l'épreuve (message qui le nomme) ; refus pour moins de 2, plus de 8, doublon, résultat non relais ; atomicité (aucun changement après un refus) ; recomposition [A,B] → [A,C] purge B orphelin
- [X] T013 [P] [US1] Écrire les tests dans `backend/tests/test_services/test_admin_actions.py` : `reassign_participation` sur un résultat attribué vide la liaison et purge les anciens équipiers orphelins
- [X] T014 [P] [US1] Écrire les tests d'API dans `backend/tests/test_api/test_admin_data_api.py` pour `PUT /api/v1/admin/participations/{id}/teammates` : 200 avec `ParticipationOut` et `teammates` ; 401 sans session ; 403 sans `participations:reassign` ; 404 participation ou athlète inconnu ; 409 et 422 selon contracts/api.md, messages en français
- [X] T015 [P] [US1] Écrire les tests de rescrape dans `backend/tests/test_services/test_import_service.py` : relais attribué **avec** dossard, le réimport garde `athlete_id` et la liaison ; relais attribué **sans** dossard, le réimport apparie par `team_name` et ne crée aucune ligne en double ; dans les deux cas la fiche d'équipe recréée est purgée comme orpheline ; un résultat non attribué reste réconcilié comme avant. Couvrir les trois chemins : rescrape d'une épreuve depuis l'administration (`admin_actions`), `rescrape-db` (`rescrape_service`, tests dans `backend/tests/test_services/test_rescrape_service.py`) et import SSE forcé (`import_service`) ; les trois écrivent par `_Persister`, testé une fois dans `backend/tests/test_services/test_import_service.py`. Cas d'appariement sans dossard (research R3) : prénom vide (oktime, raceresult), nom découpé en nom et prénom (timepulse), écart de casse, d'accents et d'espaces ; un `team_name` saisi à la main n'est pas écrasé

### Implementation for User Story 1

- [X] T016 [US1] Ajouter les schémas d'entrée `TeammateRef` (`athlete_id` seul pour US1) et `TeammatesUpdate` (`teammates`, 2 à 8, sans doublon) dans `backend/app/schemas/admin.py` (à côté de `ParticipationReassign`)
- [X] T017 [US1] Implémenter `set_teammates` dans `backend/app/services/admin_actions.py`, sur le modèle de `reassign_participation` (~l. 792-838) : validation relais (`Participation.is_relay` ou `Course.is_relay`), refus d'équipier déjà classé, `replace_teammates`, `athlete_id` = premier équipier, `team_name` composé selon research R3 (jamais écrasé s'il est déjà renseigné), purge via `delete_orphans_among`, journal, messages `DomainError` en français
- [X] T018 [US1] Faire vider la liaison par `reassign_participation` dans `backend/app/services/admin_actions.py` (T013). La route bénévoles (`backend/app/api/v1/benevoles.py`, ~l. 158-175) appelle la même fonction : couvrir le cas dans `backend/tests/test_api/test_benevoles_api.py`
- [X] T019 [US1] Ajouter la route `PUT /admin/participations/{participation_id}/teammates` dans `backend/app/api/v1/admin_data.py`, gardée par `require_permission(P.PARTICIPATIONS_REASSIGN)`, avec `db.commit()` et `capture_event("participation_teammates_set", ...)` comme la réattribution (~l. 100-124)
- [X] T020 [US1] Protéger la composition au rescrape dans `backend/app/services/import_service.py` : `_reconcile_resolved` (~l. 790-812) ignore une participation qui a des équipiers ; appariement préalable, sans dossard, d'une ligne de relais scrapée avec une participation attribuée de la même épreuve dont `team_name` égale le nom scrapé (`_match_without_bib`, ~l. 814-826)
- [X] T021 [P] [US1] Écrire les tests front dans `frontend/components/athletes/TeammatesDialog.test.tsx` : sélection de 2 à 8 athlètes via la recherche, retrait d'un équipier, bouton de validation inactif sous 2, avec un seul équipier restant le message « Pour un seul athlète, utilisez Réattribuer », envoi de la requête `PUT`, affichage du message d'erreur serveur, focus et fermeture
- [X] T022 [P] [US1] Ajouter `setParticipationTeammates` dans `frontend/lib/api/client.ts` et le hook `useSetParticipationTeammates` (invalidation des requêtes de la fiche athlète et de l'épreuve, comme `useReassignParticipation`) dans `frontend/lib/queries/admin.ts`, testés dans `frontend/lib/queries/admin.test.ts` (aucun test dédié à `client.ts` : le client est couvert à travers le hook)
- [X] T023 [US1] Créer `frontend/components/athletes/TeammatesDialog.tsx` en primitives `tcn` (écran public), avec `useAdminAthleteSearch`, sur le patron de la modale de rattachement de `ParticipationAdminActions.tsx` ; avec un seul équipier restant, validation inactive et renvoi vers « Réattribuer » (T021)
- [X] T024 [US1] Écrire puis faire passer les tests dans `frontend/components/athletes/ParticipationAdminActions.test.tsx` : la commande « Attribuer aux équipiers » n'apparaît que sur un résultat de relais (lu sur `participation.is_relay`) et pour `participations:reassign` ; elle ouvre `TeammatesDialog` ; implémentation dans `frontend/components/athletes/ParticipationAdminActions.tsx`
- [X] T025 [US1] Écrire puis faire passer les tests dans `frontend/app/(public_restricted)/athletes/[id]/EventsTable.test.tsx` : un résultat de relais attribué affiche le nom d'équipe et les noms des équipiers (grille et cartes) ; implémentation dans `frontend/app/(public_restricted)/athletes/[id]/EventsTable.tsx`
- [X] T026 [P] [US1] Écrire puis faire passer les tests dans `frontend/components/results/RaceFinishers.test.tsx` (grille et cartes) : une ligne de relais attribué affiche le nom d'équipe en titre et les équipiers en dessous ; une ligne non attribuée est inchangée ; implémentation dans `frontend/components/results/RaceFinishers.tsx`

**Checkpoint**: US1 livrable seule. Quickstart scénarios 1, 3, 4 et 6.

---

## Phase 4: User Story 2 - Équipier sans fiche (Priority: P2)

**Goal**: dans le même geste, un équipier saisi par nom et prénom est créé, ou réutilisé si la fiche existe.

**Independent Test**: `PUT .../teammates` avec un athlète existant et `{nom, prenom}` ; la fiche est créée et porte le résultat ; un second appel avec le même nom ne crée pas de doublon.

- [X] T027 [US2] Écrire les tests dans `backend/tests/test_services/test_admin_actions.py` et `backend/tests/test_api/test_admin_data_api.py` : équipier saisi par nom créé ; nom identique à une fiche existante réutilisé ; entrée incomplète (`athlete_name` ou `athlete_firstname` vide, ou `athlete_id` et nom ensemble) refusée en 422 ; `athletes_created` renseigné dans le journal
- [X] T028 [US2] Étendre `TeammateRef` (soit `athlete_id`, soit `athlete_name` + `athlete_firstname` non vides, cf. contracts/api.md) dans `backend/app/schemas/participation.py` et la résolution par `mapping.get_or_create_athlete` (`backend/app/services/mapping.py`, ~l. 197) dans `set_teammates`, `backend/app/services/admin_actions.py`
- [X] T029 [US2] Écrire puis faire passer les tests dans `frontend/components/athletes/TeammatesDialog.test.tsx` : ajout d'une personne par nom et prénom, validation des deux champs, envoi dans la requête ; implémentation dans `frontend/components/athletes/TeammatesDialog.tsx`

**Checkpoint**: US1 + US2. Quickstart scénario 2.

---

## Phase 5: User Story 3 - Décompte des podiums de relais (Priority: P3)

**Goal**: les compteurs individuels excluent tous les relais (FR-011) ; les podiums du club comptent un relais une fois et nomment ses équipiers (FR-010).

**Independent Test**: un relais 2e attribué à deux adhérents n'entre dans les podiums d'aucun des deux et compte une fois dans les podiums du club.

- [X] T030 [P] [US3] Écrire les tests dans `backend/tests/test_services/test_stats_service.py` : compteurs par athlète (`_rank_counters` via `stats_rank_rows`, participation_repository.py ~l. 868) sans relais ; compteurs du club inchangés ; drapeau lu sur `Participation.is_relay` (cas TimePulse mixte)
- [X] T031 [US3] Filtrer `Participation.is_relay == False` dans `stats_rank_rows` quand elle sert un athlète, dans `backend/app/repositories/participation_repository.py`, et dans les sommes de podiums par athlète du roster, `backend/app/repositories/athlete_repository.py` (~l. 483-489)
- [X] T032 [P] [US3] Écrire les tests dans `backend/tests/test_api/test_club_api.py` : `ClubPodiumEntry.teammate_names` vide par défaut, rempli pour un relais attribué, relais compté une fois
- [X] T033 [US3] Ajouter `teammate_names: list[str] = []` à `ClubPodiumEntry` dans `backend/app/schemas/club.py`, l'alimenter dans `club_podiums` (`backend/app/repositories/participation_repository.py`, ~l. 898-938) et `backend/app/services/club_service.py` ; type `ClubPodiumEntry` dans `frontend/lib/types.ts`
- [X] T034 [P] [US3] Écrire puis faire passer les tests dans `frontend/lib/utils/ma-saison.test.ts` et `frontend/app/(public_restricted)/athletes/[id]/page.test.tsx` : les podiums, victoires et top 10 individuels ignorent `is_relay` ; implémentation dans `frontend/lib/utils/ma-saison.ts` (~l. 30-33) et `frontend/app/(public_restricted)/athletes/[id]/page.tsx` (~l. 46-48)

**Checkpoint**: toutes les stories. Quickstart scénario 5.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T035 [P] Documenter la liaison et ses invariants dans `backend/app/models/AGENTS.md`, et l'endpoint et le champ `teammates` dans `docs/api/admin-donnees.md` (renvoyé par `backend/app/api/AGENTS.md`)
- [X] T036 [P] Mettre à jour `docs/modele-donnees.md` (section relais, ~l. 111-128)
- [X] T037 Vérification complète : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` ; `cd frontend && npm test && npm run lint && npm run build`
- [ ] T038 Dérouler le contrôle manuel de `quickstart.md`

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → stories.
- US1 dépend de la Phase 2 seule. US2 étend `TeammateRef` et `TeammatesDialog` de US1 : **après** US1. US3 dépend de la Phase 2 seule et peut suivre US1 ou US2.
- Dans chaque story : tests rouges → schémas → service → route → front.
- T020 (rescrape) dépend de T006 (liaison lisible) et de T017 (`team_name` posé).

## Parallel Opportunities

- Phase 2 : T007, T009, T011 en parallèle une fois T003-T004 faits.
- US1 : T013, T014, T015 en parallèle après T012 ; T021, T022 et T026 en parallèle du backend.
- US3 : T030, T032, T034 en parallèle.

## Implementation Strategy

1. **MVP** : Phases 1-3. Livre la correction des deux cas signalés dans #889, dès lors que les équipiers ont une fiche.
2. **Incrément 2** : US2, pour les équipes sans fiche d'équipier.
3. **Incrément 3** : US3, règle de décompte.
4. PR de la sous-issue vers `epic/889-relais` avec `Refs #889` (pas `Closes`), `Closes #894`.
