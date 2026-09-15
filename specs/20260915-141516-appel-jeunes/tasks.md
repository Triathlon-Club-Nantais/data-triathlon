# Tasks: Appel de présence jeunes

**Input**: Design documents from `/specs/20260915-141516-appel-jeunes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Principe III (TDD sans réseau, non-négociable) — chaque capacité
backend et frontend est précédée d'un test qui échoue avant l'implémentation.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

Aucune tâche : le projet, ses dépendances et son outillage existent déjà
(`backend/`, `frontend/`), et le calendrier (#868) comme les profils (#867)
sont mergés sur cette branche.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: les deux colonnes ajoutées aux modèles existants, leur
migration, et la fusion de navigation (FR-013) — dont dépendent les trois
user stories et qui n'ont chacune de valeur qu'ensemble (une seule révision
Alembic, cf. `research.md`).

**⚠️ CRITICAL**: aucune user story ne démarre avant la fin de cette phase.

- [X] T001 [P] Colonne `present: bool | None` (nullable, défaut `NULL`) sur
      `EntrainementParticipant` dans
      `backend/app/models/entrainement_participant.py` (cf. `data-model.md`)
- [X] T002 [P] Colonne `note: str` (`Text`, défaut `""`) sur `Entrainement`
      dans `backend/app/models/entrainement.py` (cf. `data-model.md`)
- [X] T003 Migration Alembic (`uv run alembic revision --autogenerate -m
      "add appel presence jeunes"` puis relecture manuelle de la révision
      générée, `backend/alembic/versions/`) ; valider
      `upgrade` → `downgrade -1` → `upgrade` (dépend de T001, T002)
- [X] T004 [P] Test nav.config : une seule section « Jeunes » à trois items
      (profils, calendrier, appel), chacun avec `permission: "jeunes:read"`
      et une `description` (donc `ecran()` ne lève pas), et disparition de
      l'entrée `a-jeunes` de la section « Administration » — dans
      `frontend/components/layout/nav.config.test.ts`
- [X] T005 Fusionner les deux entrées « Jeunes » en une seule section à trois
      items dans `frontend/components/layout/nav.config.ts` (retirer
      `a-jeunes` de la section `admin`, ajouter un item `j-profils` vers
      `/admin/jeunes` et un item `j-appel` vers `/admin/jeunes/appel` à côté
      de `j-calendrier` existant dans la section racine `jeunes` ; hrefs de
      `/admin/jeunes` et `/admin/jeunes/calendrier` inchangés — aucune page
      existante à modifier) (fait passer T004)

**Checkpoint**: `uv run alembic upgrade head` réussit, `uv run pytest -m "not
integration"` et `npm test` restent verts avant toute user story.

---

## Phase 3: User Story 1 - Réaliser l'appel de début d'une séance (Priority: P1) 🎯 MVP

**Goal**: un porteur de `jeunes:write` pointe chaque jeune inscrit à une
séance comme présent ou absent, statut conservé ; la séance du jour se crée
au besoin ; un jeune non encore inscrit s'ajoute et se pointe en un geste.

**Independent Test**: ouvrir l'appel d'une séance sans aucun pointage,
marquer plusieurs jeunes présents et absents, vérifier que le statut est
conservé après rechargement de l'écran.

### Tests for User Story 1

