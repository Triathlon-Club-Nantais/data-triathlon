---

description: "Sélecteur de type de rang (scratch / catégorie / genre) — tasks.md"
---

# Tasks: Sélecteur de type de rang sur les cartes de stats

**Input**: Design documents from `specs/003-dashboard-rank-selector/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rank-url-param.md, quickstart.md — tous présents.

**Tests**: Principe III de la constitution v1.0.0 — TDD non-négociable. Chaque story porte ses tests avant implémentation. Aucune dérogation demandée.

**Organization**: 4 user stories (US1..US4) issues de la spec, ordonnées P1 → P3. Toutes couvertes par le même toggle → l'ordre naturel d'exécution est monolithique une fois la fondation posée (le toggle et le paramètre URL sont partagés par toutes les stories). US1 est le MVP livrable.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : peut tourner en parallèle (fichiers différents, pas de dépendance non complétée).
- **[Story]** : US1 / US2 / US3 / US4.
- Chaque tâche cite un chemin de fichier exact.

## Path Conventions

Toute la feature est frontend. Chemins relatifs à `frontend/`. Pas de dossier `tests/` séparé : chaque source a son voisin `*.test.ts(x)` selon la convention Vitest en place.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: minimum de préparation. La feature est purement front, pas de nouveau outillage. Rien à installer, rien à configurer.

- [ ] T001 Vérifier que la branche `feat/104-dashboard-rank-selector` est bien active et que `main` est à jour : `git -C . status -sb` puis `git -C . rev-list --count main..HEAD` (attend 0 avant tout travail — la branche part de main sans commit intermédiaire).

**Checkpoint**: environnement prêt, une seule tâche parce que le projet n'exige rien de plus pour une modif front.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: le parser `RankType` et l'enrichissement des fonctions utilitaires de `club-aggregate.ts` sont utilisés par **toutes** les user stories. Ils sont donc factorisés dans cette phase — impossible de démarrer US1 sans eux.

**⚠️ CRITICAL**: Aucun travail de story ne peut commencer avant la fin de cette phase.

### Tests foundationaux (rouge d'abord)

- [ ] T002 [P] Créer `frontend/lib/rank.test.ts` avec les 7 cas du tableau `contracts/rank-url-param.md` §« Défaut et valeurs invalides » : 4 valeurs canoniques → identité ; `undefined`, `""`, `"foo"` → `"scratch"`. Le fichier ne compile pas encore (`rank.ts` n'existe pas). C'est attendu.
- [ ] T003 [P] Étendre `frontend/lib/utils/club-aggregate.test.ts` — nouveaux cas sur `bestRank(p, rankType)` : mode `"scratch"` retourne uniquement `rank_overall` ; mode `"category"` uniquement `rank_category` ; mode `"gender"` uniquement `rank_gender` ; mode `"all"` (défaut sans param) préserve exactement l'ordre actuel (min-des-trois, départage `overall > gender > category`). Ces tests doivent échouer avant T007.

### Implémentation foundationale

- [ ] T004 [P] Créer `frontend/lib/rank.ts` sur le patron de `frontend/lib/scope.ts` : exporte `RankType`, `RANK_PARAM = "rank"`, `RANK_DEFAULT = "scratch"`, et `rankTypeFromParam(v: string | undefined): RankType` (whitelist stricte des 4 valeurs canoniques, tout autre → défaut). Le test T002 passe au vert.
- [ ] T005 [P] Étendre `frontend/lib/utils/club-aggregate.ts` — signature de `bestRank(p: Participation, rankType?: RankType): BestRank | null`. Implémenter le `switch` sur `rankType` (`"scratch"` → `[overall]`, `"category"` → `[category]`, `"gender"` → `[gender]`, `"all"` ou `undefined` → `[overall, gender, category]` comme aujourd'hui). Préserver le tri de départage existant.
- [ ] T006 Ajouter au même fichier les types `RankCountersScalar` / `RankCountersGender` / `RankCountersResult` (union discriminée `kind: "scalar" | "gender"`) — cf. `data-model.md`. Aucune fonction ne les consomme encore, c'est intentionnel : ils sont posés en foundation pour ne pas dupliquer entre stories.
- [ ] T007 Faire tourner `npm test -- lib/rank club-aggregate` — les 2 fichiers de test doivent être verts. Si `club-aggregate.test.ts` échoue, corriger T005, pas les tests.

**Checkpoint**: `rank.ts` en place, `bestRank` accepte le paramètre, types discriminés définis. Les stories peuvent démarrer.

---

## Phase 3: User Story 1 — Comparer les stats du club au bilan présenté en AG (Priority: P1) 🎯 MVP

**Goal**: sur `/dashboard`, un toggle affiche « Scratch » actif par défaut ; les cartes Victoires / Podiums / Top 10 reflètent le décompte scratch (sur `rank_overall` seul). L'URL passe à `?rank=scratch` (ou reste implicite).

**Independent Test**: `curl -s /dashboard` ou ouverture navigateur → toggle visible, « Scratch » actif, libellé « scratch » sous les cartes ; `?rank=category` change le mode ; `?rank=foo` retombe silencieusement sur scratch.

### Tests pour User Story 1

> **Écrire ces tests d'abord, ils doivent échouer avant l'implémentation** (Principe III).

- [ ] T008 [P] [US1] Étendre `frontend/lib/utils/club-aggregate.test.ts` — `rankCounters(parts, "scratch")` retourne `{kind: "scalar", …}` avec les comptes sur `rank_overall` seul. Idem `rankCounters(parts, "category")`. Idem `rankCounters(parts)` (défaut = comportement `"all"` actuel, `kind: "scalar"`).
- [ ] T009 [P] [US1] Créer `frontend/components/layout/RankTypeToggle.test.tsx` — rendu 4 boutons (Scratch / Catégorie / Genre / Tous) ; bouton actif = valeur URL courante (mock `useSearchParams` avec `?rank=category`) ; sans `?rank=` → « Scratch » actif ; clic sur un bouton appelle `router.push` avec le bon `?rank=`.
- [ ] T010 [US1] Créer `frontend/app/dashboard/page.test.tsx` — rendu SSR de `/dashboard` : sans `?rank=`, libellé secondaire « scratch » sur les 3 cartes, chiffres cohérents avec le fixture. Avec `?rank=category`, libellé « catégorie », chiffres différents. Avec `?rank=foo`, comportement identique au défaut.

### Implémentation pour User Story 1

- [ ] T011 [US1] Étendre `rankCounters` dans `frontend/lib/utils/club-aggregate.ts` — signature `(parts, rankType?)`, retourne toujours `RankCountersScalar` en modes `"scratch"` / `"category"` / `"all"` (le mode `"gender"` viendra en US3). Les modes scalaires s'appuient sur `bestRank(p, rankType)`. Le test T008 passe.
- [ ] T012 [P] [US1] Créer `frontend/components/layout/RankTypeToggle.tsx` — client component (`"use client"`), sur le patron exact de `DisciplineToggle.tsx` (mêmes hooks `useRouter/usePathname/useSearchParams/useTransition`). Rendu 4 boutons ; état actif dérivé de `rankTypeFromParam(sp.get(RANK_PARAM))`. Clic → `router.push(pathname?rank=…)` en `startTransition`. Le test T009 passe.
- [ ] T013 [US1] Modifier `frontend/app/dashboard/page.tsx` — lire `rankTypeFromParam(sp.rank)`, passer à `rankCounters(participations, rankType)`, brancher le libellé secondaire sur le mode courant (`SCRATCH_LABEL`, `CATEGORY_LABEL`, `GENDER_LABEL`, `ALL_LABEL` — 4 constantes locales), monter `<RankTypeToggle />` dans le header à côté du `<DisciplineToggle />` et du `<SeasonSelector />`. Ne rien changer aux autres cartes / graphiques. Le test T010 passe.
- [ ] T014 [US1] `npm test -- dashboard club-aggregate RankTypeToggle rank` → tout vert. Puis `npm run lint`, puis `npm run build`. Zéro warning.

**Checkpoint**: US1 fonctionne bout en bout sur `/dashboard`. C'est le MVP livrable. La page `/club` n'est pas encore touchée (elle continue de rendre l'ancienne agrégation `all`). US2/US3/US4 étendront ce socle.

---

## Phase 4: User Story 2 — Regarder les stats par catégorie d'âge (Priority: P2)

**Goal**: `?rank=category` est déjà rendu sur `/dashboard` (fait en US1 via `rankCounters`), il reste à étendre `/club` pour qu'il propage aussi le paramètre à `listPodiums`, `isPodium` et `isTopN` — sinon la liste des podiums récents de `/club` reste sur le comportement `all`. Cette story livre `/club` sur les modes scalaires (`scratch`, `category`, `all`).

**Independent Test**: `/club?rank=category` → la liste « Podiums & performances » ne montre que les podiums catégorie (badge « Catégorie » partout). Les KPI en tête de page (Résultats / Athlètes / Épreuves / Podiums) restent inchangés (hors périmètre).

### Tests pour User Story 2

- [ ] T015 [P] [US2] Étendre `frontend/lib/utils/club-aggregate.test.ts` — `isPodium(p, "scratch")` regarde seulement `rank_overall` ; `isPodium(p, "category")` seulement `rank_category` ; `isTopN(p, 10, "scratch")` idem. Cas edge : `isPodium` sans `rank_overall` en mode scratch → `false`.
- [ ] T016 [P] [US2] Étendre `frontend/lib/utils/club-aggregate.test.ts` — `listPodiums(parts, "scratch")` ne renvoie que les entrées où `rank_overall ≤ 3` (badge `scope: "overall"` sur toutes). Idem `"category"` et `"all"` (comportement mélangé actuel préservé). Ordre de tri inchangé.
- [ ] T017 [P] [US2] Créer `frontend/components/club/ClubDashboard.test.tsx` — `<ClubDashboard>` rend la liste des podiums selon `rankType` reçu en prop ; en `"category"`, aucun badge « Général » n'apparaît dans la liste ; en `"scratch"`, aucun badge « Catégorie ».

### Implémentation pour User Story 2

- [ ] T018 [US2] Étendre `isPodium`, `isTopN` dans `frontend/lib/utils/club-aggregate.ts` — signature `(p, rankType?)` (et `(p, n, rankType?)`), délégation à `bestRank(p, rankType)`. Défaut à `"all"` pour rétro-compat locale (`buildRoster`, `clubSummary` restent inchangés). Test T015 passe.
- [ ] T019 [US2] Étendre `listPodiums` dans le même fichier — signature `(parts, rankType?)`. Délégation à un `bestPodiumRank(p, rankType)` local (renommer/ajouter le paramètre). Test T016 passe.
- [ ] T020 [US2] Modifier `frontend/components/club/ClubDashboard.tsx` — accepter une prop `rankType: RankType`, passer à `listPodiums(participations, rankType)`. Ne pas toucher `buildRoster`, `clubSummary`, `recentParticipations` (défaut `"all"` préservé). Test T017 passe.
- [ ] T021 [US2] Modifier `frontend/app/club/page.tsx` — lire `rankTypeFromParam(sp.rank)`, passer en prop à `<ClubDashboard rankType={…} />`, monter `<RankTypeToggle />` dans le `PageHeader.actions` à côté du `<DisciplineToggle />`.
- [ ] T022 [US2] `npm test -- club-aggregate ClubDashboard` → vert. Vérifier manuellement `/club?rank=scratch` puis `/club?rank=category` selon `quickstart.md` §6–7.

**Checkpoint**: `/club` en modes scratch / catégorie / all fonctionne. Le mode gender reste en défaut scalaire pour l'instant (US3 le complète).

---

## Phase 5: User Story 3 — Regarder les stats par genre, ventilées Femmes / Hommes (Priority: P2)

**Goal**: `?rank=gender` sur `/dashboard` **et** `/club`. Sur `/dashboard`, chaque carte se dédouble en F et H (2 compteurs distincts par carte). Sur `/club`, la liste des podiums filtre sur `rank_gender ≤ 3` en gardant F et H mélangés (badge scope reste « Genre »).

**Independent Test**: `/dashboard?rank=gender` → chaque carte porte deux valeurs séparées ; un athlète homme rangé 1er `rank_gender` compte dans « Hommes », jamais dans « Femmes ». Un athlète sans `athlete.gender` renseigné n'est compté nulle part.

### Tests pour User Story 3

- [ ] T023 [P] [US3] Étendre `frontend/lib/utils/club-aggregate.test.ts` — `rankCounters(parts, "gender")` retourne `{kind: "gender", women: {…}, men: {…}}`. Fixture : 1 femme rang gender=1, 1 homme rang gender=1, 1 athlète sans genre rang gender=2. Attendu : `women.victories = 1`, `men.victories = 1`, aucun compte lié à l'athlète sans genre.
- [ ] T024 [P] [US3] Ajouter dans le même fichier — `isPodium(p, "gender")` **exclut** les participations où `athlete.gender` est vide/null, même si `rank_gender` est présent (garde-fou du DTO malformé, cf. `data-model.md`).
- [ ] T025 [P] [US3] Étendre `frontend/app/dashboard/page.test.tsx` — cas `?rank=gender` : le rendu contient 3 cartes, chacune avec deux valeurs numériques distinctes (F et H). Assertion : le compteur homme d'une carte ≠ 0 sur le fixture ; il ne se confond pas avec le compteur femme.
- [ ] T026 [P] [US3] Étendre `frontend/components/club/ClubDashboard.test.tsx` — `<ClubDashboard rankType="gender">` : la liste des podiums ne contient que des entrées où `rank_gender ≤ 3`, F et H mélangés (badge « Genre » sur toutes).

### Implémentation pour User Story 3

- [ ] T027 [US3] Étendre `rankCounters` — branche `"gender"` qui itère les participations en séparant `athlete.gender === "F"` de `"M"`, compte pour chaque via `rank_gender`, retourne `{kind: "gender", women, men}`. Test T023 passe.
- [ ] T028 [US3] Ajouter la garde `athlete.gender` non vide dans `isPodium(p, "gender")` / `isTopN(p, n, "gender")` (via `bestRank` ou directement). Test T024 passe.
- [ ] T029 [US3] Modifier `frontend/app/dashboard/page.tsx` — quand `rankType === "gender"`, `rankCounters` retourne `RankCountersGender` (discriminant `kind: "gender"`), rendre 3 cartes dédoublées : chaque carte affiche deux valeurs (F: X · H: Y ou équivalent avec un label lisible). Utiliser `switch (counters.kind)` pour l'exhaustivité TS. Test T025 passe.
- [ ] T030 [US3] Modifier `listPodiums` dans `club-aggregate.ts` — en mode `"gender"`, filtrer sur `rank_gender ≤ 3` (l'exclusion des athlètes sans genre est déjà déléguée à `bestPodiumRank`/`bestRank`). Test T026 passe.
- [ ] T031 [US3] `npm test -- dashboard club-aggregate ClubDashboard` → vert. Vérifier manuellement `/dashboard?rank=gender` et `/club?rank=gender` (quickstart §3, 6).

**Checkpoint**: le mode Genre est fonctionnel sur les deux pages avec dédoublement F/H sur `/dashboard` et filtrage sur `/club`.

---

## Phase 6: User Story 4 — Conserver la vue agrégée actuelle en option (Priority: P3)

**Goal**: `?rank=all` produit exactement les valeurs affichées avant la feature (min-des-trois, `kind: "scalar"`, libellé « scratch, genre ou catégorie »). Trappe de rétro-compat explicite.

**Independent Test**: comparer les chiffres de `?rank=all` avec ceux d'un snapshot pré-feature (ou avec la sortie du code de `main` avant le patch).

### Tests pour User Story 4

- [ ] T032 [P] [US4] Étendre `frontend/lib/utils/club-aggregate.test.ts` — `rankCounters(parts, "all")` retourne exactement les mêmes valeurs que `rankCounters(parts)` sans paramètre (comportement legacy). Fixture avec au moins un cas où `rank_overall > rank_category` pour s'assurer que le `min` est bien appliqué.
- [ ] T033 [P] [US4] Étendre `frontend/app/dashboard/page.test.tsx` — cas `?rank=all` : libellé « scratch, genre ou catégorie ».

### Implémentation pour User Story 4

- [ ] T034 [US4] Vérifier qu'aucune modification supplémentaire n'est nécessaire dans `rankCounters` — la branche `"all"` a été codée en T011. Les tests T032/T033 doivent passer immédiatement. Si un test échoue, ajuster la valeur du libellé « scratch, genre ou catégorie » constante dans `dashboard/page.tsx`.
- [ ] T035 [US4] `npm test` complet (toute la suite frontend) → vert. `npm run lint` propre. `npm run build` OK.

**Checkpoint**: la feature est complète. Les 4 modes fonctionnent sur les deux pages.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: relire, nettoyer, vérifier de bout en bout, préparer PR.

- [ ] T036 [P] Vérification visuelle des 7 URLs de `quickstart.md` en dev local (`backend` + `frontend` up). Noter les captures d'écran pour la description de PR (facultatif).
- [ ] T037 [P] Relire les diffs pour supprimer tout commentaire tautologique ajouté à `club-aggregate.ts` — Principe VI : par défaut pas de commentaires. Un commentaire justifié par un « pourquoi » non-évident (ex. l'exclusion `athlete.gender` en mode gender) est OK, tout le reste doit sauter.
- [ ] T038 Suite `npm test` finale complète (tous les fichiers modifiés confondus) — vert. `npm run lint` propre. `npm run build` OK. Vérifier `git status` : seuls les fichiers listés dans `plan.md` §Structure sont modifiés.
- [ ] T039 Rédiger un commit unique (ou une paire de commits logiques : `feat(front/lib): …` + `feat(front): …`) au format Conventional Commits, référencer `#104`. Push et ouvrir la PR selon `AGENTS.md` (titre en Conventional Commits, description en français, section « Test plan » avec les commandes de vérification).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : T001 seul, immédiat.
- **Foundational (Phase 2)** : T002–T007. Bloque tout le reste. La partie test (T002, T003) est parallélisable ; l'implémentation (T004, T005, T006) l'est aussi mais chaque `[P]` doit avoir son test rouge en amont.
- **US1 (Phase 3)** : dépend de Phase 2. C'est le MVP livrable.
- **US2 (Phase 4)** : dépend de Phase 2 (foundation) et **de la présence du `RankTypeToggle`** créé en T012. Techniquement US2 pourrait démarrer en parallèle de US1 dès que T007 est terminé, mais le composant `<RankTypeToggle />` reste porté par US1 — donc `/club` peut monter le toggle dès T012 disponible.
- **US3 (Phase 5)** : dépend de US1 (branche `rankCounters` existe, `RankTypeToggle` existe) et de US2 (`listPodiums` accepte `rankType`).
- **US4 (Phase 6)** : parallèle à US1 (le mode `"all"` est codé en T011). L'existence de T032/T033 sert de non-régression.
- **Polish (Phase 7)** : après US1..US4.

