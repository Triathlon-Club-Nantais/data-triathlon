# Tasks: RBAC — rôles composables et protection des ressources d'administration

**Input**: `specs/20260804-214724-auth-rbac-roles/`

**Prerequisites**: [plan.md](plan.md) (v3), [spec.md](spec.md) (v3, 42 FR),
[research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests** : le Principe III de la constitution v1.1.0 est **non-négociable**.
Chaque tâche d'implémentation est précédée de sa tâche de test, et **ces tests
doivent échouer avant** que l'implémentation ne soit écrite. Aucun réseau : ce
périmètre n'en a pas, et c'est ce qui a disqualifié les moteurs de politiques
externes (`research.md` §D2).

**Organization**: par user story, chaque phase étant un incrément livrable et
testable seul.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable — fichier distinct, aucune dépendance sur une tâche inachevée
- **[Story]** : US1…US5, d'après `spec.md`
- Chemins de fichiers exacts, depuis la racine du dépôt

## Path Conventions

Application web existante : `backend/app/`, `backend/tests/`, `frontend/`.
Aucune structure à créer.

---

## Deux règles qui priment sur toute tâche ci-dessous

1. **Aucune migration ne recompose un rôle déjà semé** (FR-041). Une seule
   révision Alembic existe dans tout ce plan, T009. Si l'exécution fait naître
   une seconde révision écrivant dans `role_permissions` pour `admin`,
   `validator` ou `moderator`, c'est une tâche à supprimer, pas à exécuter.
2. **Aucune garde n'est posée globalement ni par préfixe** (FR-018).
   `POST /admin/pending-providers` est le signalement anonyme du site public :
   une garde de préfixe supprimerait la fonctionnalité sans que rien ne la nomme.

---

## Phase 1: Setup

**Purpose** : établir la ligne de base rouge/vert avant toute modification.

- [ ] T001 Vérifier la ligne de base : `cd backend && uv run pytest -m "not integration"` et `cd frontend && npm test` sont **verts** avant la première modification. Consigner le nombre de tests dans le message du premier commit — c'est la seule façon de distinguer plus tard « test cassé par la feature » de « test déjà rouge ».

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose** : le schéma, le catalogue et le mécanisme de décision. **Aucune user
story ne peut commencer avant.** Rien de ce qui suit n'est visible d'un
utilisateur : à la fin de cette phase, aucune route n'a changé de comportement.

### Le catalogue de pouvoirs

- [ ] T002 [P] Écrire `backend/tests/test_core/test_permissions.py` : le catalogue expose exactement les neuf codes du contrat (`roles:read`, `roles:write`, `roles:assign`, `users:read`, `pending_providers:read`, `pending_providers:handle`, `quality:override`, `participations:write`, `participations:delete`), chacun avec un libellé et une description **en français** et une fonctionnalité de rattachement ; chaque code suit la forme `<domaine>:<geste>` (FR-040) ; la structure est immuable (dataclass gelée) et ne fait aucun accès base ni réseau.
- [ ] T003 Créer `backend/app/core/permissions.py` (FR-001, FR-002, FR-014) : dataclass gelée, catalogue groupé par fonctionnalité, plus l'accès par code. Aucune session, aucun état — c'est ce qui autorise `core/` (Principe II). C'est ce fichier qui matérialise la distinction pouvoir / rôle / attribution : le pouvoir est **ici**, le rôle et l'attribution sont en base. Ajouter un pouvoir consiste à ajouter un membre — **aucune migration** (FR-014), la base ne stockant que les codes portés par les rôles.

### Modèles et migration

- [ ] T004 [P] Écrire `backend/tests/test_auth/test_rbac_models.py` : `UNIQUE(organisation_id, slug)` sur `roles` ; deux rôles **globaux** de même slug sont refusés (index partiel `WHERE organisation_id IS NULL`) ; deux rôles de même slug dans **deux organisations** sont acceptés ; `UNIQUE(user_id, role_id, organisation_id)` sur `user_roles` ; supprimer un utilisateur emporte ses attributions (FR-013) ; `users` **ne porte toujours aucune colonne de rôle** — vérifié sur le schéma appliqué, pas sur le modèle, comme le test équivalent de #114.
- [ ] T005 [P] Créer `backend/app/models/organisation.py` : `id`, `slug` UNIQUE, `name`, `created_at`.
- [ ] T006 [P] Créer `backend/app/models/role.py` : colonnes de `data-model.md`, **les deux** contraintes d'unicité déclarées dans `__table_args__` — `UniqueConstraint("organisation_id", "slug")` **et** l'`Index` partiel unique sur `slug` avec `sqlite_where=` **et** `postgresql_where=`. Les deux dialectes sont obligatoires : n'en donner qu'un produit un index *complet* sur l'autre moteur, ce qui interdirait silencieusement un même slug dans deux organisations. Et `__table_args__` plutôt que la seule migration, parce que `tests/conftest.py` construit le schéma par `create_all`.
- [ ] T007 [P] Créer `backend/app/models/role_permission.py` : `role_id` FK indexé, `permission_code` **chaîne indexée, sans clé étrangère**, `UNIQUE(role_id, permission_code)`. Le code porté par un rôle est bien une donnée en base ; ce qui n'existe pas, c'est une table `permissions` listant les codes possibles — décision structurante, `research.md` §D3, précisée par la clarification du 2026-08-05.
- [ ] T008 Créer `backend/app/models/user_role.py` (`organisation_id` **non nul**) et ajouter `User.roles` dans `backend/app/models/user.py` avec `cascade="all, delete-orphan"`, sans `ondelete` — `core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`, la contrainte serait inerte en SQLite et active en PostgreSQL ; la cascade ORM couvre les deux.
- [ ] T009 Créer la révision Alembic `backend/alembic/versions/<rev>_rbac_and_manual_reliability.py` (`down_revision = "d5e6f7a8b9c0"`) : les 4 tables, le semis d'une organisation (`tcn`) et des **trois** rôles système (`admin` superutilisateur, `validator` → `quality:override`, `moderator` → `pending_providers:read` + `pending_providers:handle`), **plus** le renommage `courses.is_reliable` → `is_reliable_computed` et l'ajout de `courses.reliability_override` (`batch_alter_table`, `render_as_batch=True` est déjà actif).
- [ ] T010 Mettre à jour `backend/tests/test_migrations.py` : les trois assertions portant sur `is_reliable` visent désormais `is_reliable_computed` **et** `reliability_override` ; ajouter que la migration sème exactement trois rôles, que `moderator` porte ses **deux** codes et qu'`admin` est le seul `is_superuser`.

### Le verdict de fiabilité — deux colonnes, une propriété

*Ici et non en US5 : le modèle doit suivre la migration dans le même incrément,
sans quoi l'ORM lit une colonne qui n'existe plus.*

- [ ] T011 [P] Écrire `backend/tests/test_repositories/test_course_reliability.py` : `is_reliable` rend `reliability_override` quand elle est posée, `is_reliable_computed` sinon, `None` quand les deux le sont ; l'expression est utilisable dans un `WHERE` (filtrer en SQL sur `Course.is_reliable`) ; poser puis lever l'override fait réapparaître le **dernier** verdict calculé, pas celui qui valait au moment de la décision humaine (FR-039).
- [ ] T012 Modifier `backend/app/models/course.py` : `is_reliable` devient `is_reliable_computed`, ajouter `reliability_override`, et `is_reliable` devient une `hybrid_property` `coalesce(reliability_override, is_reliable_computed)` **avec son `@expression`** — sans lui elle serait illisible en SQL.
- [ ] T013 Répercuter le renommage sur les trois seuls sites d'écriture relevés : `backend/app/repositories/course_repository.py:99-102` (paramètre et affectation), `backend/app/services/import_service.py:318` (mot-clé passé à `set_quality`). `backend/app/schemas/course.py` **ne change pas** : `from_attributes=True` lit une propriété comme une colonne (FR-038).

### Repositories et décision d'accès

- [ ] T014 [P] Écrire `backend/tests/test_repositories/test_role_repositories.py` : résolution d'un rôle par slug et par portée, comptage des porteurs, comptage des superutilisateurs **actifs** d'une organisation (un compte désactivé ne compte pas), attribution idempotente sous contrainte d'unicité.
- [ ] T015 [P] Créer `backend/app/repositories/role_repository.py` et `backend/app/repositories/user_role_repository.py` — **seule couche qui touche la `Session`** (Principe II).
- [ ] T016 [P] Ajouter `list_all` et `find_by_email` à `backend/app/repositories/user_repository.py`. `find_by_email` rend une **liste** : `users.email` n'est pas unique, délibérément (#114, FR-003), et rendre un scalaire rouvrirait le choix au hasard que `grant-role` doit refuser.
- [ ] T017 [P] Écrire `backend/tests/test_services/test_authorization.py` : les pouvoirs effectifs sont l'**union** des rôles portés (Edge Case « un utilisateur porte plusieurs rôles ») ; un rôle `is_superuser` franchit un code **absent de tous ses `role_permissions`**, y compris un code inventé après coup (FR-009, SC-006 — c'est ce qui garantit qu'une livraison n'exige ni migration ni recochage, FR-014) ; un code présent en base mais **absent du catalogue** n'accorde rien et ne fait pas lever (FR-042) ; la décision relit la base à chaque appel et ne met rien en cache (FR-016).
- [ ] T018 Créer `backend/app/services/auth/authorization.py` : `has_permission`, `effective_permissions`, `count_active_superusers`. Rien d'autre pour l'instant — le CRUD arrive en US3, l'invariant en US4.
- [ ] T019 [P] Écrire `backend/tests/test_auth/test_require_permission.py` : une requête **sans session** sur une ressource gardée rend **401**, une session **sans le pouvoir** rend **403**, et les deux ne se confondent jamais (FR-015) ; le corps du 403 est un message **français** qui ne nomme ni le pouvoir exigé ni ceux portés (FR-019) ; un compte désactivé rend 401 et non 403, la session étant déjà tombée.
- [ ] T020 Ajouter `require_permission(code)` et `InsufficientPermissionError` (403) à `backend/app/api/deps.py`. La fabrique **compose `current_user`** : c'est ce qui rend l'ordre 401-avant-403 structurel et non défensif — une requête sans session n'atteint jamais le contrôle de pouvoir.
- [ ] T021 Journaliser un refus pour pouvoir insuffisant avec l'identifiant de l'utilisateur et la ressource visée (FR-034), en anglais, sans jeton ni secret (FR-035) — dans `backend/app/api/deps.py`, sur le patron de `services/auth/`.

