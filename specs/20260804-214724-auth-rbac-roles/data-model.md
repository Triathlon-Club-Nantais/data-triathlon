# Phase 1 — Modèle de données

**Feature** : RBAC — rôles composables · **Révisé** : 2026-08-05 (v3)

Quatre tables nouvelles, deux colonnes sur `courses`. Aucune table de #114 n'est
modifiée.

---

## Vue d'ensemble

```
organisations ──┬──< roles ──< role_permissions        (permission_code : chaîne, pas de FK)
                │      │
                └──< user_roles >── users              (attribution)
```

**Le pouvoir n'est pas dans ce schéma.** Il vit dans l'application
(`core/permissions.py`) et la base n'en stocke que le code. C'est la décision
centrale du modèle, démontrée plus bas.

---

## `organisations`

| Colonne | Type | Contraintes |
| --- | --- | --- |
| `id` | entier | PK |
| `slug` | chaîne | **UNIQUE**, non nul |
| `name` | chaîne | non nul |
| `created_at` | horodatage | défaut `utcnow` |

Une ligne semée par la migration : `('tcn', 'Triathlon Club Nantais')`.

**Pourquoi la créer maintenant alors qu'une seule ligne existera.** Pas pour la
raison qu'on croit : l'argument « ajouter une clé étrangère plus tard coûte un
`batch_alter_table` sur SQLite » a été **mesuré et réfuté** — `alembic/env.py:33`
porte déjà `render_as_batch=True`, 5 des 8 révisions existantes l'emploient, et
l'ajout après coup coûte 6 lignes et 8 ms sur 200 lignes, index préservés.

La vraie raison est une **décision produit** (2026-08-04, « modèle maintenant,
usage plus tard ») et un gain technique précis : elle permet
`user_roles.organisation_id` **non nul**, ce qui supprime le piège des deux index
d'unicité qu'imposerait une colonne nullable (voir plus bas).

**Ce que cette table ne portera jamais** : de la donnée sportive. `Course` est
unique par `(name, event_date, event_type, is_relay)` — deux clubs important la
même épreuve obtiennent **la même ligne**. Y ajouter une organisation casserait
la déduplication ou dupliquerait des milliers de participations par club.

---

## `roles`

| Colonne | Type | Contraintes | Sens |
| --- | --- | --- | --- |
| `id` | entier | PK | Ce que référence l'attribution — **jamais le nom**. |
| `organisation_id` | entier, **nullable** | FK → `organisations.id`, indexé | `NULL` = rôle partagé par toutes les organisations. Renseigné = propre à celle-là. |
| `slug` | chaîne | non nul, **immuable** | Le seul nom qui traverse une frontière (`grant-role --role`, seed). |
| `name` | chaîne | non nul | Libellé affiché, **libre et renommable**. |
| `description` | chaîne | défaut `""` | |
| `is_system` | booléen | non nul, défaut `false` | Semé par la migration : non supprimable, slug figé. |
| `is_superuser` | booléen | non nul, défaut `false` | Franchit tout pouvoir, **y compris ceux pas encore écrits**. |
| `created_at` | horodatage | défaut `utcnow` | |

**Deux contraintes d'unicité, pas une** — et c'est un piège réel :

```python
UniqueConstraint("organisation_id", "slug", name="uq_role_org_slug"),
Index("uq_role_global_slug", "slug", unique=True,
      sqlite_where=text("organisation_id IS NULL"),
      postgresql_where=text("organisation_id IS NULL")),
```

SQLite comme PostgreSQL tiennent deux `NULL` pour **distincts** : la première
contrainte laisse passer deux rôles globaux de même slug. L'index partiel est la
seule forme qui couvre le cas, et **les deux dialectes doivent être renseignés** —
n'en donner qu'un produit un index *complet* sur l'autre moteur, ce qui
interdirait silencieusement un même slug dans deux organisations.

**Ces index vivent dans `__table_args__`, pas seulement dans la migration** :
`tests/conftest.py` construit le schéma par `Base.metadata.create_all`, jamais
par Alembic. Un index déclaré uniquement dans la révision n'existerait dans aucun
test.

### `is_superuser` — pourquoi ce booléen vaut une table

C'est lui qui referme la seule objection sérieuse aux rôles en base : *« une
fonctionnalité livrée mardi n'est administrable que si quelqu'un pense à cocher
son pouvoir »*. Un rôle superutilisateur franchit **tout pouvoir, présent et à
venir**. Une livraison n'exige donc ni migration de données, ni recochage, ni
même que l'exploitant sache qu'elle a eu lieu.

Corollaire non négociable (FR-010) : `is_superuser` n'est posable **ni retirable**
que par quelqu'un qui le porte déjà. C'est le seul attribut qui ne se compose pas.

