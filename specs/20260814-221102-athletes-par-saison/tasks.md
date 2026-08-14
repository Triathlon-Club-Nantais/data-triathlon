---

description: "Task list for feature implementation"
---

# Tasks: Page de visualisation des athlètes par saison

**Input**: Design documents from `/specs/20260814-221102-athletes-par-saison/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/athletes-season-activity.md, quickstart.md

**Tests**: Le Principe III de la constitution v1.1.1 est **non-négociable** — TDD sans réseau. Chaque tâche d'implémentation est précédée d'une tâche de test qui doit échouer avant elle.

**Organization**: Tasks are grouped by user story (P1/P2/P3 de `spec.md`) pour une implémentation et une validation indépendantes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Peut s'exécuter en parallèle (fichiers différents, aucune dépendance non résolue)
- **[Story]**: User story concernée (US1, US2, US3)

## Path Conventions

Web app existante (backend/, frontend/) — cf. `plan.md` §Project Structure. Aucun nouveau dossier de premier niveau.

---

## Phase 1: Foundational — contrat backend (bloquant pour US1 et US2)

**Purpose**: L'endpoint `GET /athletes/season-activity` (contracts/athletes-season-activity.md) est le socle que US1 et US2 consomment tous les deux (même route, `seasons` en paramètre). US3 n'en dépend pas (tri 100 % client).

**⚠️ CRITICAL**: Aucune tâche frontend de US1/US2 ne démarre avant le checkpoint de cette phase.

- [X] T001 [P] Test repository — cas nominal + jointure interne (0 participation ⇒ absent) + tri nom/prénom, dans `backend/tests/test_repositories/test_athlete_repository.py` (doit échouer : la fonction n'existe pas encore)
- [X] T002 Implémenter `list_with_season_participation_count(db, *, seasons, club_only)` dans `backend/app/repositories/athlete_repository.py` (fait passer T001 — cf. data-model.md pour la forme de la requête, `_season_clause`/`tcn_clause` réutilisés tels quels)
- [X] T003 [P] Ajouter le schéma `AthleteSeasonActivity` dans `backend/app/schemas/athlete.py` (cf. data-model.md)
- [X] T004 [P] Test API — `GET /athletes/season-activity` : scope club, filtre saison, liste vide sur saison sans activité, dans `backend/tests/test_api/test_athletes_api.py` (doit échouer : route absente)
- [X] T005 Implémenter la route `GET /athletes/season-activity` dans `backend/app/api/v1/athletes.py` (fait passer T004 — dépend de T002, T003)

**Checkpoint**: `uv run pytest -m "not integration" -k athlete` vert. Le contrat de contracts/athletes-season-activity.md est honoré.

---

## Phase 2: User Story 1 — Consulter la liste des athlètes actifs d'une saison (Priority: P1) 🎯 MVP

**Goal**: Page publique `/club/athletes` listant les athlètes club actifs de la saison en cours, avec leur nombre d'épreuves.

**Independent Test**: Ouvrir `/club/athletes` sans paramètre : la liste ne montre que des athlètes à ≥1 participation sur la saison en cours, chacun avec son compteur (spec.md, US1, scénarios 1 et 2).

### Tests for User Story 1

- [X] T006 [P] [US1] Test du composant liste (rend une ligne par athlète avec nom + compteur ; rend l'état vide FR-007 si la liste est vide) dans `frontend/components/club/AthleteSeasonList.test.tsx`
- [X] T007 [P] [US1] Test de la page `/club/athletes` (server component, saison en cours par défaut) dans `frontend/app/club/athletes/page.test.tsx`

### Implementation for User Story 1

- [X] T008 [US1] Ajouter le type `AthleteSeasonActivity` dans `frontend/lib/types.ts`
- [X] T009 [US1] Ajouter `apiServer.listAthleteSeasonActivity(opts)` dans `frontend/lib/api/server.ts` (dépend de T008, miroir de `apiServer.getStats`)
- [X] T010 [P] [US1] Créer `AthleteSeasonList` (liste + état vide) dans `frontend/components/club/AthleteSeasonList.tsx` (fait passer T006)
- [X] T011 [US1] Créer la page `frontend/app/club/athletes/page.tsx` (RSC, saison en cours via `current_season()`, appelle `apiServer.listAthleteSeasonActivity({scope: SCOPE_CLUB, seasons: [currentSeason()]})`, rend `AthleteSeasonList`) — fait passer T007, dépend de T009, T010
- [X] T012 [US1] Ajouter l'entrée de navigation dans `frontend/components/layout/nav.config.ts` (section `club`, item `href: "/club/athletes"`) — a aussi nécessité la mise à jour d'un test existant (`AppNav.test.tsx`) qui documentait « Club » comme section 100 % `soon`, désormais fausse

**Checkpoint**: US1 démontrable seule — `npm test -- athletes` vert, page fonctionnelle sans sélecteur de saison ni tri.

---

## Phase 3: User Story 2 — Filtrer par saison (Priority: P2)

**Goal**: Le visiteur choisit une saison antérieure ; la liste et les compteurs se recalculent pour cette saison.

**Independent Test**: Sélectionner une saison antérieure change la liste sans rechargement complet ; une saison sans aucune activité club affiche l'état vide de US1 (spec.md, US2, scénarios 1 et 2).

### Tests for User Story 2

- [X] T013 [P] [US2] Étendre `frontend/app/club/athletes/page.test.tsx` : lit `?seasons=`, retombe sur la saison en cours si absent, propage à `listAthleteSeasonActivity` et à `SeasonSelector` (doit échouer avant T014 : la page ignore encore le paramètre)

### Implementation for User Story 2

- [X] T014 [US2] Étendre `frontend/app/club/athletes/page.tsx` : lire `searchParams.seasons` (comme `app/club/page.tsx`), appeler `apiServer.listSeasons({scope: SCOPE_CLUB})` et rendre `<SeasonSelector>` au-dessus de `AthleteSeasonList` (fait passer T013) — a aussi nécessité de généraliser `SeasonSelector`/`buildSeasonsHref` (`/dashboard` codé en dur → `usePathname()`, comme `RankTypeToggle`), avec mise à jour de `SeasonSelector.test.tsx` en conséquence

**Checkpoint**: US1 + US2 fonctionnent ensemble — changer de saison dans l'URL (`?seasons=2024`) met à jour la liste sans régression sur l'état vide.

---

## Phase 4: User Story 3 — Trier la liste (Priority: P3)

**Goal**: Basculer le tri entre nombre d'épreuves (décroissant, défaut) et nom de famille (alphabétique), sans aller-retour réseau.

**Independent Test**: Sur la liste déjà affichée, activer chaque tri change l'ordre des lignes sans modifier les données (spec.md, US3, scénarios 1 et 2).

### Tests for User Story 3

- [X] T015 [P] [US3] Test du composant de bascule : `?sort=count`/`?sort=nom` écrit en `pushState` (pas `router.push`), lecture via `useSearchParams` dans `frontend/components/club/AthleteSortToggle.test.tsx`
- [X] T015b [P] [US3] Test du comparateur de tri : ordre par défaut (nombre d'épreuves décroissant), bascule vers le nom de famille alphabétique, égalité de compteur départagée par nom de famille (Edge Cases du spec) dans `frontend/components/club/AthleteSeasonList.test.tsx` (doit échouer avant T017 : `AthleteSeasonList` ne trie pas encore)

### Implementation for User Story 3

- [X] T016 [US3] Créer `AthleteSortToggle` (mirroring `RankTypeToggle` — `window.history.pushState`, lecture `useSearchParams`) dans `frontend/components/club/AthleteSortToggle.tsx` (fait passer T015)
- [X] T017 [US3] Intégrer le tri en mémoire dans `frontend/components/club/AthleteSeasonList.tsx` : lit `?sort=`, trie la liste déjà chargée (défaut = nombre d'épreuves décroissant, ordre secondaire nom de famille), rend `AthleteSortToggle` (fait passer T015b)

**Checkpoint**: Les trois user stories fonctionnent ensemble sur `/club/athletes`.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T018 [P] Exécuter `quickstart.md` de bout en bout (backend + frontend démarrés, les 3 scénarios de validation) — §1 vérifié (repository direct + `curl` sur le serveur de dev réel : 153 athlètes actifs saison 2025, accès 200 sans authentification) ; §2 (parcours navigateur) non exécuté faute d'outil de navigation dans cet environnement — couvert par les tests RTL de bout en bout à la place
- [X] T019 [P] `uv run ruff check` (backend, 0 issue) et `npm run lint` + `npm run build` (frontend, TypeScript strict + RSC, 0 erreur) — `uv run pytest -m "not integration"` : 3385 verts ; `npm test` : 736 verts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)** : aucune dépendance — démarre immédiatement. **Bloque** US1 et US2 (même endpoint).
- **US1 (Phase 2)** : dépend de Phase 1. Aucune dépendance sur US2/US3.
- **US2 (Phase 3)** : dépend de Phase 1 (endpoint) **et** de T011 (la page de US1 existe déjà — US2 l'étend, ne la recrée pas). Reste indépendamment testable : sans US2, la page fonctionne déjà sur la saison en cours.
- **US3 (Phase 4)** : dépend de T010 (`AthleteSeasonList` existe déjà — US3 l'étend). Aucune dépendance sur US2 : le tri s'applique à la liste, quelle que soit la saison affichée.
- **Polish (Phase 5)** : dépend de toutes les user stories livrées.

### Parallel Opportunities

- T001 et T003 (fichiers distincts, aucune dépendance mutuelle)
- T006 et T007 (deux fichiers de test frontend distincts)
- T010 en parallèle de T008/T009 (composant vs types/client API), mais T011 attend les deux
- T018 et T019 (validation manuelle vs lint, aucune dépendance mutuelle)

---

## Parallel Example: Phase 1 (Foundational)

```bash
Task: "Test repository dans backend/tests/test_repositories/test_athlete_repository.py"
Task: "Schéma AthleteSeasonActivity dans backend/app/schemas/athlete.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Foundational) — l'endpoint est le socle de tout le reste.
2. Phase 2 (US1) — page fonctionnelle sur la saison en cours, sans sélecteur ni tri.
3. **STOP and VALIDATE** : `npm test -- athletes` + `uv run pytest -k athlete`, puis `quickstart.md` §1-2 partiel.
4. Démontrable en l'état : répond déjà à la demande centrale de l'issue #274.