- [X] T006 [P] [US1] Test repository `add_participant(present=...)` (statut
      posé à la création) et nouveau `set_presence` (bascule présent/absent
      sur une ligne existante, `None` si le jeune n'est pas inscrit) dans
      `backend/tests/test_repositories/test_entrainement_repository.py`
- [X] T007 [P] [US1] Test service `add_participant` avec `present`, et
      nouveau `set_presence` (404 si le jeune n'est pas inscrit à cette
      séance) dans `backend/tests/test_services/test_entrainements_jeunes.py`
- [X] T008 [P] [US1] Test API `PATCH
      /admin/jeunes/entrainements/{id}/participants/{jeune_id}/presence` (401
      sans session, 403 pour `jeunes:read` seul, 200 pour `jeunes:write`, 404
      si l'entraînement ou l'inscription n'existe pas), `POST
      .../participants` avec `present` dans le corps (le participant créé
      porte le statut fourni), **et** un second `GET
      /admin/jeunes/entrainements/{id}` après le `PATCH` qui confirme que le
      statut posé est bien celui rendu (SC-002) — dans
      `backend/tests/test_api/test_admin_jeunes_entrainements.py`
- [X] T009 [P] [US1] Test composant `AppelPresence` (liste des inscrits,
      boutons présent/absent qui appellent l'API et reflètent le statut
      renvoyé, ajout d'un jeune non inscrit + pointage en un geste, aucun
      contrôle d'écriture sans `jeunes:write`) dans
      `frontend/components/admin/jeunes/AppelPresence.test.tsx`

### Implementation for User Story 1

- [X] T010 [US1] Implémenter `set_presence` et étendre `add_participant`
      d'un paramètre `present: bool | None = None` dans
      `backend/app/repositories/entrainement_repository.py` (fait passer
      T006 ; dépend de T003)
- [X] T011 [US1] Implémenter `set_presence` et étendre `add_participant` du
      même paramètre dans `backend/app/services/jeunes/entrainements.py`
      (fait passer T007 ; dépend de T010)
- [X] T012 [US1] Étendre `ParticipantAdd`/`ParticipantRead` (`present`) et
      ajouter `PresenceUpdate` dans `backend/app/schemas/entrainement.py` ;
      implémenter la route `PATCH .../presence` et étendre `POST
      .../participants` dans
      `backend/app/api/v1/admin_jeunes_entrainements.py`, gardées par
      `require_permission(P.JEUNES_WRITE)` (fait passer T008 ; dépend de
      T011)
- [X] T013 [P] [US1] Type `EntrainementParticipant.present` dans
      `frontend/lib/types.ts` ; appel `setEntrainementParticipantPresence` et
      extension d'`addEntrainementParticipant(present?)` dans
      `frontend/lib/api/client.ts`
- [X] T014 [US1] Hook `useSetPresence` et extension de
      `useAddEntrainementParticipant` (paramètre `present` optionnel) dans
      `frontend/lib/queries/admin.ts` (dépend de T013)
- [X] T015 [US1] Composant `AppelPresence.tsx` (cartes mobile-first, patron
      `CalendrierEntrainements.tsx` : un jeune par carte, deux boutons
      présent/absent, un sélecteur pour ajouter un jeune non inscrit tiré de
      `useProfiles()`) dans
      `frontend/components/admin/jeunes/AppelPresence.tsx` (fait passer T009 ;
      dépend de T014)
- [X] T016 [US1] Pages `frontend/app/admin/jeunes/appel/page.tsx` (résout la
      séance du jour via `useEntrainements()` ; l'absence propose sa création
      par `useCreateEntrainement()` déjà existant, puis redirige) et
      `frontend/app/admin/jeunes/appel/[id]/page.tsx` (rend `AppelPresence`)
      (dépend de T015)
- [X] T017 [US1] Lien « Ouvrir l'appel » vers `/admin/jeunes/appel/{id}` dans
      `frontend/components/admin/jeunes/EntrainementDetailDialog.tsx` (dépend
      de T016)

**Checkpoint**: US1 fonctionnelle et testable seule — l'appel de début pointe
et conserve un statut, sans appel de fin ni notes.

---

## Phase 4: User Story 2 - Vérifier la présence en fin de séance (Priority: P2)

**Goal**: un encadrant reboucle sur les jeunes marqués présents à l'appel de
début pour confirmer visuellement qu'aucun n'est manquant, sans qu'aucune
écriture ne parte au serveur.

**Independent Test**: ouvrir l'appel de fin d'une séance déjà pointée (via
fixture ou US1), cocher les jeunes retrouvés, vérifier qu'aucune requête
réseau d'écriture n'est émise et que l'écran repart vierge après remontage.

### Tests for User Story 2

- [X] T018 [P] [US2] Test composant `AppelFin` (ne montre que les
      participants `present === true`, cases à cocher en état local
      uniquement, aucun appel réseau d'écriture, indicateur « N restants »,
      état vide explicite si aucun jeune n'a encore été pointé au début) dans
      `frontend/components/admin/jeunes/AppelFin.test.tsx`

### Implementation for User Story 2

- [X] T019 [US2] Composant `AppelFin.tsx` (filtre en mémoire sur les
      participants déjà chargés, état de cases cochées local au composant,
      aucun appel `mutate`) dans
      `frontend/components/admin/jeunes/AppelFin.tsx` (fait passer T018)
- [X] T020 [US2] Bascule « Appel de début » / « Appel de fin » dans
      `frontend/app/admin/jeunes/appel/[id]/page.tsx` (ou `AppelPresence.tsx`
      selon l'emplacement le plus simple pour l'état de l'onglet actif)
      (dépend de T019, T015)

**Checkpoint**: US1 + US2 fonctionnelles ensemble — appel de début persistant,
appel de fin éphémère par-dessus.

---

## Phase 5: User Story 3 - Enrichir l'appel de contexte sur un jeune (Priority: P3)

**Goal**: un porteur de `jeunes:write` ajoute une note de séance et une note
sur un jeune pendant l'appel, et atteint le profil complet d'un jeune en un
geste.

**Independent Test**: depuis l'écran d'appel, enregistrer une note de séance,
ajouter une note à un jeune, vérifier qu'elle apparaît dans son journal de
bord (`/admin/jeunes/{id}`), et ouvrir son profil en un clic.

### Tests for User Story 3

- [X] T021 [P] [US3] Test repository `update(note=...)` (patron sentinelle
      `...`, absent du `PATCH` n'écrase pas la note existante) dans
      `backend/tests/test_repositories/test_entrainement_repository.py`
- [X] T022 [P] [US3] Test service `update_entrainement(note=...)` dans
      `backend/tests/test_services/test_entrainements_jeunes.py`
- [X] T023 [P] [US3] Test API `PATCH /admin/jeunes/entrainements/{id}` avec
      `note`, et présence de `note` dans les réponses `GET`/`POST` dans
      `backend/tests/test_api/test_admin_jeunes_entrainements.py`
- [X] T024 [P] [US3] Test composant `NoteSeanceForm` (affiche la note
      existante, soumission déclenche `PATCH`, désactivé sans `jeunes:write`,
      une soumission de texte vide/blanc n'appelle pas la mutation — Edge
      Cases de spec.md) dans
      `frontend/components/admin/jeunes/NoteSeanceForm.test.tsx`
- [X] T025 [P] [US3] Test composant `AjouterNoteJeuneDialog` (délègue au hook
      existant d'ajout d'entrée de journal, ferme après succès) dans
      `frontend/components/admin/jeunes/AjouterNoteJeuneDialog.test.tsx`
- [X] T025b [P] [US3] Test : chaque participant de `AppelPresence` porte un
      lien vers `/admin/jeunes/{jeune_id}` (FR-010) — extension de
      `frontend/components/admin/jeunes/AppelPresence.test.tsx`

### Implementation for User Story 3

- [X] T026 [US3] Implémenter `update(note=...)` (sentinelle `...`) dans
      `backend/app/repositories/entrainement_repository.py` (fait passer
      T021 ; dépend de T003)
- [X] T027 [US3] Étendre `update_entrainement` du paramètre `note` dans
      `backend/app/services/jeunes/entrainements.py` — `create_entrainement`
      n'en a pas besoin, une séance naît toujours à note vide (`""`, défaut
      du modèle) (fait passer T022 ; dépend de T026)
- [X] T028 [US3] Étendre `EntrainementRead`/`EntrainementCreate`/
      `EntrainementUpdate` du champ `note` dans
      `backend/app/schemas/entrainement.py`, plomber le champ dans les routes
      `POST`/`PATCH` de `backend/app/api/v1/admin_jeunes_entrainements.py`
      (fait passer T023 ; dépend de T027)
- [X] T029 [P] [US3] Type `Entrainement.note` dans `frontend/lib/types.ts`
      (déjà transporté par `updateEntrainement`/`createEntrainement`
      existants, aucun changement de signature côté client nécessaire)
- [X] T030 [US3] Composant `NoteSeanceForm.tsx` (textarea + bouton
      « Enregistrer », utilise `useUpdateEntrainement` existant) dans
      `frontend/components/admin/jeunes/NoteSeanceForm.tsx` (fait passer T024 ;
      dépend de T029)
- [X] T031 [US3] Composant `AjouterNoteJeuneDialog.tsx` (délègue à
      `useAddProfileLogEntry` déjà existant, #867) dans
      `frontend/components/admin/jeunes/AjouterNoteJeuneDialog.tsx` (fait
      passer T025)
- [X] T032 [US3] Intégrer `NoteSeanceForm`, `AjouterNoteJeuneDialog` et un
      lien « Voir le profil » (`next/link` vers `/admin/jeunes/{jeune_id}`)
      par jeune dans `frontend/components/admin/jeunes/AppelPresence.tsx`
      (fait passer T025b ; dépend de T030, T031, T015)

**Checkpoint**: les trois user stories fonctionnelles ensemble — c'est le
périmètre complet de #869.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T033 [P] `uv run ruff check .` et `uv run pytest -m "not integration"`
      verts (`backend/`)
- [X] T034 [P] `npm run lint`, `npm test` et `npm run build` verts
      (`frontend/`)
- [X] T035 Valider `quickstart.md` de bout en bout, largeur 375 px sans
      défilement horizontal sur l'écran d'appel (FR-011)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)** bloque toutes les user stories.
- **US1 (Phase 3)** peut démarrer dès la Phase 2 terminée.
- **US2 (Phase 4)** dépend de la Phase 2 et réutilise `AppelPresence.tsx`
  d'US1 (T020 dépend de T015) — sans backend propre, elle ne peut donc être
  démontrée qu'après US1, même si son composant (`AppelFin.tsx`) se teste
  seul.
- **US3 (Phase 5)** dépend de la Phase 2 ; ses tests backend sont
  indépendants d'US1/US2, son intégration frontend finale (T032) dépend
  d'`AppelPresence.tsx` (T015).
- **Polish (Phase 6)** après les user stories retenues.

### Parallel Opportunities

- T001/T002 en parallèle (fichiers distincts) ; T004 peut s'écrire en
  parallèle des deux.
- Les tests marqués `[P]` d'une même phase (T006-T009, T021-T025) s'écrivent
  en parallèle — fichiers distincts, aucune dépendance entre eux.
- US3 (tests et repository/service/schema backend) peut être menée en
  parallèle d'US1 par une deuxième personne dès la Phase 2 terminée — leurs
  fonctions backend sont disjointes (`set_presence` vs `update(note=...)`)
  même si elles partagent les mêmes trois fichiers (sérialiser les commits
  reste nécessaire).

---

## Implementation Strategy

### MVP First

1. Phase 2 (Foundational)
2. Phase 3 (US1) — **STOP and VALIDATE** : appel de début persistant et
   testable seul
3. Déployer/démontrer si suffisant

### Incremental Delivery

Phase 2 → US1 (MVP) → US2 → US3 → Polish, chaque phase testée et validée
avant la suivante.