### Rôles semés par la migration

| slug | name | is_system | is_superuser | Pouvoirs |
| --- | --- | --- | --- | --- |
| `admin` | Administrateur | ✔ | ✔ | tous, par construction |
| `validator` | Validateur | ✔ | ✖ | `quality:override` |
| `moderator` | Modérateur | ✔ | ✖ | `pending_providers:read`, `pending_providers:handle` |

`organisation_id` à `NULL` pour les trois : ce sont des rôles partagés.

`moderator` est semé parce que ses deux pouvoirs sont **couplés** — instruire un
signalement sans pouvoir lire la liste n'a pas de sens — et que l'oubli du
pouvoir de lecture est le bug attendu d'une composition à la main. Il porte le
coût assumé de FR-006 : livré, donc non supprimable, même sans porteur.

### Ce semis ne se rejoue jamais (FR-041)

La migration initiale sème ces trois lignes. **Aucune migration ultérieure ne
recompose un rôle existant** — ni pour lui ajouter un pouvoir nouvellement livré,
ni pour « corriger » sa composition. Dès lors qu'un rôle est éditable à chaud, sa
composition est une donnée d'exploitation ; une migration qui la réécrirait
effacerait une décision humaine sans laisser de trace.

Ajouter un rôle **nouveau** par migration reste possible et sans risque : il
n'écrase rien. C'est la recomposition d'un rôle existant qui est proscrite.

---

## `role_permissions`

| Colonne | Type | Contraintes |
| --- | --- | --- |
| `id` | entier | PK |
| `role_id` | entier | FK → `roles.id`, indexé, non nul |
| `permission_code` | chaîne | non nul, indexé |

`UNIQUE(role_id, permission_code)`. Relation `Role.permissions`,
`cascade="all, delete-orphan"`.

### Les codes sont en base ; c'est leur **liste de référence** qui n'y est pas

À lire avant le reste, parce que la formulation précédente — « chaîne nue » — se
comprenait de travers et l'a été (clarification du 2026-08-05) :

- **`permission_code` est bien une donnée en base**, une chaîne stockée dans une
  ligne de `role_permissions` : `"quality:override"`, `"pending_providers:read"`.
  Elle s'écrit et se lit en base, et se modifie à chaud par `PATCH`.
- **« Nue » qualifie l'absence de clé étrangère**, pas l'absence de stockage. Le
  précédent explicite du dépôt est `Course.event_type`, qui porte `triathlon-m`
  en `String` avec la nomenclature tenue en Python (`core/discipline.py`).
- **Ce qui n'existe pas, c'est une table `permissions`** qui listerait les codes
  possibles — un second inventaire, en base, doublant celui de l'application.

Cette absence est la décision structurante du modèle, et elle est **moins chère
et plus sûre** qu'une table :

| | Sans table (retenu) | Avec table + synchronisation |
| --- | --- | --- |
| Capacité offerte à l'exploitant | identique | **identique** |
| Écriture au démarrage | aucune | un upsert par pouvoir, à chaque boot |
| Migration à chaque fonctionnalité livrée | **aucune** | une, si l'on sème par migration |
| Risque | néant | un module non importé au boot rend le catalogue partiel ; un sync qui supprime les absents **efface des attributions en production**, sans bruit |
| Ce que la clé étrangère protégerait | — | rien : le seul écrivain valide déjà contre le catalogue et rend 422 |
| Lignes supplémentaires | — | ≈ 170 |

**Les lignes orphelines sont inertes par construction.** La garde ne demande
jamais « quels codes ce rôle porte-t-il ? » mais « porte-t-il *ce* code ? », et
ce code est une constante de l'application. Un pouvoir retiré par une livraison
n'est plus jamais interrogé. L'API les expose dans un bloc « pouvoirs obsolètes »
(`stale_permissions`) : hygiène, jamais correction.

**La purge n'est pas une ressource**, c'est l'effet du `PATCH` : celui-ci
remplace l'ensemble des pouvoirs, donc omettre un code périmé le supprime. Cela
n'est vrai qu'à une condition, et elle est structurante : la règle de
non-amplification ne compare **que les codes de l'inventaire** (FR-011). Si elle
comptait les codes périmés, personne ne pourrait les retirer — pas même un
superutilisateur, dont les pouvoirs effectifs *sont* l'inventaire — et le rôle
serait gelé, `is_system` ou attribué donc indélébile. Une suppression de
fonctionnalité ordinaire suffirait à le produire.

---

## `user_roles`

