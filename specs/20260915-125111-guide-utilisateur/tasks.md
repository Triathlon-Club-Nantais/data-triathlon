# Tasks: Guide utilisateur intégré

**Input**: Design documents from `specs/20260915-125111-guide-utilisateur/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Le Principe III de la constitution (`.specify/memory/constitution.md`, v1.2.0) est **non-négociable** — TDD sans réseau. Les tâches de test sont générées pour chaque user story ; aucune dérogation n'a été justifiée dans `plan.md`.

**Organization**: Tasks are grouped by user story (P1, P2, P3 de `spec.md`) pour permettre une implémentation et une validation indépendantes de chacune.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Peut s'exécuter en parallèle (fichiers différents, aucune dépendance non résolue)
- **[Story]**: User story concernée (US1, US2, US3)
- Chemins exacts inclus dans chaque description

## Path Conventions

Feature 100% `frontend/` (Next.js App Router). Aucun chemin `backend/` concerné —
voir plan.md §Constitution Check (Principe II : N/A).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Créer l'arborescence des dossiers de la feature. Aucune nouvelle
dépendance (toutes déjà présentes — plan.md §Technical Context).

- [X] T001 Créer les dossiers vides `frontend/app/(public_restricted)/guide/`, `frontend/app/admin/guide/`, `frontend/components/guide/`, `frontend/public/guide/membre/`, `frontend/public/guide/admin/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Le type de contenu et les deux composants de rendu partagés par
`/guide` et `/admin/guide` (US1, US2, US3 en dépendent tous).

**⚠️ CRITICAL**: Aucune user story ne démarre avant la fin de cette phase.

