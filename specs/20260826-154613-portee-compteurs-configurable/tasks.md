---

description: "Task list — Portée des compteurs configurable depuis le panel admin"
---

# Tasks: Portée des compteurs configurable depuis le panel admin

**Input**: Design documents from `/specs/20260826-154613-portee-compteurs-configurable/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/admin-counter-scope.md](./contracts/admin-counter-scope.md)

**Issue**: [#95](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/95)

**Tests**: le Principe III de la constitution v1.1.1 est **non-négociable** — TDD sans réseau. Chaque tâche de test précède l'implémentation qu'elle couvre et doit **échouer** avant d'être satisfaite. Aucune dérogation demandée dans le `plan.md`.

**Organization**: tâches groupées par user story, chacune livrable et vérifiable seule.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, aucune dépendance sur une tâche en cours)
- **[Story]** : US1 / US2 / US3, selon `spec.md`
- Chemins de fichiers explicites, relatifs à la racine du worktree

## Path Conventions

Application web existante : `backend/` (Python) et `frontend/` (Next.js). Aucun dossier nouveau — la feature s'insère dans l'arborescence en place (cf. `plan.md` §Project Structure).

---

## Note d'ordonnancement, à lire avant de commencer

La phase 2 est **grosse et incompressible**, et c'est délibéré. Les deux listes sont lues par les mêmes quatre prédicats, aux mêmes 29 sites d'appel : basculer les prédicats sur un registre est un préalable indivisible, qui ne peut pas se découper par user story sans laisser le dépôt dans un état à moitié converti.

Sa propriété rachète son poids : **elle ne change aucun comportement**. À la fin de la phase 2, `uv run pytest -m "not integration"` doit être vert **sans qu'une seule assertion de la suite existante ait été modifiée**. Si un test existant a dû bouger, la bascule a changé quelque chose qu'elle ne devait pas changer — c'est le signal d'arrêt, pas un test à ajuster.

---

## Phase 1: Setup

**Purpose**: rien à initialiser — la stack, les outils et le lint sont en place. Cette phase se réduit à borner le terrain avant de le toucher.

- [X] T001 Relever les sites d'appel de `is_tcn`, `tcn_clause`, `is_federal` et `federal_clause` dans `backend/app/` — `grep -rn "is_federal(\|federal_clause(\|is_tcn(\|tcn_clause(" backend/app/` — et vérifier que le compte correspond aux 29 annoncés dans `plan.md`. Un écart signifie que le dépôt a bougé depuis la conception, et que le périmètre de la bascule de la phase 2 est à revoir avant de commencer
- [X] T002 Vérifier l'état de départ vert : `cd backend && uv run pytest -m "not integration"` et `cd frontend && npm test`

**Checkpoint**: point de comparaison établi.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: porter la configuration en base et faire lire les prédicats depuis un registre, **à comportement strictement constant**.

**⚠️ CRITICAL**: aucune user story ne peut commencer avant la fin de cette phase.

### Tests de la phase fondatrice

- [X] T003 [P] Écrire `backend/tests/test_core/test_counter_scope.py` : les défauts du registre valent les 9 disciplines et 3 libellés d'aujourd'hui, `load()` remplace les deux ensembles d'un seul geste, `reset()` revient aux défauts, les accesseurs rendent un `frozenset` non mutable par l'appelant, et **une référence obtenue avant un `load()` reste inchangée après** — c'est ce qui prouve le rebinding plutôt que la mutation en place, et donc qu'un lecteur concurrent ne voit jamais d'ensemble à moitié écrit
- [X] T004 [P] Écrire `backend/tests/test_repositories/test_counter_scope_repository.py` : lecture des entrées par `kind`, création, suppression, et rejet en base d'un doublon `(kind, value)` par la contrainte d'unicité
- [X] T005 [P] Étendre `backend/tests/test_migrations.py` de deux cas, sur le patron de `test_la_migration_seme_exactement_trois_roles_systeme` et de `test_downgrade_puis_upgrade_du_rbac` : (a) sur une base vierge migrée jusqu'à `head`, les lignes amorcées de `counter_scope_entries` sont **exactement** les défauts de `app/core/counter_scope.py` — le garde-fou contre la divergence entre les littéraux de la migration et ceux du code (research.md §3) ; (b) un `downgrade` puis `upgrade` retrouve les 12 lignes, comme les six migrations qui portent déjà ce test
- [X] T006 Étendre `backend/tests/test_repositories/test_club_filter.py` : après un `counter_scope.load(...)` qui ajoute un libellé et en retire un autre, `is_tcn` et `tcn_clause` rendent **toujours** le même verdict sur le corpus. Le contrat existant est éprouvé sur une configuration **modifiée**, pas seulement sur celle livrée (FR-005, SC-005)

### Implémentation de la phase fondatrice

- [X] T007 [P] Créer le modèle `CounterScopeEntry` dans `backend/app/models/counter_scope_entry.py` — colonnes, `UNIQUE (kind, value)`, `created_by_user_id` nullable (cf. data-model.md), et l'enregistrer dans `backend/app/models/__init__.py`
- [X] T008 [P] Créer le registre `backend/app/core/counter_scope.py` : `DEFAULT_NON_FEDERAL_DISCIPLINES`, `DEFAULT_TCN_CLUB_LABELS`, `non_federal_disciplines()`, `tcn_club_labels()`, `load()`, `reset()`. Aucune Session, aucun import d'une couche supérieure — c'est ce qui autorise ce module dans `core/`. `load()` **réassigne** les deux noms sur de nouveaux `frozenset`, jamais de mutation en place : le scrape SSE lit le registre depuis un thread pendant qu'un admin peut écrire (data-model.md §Registre)
- [X] T009 Générer la migration Alembic (`cd backend && uv run alembic revision --autogenerate -m "counter scope entries"`), la **relire à la main**, et y ajouter l'amorçage des 12 valeurs **en littéral** — jamais importées depuis `app.core` (data-model.md §Amorçage). Dépend de T007
- [X] T010 Créer `backend/app/repositories/counter_scope_repository.py` : `list_entries(db, kind=None, with_created_by=False)`, `create_entry`, `delete_entry`, `count_entries(db, kind)`. Ne commite jamais — la transaction reste portée par le service (patron de `site_access_config_repository.py`). Dépend de T007
- [X] T011 Basculer `backend/app/core/club.py` : supprimer `TCN_CLUB_LABELS`, faire lire `is_tcn` et `tcn_clause` depuis `counter_scope.tcn_club_labels()`. `normalize_club`, `_normalise_sql`, `CLUB_NORMALIZED_INDEX_EXPRESSION`, `TCN_CANONICAL_NAME`, `SCOPE_CLUB` et `is_club_scope` restent **strictement inchangés** — la normalisation ne bouge pas, sous peine de périmer l'index fonctionnel en silence (research.md §6). Dépend de T008
- [X] T012 Basculer `backend/app/core/discipline.py` : supprimer `NON_FEDERAL_TYPES`, faire lire `is_federal` et `federal_clause` depuis `counter_scope.non_federal_disciplines()`. Dépend de T008
- [X] T013 [P] Mettre à jour les docstrings de `backend/app/core/club.py` et `backend/app/core/discipline.py` : elles décrivent des listes figées dans le code, description devenue fausse. Conserver ce qui reste vrai et qui compte — liste d'**exclusion** pour les disciplines, match à l'**égalité** pour le club, comparaison de chaînes entières des deux côtés. Dépend de T011, T012
- [X] T014 Créer `backend/app/services/counter_scope.py` avec `load_from_db(db)` : lit les deux `kind` via le repository et pousse le résultat dans le registre par un unique `counter_scope.load(...)`. Dépend de T010
- [X] T015 [P] Remplir le registre au démarrage de l'API, dans le `lifespan` de `backend/app/main.py` (après `alembic upgrade head` du `startCommand`, cf. `render.yaml`). Dépend de T014
- [X] T016 [P] Remplir le registre à l'entrée de la CLI, dans `backend/app/cli/__main__.py`, à côté de `configure_cli_logging()` — le remplissage est le rôle du processus, pas d'un module importé. Dépend de T014
- [X] T017 [P] Ajouter dans `backend/tests/conftest.py` une fixture `autouse` qui remet le registre aux défauts entre deux tests, sur le patron de `_compteurs_de_debit_vierges` — un registre modifié par un test ne doit pas fuir dans le suivant. Dépend de T008

**Checkpoint**: `cd backend && uv run pytest -m "not integration"` est vert **sans qu'une assertion existante ait changé**. La configuration vit en base, les prédicats la lisent, et rien ne se comporte différemment.

---

## Phase 3: User Story 1 — Déclarer une nouvelle orthographe du club (Priority: P1) 🎯 MVP

**Goal**: un administrateur ajoute un libellé de club depuis le panel admin, et les résultats qui le portent entrent immédiatement dans les compteurs du club.

**Independent Test**: ajouter un libellé depuis l'écran, recharger une page de résultats contenant ce libellé, constater le badge du club et l'augmentation du compteur — sans redémarrage.

### Tests for User Story 1

> Écrire ces tests **d'abord**, vérifier qu'ils échouent (Principe III).

- [ ] T018 [P] [US1] `backend/tests/test_services/test_counter_scope.py` : normalisation à l'écriture (« TRIATHLON  CLUB NANTAIS 44 » → `triathlon club nantais 44`), refus d'une valeur vide une fois normalisée (FR-009), refus du doublon (FR-009), refus du retrait du dernier libellé de club (FR-010), et rechargement du registre après écriture (FR-008)
- [ ] T019 [P] [US1] `backend/tests/test_api/test_admin_counter_scope.py` : `GET` rend les deux listes triées par `value` ; `POST /club-labels` rend 201 et la valeur normalisée ; doublon → 409 ; valeur vide → 400 ; `DELETE` du dernier libellé → 409 ; `kind` inconnu → 422 ; sans le pouvoir → 403 (FR-012). Messages d'erreur **en français** (clause « cas mixte » du Principe I)
- [ ] T020 [P] [US1] `backend/tests/test_api/test_admin_counter_scope.py` (même fichier, cas dédié) : après un `POST` de libellé, un `GET /api/v1/participations` sur une participation portant ce libellé rend `is_tcn: true` **et** le compteur `scope=club` l'inclut — le badge et le compteur bougent ensemble (FR-005)
- [ ] T021 [P] [US1] `frontend/components/admin/CounterScopeCard.test.tsx` : rendu de la liste, ajout, états de chargement et d'erreur, confirmation au retrait, et phrase spécifique quand la valeur retirée est celle du nom affiché du club (FR-017)

### Implementation for User Story 1

- [ ] T022 [P] [US1] Ajouter le pouvoir `counter_scope:manage` et la fonctionnalité `FEATURE_COUNTER_SCOPE = "Portée des compteurs"` dans `backend/app/core/permissions.py`, membre de `P` **et** entrée dans `ALL` — le méta-test `tests/test_permissions_catalogue.py` rougit tant que la garde manque
- [ ] T023 [P] [US1] Créer les schémas Pydantic dans `backend/app/schemas/counter_scope.py` : `CounterScopeEntryOut` (`id`, `value`, `is_known`, `created_at`, `created_by`), `CounterScopeOut` (`disciplines`, `club_labels`), `CounterScopeEntryIn` (`value`), et l'énumération d'URL `disciplines` / `club-labels`
- [ ] T024 [US1] Compléter `backend/app/services/counter_scope.py` : `add_entry(db, kind, value, admin_user_id)` et `remove_entry(db, kind, entry_id)` — normalisation par `normalize_club` pour un libellé, minuscules et bords rognés pour une discipline ; refus de la valeur vide et du doublon ; refus du retrait du dernier libellé de club ; rechargement du registre **après le commit**. Dépend de T014, T023
- [ ] T025 [US1] Créer le routeur `backend/app/api/v1/admin_counter_scope.py` : `GET /admin/counter-scope`, `POST /admin/counter-scope/{kind}`, `DELETE /admin/counter-scope/{kind}/{entry_id}`, chacun gardé par `require_permission(P.COUNTER_SCOPE_MANAGE)`. Routeur **fin** : validation et délégation au service, jamais un appel direct au repository pour les écritures. Dépend de T022, T023, T024
- [ ] T026 [US1] Monter le routeur dans `backend/app/api/v1/router.py`, **derrière** `require_site_access` — rien ici ne participe à la pose du cookie de site, donc aucune exemption ne se justifie. Dépend de T025
- [ ] T027 [P] [US1] Câbler la lecture et les deux mutations dans `frontend/lib/queries/admin.ts`, avec les clés dans `frontend/lib/queries/keys.ts` ; chaque mutation invalide la clé de lecture **et** les clés des écrans dont les compteurs dépendent de la configuration — un tableau de bord en cache afficherait sinon les anciens compteurs
- [ ] T028 [US1] Créer `frontend/components/admin/CounterScopeCard.tsx` : une carte paramétrée par la nature, liste des entrées, champ d'ajout, retrait avec confirmation (`DangerConfirm`), états vide / chargement / erreur. La confirmation porte une phrase supplémentaire quand la valeur retirée égale `normalize(CLUB_NAME)` de `frontend/lib/club.ts` — plus rien portant le nom affiché du club ne serait compté (FR-017). Dépend de T027
- [ ] T029 [US1] Créer l'écran `frontend/app/admin/portee-compteurs/page.tsx` montant la carte pour les **libellés de club** (la seconde carte arrive en US2), sur le patron de `app/admin/acces/page.tsx`. Dépend de T028
- [ ] T030 [US1] Ajouter l'entrée de navigation dans `frontend/components/layout/nav.config.ts`, visible sous le pouvoir `counter_scope:manage` — ce n'est pas une garde, la route de l'API porte la sienne. Dépend de T029

**Checkpoint**: US1 est complète et démontrable seule. Un administrateur ajoute une orthographe de club et voit les compteurs bouger, sans développeur ni déploiement.

---

## Phase 4: User Story 2 — Sortir ou rentrer une discipline des compteurs (Priority: P2)

**Goal**: un administrateur agit sur la liste des disciplines exclues, et le toggle « Inclure les autres disciplines » reflète sa décision.

**Independent Test**: exclure une discipline depuis l'écran, constater que ses résultats sortent des compteurs `federal_only=true` et y reviennent au retrait de l'entrée.

### Tests for User Story 2

- [ ] T031 [P] [US2] `backend/tests/test_services/test_counter_scope.py` (cas dédiés) : une discipline hors `classify.CANONICAL_TYPES` est **acceptée** avec `is_known: false`, jamais refusée (FR-011) ; vider entièrement la liste des disciplines est légitime, contrairement aux libellés de club
- [ ] T032 [P] [US2] `backend/tests/test_api/test_admin_counter_scope.py` (cas dédiés) : après un `POST /disciplines`, un endpoint `federal_only=true` exclut les résultats de cette discipline, et une discipline absente de la liste reste comptée — l'inconnu reste fédéral par défaut (FR-004)

### Implementation for User Story 2

- [ ] T033 [US2] Calculer `is_known` dans `backend/app/services/counter_scope.py` par appartenance à `app.scrapers.classify.CANONICAL_TYPES` pour les disciplines, toujours `true` pour un libellé de club — un service peut importer `scrapers`, l'inverse serait une remontée de couche. Dépend de T024
- [ ] T034 [US2] Monter la seconde carte (disciplines) dans `frontend/app/admin/portee-compteurs/page.tsx` — le composant de T028 est réutilisé tel quel, paramétré par la nature. Dépend de T029, T033
- [ ] T035 [P] [US2] Afficher le badge d'avertissement « discipline inconnue » dans `frontend/components/admin/CounterScopeCard.tsx` quand `is_known` est faux (FR-011), et couvrir ce rendu dans `frontend/components/admin/CounterScopeCard.test.tsx`. Dépend de T034

**Checkpoint**: les deux listes sont éditables et les deux user stories fonctionnent indépendamment.

---

## Phase 5: User Story 3 — Comprendre et auditer la configuration (Priority: P3)

**Goal**: la configuration se lit, s'explique et se trace.

**Independent Test**: ouvrir l'écran, lire les deux listes et leur explication, modifier une entrée, retrouver la modification dans le journal d'administration.

### Tests for User Story 3

- [ ] T036 [P] [US3] `backend/tests/test_api/test_admin_counter_scope.py` (cas dédiés) : un `POST` et un `DELETE` posent chacun une ligne dans `admin_action_log` (`counter_scope.entry_add` / `counter_scope.entry_remove`, `entity_type` `counter_scope_entry`), avec l'auteur (FR-013)
- [ ] T037 [P] [US3] `frontend/components/admin/CounterScopeCard.test.tsx` (cas dédiés) : l'auteur et la date s'affichent par entrée, et une entrée sans auteur rend « Configuration initiale » (FR-016)

### Implementation for User Story 3

- [ ] T038 [US3] Journaliser les deux écritures dans `backend/app/api/v1/admin_counter_scope.py` via `admin_action_log_repository.create`, dans la même transaction que l'écriture (patron de `admin_site_access.py`). Dépend de T025
- [ ] T039 [US3] Charger l'auteur par `joinedload` à la lecture dans `backend/app/repositories/counter_scope_repository.py` et l'exposer dans `CounterScopeEntryOut.created_by` — jamais sur les autres chemins, qui n'ont pas à payer la jointure. Dépend de T010, T023
- [ ] T040 [US3] Afficher provenance et date par entrée dans `frontend/components/admin/CounterScopeCard.tsx`, « Configuration initiale » quand l'auteur est absent (FR-016). Dépend de T039
- [ ] T041 [US3] Écrire la phrase d'explication de chaque liste dans `frontend/app/admin/portee-compteurs/page.tsx` (FR-015) : exclusion pour les disciplines — une discipline inconnue reste comptée ; libellés reconnus pour le club — la comparaison ignore casse et espaces, et un libellé qui contient le nôtre sans lui être égal n'est pas le nôtre. Dépend de T034

**Checkpoint**: les trois user stories fonctionnent indépendamment.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T042 [P] Aligner `backend/app/cli/commands/club_labels.py` sur la configuration en vigueur (FR-020) et couvrir le cas dans `backend/tests/test_cli/` — la commande sert précisément à repérer les libellés manquants, elle doit se prononcer selon ce qui est configuré, pas selon une constante
- [ ] T043 [P] Documenter les trois routes dans `docs/api/admin-donnees.md`
- [ ] T044 [P] Mettre à jour `backend/AGENTS.md` et `backend/app/core/AGENTS.md` là où ils décrivent les deux listes comme figées dans le code, et consigner dans `backend/app/core/AGENTS.md` la seule vraie subtilité du module : le registre porte de l'**état** dans `core/`, poussé depuis le dessus, et pourquoi les trois alternatives ont été écartées (renvoi à `research.md` §2)
- [ ] T045 [P] Consigner dans `backend/app/core/club.py` l'avertissement que la feature rend tentant : rendre l'**ensemble** des libellés configurable ne rend pas la **normalisation** configurable, et toute évolution de `_normalise_sql` exige une migration de reconstruction de `ix_participations_club_normalized` (research.md §6)
- [ ] T046 Vérifier FR-006 et SC-004 : lancer le classement d'une grosse épreuve avec `SQL_QUERY_STATS=true` avant et après la bascule, et constater un nombre de requêtes **identique** — le registre étant lu en mémoire, la feature ne doit ajouter aucune requête. Consigner les deux comptes dans la description de la PR. Le nombre de requêtes, et non le chrono : c'est la grandeur reproductible, et c'est elle qui régresserait si un chemin se remettait à lire la base par participation
- [ ] T047 Dérouler `specs/20260826-154613-portee-compteurs-configurable/quickstart.md` de bout en bout, §1 à §8
- [ ] T048 Vérification finale : `cd backend && uv run pytest -m "not integration"` et `uv run ruff check .` ; `cd frontend && npm test && npm run lint && npm run build`
- [ ] T049 Sous-agent `ui-ux-review` sur l'écran d'administration — la branche touche `frontend/`, la revue de rendu s'insère après la revue de code (AGENTS.md §Workflow IA)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance
- **Foundational (Phase 2)** : dépend de la phase 1 — **bloque toutes les user stories**
- **US1 (Phase 3)** : dépend de la phase 2
- **US2 (Phase 4)** : dépend de la phase 2 ; réutilise le routeur et le composant d'US1 (T033 dépend de T024, T034 de T029)
- **US3 (Phase 5)** : dépend de la phase 2 ; T038 dépend du routeur d'US1 (T025)
- **Polish (Phase 6)** : dépend des user stories retenues

### Une indépendance partiellement vraie, et il vaut mieux le dire

US2 et US3 sont indépendamment **testables**, mais pas indépendamment **implémentables** : les trois stories passent par le même routeur et le même composant de carte, l'une des deux natures étant un paramètre. Répartir les trois entre trois personnes ferait converger tout le monde sur `admin_counter_scope.py` et `CounterScopeCard.tsx`.

Ce que l'ordre achète réellement, ce n'est donc pas du parallélisme d'équipe, c'est un **arrêt possible après US1** : à ce point la feature a déjà sa valeur entière pour le geste le plus fréquent, et le reste peut attendre.

### Within Each User Story

- Les tests sont écrits **avant** et doivent échouer (Principe III)
- Modèle → repository → service → routeur → front
- Une story complète avant de passer à la suivante

### Parallel Opportunities

- T003, T004, T005 (phase 2) : trois fichiers de test distincts
- T007 et T008 : modèle et registre, sans lien
- T015, T016, T017 : les trois points de remplissage, trois fichiers
- T018 à T021 (US1) : quatre fichiers de test distincts
- T022, T023, T027 : pouvoir, schémas, câblage front
- T042 à T045 (polish) : quatre fichiers de documentation et d'outillage

---

## Parallel Example: phase 2

```bash
# Les tests de la phase fondatrice, ensemble :
Task: "T003 registre en mémoire dans backend/tests/test_core/test_counter_scope.py"
Task: "T004 repository dans backend/tests/test_repositories/test_counter_scope_repository.py"
Task: "T005 amorçage de la migration dans backend/tests/test_migrations.py"

