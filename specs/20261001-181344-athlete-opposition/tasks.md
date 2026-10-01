# Tasks: Droit d'opposition effectif d'un athlète

**Input**: Design documents from `specs/20261001-181344-athlete-opposition/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-oppositions.md

**Tests**: obligatoires (Principe III). Chaque test est écrit et vu échouer avant son code.

## Phase 1: Setup

Aucune dépendance nouvelle.

## Phase 2: Foundational

- [ ] T001 [P] Écrire `backend/tests/test_core/test_identity.py` : `opposition_key` rend la même clé pour « Jean-Pierre DUPONT », « Jean Pierre Dupont » et l'inversion nom/prénom ; accents et ponctuation ignorés ; deux personnes différentes, deux clés ; `identity_hash` rend 64 caractères hexadécimaux, stables
- [ ] T002 Implémenter `backend/app/core/identity.py` (`opposition_key`, `identity_hash`, avec `core/text.deaccent`), jusqu'à faire passer T001
- [ ] T003 Créer le modèle `backend/app/models/athlete_opposition.py` (data-model.md), l'enregistrer dans `app/models/__init__.py`, et la migration Alembic `athlete_oppositions` ; vérifier `tests/test_migrations.py`
- [ ] T004 Ajouter `OPPOSITIONS_MANAGE` (`oppositions:manage`, libellé et description en français, fonctionnalité athlètes) dans `backend/app/core/permissions.py` et à `ALL` ; l'ajouter à `CODES_ATTENDUS` de `backend/tests/test_core/test_permissions.py`
- [ ] T005 [P] Écrire `backend/tests/test_repositories/test_opposition_repository.py` : création, recherche par empreinte, ensemble des empreintes, liste triée par `applied_at` décroissant
- [ ] T006 Implémenter `backend/app/repositories/opposition_repository.py` (`get_by_hash`, `all_hashes`, `create`, `list_recent`) et, dans les repositories existants, les primitives d'application : athlètes par clé d'opposition (`athlete_repository`), participations portées et liaisons d'équipier d'un athlète (`participation_repository`), suppression des `volunteer_actions`/`season_validations` d'un athlète, détachement de `users.athlete_id` ; jusqu'à faire passer T005

## Phase 3: User Story 1, appliquer une opposition et la faire tenir (P1) 🎯 MVP

**Goal**: les résultats deviennent anonymes, la fiche disparaît, aucun import ne la ramène.

**Independent Test**: appliquer, réimporter, constater l'anonymat et les rangs inchangés.

- [ ] T007 [P] [US1] Écrire `backend/tests/test_services/test_opposition_service.py` (fixture `db_session_fk`) : `preview` compte athlètes et résultats, homonymes compris ; `apply` anonymise chaque participation (« Anonyme {course}-{dossard} », club, catégorie et `raw_data` vidés, dossard, temps, rangs, statut conservés), ajuste `tcn_count`, retire la personne des équipes de relais, détache `users.athlete_id`, supprime volontariat et validations de saison puis la fiche, journalise sans nom (`requested_on`, `anonymised_count`) ; rangs des autres inchangés ; `requested_on` futur refusé ; réapplication idempotente
- [ ] T008 [US1] Implémenter `backend/app/services/opposition_service.py` (`preview`, `apply`, `is_opposed`, `list_oppositions`), jusqu'à faire passer T007
- [ ] T009 [P] [US1] Écrire `backend/tests/test_services/test_opposition_on_import.py` : une ligne scrapée d'identité opposée (variante d'écriture comprise) est enregistrée « Anonyme {course}-{dossard} » sans club ni catégorie, sans fiche nominative ; sans dossard, elle est ignorée ; un re-scrape après application garde l'anonymat et ne recrée aucune fiche ; un équipier opposé d'un relais découpé n'entre pas dans la composition ; les rangs des autres lignes sont ceux de la source
- [ ] T010 [US1] Filtrer dans `backend/app/services/import_service.py` (`_Persister.add` après la renumérotation, empreintes chargées une fois par `_Persister` ; `_resolve_pending` pour les équipiers), jusqu'à faire passer T009
- [ ] T011 [P] [US1] Écrire les tests de refus : `POST /participations` sur une identité opposée rend 422 avec le message du contrat (`backend/tests/test_api/`), et la composition d'équipe (`admin_actions.set_teammates`) refuse un équipier opposé (`backend/tests/test_services/`)
- [ ] T012 [US1] Implémenter les refus dans `backend/app/services/scrape_service.py` et `backend/app/services/admin_actions.py` (`DomainError`, message français), jusqu'à faire passer T011
- [ ] T013 [P] [US1] Écrire `backend/tests/test_auth/test_admin_oppositions_api.py` : `preview`, `POST` (201 puis 200 idempotent, 404, 422 identité absente ou date future), 401/403 sans session ou pouvoir ; inscrire les routes dans les inventaires de gardes (`test_permissions_catalogue.py`)
- [ ] T014 [US1] Implémenter `backend/app/schemas/opposition.py`, `backend/app/api/v1/admin_oppositions.py` et son montage dans `v1/router.py`, jusqu'à faire passer T013
- [ ] T015 [P] [US1] Écrire `frontend/components/athletes/AthleteAdminPanel.test.tsx` (cas ajoutés) : le geste « Appliquer une opposition » n'apparaît qu'avec `oppositions:manage` ; il appelle `preview`, affiche le nombre de résultats (et l'avertissement d'homonymes), demande la date de la demande, confirme par `DangerConfirm`, puis appelle `POST /admin/oppositions`
- [ ] T016 [US1] Implémenter le geste dans `frontend/components/athletes/AthleteAdminPanel.tsx`, l'API dans `frontend/lib/api/client.ts`, les hooks dans `frontend/lib/queries/admin.ts`, les types dans `frontend/lib/types.ts`, jusqu'à faire passer T015

## Phase 4: User Story 2, demander le retrait depuis le site (P2)

- [ ] T017 [P] [US2] Écrire les tests du type `retrait` : `POST /feedback` l'accepte (`backend/tests/`) ; `FeedbackButton` propose « Retrait de mes données » avec son aide (nom, prénom, épreuve, réponse sous un mois) ; `FeedbackTable` l'affiche avec un badge distinct
- [ ] T018 [US2] Implémenter le type dans `backend/app/models/user_feedback.py`, `backend/app/schemas/feedback.py`, `frontend/components/tcn/FeedbackButton.tsx`, `frontend/components/admin/FeedbackTable.tsx`, `frontend/lib/types.ts`, jusqu'à faire passer T017
- [ ] T019 [US2] Mettre à jour `frontend/components/legal/content/confidentialite.tsx` (canal « Retrait de mes données », anonymisation des résultats, empreinte conservée) et son test, `updatedAt` à jour

## Phase 5: User Story 3, prouver le délai (P3)

- [ ] T020 [P] [US3] Écrire `frontend/components/admin/OppositionsScreen.test.tsx` : liste (dates, délai en jours, auteur, nombre de résultats, aucun nom), signalement du dépassement d'un mois, état vide, formulaire par nom avec date, confirmation et nombre de résultats annoncé
- [ ] T021 [US3] Implémenter `frontend/app/admin/oppositions/page.tsx`, `frontend/components/admin/OppositionsScreen.tsx` et l'entrée `nav.config.ts` (pouvoir `oppositions:manage`), titre ajouté à `app/page-titles.test.tsx`, jusqu'à faire passer T020

## Phase 6: Polish

- [ ] T022 Documenter : `backend/app/models/AGENTS.md` (table et effets), `backend/app/api/AGENTS.md` ou `docs/api/admin-donnees.md` (routes), décision #332 (opposition tenue, empreinte pseudonyme)
- [ ] T023 `uv run pytest -m "not integration"`, `uv run ruff check .`, `npm test`, `npm run lint`, `npm run build` ; corriger toute régression
- [ ] T024 Vérification manuelle selon `quickstart.md`

## Dependencies & Execution Order

- Phase 2 bloque tout. T008 dépend de T006 ; T010 de T002 et T006.
- US1 : T007→T008, T009→T010, T011→T012, T013→T014 (T014 après T008), T015→T016 (après T014).
- US2 et US3 dépendent de T014 (API) ; US3 de T008.

## Implementation Strategy

US1 livre l'obligation légale et se teste seule. US2 et US3 complètent avant la PR, dans la même branche.