**Checkpoint** : la suite est verte, `uv run alembic upgrade head` passe, et
**aucune route n'a changé de comportement**. `git diff` ne touche aucun fichier
de `app/api/v1/`.

---

## Phase 3: User Story 1 — Fermer les ressources d'administration (P1)

**Goal** : les ressources d'administration et les deux routes destructives
exigent un pouvoir ; le signalement public et tout le site public sont intacts.

**Independent Test** : sur `/admin/pending-providers`, obtenir 401 anonyme,
403 connecté sans pouvoir, 200 avec le pouvoir ; poster un signalement **sans
cookie** et obtenir 201 ; parcourir les six pages publiques sans redirection.

### Tests (écrire d'abord — ils doivent échouer)

- [ ] T022 [P] [US1] Réécrire `backend/tests/test_auth/test_public_routes_still_open.py` (FR-024, FR-025, SC-001, SC-002). Il n'interdit plus tout refus : il exige que **toute** ressource sous `/api/v1/admin/` soit soit gardée, soit **déclarée publique nommément**, et que toute autre route existante réponde sans session. Une ressource d'administration ajoutée sans classement doit faire rougir la suite **en nommant la route**. Ajouter en docstring ce que ce filet ne prouve **plus** : avec la politique en base, il établit qu'une ressource exige *un* pouvoir, jamais *qui* le porte — prix assumé de l'édition à chaud.
- [ ] T023 [P] [US1] (SC-009) Écrire `backend/tests/test_permissions_catalogue.py` : lecteur d'**AST** dans **trois** sens (patron de `tests/test_core_http.py`). Les deux premiers tiennent FR-026 — aucun pouvoir du catalogue n'est cité par zéro garde, et aucune garde ne cite un code absent du catalogue. C'est le seul filet contre le couplage par chaîne : `require_permission("pending_providres")` refuserait tout le monde, en silence. Le troisième tient **FR-031** : aucune route classée publique, et aucune route n'exigeant qu'une session, n'écrit dans `roles`, `role_permissions` ou `user_roles`. La propriété tient aujourd'hui par construction — les deux ressources qui distribuent des pouvoirs sont gardées, `GET /auth/me` ne fait que lire, `POST /admin/pending-providers` n'accorde rien — mais rien ne la **retient** : c'est l'invariant qui se perd à la route suivante, et qui ne se rattrape pas après coup.
- [ ] T024 [P] [US1] (SC-004) Écrire dans `backend/tests/test_auth/test_admin_guards.py` les trois issues de `GET /admin/pending-providers` et de `DELETE /admin/pending-providers/{id}` : 401, 403, succès.
- [ ] T025 [P] [US1] (SC-003) Écrire dans le même fichier les trois issues de `POST /participations` et `DELETE /participations/{id}` (FR-023), **et** un test nommé qui vérifie que `POST /admin/pending-providers` répond **sans aucun cookie** (FR-022) — c'est le fait de terrain qui interdit la garde de préfixe.

