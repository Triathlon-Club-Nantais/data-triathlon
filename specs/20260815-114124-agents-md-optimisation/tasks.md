# Tasks: Optimisation des fichiers AGENTS.md avec référence

**Input**: spec.md, plan.md, research.md, quickstart.md — `specs/20260815-114124-agents-md-optimisation/`

**Tests** : non générées — feature purement documentaire, aucun code exécutable
(Constitution Check du plan.md : Principe III marqué N/A). Vérification par
lecture et mesure (`quickstart.md`), pas par pytest.

## Phase 1: Setup

- [X] T001 Créer les dossiers `docs/api/` et `docs/auth/` s'ils n'existent pas

## Phase 2: Foundational

*Aucune tâche bloquante partagée — les 4 user stories touchent des fichiers
disjoints et sont indépendantes.*

## Phase 3: User Story 1 — Split des `AGENTS.md` verbeux (Priority: P1) 🎯 MVP

**Goal** : `backend/app/api/AGENTS.md` et `backend/app/services/auth/AGENTS.md`
perdent ≥ 40 % de leurs lignes, sans perte d'information, en déplaçant les
sections détachables identifiées par `research.md` vers `docs/api/` et
`docs/auth/`.

**Independent Test** : `wc -l` sur les deux fichiers avant/après, `grep` des
renvois, relecture des 5 nouveaux fichiers pour confirmer qu'aucun contenu n'a
disparu.

- [X] T002 [P] [US1] Créer `docs/api/courses-sources-fusion.md` avec le
      contenu intégral des sections « Sources d'une épreuve (#284) »,
      « Basculer la source active (#285) », « Re-scraper à la demande (#118) »,
      « Aperçu d'impact avant fusion (#286) » et « Fusionner (#287) », retirées
      de `backend/app/api/AGENTS.md` (lignes 84-306 à la lecture de référence)
- [X] T003 [P] [US1] Créer `docs/api/admin-donnees.md` avec le contenu intégral
      des sections « Révocation d'urgence des sessions (#169) »,
      « Administration des données (#117) » et « Doublons suspects (#288) »,
      retirées de `backend/app/api/AGENTS.md`
- [X] T004 [P] [US1] Créer `docs/api/feedback-stats.md` avec le contenu
      intégral des sections « Retours utilisateurs (#267) » et « Statistiques
      détaillées d'une participation (#272) », retirées de
      `backend/app/api/AGENTS.md`
- [X] T005 [US1] Réécrire `backend/app/api/AGENTS.md` : conserver « Portée
      club et disciplines », « Classement d'une épreuve : paginé (#163) » et
      « Protéger une ressource (#115) » tels quels ; remplacer les sections
      déplacées (T002-T004) par une table de renvoi courte (patron
      `backend/app/scrapers/AGENTS.md`) — dépend de T002, T003, T004
- [X] T006 [P] [US1] Créer `docs/auth/liste-autorisation.md` avec le contenu
      intégral de la section « Liste d'autorisation en base (#170) », retirée
      de `backend/app/services/auth/AGENTS.md`
- [X] T007 [P] [US1] Créer `docs/auth/groupes.md` avec le contenu intégral de
      la section « Groupes d'appartenance (#197) », retirée de
      `backend/app/services/auth/AGENTS.md`
- [X] T008 [US1] Réécrire `backend/app/services/auth/AGENTS.md` : conserver
      « Authentification (#114) » et « Autorisation (#115) » tels quels ;
      remplacer les sections déplacées (T006-T007) par un renvoi court —
      dépend de T006, T007
- [X] T009 [US1] Vérifier avec `wc -l` que les deux fichiers atteignent la
      cible de réduction (SC-001) et qu'aucune information n'a disparu (chaque
      renvoi pointe vers un fichier existant et non vide)

**Checkpoint** : US1 livrable seule — les deux `AGENTS.md` sont allégés, tout
le contenu reste lisible depuis `docs/`.

---

## Phase 4: User Story 2 — Convention d'assignation GitHub (Priority: P2)

**Goal** : `AGENTS.md` racine § Conventions générales documente la règle
assignation issue → assignation PR → reviewer si ready-for-review.

**Independent Test** : relire `AGENTS.md`, confirmer la présence des 3 gestes
en une entrée courte.

- [X] T010 [US2] Ajouter dans `AGENTS.md` § Conventions générales une entrée
      courte (3-4 lignes, patron de l'entrée « Lier une PR à son issue... ») :
      s'assigner une issue au démarrage du travail, assigner toute PR créée,
      demander une review dès qu'elle n'est plus en brouillon

**Checkpoint** : US2 livrable indépendamment de US1.

---

## Phase 5: User Story 3 — Titres d'issues en anglais (Priority: P3)

**Goal** : la règle de langue (Principe I) couvre explicitement les titres
d'issues GitHub, au même titre que les titres de PR déjà couverts par la
constitution.

**Independent Test** : relire la clause langue d'`AGENTS.md`, confirmer la
mention explicite des titres d'issues.

- [X] T011 [US3] Étendre la puce « Langue » de `AGENTS.md` § Conventions
      générales (ou ajouter une clause attenante courte) pour préciser que les
      titres d'issues GitHub suivent la règle anglaise des identifiants
      techniques

**Checkpoint** : US3 livrable indépendamment de US1/US2.

---

## Phase 6: User Story 4 — Commentaires de code (Priority: P3)

**Goal** : vérifier qu'aucune duplication n'est nécessaire (déjà couvert par
le Principe VI de la constitution, cf. `research.md`) — aucune tâche
d'écriture, seulement une tâche de vérification.

**Independent Test** : `grep` sur `.specify/memory/constitution.md` confirme
la règle existante ; `AGENTS.md` n'en porte pas de duplicat.

- [X] T012 [US4] Confirmer (déjà fait dans `research.md`) qu'aucun ajout n'est
      nécessaire dans `AGENTS.md` — ne rien écrire, ce constat **est** le
      livrable de cette story

**Checkpoint** : US4 livrable indépendamment des autres (c'est un no-op
documenté).

---

## Phase 7: Polish

- [X] T013 Relire `AGENTS.md` racine en entier : confirmer qu'il reste sous
      ~210 lignes malgré les ajouts T010-T011 (SC-003 : < 15 lignes nettes
      ajoutées)
- [X] T014 Exécuter `quickstart.md` intégralement et confirmer chaque
      résultat attendu

## Dependencies

- Setup (T001) avant tout.
- US1 (T002-T009) : T002/T003/T004/T006/T007 parallélisables entre elles
  (fichiers disjoints) ; T005 dépend de T002-T004 ; T008 dépend de T006-T007 ;
  T009 dépend de T005 et T008.
- US2 (T010), US3 (T011), US4 (T012) : indépendantes entre elles et de US1 —
  toutes trois éditent `AGENTS.md` racine, donc **séquentielles entre elles**
  (même fichier) mais chacune indépendamment testable.
- Polish (T013-T014) après tout le reste.

## Parallel Example

```text
# Après T001, en parallèle :
T002 Créer docs/api/courses-sources-fusion.md
T003 Créer docs/api/admin-donnees.md
T004 Créer docs/api/feedback-stats.md
T006 Créer docs/auth/liste-autorisation.md
T007 Créer docs/auth/groupes.md
```

## Implementation Strategy

MVP = US1 seule (le split, titre d'origine de l'issue #335). US2-US4 sont de
courts ajouts de convention, livrables dans la foulée sans risque — l'ordre
P1→P2→P3→P3 est respecté mais n'implique pas d'arrêt entre les phases pour
cette taille de changement.