### User Story Dependencies

- **US1 (P1)** : socle applicatif du dashboard, aucune dépendance à une autre story.
- **US2 (P2)** : dépend indirectement de US1 pour le composant `RankTypeToggle`. Le passage de `rankType` à `listPodiums` est autonome sinon.
- **US3 (P2)** : dépend de US1 (structure de `dashboard/page.tsx`) et de US2 (`listPodiums` accepte le paramètre) pour être complète.
- **US4 (P3)** : de facto livrée avec US1 (une seule ligne à ne pas casser). Reste testée séparément pour éviter la régression silencieuse.

### Within Each User Story

- Tests d'abord (Principe III non-négociable).
- Fonctions utilitaires avant composants.
- Composants avant pages.
- Vérification visuelle en dernier.

### Parallel Opportunities

- T002, T003, T004, T005, T006 sont marqués `[P]` mais **T004 doit précéder T005** (T005 importe `RankType` de `rank.ts`). L'ordre à respecter est : T002 || T003 (tests) → T004 → T005 → T006 → T007.
- T008, T009, T010 (tests US1) parallèles.
- T015, T016, T017 (tests US2) parallèles.
- T023, T024, T025, T026 (tests US3) parallèles.
- T032, T033 (tests US4) parallèles.
- Deux développeurs peuvent se partager US2 et US3 après T012 (composant toggle disponible).

