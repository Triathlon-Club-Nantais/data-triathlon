---

description: "Task list — issue #481, les six grilles publiques en tableaux à lignes liées"
---

# Tasks: Des tableaux qui se lisent, des lignes qui se partagent

**Input**: Design documents from `specs/20260825-103900-tables-liees/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/structure-accessible.md](./contracts/structure-accessible.md), [quickstart.md](./quickstart.md)

**Tests** : le Principe III de la constitution v1.1.1 est **non-négociable** — TDD sans réseau. Chaque conversion est précédée d'un test rouge. Aucune dérogation n'est demandée ici, et le `plan.md` §Complexity Tracking est vide.

**Organization** : tâches groupées par user story. US1 traverse les six listes ; US2 et US3 ne portent que sur le classement d'épreuve.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable — fichier distinct, aucune dépendance sur une tâche inachevée
- **[Story]** : US1, US2, US3 (cf. `spec.md`)
- Chemins exacts dans chaque description, relatifs à la racine du dépôt

## Le classement d'épreuve est touché trois fois, et c'est voulu

`components/results/RaceFinishers.tsx` apparaît en US1 (conversion en tableau),
puis en US2 (la ligne devient un lien), puis en US3 (l'attente). Chaque passage
est un incrément **indépendamment testable**, et le découpage suit celui que
l'issue #481 prévoit elle-même (« le gain immédiat est en S et se livre
d'abord »). Fusionner les trois ferait perdre le test rouge intermédiaire.

---

## Phase 1: Setup

**Purpose** : partir d'une base connue, et mesurer l'avant.

- [X] T001 Installer les dépendances du worktree : `npm ci` depuis `frontend/` (un worktree n'hérite pas de `frontend/node_modules/`, cf. #337 et `README.md` §5)
- [X] T002 Établir la ligne de base verte : `npm test`, `npm run lint` et `npm run build` depuis `frontend/`, et noter le nombre de tests — il ne devra qu'augmenter
- [X] T003 [P] Mesurer l'avant de FR-003 : lancer les deux serveurs de dev puis `curl -s http://localhost:3000/courses/<ID> | grep -c 'href="/courses/<ID>/participations/'` en suivant `quickstart.md` §2, et consigner le résultat attendu **0** dans la description de la PR
- [ ] T004 [P] Capturer l'avant de FR-007 : une capture par liste des six écrans de `data-model.md` §1, à comparer en T035

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose** : le mécanisme de ligne activable, que les six listes consomment.

**⚠️ CRITICAL** : T005 bloque toute tâche d'implémentation d'US1 et d'US2.

- [X] T005 Étendre `.tcn-rowlink` dans `frontend/app/globals.css` : la classe passe de l'ancre à la **ligne** (`position: relative`), une classe sœur `.tcn-rowlink__cible` porte la cible dont le `::after` couvre la ligne en `position: absolute; inset: 0`, et l'anneau de focus se pose par `.tcn-rowlink:has(a:focus-visible), .tcn-rowlink:has(button:focus-visible)` — `:hover`, le fond transparent et `outline-offset: -2px` restent ceux d'aujourd'hui (`data-model.md` §3, `research.md` D2)
- [X] T006 Documenter dans `frontend/app/globals.css`, au-dessus du bloc, **pourquoi** la cible est dans une cellule et non sur la ligne : un rôle ARIA remplace le rôle implicite, donc un `<a role="row">` cesserait d'être annoncé comme un lien (`research.md` D2). C'est un « pourquoi » non-évident au sens du Principe VI.

**Note sur la preuve** : T005 est du CSS, il n'a pas de test propre. Sa
vérification arrive avec la première liste convertie (T008), dont le test
assertera que la ligne porte `.tcn-rowlink` et la cible `.tcn-rowlink__cible` —
même patron que `components/club/AthleteSortToggle.test.tsx:34`, qui verrouille
déjà un `:has()` de `globals.css`. Le bloc **se fige à la fin d'US1-a** (T009) :
les cinq listes suivantes le consomment sans le rouvrir.

---

## Phase 3: User Story 1 — Lire un tableau au lecteur d'écran (Priority: P1) 🎯 MVP

**Goal** : les six listes exposent une structure de tableau — chaque cellule
rattachée à l'en-tête de sa colonne, l'ensemble annoncé avec ses dimensions —
et les en-têtes triables du classement annoncent la direction du tri.

**Independent Test** : liste par liste, sans toucher à la navigation.
`getByRole("table")`, `getAllByRole("row")`,
`getByRole("columnheader", { name })` répondent ; l'apparence est inchangée.
Contrat détaillé : `contracts/structure-accessible.md` C1, C2, C5.

