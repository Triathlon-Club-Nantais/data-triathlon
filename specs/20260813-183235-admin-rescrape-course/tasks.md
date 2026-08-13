---

description: "Task list for feature implementation"
---

# Tasks: Re-scrape à la demande d'une course depuis le back-office

**Input**: Design documents from `specs/20260813-183235-admin-rescrape-course/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-rescrape-sse.md, quickstart.md

**Tests**: Le Principe III de la constitution (v1.1.1) est **non-négociable** —
TDD sans réseau. Chaque tâche de test ci-dessous est à écrire et à voir
échouer **avant** la tâche d'implémentation correspondante.

**Organization**: Tâches groupées par user story (spec.md) pour une
implémentation et une validation indépendantes de chacune.

**Révision** : ce fichier intègre les corrections de `/speckit-analyze`
(2026-08-13) — trois tâches de test ajoutées (T005-T007, refus zéro résultat,
refus épreuve divergente, survie à une déconnexion client — FR-009/FR-011),
et T003 étendue au scénario réel de purge d'orphelins (FR-006). Numérotation
renumérotée en conséquence.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallélisable (fichiers différents, aucune dépendance non résolue)
- **[Story]**: US1 / US2 / US3, cf. spec.md
- Chemins de fichiers exacts dans chaque description

## Path Conventions

Web app existante : `backend/app/`, `backend/tests/`, `frontend/`. Cf. plan.md
§Project Structure pour l'arborescence complète touchée.

---

## Phase 1: Setup

**Purpose**: Aucune initialisation de projet requise — application existante,
aucune nouvelle dépendance (cf. plan.md, Scale/Scope). Phase sans tâche.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Le seul prérequis partagé par les trois user stories est la
capacité de scraper **sans aucun cache**, y compris par heat d'un provider
fan-out (R2 de research.md) — sans quoi US1 re-scraperait une épreuve fan-out
sans rafraîchir ses heats, et US3 verrouillerait un geste qui n'aurait rien
fait.

**⚠️ CRITICAL**: Aucune user story ne peut être validée avant cette phase.

- [ ] T001 Test (rouge) : `_scrape_all_streaming(url, db, settings, use_cache_probe=False)` n'invoque jamais le `cache_probe` passé au dispatcher fan-out, contrairement au défaut `True` qui le passe — dans `backend/tests/test_services/test_import_service.py`
- [ ] T002 Implémentation : ajouter le paramètre `use_cache_probe: bool = True` à `_scrape_all_streaming` **et** `iter_import_event`, propagé au `registry_scrape_event_all(..., cache_probe=...)` — dans `backend/app/services/import_service.py` (mêmes docstrings que `_scrape_all`, cf. research.md R2)

**Checkpoint** : `uv run pytest -m "not integration" backend/tests/test_services/test_import_service.py` vert. Le comportement par défaut (`use_cache_probe=True`) est inchangé pour tous les appelants existants (import public, `run_batch`).

---

## Phase 3: User Story 1 - Rafraîchir une course après correction chronométreur (Priority: P1) 🎯 MVP

**Goal**: Un administrateur clique « Re-scraper » sur la page d'une course,
voit la progression en direct, et retrouve à la fin des résultats et
métadonnées à jour — issus de la source active, sans doublon — même si la
connexion est interrompue en cours de route.

**Independent Test**: Déclencher un re-scrape sur une course dont les temps
source ont changé (mock `httpx`) et vérifier que le classement affiché et les
métadonnées de la course reflètent la nouvelle donnée à la fin du flux SSE.

### Tests for User Story 1

> **Écrire ces tests D'ABORD, vérifier qu'ils échouent avant toute implémentation.**

- [ ] T003 [P] [US1] Test service : `admin_actions.iter_rescrape_course` scrape l'URL de la **source active** de la course, upsert les participations (aucun doublon sur un dossard déjà présent), met à jour les métadonnées de la course si changées, purge une fiche coureur devenue orpheline par réconciliation d'identité pendant ce re-scrape (fixture : un athlète ne porte plus qu'une participation sur la course visée, dossard réattribué par le scrape simulé → fiche supprimée et comptée dans `orphans_removed`), et écrit une entrée `admin_action_log` (`action="course.rescrape"`) — dans `backend/tests/test_services/test_admin_actions.py`
- [ ] T004 [P] [US1] Test API/contrat : `POST /admin/courses/{course_id}/rescrape` — 401 sans session, 403 sans `courses:sources`, 200 en `text/event-stream` avec au moins un événement `scraping`, un `saving` et un `done` portant `imported`/`updated`/`total`/`orphans_removed` (cf. contracts/admin-rescrape-sse.md) — dans `backend/tests/test_api/test_admin_course_rescrape.py`
- [ ] T005 [P] [US1] Test service (FR-009) : `iter_rescrape_course` refuse — erreur explicite, course **inchangée** — quand le scrape simulé de la source active ne renvoie aucun résultat — dans `backend/tests/test_services/test_admin_actions.py`
- [ ] T006 [P] [US1] Test service (FR-009) : `iter_rescrape_course` refuse — erreur explicite, course **inchangée** — quand le scrape simulé publie une épreuve d'identité différente (nom/date/type divergents) — dans `backend/tests/test_services/test_admin_actions.py`
- [ ] T007 [P] [US1] Test service (FR-011) : `iter_rescrape_course` termine et commite (participations persistées, orphelins purgés, entrée journal écrite) même si le consommateur du générateur arrête de lire à mi-flux (simulateur : itérer deux événements puis abandonner la boucle) — dans `backend/tests/test_services/test_admin_actions.py`
- [ ] T008 [P] [US1] Test front : `useRescrapeStream` — état `running` pendant le flux, `phase`/`progress` mis à jour à chaque événement `saving`, `done` final expose `imported`/`updated`/`total` — dans `frontend/hooks/useRescrapeStream.test.ts`
- [ ] T009 [P] [US1] Test front : `CourseSourcesPanel` affiche un bouton « Re-scraper » quand `courses:sources` est porté, une barre de progression pendant le flux, et un message de succès en fin d'opération — dans `frontend/components/courses/CourseSourcesPanel.test.tsx`

### Implementation for User Story 1

- [ ] T010 [US1] Générateur `iter_rescrape_course(db, *, course_id, user_id, settings) -> Iterator[dict]` — le scrape et la persistance tournent dans un **thread dédié**, indépendant de la consommation du flux SSE (patron `queue.Queue` + sentinel de `_scrape_all_streaming`, étendu à toute l'opération — research.md R7), pour survivre à une déconnexion (FR-011, T007) ; 404 si course introuvable ou sans source active, scrape via `_scrape_all_streaming(..., use_cache_probe=False)` (T002), refuse zéro résultat / épreuve divergente via `_require_same_event` réutilisé tel quel (T005, T006), persiste en upsert (`_Persister`, patron `iter_import_event`), purge les orphelins (`athlete_repository.only_on_course` avant / `delete_orphans_among` après, T003), journalise (`admin_action_log_repository.create`) — dans `backend/app/services/admin_actions.py` (dépend de T002, T003, T005, T006, T007)
- [ ] T011 [US1] Route `POST /admin/courses/{course_id}/rescrape` — `Depends(require_permission(P.COURSES_SOURCES))`, `StreamingResponse` sur `iter_rescrape_course`, mêmes en-têtes SSE que `scrape_event_stream` (padding 2 Ko, `Cache-Control`, `X-Accel-Buffering`, `Content-Encoding: identity`) — nouveau fichier `backend/app/api/v1/admin_course_rescrape.py` (dépend de T010)
- [ ] T012 [US1] Monter `admin_course_rescrape` dans l'agrégateur — `backend/app/api/v1/router.py` (dépend de T011)
- [ ] T013 [P] [US1] Lecteur SSE du nouvel endpoint (patron `importEventStream`) — `frontend/lib/api/sse.ts` (dépend de T011)
- [ ] T014 [US1] Hook `useRescrapeStream` (patron `useImportStream`, état `running`/`phase`/`progress`/`imported`/`updated`/`total`/`error`) — nouveau fichier `frontend/hooks/useRescrapeStream.ts` (dépend de T013, T008)
- [ ] T015 [US1] Bouton « Re-scraper » + barre de progression, visibles si `session.permissions.includes("courses:sources")`, désactivés pendant `running`, toast de succès/erreur en fin de flux — `frontend/components/courses/CourseSourcesPanel.tsx` (dépend de T014, T009)

**Checkpoint**: User Story 1 fonctionnelle et testable de bout en bout —
`uv run pytest -m "not integration" backend/tests/test_services/test_admin_actions.py backend/tests/test_api/test_admin_course_rescrape.py` et `npm test -- useRescrapeStream CourseSourcesPanel` verts.

---

## Phase 4: User Story 2 - Rejouer un import qui avait échoué (Priority: P2)

**Goal**: Relancer un re-scrape sur une course dont l'import précédent était
partiel complète les participants manquants, sans dupliquer ceux déjà
présents. Aucune implémentation nouvelle : c'est une propriété de l'upsert
déjà construit pour US1 (`_Persister`, contrainte `uq_participation_bib`) —
cette phase la **valide** explicitement sur le chemin ciblé par course_id.

**Independent Test**: Persister un jeu partiel de participations pour une
course, puis déclencher le re-scrape avec un mock renvoyant le jeu complet ;
vérifier que les manquants apparaissent et qu'aucun dossard existant n'est
dupliqué.

### Tests for User Story 2

- [ ] T016 [P] [US2] Test service : `iter_rescrape_course` sur une course dont seule une partie des participants est en base (fixture) — le mock de scrape renvoie l'ensemble complet, le résultat ajoute les manquants et laisse le total de participations égal au nombre de dossards uniques renvoyés (aucun doublon) — dans `backend/tests/test_services/test_admin_actions.py`

**Checkpoint**: `uv run pytest -m "not integration" backend/tests/test_services/test_admin_actions.py -k replay` vert, sans modification d'`admin_actions.py` au-delà de T010.

---

## Phase 5: User Story 3 - Empêcher deux re-scrapes concurrents sur la même course (Priority: P3)

**Goal**: Un second re-scrape déclenché sur une course déjà en cours de
re-scrape est refusé explicitement (409), sans affecter les re-scrapes
d'autres courses.

**Independent Test**: Déclencher un re-scrape sur la course A (flux tenu
ouvert via un mock lent), tenter un second déclenchement sur A pendant que le
premier tourne (refusé), puis un déclenchement sur B différente (accepté).

### Tests for User Story 3

- [ ] T017 [P] [US3] Test service : `iter_rescrape_course` lève un refus explicite si un re-scrape est déjà en cours sur le **même** `course_id`, et n'est pas affecté par un re-scrape en cours sur une course différente — dans `backend/tests/test_services/test_admin_actions.py`
- [ ] T018 [P] [US3] Test API : la route répond `409` (corps `{"detail": "..."}`) **avant** l'ouverture du flux SSE si une requête concurrente cible la même course — dans `backend/tests/test_api/test_admin_course_rescrape.py`

### Implementation for User Story 3

- [ ] T019 [US3] Verrou en mémoire par `course_id` (`dict[int, bool]` + `threading.Lock`, module-level dans `admin_actions.py`) : acquis à l'entrée d'`iter_rescrape_course`, relâché en `finally`, lève `CourseRescrapeAlreadyRunningError` (`DomainError`, 409) si déjà tenu — `ponytail: verrou process unique, migrer vers un verrou DB si le service passe multi-instance` — dans `backend/app/services/admin_actions.py` (dépend de T010, T017)
- [ ] T020 [US3] Propager `CourseRescrapeAlreadyRunningError` en 409 avant tout octet du flux — `backend/app/api/v1/admin_course_rescrape.py` (dépend de T019, T018)

**Checkpoint**: Les trois user stories passent indépendamment ; SC-005 vérifié par T017/T018.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cohérence documentaire et validation de bout en bout.

- [ ] T021 [P] Documenter la nouvelle ressource dans `backend/app/api/AGENTS.md` (section « Re-scraper une épreuve à la demande : `POST /admin/courses/{id}/rescrape` (#118) »), sur le même patron que les sections #284/#285/#286 déjà présentes
- [ ] T022 `uv run ruff check backend/app` et `npm run lint` (frontend) sans nouvelle alerte
- [ ] T023 Dérouler les 3 scénarios de `quickstart.md` en dev local et confirmer les résultats attendus

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: aucune tâche.
- **Foundational (Phase 2)**: T001-T002 — bloque toutes les user stories.
- **User Story 1 (Phase 3)**: dépend de Phase 2. MVP.
- **User Story 2 (Phase 4)**: dépend de Phase 2 **et** de T010 (US1) — c'est une
  validation du même générateur, pas une story indépendante en code.
- **User Story 3 (Phase 5)**: dépend de Phase 2 **et** de T010 (US1) — le verrou
  s'ajoute au générateur déjà écrit.
- **Polish (Phase 6)**: dépend des stories livrées.

### Parallel Opportunities

- T003-T009 (tests US1) en parallèle entre eux — fichiers distincts (T003,
  T004, T005, T006, T007 partagent `test_admin_actions.py`/`test_admin_course_rescrape.py`
  mais sont des cas indépendants, à regrouper dans la même PR pour limiter le
  risque de conflit).
- T013 (front SSE reader) en parallèle de T010-T012 (backend) une fois T011 mergé côté contrat (le mock front n'attend pas l'implémentation réelle).
- T016 (US2) et T017-T018 (US3) en parallèle entre eux une fois T010 posé.

---

## Parallel Example: User Story 1

```bash
# Tests US1, en parallèle :
Task: "Test service iter_rescrape_course (chemin heureux + purge) dans backend/tests/test_services/test_admin_actions.py"
Task: "Test API SSE (contrat, auth) dans backend/tests/test_api/test_admin_course_rescrape.py"
Task: "Test service : refus zéro résultat (FR-009) dans backend/tests/test_services/test_admin_actions.py"
Task: "Test service : refus épreuve divergente (FR-009) dans backend/tests/test_services/test_admin_actions.py"
Task: "Test service : survit à une déconnexion client (FR-011) dans backend/tests/test_services/test_admin_actions.py"
Task: "Test hook useRescrapeStream dans frontend/hooks/useRescrapeStream.test.ts"
Task: "Test CourseSourcesPanel dans frontend/components/courses/CourseSourcesPanel.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 2 (Foundational) — cache désarmé par heat.
2. Phase 3 (US1) — bouton, SSE, upsert, métadonnées à jour, refus explicites, survie à la déconnexion.
3. **STOP and VALIDATE** : scénarios 1 et 2 de `quickstart.md`.
4. Démo/déploiement possible dès là — US2 et US3 sont des durcissements, pas des prérequis à la valeur livrée.

### Incremental Delivery

1. Foundational → Phase 3 (US1, MVP) → valider → livrer.
2. Phase 4 (US2) → valider le rejeu d'import partiel → livrer.
3. Phase 5 (US3) → valider le refus de concurrence → livrer.
4. Phase 6 (Polish) → documentation + lint + quickstart complet.

---

## Notes

- [P] = fichiers différents, aucune dépendance non résolue.
- US2 et US3 ne créent aucun nouveau fichier de production hors T019-T020
  (verrou) — elles durcissent T010, elles ne le dupliquent pas.
- Vérifier que chaque test échoue avant d'écrire l'implémentation qui le fait
  passer (Principe III).
- Committer après chaque tâche ou groupe cohérent.
- S'arrêter à chaque checkpoint pour valider la story indépendamment.