### Implémentation

- [ ] T026 [US1] (FR-021) Poser `require_permission(P.PENDING_PROVIDERS_READ)` et `…_HANDLE` sur les deux routes de `backend/app/api/v1/admin.py`, **sans toucher** à `POST /admin/pending-providers`.
- [ ] T027 [US1] Poser `require_permission(P.PARTICIPATIONS_WRITE)` et `…_DELETE` sur `POST /participations` et `DELETE /participations/{id}` dans `backend/app/api/v1/participations.py`. Ces deux routes sont **ouvertes à Internet aujourd'hui** (`db.delete(row)` puis `db.commit()` sans aucune garde, lignes 105-113) : c'est le correctif de sécurité de la feature.
- [ ] T028 [US1] Conserver telles quelles, dans `backend/tests/test_auth/test_public_routes_still_open.py`, les deux assertions de #114 qui interdisent la garde globale : `app.router.dependencies == []` et, router par router y compris `admin`, `module.router.dependencies == []` (FR-018). La réécriture de T022 change le reste du fichier ; ces deux lignes ne bougent pas.

**Checkpoint** : US1 est livrable seule. Les ressources d'administration sont
fermées, le site public est intact — mais **personne ne peut encore les
franchir** : c'est l'objet d'US2.

---

## Phase 4: User Story 2 — Amorcer le premier administrateur hors ligne (P1)