**Ordre** : le classement d'abord — il porte la géométrie la plus mouvante
(colonnes d'inters variables) et ce qui s'y révèle vaut pour les cinq autres
(`plan.md` §Ordre d'exécution).

### US1-a — Classement d'une épreuve (le cas le plus dur)

- [X] T007 [US1] Écrire le test rouge de structure dans `frontend/components/results/RaceFinishers.test.tsx` : un `table`, 1 + n `row`, un `columnheader` par colonne dont « Rang », « Athlète », « Temps total » et les inters de l'épreuve rendue, et la cellule *i* d'une ligne porte la valeur de la colonne *i* ; **plus le cas vide** : `getAllByRole("row")` vaut 1 et l'`EmptyState` n'est pas un `row` (C1, C2)
- [X] T008 [US1] Convertir le classement en tableau dans `frontend/components/results/RaceFinishers.tsx` : `<table role="table">` / `<thead role="rowgroup">` / `<tbody role="rowgroup">` / `<tr role="row">` / `<th role="columnheader" scope="col">` / `<td role="cell">`, en **recopiant littéralement** `gridTemplateColumns: fcols`, `gap: "0 12px"`, `alignItems`, les paddings et le `minWidth: 1080` du conteneur défilable ; la ligne prend `.tcn-rowlink`, le `role="button"` et son `onKeyDown` déménagent **tels quels** dans la cellule « Athlète » (le remplacement par un lien est US2), le liseré `is_tcn` et le fond des non-finishers restent sur le `<tr>` ; les quatre branches d'`EmptyState` (page inexistante, recherche sans résultat, portée club vide, épreuve vide) se rendent **après** le `</table>`, dans le même `<div style={{minWidth:1080}}>`, le `<tbody>` restant vide (C1)
- [X] T009 [US1] Vérifier T007 au vert, puis **figer** le bloc `.tcn-rowlink` de T005 — les cinq listes suivantes le consomment sans le modifier
- [X] T010 [US1] Écrire le test rouge d'`aria-sort` dans `frontend/components/results/RaceFinishers.test.tsx` : `ascending` / `descending` sur la colonne triée, `none` sur les autres colonnes triables, attribut absent sur « Rang », « Athlète », « Catég. », « Sexe » et « Club » (C5)
- [X] T011 [US1] Poser `aria-sort` sur le `<th>` dans `frontend/components/results/RaceFinishers.tsx` — sur l'en-tête, jamais sur le bouton d'`EnteteTriable`, qui garde son `aria-label` annonçant l'action **à venir** (`research.md` D6)

### US1-b — Les trois listes simples

- [X] T012 [P] [US1] Écrire le test rouge de structure dans `frontend/app/(public_restricted)/ajouter/page.test.tsx` : un `table`, les `columnheader` « Date », « Épreuve », « Format », « Athlètes club », une ligne activable qui reste un `link` vers l'épreuve, **le cas vide** (`getAllByRole("row")` vaut 1, l'`EmptyState` n'est pas un `row`) et **l'assertion FR-011** : chaque `<tr>` ne contient qu'un élément focalisable, compté par ligne et non par entrée (C1, C2, C3)
- [X] T013 [P] [US1] Convertir « Derniers résultats enregistrés » en tableau dans `frontend/app/(public_restricted)/ajouter/page.tsx` : géométrie `RCOLS` et `minWidth: 480` recopiées, la ligne devient `<tr class="tcn-rowlink">` et le `<Link>` descend dans la cellule « Épreuve » en `.tcn-rowlink__cible` ; l'`EmptyState` se rend **après** le `</table>` et non plus à la place des lignes (C1)
- [X] T014 [P] [US1] Écrire le test rouge de structure dans `frontend/components/dashboard/RecentCourses.test.tsx` : un `table`, les `columnheader` « Date », « Épreuve », « Format », « Dossards », une ligne qui reste un `link`, **l'assertion FR-011** (un seul élément focalisable par `<tr>`) et le cas vide : **aucun** `table` — cette liste masque déjà son en-tête (C1, C2, C3)
- [X] T015 [P] [US1] Convertir « Dernières épreuves » en tableau dans `frontend/components/dashboard/RecentCourses.tsx` : géométrie `GRID_COLUMNS` recopiée, le `<Link>` descend dans la cellule « Épreuve », **`prefetch={false}` conservé** (#425) et le trait de séparation conditionnel de la dernière ligne préservé
- [X] T016 [P] [US1] Écrire le test rouge de structure dans `frontend/app/(public_restricted)/courses/[id]/page.test.tsx` : un `table` pour « Top clubs », les `columnheader` « Club » et « Athlètes », l'assertion **négative** `within(ligne).queryByRole("link")` à `null` — ces lignes sont inertes, donc **zéro** élément focalisable (FR-011) — et **le cas vide** : `getAllByRole("row")` vaut 1, l'`EmptyState` n'est pas un `row` (C1, C2, C3)
- [X] T017 [P] [US1] Convertir « Top clubs » en tableau dans `frontend/app/(public_restricted)/courses/[id]/page.tsx` : géométrie `"1fr auto"` recopiée, **ni `.tcn-rowlink` ni cible** sur les lignes, le `textAlign: right` de la colonne « Athlètes » et la mise en avant du TCN conservés ; l'`EmptyState` (`className="px-0 py-4"`) se rend **après** le `</table>` (C1)

### US1-c — Les deux listes à structure composée

- [X] T018 [US1] Écrire le test rouge de structure dans `frontend/app/(public_restricted)/athletes/[id]/EventsTable.test.tsx` : un `table`, les sept `columnheader` (dont un sans libellé), un `rowgroup` **par entrée**, une entrée à sous-ligne qui rend deux `row` dans le même `rowgroup`, **l'assertion FR-011 comptée par `<tr>` et non par entrée** — une entrée à sous-ligne porte légitimement plus d'un élément focalisable, répartis sur ses deux lignes (C3) — et le cas vide : **aucun** `table`, cette liste masque déjà son en-tête (C1, C2)
- [X] T019 [US1] Convertir les épreuves d'un athlète en tableau dans `frontend/app/(public_restricted)/athletes/[id]/EventsTable.tsx` : **un `<tbody>` par entrée** qui reprend le `borderBottom` du `<div>` enveloppant supprimé (`research.md` D4), la sous-ligne de preuve et d'administration devient un `<tr>` à cellule unique en `colSpan`, et l'absence de trait pour une ligne en attente sans sous-ligne (#270) est préservée ; géométrie `COLS`/`GAP`/`PADDING_X`/`MIN_WIDTH` recopiée
- [X] T020 [US1] Vérifier que les filtres saison et discipline d'`EventsTable` (#489) et le marqueur d'épreuve non fiable restent intacts — `npx vitest run --project jsdom "app/(public_restricted)/athletes/[id]/EventsTable.test.tsx"`
- [X] T021 [US1] Écrire le test rouge de structure dans `frontend/components/results/EventList.test.tsx` : un `table`, les sept `columnheader` (dont la colonne « → » sans libellé), une ligne de groupe rendue comme `button` avec `expanded: false`, ses épreuves qui apparaissent comme `row` supplémentaires du **même** `rowgroup` une fois dépliée, **l'assertion FR-011** (un seul élément focalisable par `<tr>`, la ligne de groupe comprise) et le cas vide : `table` rendu, `getAllByRole("row")` vaut 1 (C1, C2, C3)
- [X] T022 [US1] Convertir la liste des épreuves en tableau dans `frontend/components/results/EventList.tsx` : `ROW_STYLE` recopié sur le `<tr>`, `EventRow` place son `<Link>` dans la cellule « Épreuve », `CompetitionRows` garde son `<button aria-expanded>` — **elle déplie, elle ne navigue pas** (`research.md` D5) — placé dans la cellule de nom, et le couple groupe + épreuves révélées forme un `<tbody>` ; une liste vide rend un `<tbody>` vide sous l'en-tête — c'est l'état actuel, ne rien y ajouter (l'état vide de `/resultats` relève d'`ETAT-3`, hors périmètre)
- [X] T023 [US1] Vérifier que le chargement à la volée (sentinelle `IntersectionObserver`) et l'assertion de pistes de `frontend/components/results/EventList.test.tsx:183` survivent à la conversion — adapter la seconde à la nouvelle position du `gridTemplateColumns` sans en affaiblir l'intention

**Checkpoint US1** : `npm test` vert, les six listes rendent un `table`, et
l'apparence est inchangée écran par écran (`quickstart.md` §3.4).

---

## Phase 4: User Story 2 — Partager le résultat d'un athlète (Priority: P1)

**Goal** : la ligne du classement devient un lien véritable — nouvel onglet,
copie de l'adresse, aperçu au survol, et une adresse par ligne dans le rendu
serveur.

**Independent Test** : sur la seule liste 1, et sur la page rendue sans
exécution de script. Contrat : `contracts/structure-accessible.md` C3, C4.

**Dependency** : US1-a (T008) — la ligne doit être un `<tr>` avec sa cellule
« Athlète » avant que l'ancre puisse y descendre.

- [X] T024 [US2] Écrire le test rouge dans `frontend/components/results/RaceFinishers.test.tsx` : chaque ligne porte un `link` dont le `href` vaut l'adresse du détail de la participation, **et** l'assertion négative `queryByRole("button", { name: /voir le détail/i })` à `null` — c'est elle qui interdit le retour du défaut (C3)
- [X] T025 [US2] Écrire le test rouge d'arrêt clavier unique dans `frontend/components/results/RaceFinishers.test.tsx` : une ligne activable ne contient **qu'un** élément focalisable (FR-011) — un `href` par cellule passerait T024 et casserait celui-ci
- [X] T026 [US2] Remplacer le `role="button"` par un `<Link>` dans `frontend/components/results/RaceFinishers.tsx` : l'ancre prend `.tcn-rowlink__cible` dans la cellule « Athlète », garde l'`aria-label` « Voir le détail du résultat de … » comme nom accessible, et **`tabIndex`, `onClick`, `onKeyDown` et `role` disparaissent** — pas de repli, le Principe de non-compatibilité ascendante s'applique
- [X] T027 [US2] Retirer de `frontend/components/results/RaceFinishers.tsx` ce que T026 rend mort : le `router.push(detailHref(p))` des lignes et, si plus aucun appelant ne subsiste, l'import de `useRouter` — le `useTransition` de l'écran **reste** pour la recherche, le tri et la pagination
- [X] T028 [US2] Vérifier FR-003 par `quickstart.md` §2 : `curl -s http://localhost:3000/courses/<ID> | grep -c 'href="/courses/<ID>/participations/'` rend le nombre de lignes affichées (**20** par défaut), contre 0 mesuré en T003 — et **reporter le résultat dans la description de la PR** : cette commande est le seul garde de FR-003, aucun test automatisé ne la double (contrat C4)
- [X] T029 [US2] Vérifier à la main les quatre gestes natifs de `quickstart.md` §3.2 : survol, clic milieu, copier l'adresse, `Tab` + `Entrée` avec un seul `Tab` par ligne

**Checkpoint US2** : le geste social central du club fonctionne — un résultat se
partage.

---

## Phase 5: User Story 3 — Savoir que le clic a été pris en compte (Priority: P2)

**Goal** : la ligne activée porte un état d'attente visible et sans mouvement
jusqu'au rendu du détail.

**Independent Test** : en observant la ligne cliquée entre le clic et l'arrivée
de la page. Contrat : `contracts/structure-accessible.md` C6.

**Dependency** : US2 (T026) — il faut une ancre avant de pouvoir lire son état.

- [X] T030 [US3] Écrire le test rouge dans `frontend/components/results/RaceFinishers.test.tsx` : la ligne du classement porte `prefetch={false}` et rend le composant d'attente à l'intérieur de son lien — sans `prefetch={false}`, la phase d'attente serait sautée en production (`research.md` D3)
- [X] T031 [US3] Ajouter dans `frontend/components/results/RaceFinishers.tsx` un composant enfant du `<Link>` qui lit `useLinkStatus()` de `next/link` et rend un voile **toujours monté** couvrant la ligne, dont seule l'**opacité** change — pas de mouvement, donc rien à conditionner à `prefers-reduced-motion` ; le voile s'appuie sur le `position: relative` du `<tr>` posé en T005
- [X] T032 [US3] Poser `prefetch={false}` sur les lignes du classement dans `frontend/components/results/RaceFinishers.tsx`, avec le commentaire qui en donne les **deux** raisons : la doc de Next l'exige pour que l'attente existe, et 20 préchargements de routes dynamiques par page sont un coût réseau — même arbitrage que `components/dashboard/RecentCourses.tsx:74` (#425)
- [X] T033 [US3] Vérifier à la main les trois points de `quickstart.md` §3.3 : la ligne cliquée se voile et elle seule, ⌘/Ctrl+clic n'allume rien, et l'attente reste perceptible sous « réduire les animations »

**Checkpoint US3** : plus aucun clic muet sur le classement.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T034 Passer les six listes au lecteur d'écran selon `quickstart.md` §3.1 — c'est **la** vérification de SC-001, celle que jsdom ne peut pas rendre (`research.md` D7)
- [X] T035 Comparer écran par écran avec les captures de T004 (`quickstart.md` §3.4) : colonnes, largeurs, gouttières, traits, survol, anneau de focus, liseré orange, fond des non-finishers — et confirmer que le défilement horizontal est **exactement** celui d'avant, #461 devant partir de cette base
- [X] T036 [P] Consigner dans `frontend/AGENTS.md` les deux arbitrages qui se re-cassent : pourquoi les rôles ARIA doublent les balises de tableau (la géométrie impose de surcharger `display`), et pourquoi la cible d'une ligne vit dans une cellule et jamais sur la ligne (un rôle ARIA remplace le rôle implicite) — avec le renvoi à `research.md` D1 et D2
- [X] T037 Vérification finale : `npm test`, `npm run lint`, `npm run build` depuis `frontend/`, le compte de tests supérieur à celui de T002
- [ ] T038 Fin de branche selon `docs/WORKFLOW-IA.md` : `requesting-code-review`, puis le sous-agent **`ui-ux-review`** (la branche touche `frontend/`, et sa grille couvre WCAG AA — c'est le second regard sur T034), puis `verification-before-completion`, puis `finishing-a-development-branch`
- [ ] T039 Ouvrir la PR avec `Closes #481` — jeton machine anglais, description en français, section « Test plan » portant les commandes de T037 et les mesures de T003/T028

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational, T005 bloquante)
                        ↓
                  Phase 3 (US1)
                   ├─ US1-a (T007→T011)  ← en premier, elle fige T005
                   ├─ US1-b (T012→T017)  ← les trois listes en parallèle
                   └─ US1-c (T018→T023)
                        ↓
                  Phase 4 (US2) — dépend de T008
                        ↓
                  Phase 5 (US3) — dépend de T026
                        ↓
                  Phase 6 (Polish)
```

### User Story Dependencies

- **US1** ne dépend que de la Phase 2. C'est le MVP.
- **US2** dépend d'US1-a seulement (T008), pas des cinq autres listes.
- **US3** dépend d'US2 (T026) : `useLinkStatus` suppose un `<Link>`.

### Within Each User Story

Test rouge → conversion → test vert → vérification visuelle de l'écran.

### Parallel Opportunities

- **T003 et T004** (mesures de l'avant) : indépendantes.
- **T012 à T017** — les trois listes simples touchent **trois fichiers de rendu
  et trois fichiers de test distincts**, sans dépendance entre elles. Trois
  paires test/impl menables de front une fois T009 passée.
- **T036** est indépendante de T034/T035 et peut s'écrire en parallèle.
- **Ce qui n'est PAS parallélisable** : T007→T011, T024→T027 et T030→T032
  touchent tous `RaceFinishers.tsx` et son test. Séquentiel, sans exception.
  De même T018→T020 (`EventsTable`) et T021→T023 (`EventList`).

## Parallel Example: US1-b

```
# Une fois T009 passée, trois chantiers indépendants :
T012 + T013   →  app/(public_restricted)/ajouter/page.tsx        (+ .test.tsx)
T014 + T015   →  components/dashboard/RecentCourses.tsx          (+ .test.tsx)
T016 + T017   →  app/(public_restricted)/courses/[id]/page.tsx   (+ .test.tsx)
```

## Implementation Strategy

### MVP First (US1 seule)

Les six listes deviennent lisibles au lecteur d'écran. C'est le défaut
d'origine, il est transversal, et il se livre sans toucher à la navigation.
Livrable et fusionnable tel quel.

### Incremental Delivery

1. **US1** → WCAG 1.3.1 sur six écrans publics. ✅ livrable
2. **US2** → WCAG 4.1.2 et le partage d'un résultat. ✅ livrable
3. **US3** → le confort du clic. ✅ livrable

Le mainteneur a demandé le **L complet** : les trois vont sur la même branche.
Le découpage reste utile comme ordre de travail et comme filet — si US3
dérape, US1 et US2 sont déjà bonnes.

### Notes

- **Aucun fichier backend n'est touché.** Pas de migration, pas de test
  `pytest`, pas de contrat `/api/v1`.
- **Aucun composant partagé créé** : le mécanisme mutualisé est une classe CSS
  qui existe déjà, et le seul composant neuf (T031) est **local à
  `RaceFinishers.tsx` et non exporté**. La frontière `tcn/` vs `ui/` n'a pas à
  être arbitrée, et #325 reste fermée (Principe VI).
- **Pas de compatibilité ascendante** : T027 supprime le chemin mort au lieu de
  le garder en repli.
- **`vitest.config.ts` n'est pas touché** : les six fichiers de test sont des
  `*.test.tsx`, donc déjà pris par le projet `jsdom` (#508).
