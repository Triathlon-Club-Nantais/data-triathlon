---

description: "Task list template for feature implementation"
---

# Tasks: Distinction abandons / non-partants / disqualifiés

**Input**: Design documents from `/specs/20260815-112430-abandons-dnf-dns-dsq/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/course-summary.md, quickstart.md

**Tests**: Principe III (non-négociable) — tâches de test générées pour la
phase Foundational (backend, seul endroit qui produit une nouvelle valeur) et
pour chacune des deux user stories (rendu frontend).

**Organization**: Une phase Foundational (backend, partagée par les deux
récits) puis une phase par user story (front, chacune indépendamment
testable).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)

## Path Conventions

Web app existante : `backend/app/`, `backend/tests/`, `frontend/app/`,
`frontend/components/`.

---

## Phase 1: Setup

Aucune tâche — projet existant, aucune nouvelle dépendance, aucune migration
(cf. plan.md § Technical Context).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose** : produire `dnf`/`dns`/`dsq` en sortie de l'API. Les deux user
stories (front) en dépendent — aucune ne peut être implémentée avant.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational

> **Écrire ces tests D'ABORD, les voir échouer avant implémentation** (Principe III).

- [ ] T001 Test `course_summary` avec des participations DNF + DNS + DSQ + finisher + statut inconnu mêlés : vérifie `dnf`, `dns`, `dsq` individuellement et l'invariant `non_finishers == dnf + dns + dsq` dans `backend/tests/test_services/test_stats_service.py`

### Implementation for Foundational

- [ ] T002 Ajouter `dnf: int`, `dns: int`, `dsq: int` à `CourseSummary` dans `backend/app/schemas/course.py` (après `non_finishers`, avant `unknown`)
- [ ] T003 Décomposer `_STATUTS_NON_FINISHERS` en trois compteurs dédiés (`dnf`, `dns`, `dsq`) dans la boucle de `course_summary`, `non_finishers` restant la somme des trois, dans `backend/app/services/stats_service.py` (depends on T002)
- [ ] T004 [P] Ajouter `dnf: number`, `dns: number`, `dsq: number` au type `CourseSummary` dans `frontend/lib/types.ts`

**Checkpoint**: `uv run pytest -m "not integration" backend/tests/test_services/test_stats_service.py` vert ; `GET /courses/{id}/summary` renvoie les trois nouveaux champs.

---

## Phase 3: User Story 1 - Pastilles distinctes sur la page de l'épreuve (Priority: P1) 🎯 MVP

**Goal**: `/courses/[id]` affiche trois pastilles séparées (Abandons /
Non-partants / Disqualifiés) au lieu d'une pastille unique « Abandons »,
chacune masquée si nulle.

**Independent Test**: Construire une réponse `CourseSummary` de test avec
`dnf=5, dns=2, dsq=1`, rendre la page, vérifier trois `MetaPill` distinctes
avec les bons chiffres ; avec `dns=0, dsq=0`, vérifier qu'aucune des deux
pastilles vides n'apparaît.

### Tests for User Story 1

> **Écrire ces tests D'ABORD, les voir échouer avant implémentation** (Principe III).

- [ ] T005 [P] [US1] Test de rendu : épreuve avec `dnf`/`dns`/`dsq` tous non nuls → trois `MetaPill` avec les bons libellés et chiffres, dans `frontend/app/courses/[id]/page.test.tsx`
- [ ] T006 [P] [US1] Test de rendu : épreuve avec `dns=0` et `dsq=0` → seule la pastille « Abandons » apparaît (si `dnf>0`), aucune pastille vide, dans `frontend/app/courses/[id]/page.test.tsx`

### Implementation for User Story 1

- [ ] T007 [US1] Remplacer la pastille unique `Abandons` par trois `MetaPill` conditionnelles (`dnf`→« Abandons », `dns`→« Non-partants », `dsq`→« Disqualifiés »), chacune affichée seulement si `> 0`, dans `frontend/app/courses/[id]/page.tsx` (depends on T004)

**Checkpoint**: User Story 1 fonctionnelle et testable indépendamment — la page de l'épreuve raconte les trois catégories séparément.

---

## Phase 4: User Story 2 - Résumé textuel cohérent (Priority: P2)

**Goal**: `resumeEpreuve()` (résumé en une ligne de la liste de résultats)
distingue les trois catégories comme le fait désormais la page de l'épreuve
(US1), au lieu du mot générique « abandons ».

**Independent Test**: Construire un `CourseSummary` de test avec les trois
statuts non nuls, appeler `resumeEpreuve`, vérifier que les trois segments
apparaissent séparément avec le bon vocabulaire ; avec seulement des abandons,
vérifier que le résumé ne mentionne ni non-partants ni disqualifiés.

### Tests for User Story 2

> **Écrire ces tests D'ABORD, les voir échouer avant implémentation** (Principe III).

- [ ] T008 [P] [US2] Test : `resumeEpreuve` avec `dnf`/`dns`/`dsq` tous non nuls produit trois segments distincts (« X abandons », « Y non-partants », « Z disqualifiés ») dans `frontend/components/results/RaceFinishers.test.tsx`
- [ ] T009 [P] [US2] Test : `resumeEpreuve` avec `dns=0` et `dsq=0` ne mentionne que les abandons, dans `frontend/components/results/RaceFinishers.test.tsx`

### Implementation for User Story 2

- [ ] T010 [US2] Réécrire `resumeEpreuve()` pour pousser trois segments conditionnels (`dnf`/`dns`/`dsq`) au lieu d'un segment `abandons` unique, dans `frontend/components/results/RaceFinishers.tsx` (depends on T004)

**Checkpoint**: Les deux user stories fonctionnent indépendamment et racontent la même histoire des trois catégories sur toute la page.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T011 [P] Vérifier l'invariant `total == finishers + dnf + dns + dsq + unknown` de bout en bout via `quickstart.md` §1-§3 (backend + frontend + vérification manuelle)
- [ ] T012 Suite complète avant PR : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` puis `cd frontend && npm test && npm run lint && npm run build` (quickstart.md §4)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: Aucune dépendance — démarre immédiatement. **BLOQUE** les deux user stories (elles consomment `dnf`/`dns`/`dsq`).
- **User Story 1 (Phase 3)**: Dépend de Foundational. Aucune dépendance sur US2.
- **User Story 2 (Phase 4)**: Dépend de Foundational. Indépendante d'US1 (fichier distinct), peut être menée en parallèle ou après.
- **Polish (Phase 5)**: Dépend des deux user stories complètes.