---

## Parallel Example: User Story 1

```bash
# Tests US1 (à écrire d'abord, tous parallélisables) :
Task: "T008 [US1] cas rankCounters(parts, 'scratch') dans frontend/lib/utils/club-aggregate.test.ts"
Task: "T009 [US1] tests de rendu RankTypeToggle dans frontend/components/layout/RankTypeToggle.test.tsx"
Task: "T010 [US1] tests de la page dashboard dans frontend/app/dashboard/page.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 uniquement)

1. Phase 1 (T001).
2. Phase 2 (T002–T007) — foundation partagée.
3. Phase 3 US1 (T008–T014).
4. **STOP** — validation manuelle sur `/dashboard` : les 4 modes doivent fonctionner sur le dashboard, mais `/club` reste sur `"all"`. C'est acceptable comme MVP.
5. Déploiement/démo possible ici.

### Incremental Delivery

1. MVP US1 → démo `/dashboard` fonctionne.
2. US2 → `/club` bascule sur le toggle en modes scalaires.
3. US3 → dédoublement F/H visible sur les deux pages.
4. US4 → non-régression du mode Tous.
5. Chaque story ajoute de la valeur sans casser les précédentes.

### Parallel Team Strategy

Non applicable : feature de petit périmètre (~10 fichiers touchés au total). Un seul développeur suit la séquence en linéaire. Le mode « parallèle » ici est purement mental, pour marquer les tâches sans dépendance stricte.

---

## Notes

- `[P]` = fichiers différents, pas de dépendance non complétée.
- `[Story]` mappe la tâche à une user story (traçabilité).
- Chaque user story est indépendamment testable une fois la phase précédente terminée.
- Vérifier que chaque test rouge échoue **avant** d'implémenter (Principe III).
- Commit après chaque tâche ou groupe logique (Conventional Commits).
- Arrêter à un checkpoint pour valider avant d'enchaîner.
- Éviter : tâches vagues, conflits de fichier, dépendances croisées entre stories qui cassent l'indépendance.
