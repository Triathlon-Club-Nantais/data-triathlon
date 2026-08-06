---

description: "Tâches — groupes d'appartenance (#197)"
---

# Tasks: Groupes d'appartenance — modéliser avant qu'un groupe porte un droit

**Input**: `specs/20260806-143225-auth-groupes-appartenance/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/admin-groups-api.md](contracts/admin-groups-api.md)

**Tests** : le Principe III de la constitution est **non-négociable**. Chaque
tâche de code est précédée de sa tâche de test, écrite pour **échouer d'abord**.
La clause « Tests are OPTIONAL » du gabarit amont ne s'applique pas à ce dépôt.

**Organization** : les tâches sont groupées par user story, chacune livrable et
testable seule.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable — fichier différent, aucune dépendance en cours.
- **[Story]** : US1…US4, dans les phases de story uniquement.
- Chemins relatifs à la racine du dépôt.

## Deux règles qui traversent toutes les phases

1. **Aucun fichier du mécanisme de décision de #115 n'est modifié.** Ni
   `api/deps.py`, ni `services/auth/authorization.py`, ni les repositories des
   rôles ; et surtout pas les deux filets, `tests/test_permissions_catalogue.py`
   et `tests/test_auth/test_public_routes_still_open.py`, dont l'immobilité est
   vérifiée en T033.

   > **Levée en revue (T041)** — `services/auth/authorization.py` **est**
   > finalement modifié. La revue y a trouvé le jumeau exact du défaut de
   > `create_group` : un `except IntegrityError` mort, donc un 500 au lieu du
   > 409 promis sur une collision de slug de rôle, en production depuis #115.
   > Arbitrage de l'utilisateur : correctif racine dans la même PR, plutôt
   > qu'une issue suiveuse. La règle valait pour ce que #197 avait à faire, pas
   > contre un correctif que la feature a fait apparaître.

   **Huit fichiers existants sont bien touchés**, tous en **ajout pur**, sans
   qu'aucune ligne existante change de sens — les lister ici évite de lire la
   règle ci-dessus comme une interdiction qu'elle n'est pas :
   `core/permissions.py` (T015, T021), `models/user.py` et `models/__init__.py`
   (T007), `schemas/admin.py` (T010), `schemas/auth.py` (T027),
   `api/v1/router.py` (T018), `api/v1/auth.py` (T028) et
   `tests/test_migrations.py` (T004).

   **Un neuvième s'est ajouté à l'implémentation** : `tests/test_core/test_permissions.py`,
   troisième filet que le plan n'avait pas repéré. Il épingle les codes **à la
   main** — « un test qui dériverait la liste du catalogue ne prouverait rien » —
   et a donc rougi à T015. Le compléter *est* le geste conscient qu'il exige.
2. **Les trois pouvoirs entrent au catalogue dans la story qui les garde**, pas
   avant. `test_permissions_catalogue.py` exige que tout pouvoir déclaré garde
   une ressource : déclarer les trois en Phase 2 rendrait la suite rouge jusqu'à
   la fin de la Phase 4. Chaque checkpoint est donc vert.

---

## Phase 1: Setup

**Purpose** : établir la ligne de base avant de toucher quoi que ce soit.

- [X] T001 Depuis `backend/`, lancer `uv sync && uv run alembic upgrade head && uv run pytest -m "not integration"` et noter le nombre de tests verts — c'est la référence contre laquelle chaque checkpoint se lit. Aucune modification de fichier.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose** : les deux tables, leur accès et leurs formes. Rien de ce qui suit
n'est exposé par une route — la surface HTTP reste identique à celle d'aujourd'hui.

**⚠️ CRITICAL** : aucune user story ne peut commencer avant la fin de cette phase.

### Tests (écrits d'abord, rouges)

- [X] T002 [P] Créer `backend/tests/test_auth/test_group_models.py` : `UNIQUE(organisation_id, slug)` refuse un doublon dans le même club et **accepte** le même slug dans deux clubs ; `groups.organisation_id` est **non nul** (une insertion sans club lève) ; `UNIQUE(user_id, group_id)` refuse une appartenance en double ; supprimer un `User` emporte ses `UserGroup` et **laisse le groupe intact** (AC5) ; `user_groups` ne porte **aucune** colonne `organisation_id`.
- [X] T003 [P] Créer `backend/tests/test_auth/test_group_repository.py` : `add_member` appelé deux fois rend `(appartenance, False)` la seconde fois sans lever ni dupliquer (idempotence par contrainte, pas par lecture préalable) ; `remove_member` sur une appartenance absente rend `False` ; `count_members` et `list_members` rendent les bonnes valeurs, membres triés par `display_name` puis `email`.
- [X] T004 [P] Étendre `backend/tests/test_migrations.py` : après `upgrade head` sur base vierge, `groups` porte exactement `created_at, description, id, name, organisation_id, slug` et `user_groups` exactement `group_id, id, joined_at, user_id` — l'absence d'`is_superuser`, d'`is_system` et d'`organisation_id` sur l'appartenance est **assertée**, pas supposée.

### Implémentation

- [X] T005 [P] Créer le modèle `Group` dans `backend/app/models/group.py` : colonnes de `data-model.md` §groups, `UniqueConstraint("organisation_id", "slug", name="uq_group_org_slug")`, **aucun** index partiel (la colonne est non nulle — c'est la 4ᵉ différence avec `Role`, à écrire dans le docstring).
- [X] T006 [P] Créer le modèle `UserGroup` dans `backend/app/models/user_group.py` : `UniqueConstraint("user_id", "group_id", name="uq_user_group")`, **pas** d'`organisation_id` (le groupe la porte), **pas** d'`ondelete` (convention #114 : aucun `PRAGMA foreign_keys=ON`), `relationship` de lecture vers `User` et `Group`.
- [X] T007 Ajouter `User.groups` (`relationship`, `cascade="all, delete-orphan"`, `back_populates`) dans `backend/app/models/user.py`, et exporter `Group` / `UserGroup` depuis `backend/app/models/__init__.py`. Aucun DDL sur `users`. (dépend de T005, T006)
- [X] T008 Générer la migration avec `uv run alembic revision --autogenerate -m "groups and memberships"` depuis `backend/`, puis **relire et corriger à la main** la révision produite : `down_revision = "f6a7b8c9d0e1"`, noms de contraintes `uq_group_org_slug` et `uq_user_group`, index sur les clés étrangères, `downgrade` qui supprime les deux tables dans l'ordre inverse, **aucun semis ni aucun `UPDATE`**. (dépend de T007)
- [X] T009 Créer `backend/app/repositories/group_repository.py` : `get`, `list_all` (trié par `slug`), `find_in_scope(slug, organisation_id)`, `create`, `delete`, `count_members`, `list_members` (jointure `User`, tri d'affichage), `add_member` (insertion sous `db.begin_nested()` puis rattrapage de l'`IntegrityError` — reprise exacte de `user_role_repository.grant`), `remove_member`. **Seule couche qui touche la `Session`** ; aucun `commit()`. (dépend de T007)
- [X] T010 [P] Ajouter les DTO dans `backend/app/schemas/admin.py` : `GroupRead`, `GroupDetailRead`, `GroupMemberRead`, `GroupCreate` (slug `^[a-z][a-z0-9-]*$`), `GroupUpdate` et `GroupMemberAdd`, tous en `extra="forbid"` pour les entrées, `created_at`/`joined_at` sérialisés avec le suffixe `Z` comme `AdminUserRead`. Formes exactes : `contracts/admin-groups-api.md`.
- [X] T011 Créer `backend/app/services/auth/groups.py` — squelette seul : `GroupSlugTakenError` (409), `GroupInUseError` (409), `get_group_or_404`, `group_view` et `group_detail_view`. Messages de `DomainError` **en français** (Principe I). **Ce module ne doit jamais être importé par `authorization.py` ni par `api/deps.py`** — c'est ce qui rend AC6 vérifiable en T027. (dépend de T009)

**Checkpoint** : `uv run pytest -m "not integration"` est vert, avec les tests de
T002–T004 en plus et **aucune route nouvelle**. Le compte de T001 a augmenté,
rien n'a rougi.

---

## Phase 3: User Story 1 — Tenir la composition des commissions (Priority: P1) 🎯 MVP

**Goal** : créer, renommer, supprimer un groupe ; y ajouter et en retirer un
membre — le tout gardé par `groups:write` et `groups:assign`.

**Independent Test** : créer un groupe, y ajouter deux personnes, en retirer une,
renommer le groupe, constater que l'appartenance restante a survécu au
renommage ; tenter la suppression du groupe encore peuplé et constater le 409 qui
nomme le nombre de membres.

### Tests for User Story 1

> Écrits d'abord, **rouges** avant toute implémentation (Principe III).

- [X] T012 [P] [US1] Créer `backend/tests/test_auth/test_admin_groups_api.py` — volet écriture : `POST` crée un groupe **vide** (201, `member_count: 0`) ; `POST` d'un slug déjà pris dans le même club rend 409 ; `PATCH` renomme sans perdre d'appartenance ; `PATCH {"slug": …}` rend **422** (`extra="forbid"`) ; `DELETE` d'un groupe vide rend 204 ; `DELETE` d'un groupe peuplé rend **409 dont le message nomme le nombre de membres**, avec l'accord au singulier comme au pluriel. **FR-023** : un `caplog` vérifie que la création et la suppression journalisent l'**auteur** et le **groupe** — l'audit de cette feature n'a pas de table, ces lignes *sont* la trace.
- [X] T013 [P] [US1] Dans le même fichier, volet appartenance : `POST /members` rend 201 et est **idempotent** (deux appels, un seul membre, aucun doublon, aucune erreur) ; `DELETE /members/{user_id}` rend 204 **même si la personne n'était pas membre** ; retirer un membre ne touche ni ses rôles ni ses autres appartenances ; un compte **désactivé** est un membre légitime ; `POST /members` avec un `user_id` inconnu rend 404. **FR-023** : un `caplog` vérifie que l'ajout et le retrait journalisent l'auteur, la cible et le sens de l'opération.
- [X] T014 [P] [US1] Dans le même fichier, volet gardes : chacune des cinq routes rend **401 sans cookie** et **403 avec une session sans pouvoir** — jamais l'inverse ; une session portant `groups:read` **seul** est refusée en 403 sur les cinq.

### Implémentation for User Story 1

- [X] T015 [US1] Ajouter `FEATURE_GROUPS = "Groupes d'appartenance"` et les pouvoirs `GROUPS_WRITE` (`groups:write`) et `GROUPS_ASSIGN` (`groups:assign`) dans `backend/app/core/permissions.py`, dans `P` **et** dans `ALL`. Libellés et descriptions en français. **Ne pas** ajouter `groups:read` ici — il entre en T021, avec la ressource qu'il garde.
- [X] T016 [US1] Implémenter dans `backend/app/services/auth/groups.py` : `create_group` (slug pris → 409 en lecture **et** sur `IntegrityError`, organisation par défaut via `role_repository.default_organisation`), `update_group` (nom, description ; jamais le slug), `delete_group` (compte les membres, `GroupInUseError` avec le nombre **dans le message**, aucune cascade), `add_member`, `remove_member`. Un `logger.info` par opération, **en anglais**, au format de #115 (`Group created: actor=… group=…`). **Aucun appel** à `assert_may_grant` ni à `administrateurs_preserves` : il n'y a ni pouvoir à amplifier, ni administrateur à préserver (FR-018, FR-019). (dépend de T011, T015)
- [X] T017 [US1] Créer `backend/app/api/v1/admin_groups.py` avec les cinq routes d'écriture de `contracts/admin-groups-api.md` (`POST`, `PATCH`, `DELETE /admin/groups[/{group_id}]`, `POST` et `DELETE` sur `/members`), **une garde `require_permission` par route**, jamais en `dependencies=` de router. Couche mince : validation, délégation au service, `db.commit()`. (dépend de T016)
- [X] T018 [US1] Monter le router dans `backend/app/api/v1/router.py`, à côté d'`admin_roles`. (dépend de T017)

**Checkpoint** : les cinq routes existent et sont gardées.
`test_public_routes_still_open.py` les classe automatiquement comme devant
refuser l'anonyme, **sans avoir été modifié** ;
`test_permissions_catalogue.py` voit deux pouvoirs de plus, chacun gardant au
moins une ressource. US1 est démontrable seule.

---

## Phase 4: User Story 2 — Lister les membres d'une commission (Priority: P1)

**Goal** : la liste des groupes et le détail nominatif d'un groupe, gardés par
`groups:read`. C'est la capacité qui justifie l'objet entier (FR-012).

**Independent Test** : peupler un groupe, demander son détail, constater qu'il
nomme exactement ses membres — sans passer par les rôles, et avec une session ne
portant que `groups:read`.

### Tests for User Story 2

- [X] T019 [P] [US2] Ajouter à `backend/tests/test_auth/test_admin_groups_api.py` le volet lecture : `GET /admin/groups` rend la liste triée par `slug` avec `member_count` juste ; `GET /admin/groups/{id}` rend les membres, triés par `display_name` puis `email`, `is_active` compris ; un groupe vide rend `members: []` ; un identifiant inconnu rend 404.
- [X] T020 [P] [US2] Dans le même fichier : les deux routes de lecture rendent 401 sans cookie et 403 pour une session sans `groups:read` ; une session portant **`groups:read` seul** les franchit **et** reste refusée en 403 sur les cinq routes d'écriture.

### Implémentation for User Story 2

- [X] T021 [US2] Ajouter le pouvoir `GROUPS_READ` (`groups:read`) dans `P` et dans `ALL`, sous `FEATURE_GROUPS`, dans `backend/app/core/permissions.py`.
- [X] T022 [US2] Ajouter `list_groups` et le rendu du détail (`group_detail_view` peuplé par `group_repository.list_members`) dans `backend/app/services/auth/groups.py`. (dépend de T021)
- [X] T023 [US2] Ajouter `GET /admin/groups` et `GET /admin/groups/{group_id}` dans `backend/app/api/v1/admin_groups.py`, gardées par `require_permission(P.GROUPS_READ)`. (dépend de T022)

**Checkpoint** : les sept routes existent, les trois pouvoirs gardent chacun au
moins une ressource, et les deux filets de #115 sont toujours verts **et
intouchés**.

---

## Phase 5: User Story 4 — Un groupe n'accorde rien (Priority: P1)

**Goal** : verrouiller la borne de la v1 par un test, pour qu'elle ne cède pas en
silence. Aucune ligne de production n'est écrite dans cette phase — ce qui est
livré, c'est la **preuve d'une absence**.

**Independent Test** : donner à un utilisateur sans aucun rôle l'appartenance à
tous les groupes, et constater qu'il est refusé exactement sur les mêmes
ressources qu'avant.

### Tests for User Story 4

- [X] T024 [P] [US4] Créer `backend/tests/test_auth/test_groups_grant_nothing.py`, volet **comportemental** : un utilisateur sans rôle, membre de tous les groupes, reste refusé en 403 sur une ressource gardée, et `authorization.effective_permissions` le concernant rend l'ensemble **vide**.
- [X] T025 [US4] Dans le même fichier, volet **structurel (AST)** : ni `backend/app/api/deps.py` ni `backend/app/services/auth/authorization.py` ne nomment `Group`, `UserGroup`, `group_repository` ni le module `services.auth.groups`. Doubler d'une **garde du garde** — un arbre fabriqué qui *contient* la référence doit être détecté —, sur le patron de `test_permissions_catalogue.py`. Le docstring dit que ce test **doit** rougir le jour de la v2, et qu'on le supprimera alors sciemment.

**Checkpoint** : AC6 est tenu par deux tests de natures différentes. Le
comportemental protège le produit, le structurel protège la borne.

---

## Phase 6: User Story 3 — Savoir à quoi on appartient (Priority: P2)

**Goal** : `GET /auth/me` rend les groupes du porteur, en champ strictement
additif.

**Independent Test** : ajouter un utilisateur à deux groupes, ouvrir une session
en son nom, constater que sa description nomme les deux ; le retirer d'un groupe
et constater le changement **à la requête suivante**, sans reconnexion.

### Tests for User Story 3

- [X] T026 [P] [US3] Créer `backend/tests/test_auth/test_me_groups.py` : `GET /auth/me` rend les groupes du porteur ; un utilisateur sans appartenance obtient `groups: []` ; **aucun pouvoir n'est exigé** ; les clés existantes de la réponse sont **inchangées** (assertion sur l'ensemble des clés, pour prouver l'additivité au sens du Principe IV) ; un retrait d'appartenance est visible à l'appel suivant sans reconnexion.

### Implémentation for User Story 3

- [X] T027 [P] [US3] Ajouter `SessionGroupRead` (id, slug, name, organisation_id) et le champ `groups: list[SessionGroupRead] = []` à `SessionUserRead` dans `backend/app/schemas/auth.py`, avec un docstring qui dit ce que le champ **n'est pas** : il sert à écrire « membre du Codir », jamais à décider d'afficher un bouton — c'est `permissions` qui répond à cela.
- [X] T028 [US3] Peupler `groups` dans `GET /auth/me` (`backend/app/api/v1/auth.py`), depuis `user.groups`, sur le patron exact de `roles`. (dépend de T027)

**Checkpoint** : les quatre user stories sont livrées et testables séparément.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T029 [P] Ajouter une section « Groupes d'appartenance (#197) » à `backend/app/services/auth/AGENTS.md` : les deux tables, les **quatre** différences avec les rôles (dont l'organisation non nulle, absente de l'issue), le refus de supprimer un groupe peuplé, et la raison d'être du test d'AC6 avec la date de sa mort attendue (la v2).
- [X] T030 [P] Ajouter dans `backend/app/api/AGENTS.md`, sous « Protéger une ressource (#115) », deux phrases sur les sept routes de groupe : elles n'ajoutent aucun mécanisme, et `GET /auth/me` gagne `groups` sans exiger de pouvoir.
- [X] T031 Lancer `uv run ruff check .` depuis `backend/` et corriger ce qui remonte.
- [X] T032 Lancer `uv run pytest -m "not integration"` et comparer au compte de T001 : le delta doit être exactement le nombre de tests ajoutés, **aucun test existant modifié ni retiré**.
- [X] T033 Vérifier l'immobilité des deux filets de #115 : `git diff --stat main -- backend/tests/test_permissions_catalogue.py backend/tests/test_auth/test_public_routes_still_open.py` doit être **vide**. Une sortie non vide est un signal de conception, pas une formalité : la feature aurait plié le mécanisme au lieu de s'y inscrire.
- [ ] T034 **(partiellement fait — étapes 1, 2 et 7 vérifiées ; 3 à 6 exigent un parcours OAuth réel depuis l'espace de travail principal, impossible ici)** Dérouler `quickstart.md` de bout en bout sur l'espace de travail principal (le parcours OAuth n'accepte qu'une URL de retour), y compris l'étape 5 — la démonstration qu'un groupe n'accorde rien.
- [X] T035 Vérifier `uv run python -m app.cli grant-role --email <adresse> --role admin` puis la lecture de `GET /admin/permissions` : les trois pouvoirs de groupe y figurent sous « Groupes d'appartenance », et **ni `validator` ni `moderator` ne les ont reçus** — FR-041 de #115, aucune migration ne recompose un rôle semé.

---

## Phase 8: Revue de code (2026-08-06)

Issues d'une revue par sous-agent sur l'ensemble du working tree. Verdict initial
« With fixes » : 1 Critical, 5 Important, 7 Minor.

- [X] T036 **(Critical)** Corriger le rattrapage mort de l'`IntegrityError` dans `create_group` (`backend/app/services/auth/groups.py`) : le point de reprise entoure désormais l'**écriture** et non un `flush` d'après-coup — `group_repository.create` flushe lui-même. Couvert par un test qui neutralise la lecture préalable, et **éprouvé par mutation** : contre l'ancien code il rougit sur une `IntegrityError` nue (500).
- [X] T037 **(Important)** Élargir `DECISION_MODULES` de `test_groups_grant_nothing.py` de 2 à **6** fichiers — `session.py`, les deux repositories de rôles et `core/permissions.py` s'ajoutent. Sans eux, une v2 écrite un cran plus bas franchirait la borne en gardant le sommet cosmétiquement propre. Le lecteur AST voit en outre les imports renommés (`import … as raccourci`), avec sa garde du garde.
- [X] T038 **(Important)** Valider l'existence du club sur `POST /admin/groups` (`_existing_organisation`) : sans `PRAGMA foreign_keys=ON`, un `organisation_id` fantaisiste passait en SQLite et levait en PostgreSQL. 422 désormais, sur les deux moteurs.
- [X] T039 **(Important)** Aligner `POST /admin/groups` sur son contrat : `response_model=GroupDetailRead`, donc `members: []` comme annoncé. Les trois gestes qui portent sur un groupe précis rendent la même forme.
- [X] T040 **(Important)** Principe I — renommer en anglais les identifiants et les noms de tests des fichiers neufs (arbitrage utilisateur du 2026-08-06). Fait par renommage **de jetons `NAME`**, jamais par regex : la prose française des docstrings et les messages `DomainError` restent intacts. Les `argnames` de `parametrize`, qui sont des chaînes, ont été repris à la main.
- [X] T041 **(Important, hors #197)** Corriger le même défaut dans `authorization.create_role` (#115), avec son test de concurrence. Voir la levée de la règle 1 ci-dessus.
- [X] T042 **(Important)** Fermer l'écart entre le docstring de FR-009 et ses assertions : le test vérifie maintenant les **trois** clauses — autre appartenance, session toujours valide, rôle conservé.
- [ ] T043 **(Minor, non faits — assumés)** N+1 sur `GET /admin/groups` et sur `/auth/me` (volume borné, YAGNI), ordre non garanti de `groups` dans `/auth/me` (identique à `roles`), journal émis avant l'écriture dans `delete_group` (identique à `delete_role`), `PATCH {"description": null}` sans effet (hérité de `RoleUpdate`), `GroupInUseError.message` de classe inutilisé (identique à `RoleInUseError`). Aucun ne se corrige sans diverger du patron de #115 ; à traiter ensemble ou pas du tout.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** — sans dépendance.
- **Phase 2 (Foundational)** — dépend de la Phase 1. **Bloque toutes les stories.**
- **Phase 3 (US1)** — dépend de la Phase 2.
- **Phase 4 (US2)** — dépend de la Phase 2. Peut être menée en parallèle d'US1 par une autre personne, à une réserve près : T017 et T023 touchent le **même fichier** (`admin_groups.py`), et T015/T021 le même `permissions.py`. En solo, faire US1 puis US2.
- **Phase 5 (US4)** — dépend de la Phase 3 **au moins** (le volet comportemental a besoin d'une ressource gardée et d'un groupe à peupler).
- **Phase 6 (US3)** — dépend de la Phase 2 seule. Réellement indépendante des trois autres.
- **Phase 7 (Polish)** — dépend de tout le reste.

### Within Each User Story

- Les tests sont écrits **et rouges** avant l'implémentation.
- Modèles → repository → service → route. Aucune couche sautée (Principe II).
- Le pouvoir entre au catalogue **dans la même story** que la ressource qu'il garde.

### Parallel Opportunities

- T002, T003, T004 — trois fichiers de test distincts.
- T005, T006 — deux modèles, deux fichiers.
- T010 — DTO, indépendant du repository.
- T012, T013, T014 — trois volets, même fichier : parallélisables en **rédaction**, à fusionner en un seul fichier.
- T026 et T027 — fichiers distincts.
- T029 et T030 — deux fichiers de documentation.

---

## Parallel Example: Phase 2

```bash
# Les trois tests d'abord, en parallèle — tous rouges :
Task: "test_group_models.py — contraintes, non-nullité, cascade AC5"
Task: "test_group_repository.py — idempotence par SAVEPOINT, tri des membres"
Task: "test_migrations.py — les deux tables après upgrade head"

