---

description: "Task list — refonte du formulaire de saisie manuelle des résultats (#270)"
---

# Tasks: Refonte du formulaire de saisie manuelle des résultats

**Input**: Design documents from `/specs/20260814-130052-saisie-manuelle-resultats/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/participations-api.md](./contracts/participations-api.md)

**Tests**: Le Principe III de la constitution v1.1.1 est **non-négociable** — TDD sans réseau. Chaque user story ouvre par ses tâches de test, écrites **avant** l'implémentation et vérifiées rouges. Aucune dérogation demandée pour cette feature.

**Organization**: Tâches groupées par user story pour permettre implémentation et vérification indépendantes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallélisable (fichiers différents, aucune dépendance en cours)
- **[Story]**: la user story couverte (US1 → US4)
- Chemins de fichiers exacts dans chaque description

## Path Conventions

Application web à deux applications : `backend/app/`, `backend/tests/`,
`frontend/`. Les tests frontend sont **co-localisés** (`Composant.test.tsx` à côté
de `Composant.tsx`), convention en place dans tout le dépôt.

---

## Phase 1: Setup

**Purpose**: Établir la ligne de base. Aucun échafaudage n'est nécessaire — la
feature modifie une application existante et ne crée qu'un module backend.

- [X] T001 Installer les dépendances des deux applications : `uv sync` depuis `backend/`, `npm install` depuis `frontend/`
- [X] T002 Établir la ligne de base verte **avant** toute modification : `uv run pytest -m "not integration"` depuis `backend/` et `npm test` depuis `frontend/`, et noter les compteurs de tests — **3309 tests backend, 656 tests frontend (83 fichiers), tous verts**

**Checkpoint**: suite verte connue — tout rouge ultérieur est imputable à la feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Le socle de données et l'invariant d'exclusion. C'est le lot 1 du
plan.

**⚠️ CRITIQUE**: aucune user story ne démarre avant la fin de cette phase. Elle
porte l'invariant de FR-021 : livrer le formulaire avant l'exclusion ferait entrer
des résultats déclarés dans les podiums pendant toute la durée du chantier.

### Tests (écrire d'abord, vérifier rouges)

- [X] T003 [P] Test de migration aller-retour (`upgrade head` / `downgrade` / `upgrade head`) et de présence des 4 colonnes dans `backend/tests/test_migrations.py` — plus un test dédié « aucun backfill » (server_default), qui a révélé et fait corriger un défaut réel : `server_default="false"` (chaîne) se relit `True` via l'ORM sur SQLite ; corrigé en `sa.false()`, cf. note de fin de phase
- [X] T004 [P] Test du prédicat et de la clause (`is_pending`, `validated_clause`) dans `backend/tests/test_core/test_validation.py` — nouveau fichier, sur le patron de `backend/tests/test_core/test_discipline.py`
- [X] T005 [P] Test de **répartition** : les 11 fonctions de `participation_repository` se rangent dans le bon groupe (5 filtrantes, 6 non filtrantes) dans `backend/tests/test_repositories/test_pending_exclusion.py` — nouveau fichier. **Déviation assumée** : comportemental (une pendante + une validée, assertion par fonction publique) plutôt qu'AST — `_apply_filters` est un helper partagé par 3 fonctions publiques, qu'un lecteur d'appels statique attribuerait mal
- [X] T006 [P] Test d'exclusion **effective** sur les 5 sites (une participation pendante n'apparaît ni dans la liste, ni dans les épreuves, ni dans les stats, ni dans le classement, ni dans la synthèse) dans `backend/tests/test_repositories/test_pending_exclusion.py`
- [X] T007 [P] Test de non-exclusion : `list_for_athlete` rend bien la participation pendante, dans `backend/tests/test_repositories/test_participation_repository.py`
- [X] T008 [P] Test de contrat d'entrée : `POST /participations` force `is_pending_validation=true` et **ignore** toute valeur envoyée par le client, dans `backend/tests/test_api/test_participations_api.py`
- [X] T009 [P] Test de contrat de sortie : `ParticipationOut` porte `is_pending_validation`, `team_name`, `evidence_url`, dans `backend/tests/test_api/test_participations_api.py`
- [X] T010 [P] Test de non-régression d'import : un résultat importé porte `is_pending_validation=false` (FR-017), dans `backend/tests/test_services/test_mapping.py`

### Implémentation

- [X] T011 [P] Ajouter `is_pending_validation`, `team_name`, `evidence_url` à `backend/app/models/participation.py` (forme exacte : data-model.md §1)
- [X] T012 [P] Ajouter `format_label` à `backend/app/models/course.py` — **hors** de `uq_course_identity` (data-model.md §2)
- [X] T013 Générer la migration (`uv run alembic revision --autogenerate -m "manual result validation"`) puis **relire à la main** la révision dans `backend/alembic/versions/` : `server_default` corrigé en `sa.false()` (cf. T003), aucun backfill (dépend de T011, T012)
- [X] T014 [P] Créer `backend/app/core/validation.py` avec `is_pending()` et `validated_clause()` — sans état, sans accès base, sur le patron littéral de `backend/app/core/discipline.py`
- [X] T015 [P] Porter les nouveaux champs sur `ScrapedResult` dans `backend/app/scrapers/base.py`, défaut non pendant
- [X] T016 Propager les champs dans `mapping.participation_fields` dans `backend/app/services/mapping.py` (dépend de T015) — et `get_or_create_course`/`course_repository.get_or_create` pour `format_label`, non prévu dans le libellé initial mais nécessaire à FR-008
- [X] T017 Étendre `ParticipationCreate` (+`status`, `team_name`, `evidence_url`, `format_label`) et `ParticipationOut` (+3 champs) dans `backend/app/schemas/participation.py` — **sans** exposer `is_pending_validation` en entrée (contracts §1). `CourseBrief` gagne aussi `format_label`
- [X] T018 Forcer `is_pending_validation=True` dans `create_participation` et relayer les nouveaux champs par `_to_scraped` dans `backend/app/api/v1/participations.py` (dépend de T017)
- [X] T019 Appliquer `validated_clause` dans `_apply_filters` de `backend/app/repositories/participation_repository.py` — couvre `list_participations` **et** `_grouped_events_query`
- [X] T020 Appliquer `validated_clause` dans `for_stats` de `backend/app/repositories/participation_repository.py` — couvre tableau de bord, page club et podiums
- [X] T021 Appliquer `validated_clause` dans `list_page_for_course` de `backend/app/repositories/participation_repository.py`
- [X] T022 Appliquer `validated_clause` dans `summary_rows_for_course` de `backend/app/repositories/participation_repository.py`
- [X] T023 Appliquer `validated_clause` dans `finishers_count_by_group` de `backend/app/repositories/participation_repository.py`
- [X] T024 [P] Ajouter `is_pending_validation`, `team_name`, `evidence_url` (Participation) et `format_label` (CourseBrief) au type frontend de `frontend/lib/types.ts`
- [X] T070 [P] [US2] Test symétrique (FR-022) exécuté avec T005/T006 dans `test_pending_exclusion.py`, par avance sur son placement de phase — cf. note en tête de fichier

**Checkpoint**: T003 à T010 verts. Une participation pendante peut exister en base
sans polluer aucun agrégat. Les user stories peuvent démarrer.

**Note de phase — régression découverte et corrigée** : faire tourner la suite
complète après ces changements a fait échouer 12 tests préexistants
(`test_federal_only.py`, `test_other_api.py`, 2 de `test_participations_api.py`)
qui utilisaient `POST /participations` comme raccourci de peuplement pour tester
le filtrage — désormais exclu des agrégats puisque pendant par défaut. Corrigé en
ajoutant `valider_toutes_les_participations(db_session)` (helper dans
`test_api/conftest.py`) aux points de seed de ces 12 tests, sans toucher au
comportement attendu de la feature. Un second défaut, réel et indépendant, a été
découvert et corrigé au passage : `server_default="false"` (chaîne) sur SQLite se
relit `True` via l'ORM (chaîne non vide) au lieu de `False` — corrigé en
`server_default=false()` pour `is_pending_validation`. **`Participation.is_relay`
porte le même défaut historique et n'a pas été touché** (hors périmètre de cette
feature) : à signaler comme ticket suiveur, cf. rapport de fin de phase.

---

## Phase 3: User Story 1 - Saisir un résultat sans se tromper (Priority: P1) 🎯 MVP

**Goal**: Le formulaire exige les quatre champs d'identité, refuse une saisie
incomplète champ par champ, et cesse de demander ce que l'athlète ne sait pas.

**Independent Test**: Ouvrir `/ajouter`, soumettre à vide → un message sous
chacun des quatre champs obligatoires, aucune requête émise ; vérifier l'absence
des champs Genre, Club et Catégorie ; remplir les quatre → `201`.

### Tests for User Story 1

- [X] T025 [P] [US1] Créer `frontend/components/scrape/ManualResultForm.test.tsx` : soumission à vide → message sous nom, prénom, date et nom de l'épreuve, et `onSubmit` non appelé
- [X] T026 [P] [US1] Test « un seul champ manquant » (prénom vide) → message ciblé, soumission bloquée, dans `frontend/components/scrape/ManualResultForm.test.tsx`
- [X] T027 [P] [US1] Test d'absence : aucun champ Genre, Club ni Catégorie rendu, et libellé « Nom de l'épreuve », dans `frontend/components/scrape/ManualResultForm.test.tsx`

### Implémentation

- [X] T028 [US1] Rendre obligatoires nom, prénom, date et nom d'épreuve dans le schéma zod de `frontend/components/scrape/ManualResultForm.tsx`, messages d'erreur en français désignant l'action (FR-005) — **discipline rendue obligatoire aussi**, cohérent avec le comportement pré-existant du formulaire (non retiré par la spec)
- [X] T029 [US1] Retirer les champs Genre, Club et Catégorie du rendu et du schéma de `frontend/components/scrape/ManualResultForm.tsx` — **sans** toucher au schéma Pydantic, que les scrapers renseignent toujours
- [X] T030 [US1] Renommer le libellé « Épreuve » en « Nom de l'épreuve » dans `frontend/components/scrape/ManualResultForm.tsx`
- [X] T031 [US1] Convention `.default("")` respectée ; **le générique explicite de `useForm` a dû être retiré** (même piège documenté aux lignes 39-40 de l'ancienne version) — `npm run build` TypeScript strict passe (hors artefact `.next/dev/types/validator.ts` préexistant, sans rapport avec cette feature, cf. note de fin de phase)

**Checkpoint**: US1 fonctionnelle et vérifiable seule.

**Déviations assumées par rapport au plan** :
- **`ui/select` non retenu** (research.md D8) : le formulaire garde des `<select>` natifs pour discipline/format/statut, comme le faisait déjà l'ancienne version pour `event_type`. Un `<select>` natif fonctionne trivialement avec `register()` de react-hook-form, alors que `ui/select` (Base UI, portail asynchrone) exige `Controller` sans gain fonctionnel ici. Simplification assumée (Principe VI).
- **`watch()` remplacé par `useWatch()`** : `watch()` de react-hook-form ne peut pas être mémoïsé par le React Compiler (avertissement ESLint `react-hooks/incompatible-library`) ; `useWatch` est son équivalent compatible, comportement identique.
- **Individuel/Collectif en radios natifs**, pas `SegmentedControl` (tcn/) : cohérent avec le choix de rester sur `ui/`, pas `tcn/`, pour ce fichier (frontend/AGENTS.md, dette assumée).

---

## Phase 4: User Story 2 - Distinguer un résultat déclaré d'un résultat chronométré (Priority: P2)

**Goal**: Le résultat déclaré est visible sur la fiche de son athlète, marqué
comme non vérifié, et ne compte nulle part ailleurs.

**Independent Test**: Saisir un résultat au nom d'un athlète connu, vérifier la
mention sur `/athletes/<id>`, puis vérifier que tableau de bord, page club,
classement d'épreuve, page résultats, page épreuves et carte n'ont pas bougé.

### Tests for User Story 2

- [X] T032 [P] [US2] Test : les stats du club sont identiques avec et sans une participation pendante, dans `backend/tests/test_services/test_stats_service.py` — au niveau service (`stats_service.get_stats`), en plus du niveau repository déjà verrouillé en Phase 2
- [X] T033 [P] [US2] Test : le classement paginé et la synthèse d'une épreuve ignorent une participation pendante, dans `backend/tests/test_api/test_courses_api.py` — au niveau contrat HTTP
- [X] T034 [P] [US2] Test : `GET /athletes/{id}` rend la participation pendante **et** un `course_finishers` qui ne la compte pas, dans `backend/tests/test_api/test_athletes_api.py`
- [X] T035 [P] [US2] Créer `frontend/components/tcn/PendingBadge.test.tsx` : rendu de la mention, libellé accessible
- [X] T036 [P] [US2] Test : la fiche athlète marque une participation pendante et ne marque pas les autres, dans `frontend/app/athletes/[id]/page.test.tsx`
- [X] T070 [P] [US2] Test **symétrique** de l'exclusion (FR-022) : une participation basculée à `is_pending_validation=False` entre dans les stats, le classement, la synthèse et les compteurs d'épreuve — dans `backend/tests/test_repositories/test_pending_exclusion.py`, à côté de T006 dont il est l'exact réciproque

### Implémentation

- [X] T037 [P] [US2] Créer `frontend/components/tcn/PendingBadge.tsx` — nouveau composant d'écran public, donc `tcn/` et non `ui/` (frontend/AGENTS.md), et l'exporter depuis l'index de `frontend/components/tcn/`
- [X] T038 [US2] Afficher la mention sur chaque ligne pendante de `frontend/app/athletes/[id]/page.tsx`, distincte au premier coup d'œil sans survol ni clic (SC-003)
- [X] T039 [US2] Vérifié : `grep -rl is_pending_validation frontend/app frontend/components` ne renvoie que `athletes/[id]/page.tsx` — `/resultats`, `/courses/[id]` et `/club` n'affichent plus ces lignes du tout depuis la Phase 2, confirmé plutôt que supposé

**Checkpoint**: US1 et US2 fonctionnent indépendamment. L'arbitrage Q1 est vérifiable de bout en bout.

---

## Phase 5: User Story 3 - Décrire précisément sa discipline (Priority: P3)

**Goal**: Les huit disciplines FFTri sont sélectionnables, avec choix du format en
deux temps pour les quatre disciplines à format et distance totale pour les
autres.

**Independent Test**: Dérouler le sélecteur (8 disciplines), choisir Triathlon
(format apparaît), choisir Autre (précision obligatoire), choisir Raid
Multisport (distance totale à la place du format), choisir Swim Bike (aucun champ
de course à pied dans l'encart temps).

> **Prérequis produit levé** : « Run & Bike » est bien le `bike-run` existant
> (confirmé le 2026-08-14). Aucun slug ni libellé supplémentaire — la liste des
> 13 slugs de T042 est complète et `bike-run` reste libellé « Bike & Run ».

### Tests for User Story 3

- [X] T040 [P] [US3] Test d'idempotence : `normalize_event_type` rend tel quel chacun des 13 nouveaux slugs, dans `backend/tests/test_classify.py`
- [X] T041 [P] [US3] Test des bases multi-mots : `_sport_base("swim-bike-m")` rend `swim-bike` (et non `swim`), idem `cross-triathlon` et `raid-multisport` ; et `build_splits` d'un `swim-bike` ne produit **aucune** clé de course à pied — dans `backend/tests/test_services/test_mapping.py`

### Implémentation

- [X] T042 [P] [US3] Ajouter les 13 slugs à `CANONICAL_TYPES` dans `backend/app/scrapers/classify.py` (liste exacte : data-model.md §6) — et rien d'autre dans ce fichier, cf. research.md D3
- [X] T043 [P] [US3] Ajouter `swim-bike`, `cross-triathlon` et `raid-multisport` à `_MULTI_WORD_BASES` dans `backend/app/services/mapping.py`
- [X] T044 [US3] Ajouter le gabarit `swim-bike` (`swim` / `t1` / `bike`, **sans** course à pied) à `_SPLIT_KEYS_BY_SPORT` dans `backend/app/services/mapping.py` ; `raid-multisport` tranché à `{}` (aucun découpage prévisible), `cross-triathlon` sans entrée (le gabarit par défaut est déjà juste)
- [X] T045 [P] [US3] Ajouter les 13 libellés à `EVENT_TYPE_LABELS` dans `frontend/lib/constants.ts`, plus `MANUAL_ENTRY_DISCIPLINES`/`_WITH_FORMAT`/`_FORMATS`/`_TIME_FIELDS` — non prévus dans le libellé initial mais nécessaires pour piloter la sélection en deux temps et l'encart temps du formulaire
- [X] T046 [US3] Implémenté la sélection en deux temps (discipline → format) dans `frontend/components/scrape/ManualResultForm.tsx` — **avec un `<select>` natif**, pas `ui/select` (déviation assumée, cf. note de fin de Phase 3)
- [X] T047 [US3] Rendu la précision obligatoire quand le format vaut « Autre », par `superRefine` sur le schéma zod, envoyée en `format_label`
- [X] T048 [US3] Ajouté un champ de distance totale (→ `distance_km`) à la place du format pour les disciplines sans format — **`distance_km` a dû être ajouté à `ParticipationCreate`/`ScrapedResult`/`_to_scraped`**, absent du schéma d'API avant cette tâche (gap découvert, cf. contracts/participations-api.md à mettre à jour)
- [X] T049 [P] [US3] Étendu `ManualResultForm.test.tsx` : 8 disciplines proposées, format conditionnel, précision bloquante, distance totale, encart temps adapté (Swim Bike sans course à pied)

**Checkpoint**: les trois user stories fonctionnent indépendamment.

---

## Phase 6: User Story 4 - Documenter et qualifier son résultat (Priority: P4)

**Goal**: Place générale, individuel/collectif avec nom d'équipe, statut sportif,
lien de vérification, et encart de temps adapté à la discipline.

**Independent Test**: Cocher « collectif » → champ nom d'équipe obligatoire ;
repasser à « individuel » → valeur non conservée ; enregistrer avec tous les
temps vides ; enregistrer un abandon sans temps ni place.

### Tests for User Story 4

- [X] T050 [P] [US4] Tests du choix individuel/collectif (défaut, champ conditionnel, valeur non conservée au retour) dans `frontend/components/scrape/ManualResultForm.test.tsx`
- [X] T051 [P] [US4] Tests du statut sportif (défaut « terminée », abandon enregistrable sans temps ni place) dans `frontend/components/scrape/ManualResultForm.test.tsx`
- [X] T052 [P] [US4] Test de l'encart temps : facultatif, et adapté à la discipline choisie, dans `frontend/components/scrape/ManualResultForm.test.tsx`
- [X] T071 [P] [US4] Test du cas limite « changement de discipline après saisie des temps » : remplir les temps d'un triathlon puis basculer sur une discipline sans natation → le temps de natation n'est **pas** envoyé à l'enregistrement, dans `frontend/components/scrape/ManualResultForm.test.tsx`
- [X] T053 [P] [US4] **Déjà couvert** par `test_derive_status_respects_explicit_status` (préexistant, non écrit dans cette feature) : `derive_status(_scraped(status="DNS"))` sans temps rend déjà `"DNS"`, pas `"DNF"`. Aucun code à changer — `derive_status` respectait déjà un statut explicite.
- [X] T054 [P] [US4] Test backend : une saisie portant un `evidence_url` crée une épreuve **sans aucune** `CourseSource` (research.md D5), dans `backend/tests/test_api/test_participations_api.py`

### Implémentation

- [X] T055 [US4] Ajouté le champ « place générale » (facultatif, → `rank_overall`) dans `ManualResultForm.tsx`
- [X] T056 [US4] Ajouté le choix individuel/collectif (→ `is_relay`, défaut individuel) et le champ conditionnel « nom de l'équipe » (→ `team_name`, obligatoire si collectif) — **radios natifs**, pas `SegmentedControl` tcn/ (cohérent avec le choix de rester sur `ui/` pour ce fichier)
- [X] T057 [US4] Ajouté le choix de statut sportif (terminée / abandon / forfait, défaut terminée)
- [X] T058 [US4] Regroupé les champs de temps dans un `<fieldset>` distinct, adapté à la discipline et entièrement facultatif ; les temps sans objet sont **purgés au submit** plutôt qu'à la saisie (même résultat côté API, moins d'effets de bord React)
- [X] T059 [US4] Ajouté le champ « lien vers les résultats » (→ `evidence_url`)
- [X] T060 [US4] `defaultUrl` alimente désormais `evidence_url` (`defaultValues` de `useForm`) ; le formulaire n'a plus de champ `source_url` du tout — `TcnScrapeForm.tsx` n'a nécessité aucun changement, son unique ligne `<ManualResultForm defaultUrl={url} .../>` couvrant déjà le nouveau contrat
- [X] T061 [P] [US4] `evidence_url` rendu en `<a target="_blank">` uniquement si `isHttpUrl()` (réutilisé depuis `lib/utils/url.ts`, pas réimplémenté), en ligne séparée du `<Link>` de la ligne — un `<a>` imbriqué dans un autre est invalide en HTML
- [X] T062 [P] [US4] Vérifié : `TcnScrapeForm.test.tsx` n'asserte jamais sur `source_url`/`evidence_url`, les 12 tests existants passent sans modification

**Checkpoint**: les quatre user stories sont complètes.

**Gaps découverts en cours d'implémentation, corrigés dans le même lot** :
- `distance_km` manquait à `ParticipationCreate`/`ScrapedResult`/`_to_scraped` (T048) — ajouté, testé (`test_distance_km_saisie_est_transmise_a_l_epreuve`).
- `server_default="false"` (chaîne) sur SQLite se relit `True` via l'ORM — détecté par le test « aucun backfill » de la Phase 2, corrigé en `sa.false()`.
- `useForm<FormValues>` générique explicite incompatible avec les `.default(...)` zod (erreur TypeScript en build) — retiré, RHF infère depuis le resolver.
- `watch()` incompatible avec le React Compiler (warning ESLint) — remplacé par `useWatch()`.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T063 [P] Documenté les 4 colonnes et les deux dimensions d'état dans `backend/app/models/AGENTS.md`
- [X] T064 [P] Mis à jour la liste des types d'épreuve en pied de `backend/app/scrapers/AGENTS.md` (les 13 slugs)
- [X] T065 [P] Documenté l'invariant d'exclusion — les 5 sites filtrés et les 6 non filtrés — dans `backend/app/api/AGENTS.md`
- [X] T072 [P] Consigné `PendingBadge` dans l'inventaire `tcn/` de `frontend/AGENTS.md`, et noté que `ManualResultForm` reste sur `ui/` malgré sa refonte
- [~] T066 **Partiellement fait** : la vérification automatisable de `quickstart.md` §2-§7 est couverte par les tests (migration aller-retour, exclusion des 5 sites + symétrique, discipline/format, individuel-collectif, evidence_url sans source). **Non fait** : le parcours navigateur réel (§3-§5, `npm run dev` + clics) — non exécuté dans cette session, à faire avant de sortir la PR du statut draft.
- [X] T067 `uv run ruff check .` (backend) et `npm run lint` (frontend) propres. `npm run build` réussit — seule erreur restante : `.next/dev/types/validator.ts`, artefact préexistant et gitignoré référençant une route absente du dépôt (`app/courses/[id]/participations/[participationId]`, une autre feature), sans rapport avec ce code
- [X] T068 Suite complète : **3349 tests backend** (3327 après Phase 2 + 22 nouveaux US3/US4/Phase7) et **677 tests frontend** (656 après Phase 1 + 21 nouveaux), tous verts
- [X] T069 PR #336 (draft) mise à jour : description réécrite avec le bilan complet (impact schéma, 4 points à relire, contrat d'API, test plan, ce qui reste à faire)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance
- **Foundational (Phase 2)** : dépend du Setup — **bloque toutes** les user stories
- **US1 (Phase 3)** → **US2 (Phase 4)** → **US3 (Phase 5)** → **US4 (Phase 6)** : toutes dépendent de la Phase 2
- **Polish (Phase 7)** : dépend des user stories retenues

### User Story Dependencies

- **US1 (P1)** : démarre après la Phase 2. Aucune dépendance sur une autre story.
- **US2 (P2)** : démarre après la Phase 2. Son backend y est déjà fait ; la phase 4 n'ajoute que la surface visible. **Indépendante d'US1** — elle se vérifie sur une participation pendante insérée à la main.
- **US3 (P3)** : démarre après la Phase 2, mais touche le **même fichier** qu'US1 (`ManualResultForm.tsx`). À séquencer après US1 plutôt qu'en parallèle.
- **US4 (P4)** : même fichier qu'US1 et US3. À séquencer en dernier.

### Within Each User Story

- Les tests sont écrits **et vérifiés rouges** avant l'implémentation
- Modèles avant services, services avant routes, backend avant front

### Parallel Opportunities

- **Phase 2** : T003 à T010 (8 tests) tous en parallèle ; puis T011, T012, T014, T015, T024 en parallèle. **T019 à T023 ne le sont pas** — même fichier, `participation_repository.py`.
- **Phase 3** : T025 à T027 en parallèle.
- **Phase 4** : T032 à T036 et T070 en parallèle (6 fichiers distincts) ; T037 en parallèle du reste.
- **Phase 5** : T040/T041 en parallèle ; T042, T043 et T045 en parallèle (3 fichiers) — **mais T043 et T044 sont dans `mapping.py`**, donc séquentiels entre eux.
- **Phase 6** : T050 à T054 et T071 en parallèle. Les tâches T055 à T060 sont **toutes** dans `ManualResultForm.tsx` : séquentielles.
- **Phase 7** : T063 à T065 et T072 en parallèle.

**Le goulot est `ManualResultForm.tsx`** : 13 tâches d'implémentation le touchent
sur trois phases. Un seul développeur dessus, ou des lots séquencés.

---

## Parallel Example: Phase 2

```bash
# Les 8 tests du socle, en parallèle (8 fichiers distincts) :
Tâche T003 : migration aller-retour dans backend/tests/test_migrations.py
Tâche T004 : prédicat et clause dans backend/tests/test_core/test_validation.py
Tâche T005 : répartition des 11 fonctions dans backend/tests/test_repositories/test_pending_exclusion.py
Tâche T007 : non-exclusion de list_for_athlete dans backend/tests/test_repositories/test_participation_repository.py
Tâche T010 : non-régression d'import dans backend/tests/test_services/test_mapping.py