**Goal** : sur une installation neuve, une commande attribue le premier rôle sans
session, sans requête HTTP, sans écriture manuelle en base.

**Independent Test** : `grant-role --email <adresse inconnue> --role admin` sort
en **2** ; après une connexion par l'interface, la même commande sort en **0**,
et une seconde fois en **0** en disant « rien à faire ».

### Tests

- [ ] T029 [P] [US2] (SC-008) Écrire `backend/tests/test_cli/test_grant_role.py` : attribution → **0** ; ré-attribution → **0** avec un rapport « rien à faire » (FR-029) ; adresse inconnue → **2**, en expliquant qu'un utilisateur naît d'une connexion et non d'une commande (FR-028) ; slug de rôle inconnu → **2** en **nommant les rôles existants** ; rôle propre à une autre organisation → **2** en nommant l'organisation ; **adresse ambiguë** → **2** avec la liste des candidats (FR-030) — ce cas n'est pas d'école, `users.email` n'est pas unique.
- [ ] T030 [P] [US2] (SC-010) Ajouter au même fichier : le rapport texte sort sur **stdout**, les journaux sur **stderr** (`configure_cli_logging`), et l'attribution est journalisée avec acteur, cible, rôle et sens (FR-033).

### Implémentation

- [ ] T031 [US2] (FR-027) Créer `backend/app/cli/commands/grant_role.py` — **couche mince**, zéro logique métier : elle délègue à `services/auth/authorization` et aux repositories. `--organisation` vaut par défaut l'unique organisation semée.
- [ ] T032 [US2] Enregistrer la commande dans `backend/app/cli/__init__.py` : `app.command("grant-role")(grant_role)`, à la suite des trois existantes.
- [ ] T033 [US2] Documenter dans `backend/README.md` et dans la section « Commandes » d'`AGENTS.md` : `uv run python -m app.cli grant-role --email <adresse> --role <slug>`. Nommer les deux contournements délibérés — elle **n'applique pas** la non-amplification (l'accès au serveur *est* le privilège) et **n'est pas soumise** à l'invariant du dernier administrateur (elle ne fait qu'accorder).