### Parallel Opportunities

- T001 (test backend) s'écrit et s'exécute seul avant T002/T003 (même fichier de service, séquentiel).
- T004 (type frontend) est parallélisable avec T001-T003 (fichiers distincts, aucune dépendance croisée).
- Une fois Foundational complète, US1 (T005-T007) et US2 (T008-T010) sont menées en parallèle par deux agents ou séquentiellement — fichiers distincts (`page.tsx` vs `RaceFinishers.tsx`), aucune dépendance croisée.
- T005/T006 parallélisables entre eux ; T008/T009 parallélisables entre eux.

---

## Parallel Example: Foundational + démarrage des user stories

```bash
# Après T001 (test rouge) :
Task: "Ajouter dnf/dns/dsq à CourseSummary (backend/app/schemas/course.py)"
Task: "Ajouter dnf/dns/dsq au type CourseSummary (frontend/lib/types.ts)"

# Une fois Foundational vert, en parallèle :
Task: "US1 — trois MetaPill dans frontend/app/courses/[id]/page.tsx"
Task: "US2 — trois segments dans frontend/components/results/RaceFinishers.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Compléter Phase 2 (Foundational) — bloquant.
2. Compléter Phase 3 (US1) — la page de l'épreuve raconte déjà les trois catégories.
3. **STOP and VALIDATE** : vérifier US1 indépendamment (quickstart.md §2-3, scope page uniquement).
4. US2 peut suivre dans une itération séparée sans casser US1 — c'est un second site de rendu du même agrégat, pas une dépendance.

### Incremental Delivery

1. Foundational → API prête.
2. US1 → page de l'épreuve corrigée → validable seule (MVP).
3. US2 → résumé de liste cohérent avec US1 → validable seule.

## Notes

- [P] tasks = fichiers différents, aucune dépendance.
- Écrire chaque test et le voir échouer avant d'implémenter (Principe III).
- Committer après chaque phase (Foundational, US1, US2, Polish) plutôt qu'après chaque tâche isolée — cohérent avec le grain des commits déjà utilisé sur ce dépôt pour les features Spec Kit.