| Colonne | Type | Contraintes |
| --- | --- | --- |
| `id` | entier | PK |
| `user_id` | entier | FK → `users.id`, indexé, non nul |
| `role_id` | entier | FK → `roles.id`, indexé, non nul |
| `organisation_id` | entier | FK → `organisations.id`, indexé, **non nul** |
| `granted_at` | horodatage | défaut `utcnow` |

`UNIQUE(user_id, role_id, organisation_id)` — c'est **elle** qui rend
l'attribution idempotente sous concurrence, pas une lecture préalable.

Relation `User.roles`, `cascade="all, delete-orphan"`, sur le patron exact de
`User.identities` et `User.sessions` de #114. **Pas d'`ondelete`**, même raison
qu'alors : `core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`, la
contrainte serait inerte en SQLite et active en PostgreSQL ; la cascade ORM fait
le travail des deux côtés.

**`role_id`, pas `role`.** C'est toute la différence entre le plan de la v1 et
ce modèle, et c'est ce qui rend le renommage d'un rôle gratuit là où une chaîne
en aurait fait une migration de données.

**Une règle que le SQL portable ne peut pas exprimer** : un rôle propre à
l'organisation A n'est pas attribuable dans B (FR-008). Elle croise deux tables ;
c'est un contrôle de service, `assert_role_assignable_in()`, plus un test. Dit
ici plutôt que de laisser croire à une contrainte.

---

## `courses` — deux colonnes

| Colonne | Type | Écrite par | Sens |
| --- | --- | --- | --- |
| `is_reliable_computed` | booléen, nullable | l'import, à chaque fois | Ce que la machine constate. `NULL` = jamais évaluée. |
| `reliability_override` | booléen, nullable | le porteur du pouvoir de qualité | Ce qu'un humain a tranché. `NULL` = personne. |

`is_reliable` est **renommée** en `is_reliable_computed` (`alter_column`, données
en place) et devient une `hybrid_property` :
`coalesce(reliability_override, is_reliable_computed)`, avec son `@expression`
pour rester utilisable dans un `WHERE`.

Le contrat public ne bouge pas (FR-038) : `CourseBrief` expose toujours
`is_reliable`, sans qu'une ligne de `schemas/course.py` ne change —
`from_attributes=True` lit une propriété comme une colonne.

Ce que cette forme supprime : **aucune branche** dans `import_service.finalize`
(l'import écrit sa colonne, toujours), **aucun recalcul** à la levée (mettre
`reliability_override` à `NULL` fait réapparaître le verdict calculé, à jour), et
**aucune perte** du verdict machine quand un humain tranche.

Surface du renommage, relevée : une écriture (`course_repository.py:102`), une
déclaration de modèle, trois assertions de `tests/test_migrations.py`. Les tests
qui affirment `course.is_reliable is True` passent **sans modification**.

---

## Cycles de vie

### Un rôle

```
(créé, sans pouvoir) ──PATCH──▶ (composé) ──PATCH──▶ (recomposé) …
        │                            │
        │  DELETE si aucun porteur   │  DELETE refusé (409) si porteurs
        ▼                            ▼
     (supprimé)              is_system ⇒ DELETE toujours refusé
```

Le renommage est libre à tout moment ; le `slug` ne se renomme pas.

### Une attribution

```
(absente) ──POST /admin/users/{id}/roles──▶ (présente)
    ▲                                            │
    └──DELETE /admin/users/{id}/roles/{role_id}──┘
              refusé si l'organisation y perdrait son dernier administrateur actif
```

`grant-role` en ligne de commande produit la même transition, sans session.

### Le verdict de fiabilité

Les deux colonnes évoluent **indépendamment** — ce ne sont pas deux états d'une
machine, ce sont deux faits qui coexistent.

```
is_reliable_computed :  NULL ──import──▶ true/false ──import──▶ …   (sans condition)
reliability_override :  NULL ──PATCH──▶ true/false ──PATCH {null}──▶ NULL
is_reliable (lu)     :  coalesce(override, computed), à tout instant
```

---

## L'invariant qui ne se garde pas par chemin

L'édition à chaud multiplie les façons de se verrouiller dehors : retirer une
attribution, supprimer un rôle, décocher `is_superuser`, désactiver un compte — et
chaque nouvelle façon d'éditer les droits en ouvrira une cinquième.

On ne garde donc pas les chemins, on garde **l'état d'arrivée**, une seule fois,
après `flush` et avant `commit` :

```
assert_organisation_keeps_an_admin(db, organisation_id)
  → 409 si count_active_superusers(organisation_id) == 0
```

« Actifs » au sens de #114 : un compte désactivé ne compte pas, ses sessions
étant déjà tombées. Quatre sites d'appel, une définition, et un cinquième chemin
ajouté demain est couvert sans qu'on y pense.