- [X] T002 [P] Définir le type `GuideSection` (`id`, `titre`, `etapes`, `casUsage`, `captures`) dans `frontend/components/guide/types.ts`, conforme à `data-model.md`
- [X] T003 [P] Test (échoue d'abord) : `GuideSection.tsx` rend le titre, les étapes, le cas d'usage et l'`alt` de chaque capture, dans `frontend/components/guide/GuideSection.test.tsx`
- [X] T004 Implémenter `GuideSection.tsx` pour faire passer T003, dans `frontend/components/guide/GuideSection.tsx` (dépend de T002, T003)
- [X] T005 [P] Test (échoue d'abord) : `GuideSommaire.tsx` rend un lien `href="#<id>"` par section reçue, dans l'ordre fourni, dans `frontend/components/guide/GuideSommaire.test.tsx`
- [X] T006 Implémenter `GuideSommaire.tsx` pour faire passer T005, dans `frontend/components/guide/GuideSommaire.tsx` (dépend de T002, T005)

**Checkpoint**: `GuideSection` et `GuideSommaire` sont prêts — les phases US1/US2/US3 peuvent commencer.

---

## Phase 3: User Story 1 - Un membre découvre les fonctionnalités du club (Priority: P1) 🎯 MVP

**Goal**: `/guide` affiche les 6 sections membres (dashboard, club, résultats,
comparaison, ajout de résultat, bénévolat), chacune avec étapes
concises + ≥1 capture, atteignable en un clic depuis la navigation. La
fonctionnalité « carte » est exclue tant qu'elle reste `soon` (spec.md
§Assumptions).

**Independent Test**: ouvrir `/guide` depuis la navigation principale, vérifier
que les 6 sections sont présentes avec capture d'écran ; cf. quickstart.md
Scénario 1.

### Tests for User Story 1

> **Écrire ces tests D'ABORD, vérifier qu'ils échouent avant l'implémentation** (Principe III, non-négociable).

- [X] T007 [P] [US1] Test : `guide-content.membre.ts` expose exactement les 6 ids attendus (`dashboard`, `club`, `resultats`, `comparaison`, `ajouter`, `benevolat`), chacun avec `etapes.length >= 1`, `casUsage` non vide et `captures.length >= 1`, dans `frontend/components/guide/guide-content.membre.test.ts`
- [X] T008 [P] [US1] Test : la page `/guide` rend le sommaire et les 6 sections, une section ciblée par son ancre (`#club`) est visible sans navigation préalable, dans `frontend/app/(public_restricted)/guide/page.test.tsx`
- [X] T009 [P] [US1] Test : `nav.config.ts` porte une entrée `guide` dans la section `consulter` avec `href: "/guide"`, dans `frontend/components/layout/nav.config.test.ts`

### Implementation for User Story 1

- [X] T010 [US1] Rédiger le contenu des 6 sections membres (étapes concises + cas d'usage réel par fonctionnalité) dans `frontend/components/guide/guide-content.membre.ts` pour faire passer T007 (dépend de T002)
- [X] T011 [P] [US1] Captures **réelles**, prises en dev local (mot de passe de site amorcé via `services/site_access.replace_password`) avec les 6 pages réelles peuplées de données démo : `frontend/public/guide/membre/*.jpg` (extension réelle du format capturé, `.png` de la description initiale corrigé)
- [X] T012 [US1] Implémenter `frontend/app/(public_restricted)/guide/page.tsx` (sommaire `GuideSommaire` + 6 `GuideSection`) pour faire passer T008 (dépend de T004, T006, T010)
- [X] T013 [US1] Ajouter l'entrée `{ id: "guide", label: "Guide", href: "/guide", icon: BookOpen }` à la section `consulter` de `frontend/components/layout/nav.config.ts` pour faire passer T009

**Checkpoint**: User Story 1 fonctionnelle et testable seule — MVP livrable.

---

## Phase 4: User Story 2 - Un administrateur découvre les outils de back-office (Priority: P2)

**Goal**: `/admin/guide` affiche les 15 sections admin (épreuves,
fournisseurs, doublons, droits, quality, batches, groupes, utilisateurs,
journal, maintenance, retours-utilisateurs, variantes-club,
portée-compteurs, validation du bénévolat, accès au back-office),
atteignable en un clic depuis l'espace admin, invisible sans session admin.
La liste couvre l'inventaire réel des écrans `/admin` non-`soon` (spec.md
§Assumptions), pas seulement les 12 fonctionnalités de l'issue #865
d'origine.

**Independent Test**: se connecter en admin, ouvrir `/admin/guide` depuis
l'espace admin, vérifier les 15 sections ; sans session, l'URL directe est
gardée par `app/admin/layout.tsx`. Cf. quickstart.md Scénario 2.

### Tests for User Story 2

- [X] T014 [P] [US2] Test : `guide-content.admin.ts` expose exactement les 15 ids attendus (`epreuves`, `fournisseurs`, `doublons`, `droits`, `quality`, `batches`, `groupes`, `utilisateurs`, `journal`, `maintenance`, `retours-utilisateurs`, `variantes-club`, `portee-compteurs`, `benevolat-validation`, `acces-backoffice`), chacun avec `etapes.length >= 1`, `casUsage` non vide et `captures.length >= 1`, dans `frontend/components/guide/guide-content.admin.test.ts`
- [X] T015 [P] [US2] Test : la page `/admin/guide` rend le sommaire et les 15 sections, et vit bien sous `frontend/app/admin/` (donc couverte par la garde de session déjà testée dans `frontend/app/admin/layout.test.tsx`, FR-011/C2), dans `frontend/app/admin/guide/page.test.tsx`
- [X] T016 [P] [US2] **Révisé en implémentation** : plus une entrée `nav.config.ts` mais un lien fixe (voir T020) — le test correspondant vit dans `frontend/app/admin/layout.test.tsx` (« propose un lien vers le guide »). `nav.config.test.ts` gagne à la place une assertion négative : aucune entrée `a-guide` n'existe dans `NAV`.

### Implementation for User Story 2

- [X] T017 [US2] Rédiger le contenu des 15 sections admin (étapes concises + cas d'usage réel par fonctionnalité) dans `frontend/components/guide/guide-content.admin.ts` pour faire passer T014 (dépend de T002)
- [X] T018 [P] [US2] **Placeholders**, pas des captures réelles : une session admin exige le SSO GitHub, non configurable dans cet environnement d'implémentation (pas de `AUTH_GITHUB_CLIENT_ID`/`_SECRET`, et l'accès à la prod a été refusé par le classificateur de permission — PII). `frontend/public/guide/admin/*.jpg` porte 15 images « Capture à venir » clairement identifiées. **Suivi** : issue de suivi à créer pour qu'un admin capture les 15 vraies captures avant mise en prod (cf. rapport de complétion).
- [X] T019 [US2] Implémenter `frontend/app/admin/guide/page.tsx` (sommaire + 15 sections) pour faire passer T015 (dépend de T004, T006, T017)
- [X] T020 [US2] **Révisé en implémentation** : `a-guide` casse deux invariants d'`estVisible()` (état vide d'`AdminIndex`, repli #482/NAV-2 « section à une seule destination ») — ajouté à la place comme lien fixe dans `frontend/app/admin/layout.tsx`, hors de `nav.config.ts`, gardé par la garde de session déjà en place. Test dans `frontend/app/admin/layout.test.tsx`. Voir research.md pour le détail des deux invariants cassés et le raisonnement complet.

**Checkpoint**: User Stories 1 ET 2 fonctionnelles indépendamment.

---

## Phase 5: User Story 3 - N'importe quel utilisateur retrouve rapidement une section précise (Priority: P3)

**Goal**: un lien direct vers `/guide#<id>` ou `/admin/guide#<id>` affiche la
section demandée sans dépendre d'un parcours préalable, y compris sous la
navigation fixe qui pourrait la masquer.

**Independent Test**: ouvrir un lien direct vers une section (ex.
`/guide#benevolat`), vérifier qu'elle est visible entièrement, non masquée
sous la nav fixe.

### Tests for User Story 3

- [X] T021 [P] [US3] Test : chaque `GuideSection` rendue porte un `id` HTML égal à son `id` de contenu, dans `frontend/components/guide/GuideSection.test.tsx`
- [X] T022 [P] [US3] Test : le `scroll-margin-top` de `.tcn-guide-section` (ou équivalent) est appliqué, dans `frontend/components/guide/GuideSection.test.tsx`

### Implementation for User Story 3

- [X] T023 [US3] Ajouter un `scroll-margin-top` sur le conteneur de chaque section rendue par `GuideSection.tsx`, pour que l'ancre ne se retrouve pas masquée sous la nav fixe (dépend de T004)

**Checkpoint**: les trois user stories sont indépendamment fonctionnelles.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Vérifications finales transverses aux trois stories.

- [X] T024 Exécuter `npm run build` (strict TS + RSC) depuis `frontend/`
- [X] T025 Exécuter `npm run lint` depuis `frontend/`
- [X] T026 Exécuter `npm test` depuis `frontend/` et confirmer la suite verte
- [X] T027 Scénario 1 dérouté intégralement au navigateur (mot de passe de site amorcé en dev, `/guide` : sommaire, 6 sections, ancre directe `#club`, captures réelles). Scénario 2 vérifié par les tests automatisés (`GuideAdminPage`, `admin/layout.test.tsx`) plutôt qu'au navigateur : aucune session admin disponible dans cet environnement (SSO GitHub non configurable ici, accès prod refusé par le classificateur PII) — voir T018 et le rapport de complétion pour le suivi.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: aucune dépendance — démarre immédiatement
- **Foundational (Phase 2)**: dépend de Setup — bloque les trois user stories
- **User Stories (Phase 3-5)**: dépendent toutes de Foundational ; US1 et US2 sont indépendantes entre elles (pages distinctes, contenu distinct) ; US3 dépend du rendu de `GuideSection` livré en Foundational et s'applique aux deux pages
- **Polish (Phase 6)**: dépend des user stories livrées

### User Story Dependencies

- **User Story 1 (P1)**: démarre après Foundational — aucune dépendance sur US2/US3
- **User Story 2 (P2)**: démarre après Foundational — indépendante de US1 (page et contenu distincts)
- **User Story 3 (P3)**: démarre après Foundational — s'applique au rendu partagé, donc bénéficie d'US1 et/ou US2 déjà livrées pour être testée en conditions réelles, mais son implémentation (T023) ne modifie que `GuideSection.tsx`

### Within Each User Story

- Tests écrits et rouges avant l'implémentation (Principe III)
- Contenu (`guide-content.*.ts`) avant la page qui le consomme
- Page avant l'entrée de navigation qui y mène

### Parallel Opportunities

- T002, T003, T005 (Foundational, marqués [P]) en parallèle
- T007, T008, T009 (tests US1) en parallèle ; T014, T015, T016 (tests US2) en parallèle
- T011 (captures membres) et T018 (captures admin) en parallèle des autres tâches de leur story
- US1 (Phase 3) et US2 (Phase 4) entièrement en parallèle une fois Foundational terminée

---

## Parallel Example: User Story 1

```bash
# Tests US1 en parallèle :
Task: "Test guide-content.membre.ts (7 ids, captures) dans frontend/components/guide/guide-content.membre.test.ts"
Task: "Test page /guide (sommaire + 7 sections) dans frontend/app/(public_restricted)/guide/page.test.tsx"
Task: "Test entrée nav guide dans frontend/components/layout/nav.config.test.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) puis Phase 2 (Foundational)
2. Phase 3 (US1) : guide membre complet
3. **STOP et VALIDER** : Scénario 1 de quickstart.md
4. Livrable en l'état : un guide membre fonctionnel, sans attendre le guide admin

### Incremental Delivery

1. Setup + Foundational → base prête
2. US1 → validation indépendante → guide membre livrable (MVP)
3. US2 → validation indépendante → guide admin livrable
4. US3 → validation indépendante → confort de navigation par ancre sur les deux guides
5. Polish → build/lint/tests/quickstart

---

## Notes

- [P] = fichiers différents, aucune dépendance non résolue
- Chaque user story reste indépendamment livrable et testable
- Vérifier que chaque test échoue avant d'écrire l'implémentation correspondante
- Un commit par tâche ou groupe cohérent de tâches