# Puis les deux modèles, en parallèle :
Task: "models/group.py"
Task: "models/user_group.py"
```

---

## Implementation Strategy

### MVP (US1 seule)

1. Phase 1 → Phase 2 → Phase 3.
2. **Arrêt et validation** : un exploitant tient la composition d'une commission
   par l'API. La lecture passe encore par la base — c'est ce qu'US2 corrige, et
   c'est pourquoi les deux sont P1.
3. Aucun déploiement intermédiaire n'est nécessaire : aucun écran ne consomme
   ces routes (épique #81).

### Livraison incrémentale

1. Phase 2 → le modèle existe, la surface HTTP est inchangée. **Déployable tel
   quel** : deux tables vides ne coûtent rien et le jalon de #197 est déjà tenu.
2. + US1 → composition administrable.
3. + US2 → « liste-moi les membres du Codir ».
4. + US4 → la borne de la v1 est verrouillée par un test.
5. + US3 → le porteur voit ses appartenances.

### Notes

- `[P]` = fichiers différents, aucune dépendance en cours.
- Un commit par tâche ou par groupe cohérent, en Conventional Commits.
- Vérifier que chaque test échoue **avant** d'écrire le code qu'il couvre.
- Ne jamais toucher `test_permissions_catalogue.py` ni
  `test_public_routes_still_open.py` : T033 le vérifie, et c'est le meilleur
  signal disponible que la feature s'inscrit dans le mécanisme de #115 au lieu
  de le plier.