# Puis modèle et registre, ensemble :
Task: "T007 modèle CounterScopeEntry dans backend/app/models/counter_scope_entry.py"
Task: "T008 registre dans backend/app/core/counter_scope.py"
```

---

## Implementation Strategy

### MVP (US1 seule)

1. Phase 1 — point de comparaison
2. Phase 2 — **critique**, bloque tout, et ne doit rien changer
3. Phase 3 — US1
4. **ARRÊT et VALIDATION** : quickstart §1, §3, §4, §5
5. Livrable tel quel : le geste le plus fréquent est couvert

### Livraison incrémentale

1. Phases 1-2 → socle posé, comportement inchangé
2. + US1 → libellés de club éditables (MVP)
3. + US2 → disciplines éditables
4. + US3 → provenance et journal
5. + Polish → documentation, CLI, revue de rendu

---

## Notes

- Commit après chaque tâche ou groupe cohérent, en Conventional Commits
- Le point d'arrêt le plus important est le checkpoint de la phase 2 : une assertion existante qui doit changer est un signal d'arrêt, pas un test à ajuster
- Ne jamais toucher `normalize_club` ni `_normalise_sql` — hors périmètre, et l'index fonctionnel en dépend silencieusement
- `rtk uv run pytest -m "not integration"` rend la même preuve pour une fraction des tokens ; jamais sur `alembic` ni sur la CLI de batch (`docs/rtk.md`)