**Checkpoint** : la couche 1 du plan est complète. US1 + US2 livrées ensemble
donnent une installation où l'administration est fermée et franchissable.

---

## Phase 5: User Story 3 — Composer un rôle sans redéploiement (P1)

**Goal** : créer un rôle, le composer dans une liste de pouvoirs rangée par
fonctionnalité, et l'attribuer — sans redéploiement, effectif à la requête
suivante du porteur.

**Independent Test** : créer un rôle, lui donner un pouvoir, l'attribuer ;
le porteur franchit la ressource correspondante et **aucune autre** ; retirer le
pouvoir du rôle et constater le refus **à la requête suivante, sans reconnexion**.

### Tests

- [ ] T034 [P] [US3] Écrire `backend/tests/test_auth/test_admin_roles_api.py` (FR-004) — parcours nominal des sept ressources de `contracts/admin-api.md` : inventaire des pouvoirs, liste et détail des rôles, création, modification, suppression, liste des utilisateurs, attribution et retrait. Deux propriétés à assurer nommément dans ce parcours : **renommer** un rôle porté par deux personnes ne perd **aucune** attribution (FR-005 — c'est la justification même de `role_id` plutôt que `role`), et **réattribuer** un rôle déjà porté est un **succès**, jamais une violation d'unicité remontée en 500 (FR-012, edge case des deux exploitants simultanés).
- [ ] T035 [P] [US3] Ajouter les refus au même fichier : `slug` soumis à `PATCH` → **422** (immuable) ; code hors catalogue → **422** ; rôle `is_system` supprimé → **409** ; rôle encore attribué supprimé → **409** **en nommant le nombre de porteurs** (FR-007) ; rôle propre à une organisation attribué dans une autre → **422** (FR-008) ; slug déjà pris dans la même portée → **409**. Et la moitié de FR-006 que le refus fait oublier : un rôle `is_system` **accepte** `PATCH` sur son libellé, sa description et ses pouvoirs — livré ne veut pas dire figé.
- [ ] T036 [P] [US3] Écrire `backend/tests/test_auth/test_stale_permissions.py` (FR-042) : un `role_permissions` portant un code absent du catalogue n'accorde rien, ne fait pas lever la décision d'accès, et ressort dans `stale_permissions` — jamais dans `permissions` — à la lecture du rôle. **Puis les deux cas qui rendent ce code purgeable** : un `PATCH` omettant le code périmé **aboutit** (c'est le seul moyen de purge, il n'existe aucune ressource dédiée), et le rôle qui le porte reste **attribuable**. Les deux valent y compris pour une session superutilisateur — dont les pouvoirs effectifs *sont* le catalogue, donc qui ne porte pas plus ce code que les autres.
- [ ] T037 [P] [US3] Écrire `backend/tests/test_auth/test_no_privilege_escalation.py` (FR-011) : une session portant `roles:write` **sans** `participations:delete` ne peut ni créer un rôle portant ce code, ni l'ajouter par `PATCH`, ni le retirer, ni attribuer un rôle qui le porte → **403** dans les quatre cas. Sans cette règle, `roles:write` équivaut à `root`. **La règle est bornée à l'inventaire** : le même test doit vérifier qu'un code **périmé** échappe aux quatre contrôles — le comparer gèlerait le rôle définitivement (T036). Et un superutilisateur n'est jamais bloqué sur un code de l'inventaire, c'est ce qui rend la délégation possible.
- [ ] T038 [P] [US3] Écrire `backend/tests/test_auth/test_me_permissions.py` (FR-020) : `GET /auth/me` rend les champs de #114 **inchangés**, plus `permissions` (codes effectifs) et `roles` (id, slug, name, organisation_id) ; la lecture **n'exige aucun pouvoir** ; un connecté sans rôle obtient deux listes vides et **non** un 403 ; et le même compte reçoit **403** sur `GET /admin/permissions`, qui exige `roles:read` (FR-003).
- [ ] T039 [P] [US3] Ajouter à `backend/tests/test_services/test_authorization.py` : un changement de composition de rôle est effectif **à la requête suivante** de tous les porteurs, sans reconnexion, et **leur session reste valide** — retirer un pouvoir n'est pas déconnecter quelqu'un (SC-005, Edge Case).

### Implémentation

- [ ] T040 [P] [US3] Créer `backend/app/schemas/admin.py` : DTO d'entrée et de sortie des rôles, des attributions et de l'inventaire, exactement aux formes de `contracts/admin-api.md`.
- [ ] T041 [US3] Étendre `backend/app/services/auth/authorization.py` du CRUD des rôles, de la validation des codes **soumis** contre le catalogue (422), de `assert_role_assignable_in()` (FR-008 croise deux tables — c'est un contrôle de service, aucun SQL portable ne l'exprime) et de la règle de non-amplification. Cette dernière **n'intersecte que le catalogue** : `(codes_visés & catalogue) - pouvoirs_de_l_appelant`. L'intersection n'est pas une précaution, c'est la condition de réversibilité — sans elle, un code périmé n'est retirable par personne et gèle son rôle pour toujours.
- [ ] T042 [US3] Créer `backend/app/api/v1/admin_roles.py` — sept routes, chacune portant sa garde **individuellement** et nommant un **pouvoir**, jamais un rôle (FR-017).
- [ ] T043 [US3] Monter le router dans `backend/app/api/v1/router.py` **sans `dependencies=`** (FR-018).
- [ ] T044 [US3] Enrichir `SessionUserRead` dans `backend/app/schemas/auth.py` de `permissions` et `roles`, et la route `GET /auth/me` de `backend/app/api/v1/auth.py`. Ajout **additif** : la docstring de #114 l'annonce déjà comme non cassant au sens du Principe IV. Les deux champs sont nécessaires et ne se déduisent pas l'un de l'autre — `permissions` décide de l'affichage d'un bouton, `roles` permet d'écrire « connecté en tant qu'administrateur » sans un second appel que `GET /admin/roles` refuserait.
- [ ] T045 [US3] Journaliser toute création, modification et suppression de rôle, et toute attribution ou retrait, avec acteur, cible et sens (FR-033) — en anglais, sans jeton (FR-035).

**Checkpoint** : US3 est livrable. Un exploitant compose des rôles à chaud — mais
rien ne l'empêche encore de se verrouiller dehors.

---

## Phase 6: User Story 4 — Ne jamais fermer la porte de l'intérieur (P1)

**Goal** : aucune séquence d'opérations effectuée **depuis l'application** ne peut
laisser une organisation sans administrateur actif.

**Independent Test** : avec le compte du seul administrateur, les quatre chemins
de verrouillage rendent **409** ; après avoir nommé un second administrateur, les
quatre aboutissent.

**Dependencies** : US3 — les quatre sites d'appel sont ses ressources.

### Tests

- [ ] T046 [P] [US4] (SC-007) Écrire `backend/tests/test_auth/test_lockout_invariant.py` : avec un **unique** administrateur actif, retirer son attribution → **409** ; supprimer le rôle qui le rend administrateur → **409** ; décocher `is_superuser` sur ce rôle → **409**. Avec **deux** administrateurs, les trois aboutissent.
- [ ] T047 [P] [US4] Ajouter la **symétrique**, qui doit aboutir : avec deux administrateurs, l'un retire à l'autre son caractère d'administration → succès (FR-010). Poser et retirer sont la même règle ; un 403 ici serait un garde défensif de trop, et il enfermerait l'installation dans une composition qu'on ne pourrait plus défaire.
- [ ] T048 [P] [US4] Ajouter le cas du compte **désactivé** : un administrateur désactivé ne compte pas comme actif, donc retirer le rôle du seul administrateur restant est refusé même si la table `user_roles` en montre deux.

### Implémentation

- [ ] T049 [US4] (FR-032) Ajouter `assert_organisation_keeps_an_admin(db, organisation_id)` à `backend/app/services/auth/authorization.py` : elle juge l'**état d'arrivée**, après `flush` et avant `commit`, et rend **409**. Une seule définition — garder les *chemins* laisserait passer le cinquième chemin qu'on ajoutera demain.
- [ ] T050 [US4] L'appeler sur les quatre sites de `backend/app/api/v1/admin_roles.py` et `backend/app/services/auth/authorization.py`. Le `409` porte sur l'état de la ressource : l'appelant *est* administrateur, sa requête est bien formée, c'est le résultat qui est interdit — d'où 409 et non 403.

**Checkpoint** : la couche 2 du plan est complète. US3 + US4 donnent l'édition à
chaud **sûre**.

---

## Phase 7: User Story 5 — Le pouvoir de trancher la qualité (P2)

**Goal** : un porteur du pouvoir de qualité fixe à la main le verdict de fiabilité
d'une épreuve, sans pouvoir supprimer une donnée ni distribuer un rôle.

**Independent Test** : marquer une épreuve douteuse comme fiable, constater que
les trois champs **divergent**, re-scraper l'épreuve et constater que le verdict
humain a survécu.

**Dependencies** : Foundational (T012 a déjà posé les colonnes et la propriété
hybride). Indépendante d'US3 et d'US4.

### Tests

- [ ] T051 [P] [US5] Écrire `backend/tests/test_services/test_course_review.py` : poser, changer et **lever** l'avis humain ; la levée fait reprendre le **dernier** verdict calculé, pas celui qui valait au moment de la décision (FR-039).
- [ ] T052 [P] [US5] Écrire dans `backend/tests/test_api/test_course_reliability_api.py` : `PATCH /admin/courses/{id}/reliability` rend les **trois** champs (`is_reliable`, `is_reliable_computed`, `reliability_override`) ; 401 anonyme, 403 sans `quality:override` ; et un porteur du seul `quality:override` reçoit **403** sur `GET /admin/users` et sur `DELETE /admin/pending-providers/{id}` — c'est la démonstration que deux rôles ont deux périmètres réellement différents.
- [ ] T053 [P] [US5] Écrire un test de non-régression du re-scrape : un import ré-écrit `is_reliable_computed` et `quality_issues`, et **ne touche pas** `reliability_override` (FR-037). Les deux chemins d'écriture ne se croisent pas — ce test constate l'absence de garde applicative, il n'en éprouve aucune.
- [ ] T054 [P] [US5] Écrire un test de contrat public (FR-038) : `GET /courses/{id}` et les listes exposent toujours `is_reliable`, sous le même nom et la même sémantique, sans les deux champs internes — ceux-ci n'apparaissent **que** sur la ressource de revue.

### Implémentation

- [ ] T055 [US5] (FR-036) Créer `backend/app/services/course_review.py` : poser et lever l'avis humain. Aucune branche, aucun recalcul — la propriété hybride fait le travail.
- [ ] T056 [US5] Ajouter `PATCH /admin/courses/{course_id}/reliability` à `backend/app/api/v1/admin.py`, gardée par `require_permission(P.QUALITY_OVERRIDE)`, avec son DTO dans `backend/app/schemas/admin.py`.

**Checkpoint** : la couche 3 est complète et livrable seule.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T057 [P] Corriger `frontend/components/admin/PendingProvidersTable.tsx` : distinguer le refus de la liste vide. Le composant ne lit aujourd'hui que `isLoading` et `data` ; sur un 403, `data` est `undefined` et il affiche « Aucun fournisseur signalé » — **un écran qui ment**. `ApiError` porte déjà `status`.
- [ ] T058 [P] Écrire `frontend/components/admin/PendingProvidersTable.test.tsx` : un 403 rend un message de refus explicite, un 200 vide rend « aucun signalement », et les deux ne se confondent pas.
- [ ] T059 [P] Supprimer `apiServer.listPendingProviders` de `frontend/lib/api/server.ts:90` : aucun appelant, et elle passe par `serverFetch`, qui ne relaie pas les cookies. Supprimée plutôt que laissée mûrir en 403.
- [ ] T060 [P] Documenter la feature dans les `AGENTS.md` **par chemin** — le fichier racine a été découpé sur `main` (`1352ffd`), la documentation ne s'ajoute donc plus en un seul endroit : `backend/app/services/auth/AGENTS.md` reçoit une section « Autorisation (#115) » à la suite de « Authentification (#114) » (le gros du texte : `is_superuser`, invariant sur l'état, non-amplification bornée à l'inventaire, trois rôles semés, FR-041, FR-042 et la limite que le filet ne prouve plus) ; `backend/app/models/AGENTS.md` les quatre tables et les deux colonnes de `courses` ; `backend/app/core/AGENTS.md` le catalogue de `permissions.py` ; `backend/app/api/AGENTS.md` `require_permission` et l'ordre 401-avant-403 ; `backend/app/cli/AGENTS.md` la commande `grant-role`.
- [ ] T061 Dérouler `quickstart.md` de bout en bout, les treize étapes, sur l'espace de travail **principal** — l'application OAuth GitHub n'accepte qu'une seule URL de retour, port compris, et `next dev` d'un second worktree atterrit sur `:3001` sans le dire.
- [ ] T062 Vérifier la ligne de base finale : `uv run pytest -m "not integration"`, `uv run ruff check .`, `npm test`, `npm run build`, et `uv run alembic upgrade head` sur une base neuve **puis** sur une base peuplée (le renommage de colonne porte des données en place).

---

## Dependencies & Execution Order

### Par phase

```
Phase 1 (Setup)
   └─▶ Phase 2 (Foundational) ─── BLOQUANTE pour tout le reste
          ├─▶ Phase 3 (US1) ─▶ Phase 4 (US2)        ← couche 1 du plan
          ├─▶ Phase 5 (US3) ─▶ Phase 6 (US4)        ← couche 2
          └─▶ Phase 7 (US5)                          ← couche 3
                 └─────────────▶ Phase 8 (Polish)    ← couche 4 + docs
```

**US2 dépend d'US1** non pas techniquement mais par le sens : `grant-role` sans
porte fermée n'attribue rien d'observable. Les deux forment la couche 1 et se
livrent ensemble.

**US4 dépend d'US3** : ses quatre sites d'appel sont les ressources d'US3.

**US5 est indépendante d'US3 et d'US4** : elle ne dépend de la phase 2 que par la
garde et par les deux colonnes.

**Le filet change de nature dans le même incrément que la première route fermée**
(T022 avec T026/T027) — un filet rouge qu'on tolère est un filet mort.

### Tâches parallélisables

**Phase 2** — T004 à T008 touchent cinq fichiers de modèles distincts ; T014 à
T017 quatre fichiers distincts. T009 (migration) est un point de synchronisation :
elle attend tous les modèles.

**Phase 3** — les quatre tâches de test (T022-T025) sont parallèles entre elles ;
les deux implémentations (T026, T027) le sont aussi, fichiers distincts.

**Phase 5** — les six tâches de test (T034-T039) sont parallèles. Côté
implémentation, seule T040 l'est : T041 à T045 se suivent, T042 dépendant de T041
et T043 de T042.

**Phase 8** — T057 à T060 sont toutes parallèles (front, front, front, docs, docs).

### Contre-exemple à ne pas paralléliser

T026 et T022 **ne** sont **pas** parallèles malgré des fichiers distincts : le
filet réécrit doit être rouge, puis vert, dans le même mouvement que la garde.
Les séparer produit un intervalle où la suite est verte pour la mauvaise raison.

---

## Implementation Strategy

**MVP** : phases 1, 2, 3 et 4 — soit **T001 à T033**. À ce point, les ressources
d'administration et les deux routes destructives sont fermées, le site public est
intact, et l'exploitant s'attribue le premier rôle depuis le serveur. C'est la
couche 1 du plan, et c'est ce qui **referme l'anomalie de sécurité** : deux
routes qui permettent aujourd'hui de créer et de supprimer des résultats sans
aucune authentification.

**Incrément suivant** : phases 5 et 6 (T034-T050) — l'exigence produit qui a
rouvert la spec, avec son garde-fou.

**Puis** : phase 7 (T051-T056), indépendante, et phase 8.

**Ce que ce plan ne livre pas, et qui est écrit** : aucun écran d'administration
des rôles (différés à la sous-issue d'interface de #81), aucun cloisonnement des
données par club, aucun groupe d'appartenance (#197), aucune vérification en
PostgreSQL — la suite tourne sur SQLite et l'index partiel n'y est éprouvé que
sur un moteur, comme `unaccent` de #163.
