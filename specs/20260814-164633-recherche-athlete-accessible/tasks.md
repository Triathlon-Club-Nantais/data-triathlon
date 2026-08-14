# Tasks: Recherche d'athlète toujours accessible et sélection explicite

**Input**: Design documents from `specs/20260814-164633-recherche-athlete-accessible/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/athlete-selection.md, quickstart.md

**Tests**: Le Principe III de la constitution (non-négociable) s'applique intégralement.
Chaque user story ouvre par ses tâches de test, qui doivent échouer avant
l'implémentation. Frontend uniquement : `npm test` (vitest + RTL, tests colocalisés `*.test.tsx`).

**Organization**: Tâches groupées par user story (spec.md) pour une implémentation
et une validation indépendantes de chacune.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallélisable (fichiers différents, aucune dépendance non résolue)
- **[Story]**: US1 (P1), US2 (P2), correspond aux priorités de spec.md
- Chemins de fichiers exacts dans chaque description

## Path Conventions

Frontend seul concerné (`frontend/`), aucune migration, aucune nouvelle
dépendance (cf. plan.md §Technical Context).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: partir d'une base verte — la feature n'ajoute ni dépendance ni configuration.

- [X] T001 Vérifier la base verte avant tout code : `cd frontend && npm test`, consigner le nombre de tests au vert comme référence (88 fichiers, 701 tests)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: aucune — US1 (rendu de la navigation) et US2 (bouton profil + synchronisation)
ne partagent aucun socle bloquant : US1 ne touche que le rendu de `NavContent`,
US2 introduit `clearAthlete()` et l'événement de synchronisation en tant que
tâches propres à sa story (research.md D2/D3), sans quoi US1 resterait
testable seule mais dépendrait d'un mécanisme qu'elle n'utilise pas (YAGNI,
Principe VI). Passer directement à la Phase 3.

---

## Phase 3: User Story 1 - Garder la recherche accessible en toutes circonstances (Priority: P1) 🎯 MVP

**Goal**: l'entrée "Rechercher un athlète" reste visible et actionnable dans
la navigation quel que soit l'état de sélection et le format (rail
déplié/replié), sans dépendre du raccourci clavier seul.

**Independent Test**: retenir un athlète, parcourir chaque combinaison
d'état de la navigation (rail déplié/replié) et vérifier que l'entrée
"Rechercher un athlète" reste visible et actionnable à la souris/au tactile
dans chacune.

### Tests for User Story 1

> **NOTE: écrire ces tests D'ABORD, vérifier qu'ils échouent avant l'implémentation** (Principe III, non-négociable).

- [X] T002 [US1] Étendre `frontend/components/layout/AppNav.test.tsx` : (1) recherche visible et actionnable sans athlète retenu, rail déplié ; (2) recherche **et** tuile toutes deux visibles avec athlète retenu, rail déplié, aucune ne remplaçant l'autre ; (3) icône de recherche visible et cliquable avec athlète retenu, rail **replié** (cas actuellement non couvert — c'est le bug central de l'issue #323) ; (4) `⌘K`/`Ctrl+K` ouvre la recherche dans chacune de ces combinaisons ; (5) la barre mobile (bouton loupe indépendant, déjà vert) et le tiroir déplié ne régressent pas

### Implementation for User Story 1

- [X] T003 [US1] Dans `NavContent` (`frontend/components/layout/AppNav.tsx:368-462`), remplacer le rendu exclusif (tuile *ou* bouton recherche) par un rendu simultané : l'entrée "Rechercher un athlète" toujours rendue (icône seule si `!expanded`, icône + libellé + raccourci si `expanded`), et la tuile athlète rendue **en complément**, jamais à la place, quand `athlete` est non nul — dans les deux largeurs de rail et dans le tiroir mobile qui réutilise le même composant (research.md D1) — dépend de T002

**Checkpoint**: US1 fonctionnelle et testable indépendamment — la recherche ne disparaît plus jamais de la navigation.

---

## Phase 4: User Story 2 - Se sélectionner ou se relâcher depuis une page profil (Priority: P2)

**Goal**: depuis la page profil d'un athlète, un bouton permet de le retenir
comme athlète sélectionné, ou de relâcher la sélection s'il l'est déjà — la
navigation reflète le changement immédiatement, sans rechargement.

**Independent Test**: depuis la page profil d'un athlète non retenu, cliquer
sur le bouton de sélection et vérifier que la navigation reflète
immédiatement ce choix ; revenir sur la même page et vérifier que le bouton
propose désormais de relâcher ; cliquer dessus et vérifier que la navigation
repasse à l'état "aucun athlète retenu".

### Tests for User Story 2

- [X] T004 [P] [US2] Créer `frontend/components/layout/AthletePicker.test.tsx` : `clearAthlete()` supprime la clé `tcn-athlete` (`readAthlete()` renvoie ensuite `null`), et `writeAthlete`/`clearAthlete` émettent chacun un `Event("tcn-athlete-changed")` sur `window` (contracts/athlete-selection.md) — doit échouer avant l'implémentation
- [X] T005 [P] [US2] Créer `frontend/app/athletes/[id]/SelectAthleteButton.test.tsx` : affiche "Sélectionner cet athlète" quand l'athlète affiché n'est pas l'athlète retenu, "Relâcher" quand il l'est déjà ; le clic appelle `writeAthlete` (cas sélection) ou `clearAthlete` (cas relâchement) — doit échouer avant l'implémentation
- [X] T006 [P] [US2] Étendre `frontend/app/athletes/[id]/page.test.tsx` : la page monte `SelectAthleteButton` avec l'`id`/`prenom`/`nom` de l'athlète affiché — doit échouer avant l'implémentation

### Implementation for User Story 2

- [X] T007 [US2] Ajouter `clearAthlete()` dans `frontend/components/layout/AthletePicker.tsx`, et faire émettre `window.dispatchEvent(new Event("tcn-athlete-changed"))` par `writeAthlete` et `clearAthlete` après écriture effective du storage (research.md D2, D3) — dépend de T004
- [X] T008 [US2] Dans `frontend/components/layout/AppNav.tsx`, abonner `AppNav` à l'événement `tcn-athlete-changed` (relecture via `readAthlete()`, mise à jour de l'état local `athlete`) en plus de la lecture au montage (`AppNav.tsx:50-65`) — dépend de T007. Se déclenche aussi sur l'écriture faite par `onPick` du picker local (`AppNav.tsx:288-293`) : re-lecture idempotente de la même valeur, pas un bug à corriger.
- [X] T009 [US2] Créer `frontend/app/athletes/[id]/SelectAthleteButton.tsx` (`"use client"`) : bouton bascule "Sélectionner cet athlète" / "Relâcher", état initial neutre puis alignement en `useEffect` via `readAthlete()` (même patron d'hydratation que `AppNav.tsx:50-65`, pour éviter un mismatch serveur/client), clic appelant `writeAthlete({id, prenom, nom})` ou `clearAthlete()` selon le cas — dépend de T005, T007
- [X] T010 [US2] Monter `SelectAthleteButton` dans `frontend/app/athletes/[id]/page.tsx`, à côté du nom dans l'en-tête existant (`page.tsx:56-62`), avec les props de l'athlète affiché — dépend de T006, T009

**Checkpoint**: US1 + US2 fonctionnelles ensemble — la sélection depuis le profil se reflète immédiatement dans une navigation qui n'a jamais cessé d'afficher la recherche.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: vérifications transverses, aucune nouvelle capacité métier.

- [X] T011 [P] Exécuter `npm run lint` depuis `frontend/` et corriger les écarts
- [X] T012 Dérouler `quickstart.md` de bout en bout (les 7 scénarios) sur un environnement de dev local — `chromium-cli`/`playwright` indisponibles dans ce conteneur (aucun navigateur installable en pratique) : substitué par un smoke test réel (backend + frontend lancés, données de dev réelles, `GET /athletes/{id}` et `/dashboard` rendus 200 avec le nouveau texte présent) qui prouve l'absence d'erreur de build/rendu, les interactions elles-mêmes (clics, bascule recherche/tuile, sélection/relâchement) restant couvertes intégralement par T002/T005/T006 en RTL
- [X] T013 Vérifier que `npm test` est vert sur l'ensemble de la feature (90 fichiers, 714 tests)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: aucune dépendance — démarre immédiatement
- **Foundational (Phase 2)**: vide — aucun socle bloquant (cf. Phase 2)
- **User Stories (Phase 3-4)**: dépendent de Setup
  - US1 (P1) et US2 (P2) touchent toutes deux `AppNav.tsx` mais sur des sections
    disjointes (`NavContent` pour US1, l'abonnement à l'événement pour US2) —
    fonctionnellement indépendantes, mais réalisées en séquence pour éviter un
    conflit d'édition sur le même fichier
- **Polish (Phase 5)**: dépend des deux stories livrées

### User Story Dependencies

- **US1 (P1)**: aucune dépendance sur une autre story — la recherche reste
  accessible même si US2 n'est jamais livrée
- **US2 (P2)**: aucune dépendance *fonctionnelle* sur US1 (le bouton profil
  fonctionnerait même si la recherche redisparaissait en rail replié), mais
  partage le fichier `AppNav.tsx` — réalisée après US1 pour rester dans le
  même diff cohérent sur ce fichier

### Within Each User Story

- Tests écrits et rouges avant l'implémentation (Principe III)
- `AthletePicker.tsx` (storage + événement) avant `AppNav.tsx` (abonnement) avant `SelectAthleteButton.tsx` avant `page.tsx`
- Story complète avant de passer à la priorité suivante

### Parallel Opportunities

- T004, T005, T006 (tests US2, trois fichiers distincts) en parallèle
- US1 et US2 pourraient être développées en parallèle par deux personnes,
  au prix d'une fusion manuelle sur `AppNav.tsx` (aucune dépendance logique)

---

## Parallel Example: User Story 2

```bash
# Tests US2 en parallèle :
Task: "Test clearAthlete() et émission de l'événement dans frontend/components/layout/AthletePicker.test.tsx"
Task: "Test SelectAthleteButton (bascule Sélectionner/Relâcher) dans frontend/app/athletes/[id]/SelectAthleteButton.test.tsx"
Task: "Étendre page.test.tsx : montage de SelectAthleteButton dans frontend/app/athletes/[id]/page.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 seule)

1. Setup (T001)
2. User Story 1 (T002-T003)
3. **Arrêt et validation** : la recherche ne disparaît plus jamais de la navigation, y compris rail replié + athlète retenu — le constat le plus bloquant de l'issue #323 est résolu.

### Incremental Delivery

1. Setup → base verte
2. US1 → recherche toujours accessible (MVP, résout le blocage principal)
3. US2 → sélection explicite depuis le profil (capacité manquante, complète l'issue)

### Parallel Team Strategy

1. Setup en solo
2. US1 et US2 pourraient être prises en parallèle par deux personnes, avec une
   fusion manuelle attendue sur `AppNav.tsx` (T003 modifie `NavContent`, T008
   modifie le corps de `AppNav`) — sinon enchaîner séquentiellement

---

## Notes

- [P] = fichiers différents, aucune dépendance non résolue
- Le label de story trace chaque tâche jusqu'à spec.md
- Vérifier que chaque test échoue avant d'implémenter (Principe III)
- Aucune ligne de Complexity Tracking à couvrir (plan.md) : pas de dérogation de test à justifier