# Puis les modèles et le module de règle, en parallèle :
Tâche T011 : 3 colonnes dans backend/app/models/participation.py
Tâche T012 : format_label dans backend/app/models/course.py
Tâche T014 : backend/app/core/validation.py
Tâche T024 : frontend/lib/types.ts
```

---

## Implementation Strategy

### MVP — Phase 2 + US1

Le MVP n'est **pas** US1 seule. La Phase 2 porte l'invariant de FR-021 : sans
elle, le formulaire produit des résultats déclarés qui comptent immédiatement dans
les podiums. Le premier incrément livrable est donc **Phase 1 + Phase 2 + US1**.

1. Phase 1 — ligne de base verte
2. Phase 2 — socle de données et exclusion (**bloquant**)
3. Phase 3 — US1
4. **ARRÊT et VÉRIFICATION** : `quickstart.md` §3
5. Livrable : un formulaire qui refuse les saisies inexploitables, et dont la
   production est confinée à la fiche athlète

### Livraison incrémentale

1. Phase 2 → socle prêt
2. + US1 → vérification indépendante → **MVP**
3. + US2 → la distinction devient visible (`quickstart.md` §6)
4. + US3 → les huit disciplines (`quickstart.md` §4)
5. + US4 → qualification complète (`quickstart.md` §5 et §7)

Chaque étape ajoute de la valeur sans casser la précédente.

### Stratégie à plusieurs

Le parallélisme est limité par `ManualResultForm.tsx`. Le découpage qui tient :

- **Développeur A** : Phase 2 backend, puis US2 backend et les tests d'agrégat
- **Développeur B** : US1, puis US3, puis US4 — tout le front du formulaire, seul
  sur le fichier
- Les deux se retrouvent sur la Phase 7

---

## Correction post-implémentation (2026-08-14) : contrôle d'accès de FR-026

**Découverte par le mainteneur en testant l'application lancée**, hors du
plan initial : `POST /api/v1/participations` était gardée par
`participations:write` depuis #115, ce qui bloquait le cas d'usage central du
formulaire — un membre sans compte ne pouvait plus rien saisir. La spec
supposait l'inverse (« Aucune modification du contrôle d'accès »), une
hypothèse jamais vérifiée sur le terrain.

**Corrigé** : la route redevient publique. C'est l'état de validation que
cette feature introduit (FR-016/FR-021) qui rend cette réouverture sûre — un
résultat créé anonymement reste en quarantaine jusqu'à validation. `DELETE`,
destructif, reste gardé.

- [X] T073 Retiré `require_permission(P.PARTICIPATIONS_WRITE)` de `create_participation` (`backend/app/api/v1/participations.py`), retiré `PARTICIPATIONS_WRITE` du catalogue (`backend/app/core/permissions.py`, membre + tuple `ALL`)
- [X] T074 Mis à jour `tests/test_auth/test_admin_guards.py` (3 tests obsolètes → 1 test de succès anonyme), `tests/test_auth/test_public_routes_still_open.py` (`ROUTES_FERMEES`), `tests/test_core/test_permissions.py` (`CODES_ATTENDUS`) — aucune autre référence au code retiré dans le dépôt (vérifié par grep)
- [X] T075 Vérifié en conditions réelles : serveur de dev relancé (`reload=True`), `POST /participations` sans cookie → `201`, `is_pending_validation: true`, absent de `GET /participations` — la quarantaine tient dès la première requête publique
- [X] T076 Spec, data-model et contrat mis à jour (FR-026 ajoutée, Assumption corrigée) — cette feature n'est pas encore livrée, corriger son propre dossier n'est pas une réécriture d'historique au sens de la constitution

Suite complète après correction : voir compteurs au commit correspondant.

---

## Notes

- **T070 à T072 sont physiquement placées dans leur phase, pas en fin de liste.**
  Elles ont été ajoutées après la passe `/speckit-analyze`, qui a relevé trois
  lacunes de couverture (FR-022 sans test automatisé, un cas limite sans tâche,
  `frontend/AGENTS.md` oublié). Leur numéro ne suit donc pas l'ordre d'exécution :
  **c'est la position dans le document qui fait foi**, l'identifiant n'étant qu'une
  référence stable. Renuméroter aurait invalidé les ~30 renvois d'identifiants des
  sections Dépendances et Parallélisme, pour un gain nul.
- `[P]` = fichiers différents, aucune dépendance en cours
- Vérifier chaque test **rouge** avant d'implémenter (Principe III)
- Un commit par tâche ou par groupe cohérent, en Conventional Commits
- La question « Run & Bike » est tranchée : même discipline que `bike-run`, rien à ajouter
- Le geste de validation lui-même appartient à **#271** : le §6 de `quickstart.md`
  provoque la bascule en base précisément parce que l'écran n'existe pas encore