### Incremental Delivery

1. Phase 1 → Phase 2 (US1, MVP) → valider → Phase 3 (US2) → valider → Phase 4 (US3) → valider → Phase 5.
2. Chaque phase ajoute de la valeur sans casser la précédente — aucune réécriture entre phases.

---

## Notes

- Aucune tâche de migration Alembic : `data-model.md` ne modifie aucune table.
- Aucun paramètre de tri côté API (Principe VI, cf. research.md) — T015-T017 sont purement frontend.
- Commit après chaque tâche ou groupe logique cohérent (convention du dépôt : Conventional Commits, un commit = un changement cohérent).

## Post-implémentation — revue de code

Deux corrections « Important » remontées par `requesting-code-review`, chacune
traitée en rouge→vert avant merge :

1. **Duplication de la clause de saison** entre `athlete_repository.py` et
   `participation_repository.py` — `_season_clause` rendue publique
   (`season_clause`) et réutilisée par `athlete_repository`, au lieu d'être
   recopiée. `core/season.py` reste pur (aucune dépendance SQLAlchemy), la
   clause vit donc dans le repository, pas dans `core/`.
2. **Edge case du spec non couvert** : un `nom` vide (import mal renseigné)
   sortait en tête de tri alphabétique plutôt qu'en fin. Corrigé côté backend
   (`case` SQL) et côté frontend (`byNomPrenom`), chacun avec son test rouge
   avant le correctif.

Vérification finale : backend 3386 tests verts, `ruff check` propre ;
frontend 737 tests verts, `npm run lint` propre.
