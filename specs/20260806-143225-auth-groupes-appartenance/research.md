# Phase 0 — Recherche : groupes d'appartenance (#197)

Huit décisions. Aucune ne porte sur un choix de bibliothèque : la feature
n'ajoute aucune dépendance et n'invente aucun mécanisme. Elles portent toutes sur
**où poser le code pour que la borne de la v1 se prouve toute seule**.

---

## D1 — Où vit la logique métier : `services/auth/groups.py`, module séparé

**Décision** : un module neuf, `app/services/auth/groups.py`. Pas de fonction
supplémentaire dans `authorization.py`.

**Rationale** — c'est AC6 qui tranche, pas le goût. « Aucune décision d'accès ne
consulte les groupes » doit être **vérifié par un test**, et un test ne sait pas
lire une intention. Avec deux modules distincts, l'énoncé devient mécanique :

> ni `api/deps.py` ni `services/auth/authorization.py` ne nomment `Group`,
> `UserGroup` ou `group_repository`.

C'est une lecture d'AST de dix lignes, sur le patron exact de
`tests/test_permissions_catalogue.py` et de `tests/test_core_http.py`. Fondues
dans `authorization.py`, les deux responsabilités ne seraient plus séparables par
aucun outil, et AC6 retomberait sur la vigilance du relecteur — précisément ce
que #115 a refusé pour la non-amplification.

**Le choix du dossier `auth/` est le point faible**, et il est assumé plutôt que
caché : en v1, un groupe ne relève ni de l'authentification ni de
l'autorisation. Trois raisons l'y placent quand même — il manipule `User` et
`Organisation`, dont tout le reste vit là ; il est gardé par le catalogue de
#115 ; et la v2 (rôles portés par un groupe) le fera entrer dans la décision
d'accès pour de bon, où un déménagement de module serait du bruit dans le diff
qui compte. **Alternative écartée** : `app/services/directory.py`, plus honnête
sur la v1, mais qui isole `Organisation` de son voisinage et ne survit pas à la
v2.

---

## D2 — `groups.organisation_id` non nul : la quatrième différence avec les rôles

**Décision** : `NOT NULL`, une seule `UniqueConstraint(organisation_id, slug)`,
et **aucune** colonne d'organisation sur `user_groups`.

**Rationale** — arbitrage utilisateur du 2026-08-06, et le modèle en tire trois
simplifications en cascade :

| | `roles` (#115) | `groups` (#197) |
| --- | --- | --- |
| `organisation_id` | nullable — un rôle **global** est une définition réutilisable | **non nul** — « Codir » sans club ne désigne rien |
| Unicité du slug | `UniqueConstraint` **plus** un index partiel `WHERE organisation_id IS NULL`, renseigné pour les **deux** dialectes | une `UniqueConstraint`, et c'est tout |
| Table d'association | `user_roles` porte `organisation_id` **non nul** — l'attribution doit dire où le rôle global s'applique | `user_groups` ne le porte pas : le groupe le porte déjà |

Le piège que #115 documente — SQLite comme PostgreSQL tiennent deux `NULL` pour
**distincts**, donc `UniqueConstraint(organisation_id, slug)` laisse passer deux
lignes globales homonymes — **ne se pose pas ici**. Il ne s'agit pas de l'avoir
évité par chance : c'est la conséquence directe du `NOT NULL`, et c'est pourquoi
la différence est nommée dans le plan plutôt que découverte à la relecture.

**Alternative écartée** : recopier le patron nullable « pour rester symétrique ».
Elle achetait une symétrie de forme au prix d'un index partiel à double dialecte
et d'une question sans réponse — qui est membre d'un groupe global, et dans quel
club ?

---

## D3 — `groups` comme nom de table : vérifié, pas supposé

**Décision** : `groups` et `user_groups`, sans préfixe ni contorsion.

**Rationale** — `GROUP` est un mot réservé de PostgreSQL, `GROUPS` ne l'est pas
(non réservé depuis son introduction pour les clauses de fenêtrage). Vérifié
plutôt que cru, en compilant le DDL des deux dialectes :

```console
$ uv run python -c "…CreateTable(Table('groups', …)).compile(dialect=…)"
postgresql -> CREATE TABLE groups (
sqlite     -> CREATE TABLE groups (
groups reserved in pg dialect: False
```

SQLAlchemy ne le cite pas, donc son dialecte PostgreSQL ne le tient pas pour
réservé, et l'ORM n'émet de toute façon aucun SQL brut sur ces tables.

**La limite est nommée** : `tests/test_migrations.py` n'applique la chaîne
Alembic que sur **SQLite**. Le chemin PostgreSQL n'est éprouvé par aucun test —
même angle mort que `unaccent` (`app/api/AGENTS.md`). Si PostgreSQL refusait le
nom, l'échec serait franc et immédiat (`alembic upgrade head` au déploiement,
`autoDeploy: false` donc sous les yeux d'un humain), et le correctif tiendrait en
un `__tablename__` renommé en `member_groups` avant la première ligne écrite.

---

## D4 — Trois pouvoirs, une fonctionnalité neuve au catalogue

**Décision** : `FEATURE_GROUPS = "Groupes d'appartenance"`, et trois membres
ajoutés à `P` **et** à `ALL` — `groups:read`, `groups:write`, `groups:assign`.

**Rationale** — la forme est imposée par `core/permissions.py` : ajouter un
pouvoir est un membre de plus dans `ALL`, **jamais une migration**. Une
fonctionnalité distincte de « Rôles et accès » parce que l'écran de composition
d'un rôle range par fonctionnalité, et que mêler « attribuer les rôles » et
« attribuer les groupes » dans le même bloc est exactement le geste que ce
regroupement existe pour éviter.

> **Corrigé à l'implémentation (2026-08-06)** — ce paragraphe annonçait deux
> filets ; il y en a **trois**. `tests/test_core/test_permissions.py` épingle les
> codes **à la main**, avec un commentaire qui dit pourquoi : « un test qui
> dériverait la liste du catalogue ne prouverait rien ». Il a donc rougi à
> l'ajout des trois pouvoirs, et il a fallu le compléter. Ce n'est pas un défaut
> du plan qu'on répare, c'est le filet qui fait exactement son travail : ajouter
> un pouvoir doit être un **geste conscient**, et c'est le seul endroit du dépôt
> qui s'y oppose. Les deux filets ci-dessous, eux, sont bien restés intouchés.

**Trois conséquences gratuites, toutes vérifiées par des filets déjà écrits** :

- `test_permissions_catalogue.py` est paramétré sur `permissions.ALL` : les trois
  pouvoirs y entrent **automatiquement**, et le fichier reste vert seulement si
  chacun garde au moins une ressource. Rien à modifier ;
- l'administrateur les porte le jour du déploiement, par `is_superuser`, sans
  migration ni recochage ;
- **aucune migration ne recompose `validator` ni `moderator`** — FR-041 de #115
  l'interdit, et c'est ici qu'on s'y tient plutôt que de « rendre service » à
  l'exploitant en cochant à sa place.

---

## D5 — Sept routes pour cinq ressources, sous `/api/v1/admin/groups`

**Décision** : un router neuf, `api/v1/admin_groups.py`, sept routes, sept
gardes individuelles.

| Route | Pouvoir |
| --- | --- |
| `GET /admin/groups` | `groups:read` |
| `GET /admin/groups/{id}` | `groups:read` |
| `POST /admin/groups` | `groups:write` |
| `PATCH /admin/groups/{id}` | `groups:write` |
| `DELETE /admin/groups/{id}` | `groups:write` |
| `POST /admin/groups/{id}/members` | `groups:assign` |
| `DELETE /admin/groups/{id}/members/{user_id}` | `groups:assign` |

**Rationale** — les cinq ressources de #197 sont là ; la sixième et la septième
sont les **deux formes de la lecture** (la liste, puis le détail avec ses
membres), séparées exactement comme #115 sépare `GET /admin/roles` de
`GET /admin/roles/{id}`. Sans le détail, FR-012 — « lister les membres de X » —
n'aurait aucun porteur, et c'est la capacité qui justifie l'objet entier.

**Un router séparé plutôt qu'un ajout à `admin_roles.py`** : le fichier de #115
s'appelle « router d'administration des rôles » et son en-tête décrit sept
ressources ; y en fondre sept autres brouillerait la lecture d'un module dont le
docstring est un contrat. `router.py` monte les deux côte à côte.

**Aucun des deux filets de #115 n'est modifié** :
`test_public_routes_still_open.py` dérive son inventaire du schéma OpenAPI et
classe **toute** route sous `/api/v1/admin/` comme devant refuser l'anonyme ;
les sept nouvelles y entrent sans être nommées, et `ADMIN_PUBLIQUES` reste à une
seule entrée. C'est le meilleur signe disponible que la feature s'inscrit dans le
mécanisme au lieu de le plier.

---

## D6 — La suppression d'un groupe peuplé : 409, et le service refuse avant l'ORM

**Décision** : `GroupInUseError` (409), message nommant le nombre de membres ;
**aucune cascade** de `Group` vers `UserGroup`.

**Rationale** — c'est l'arbitrage du 2026-08-06, et le patron de code est celui
de `delete_role` : compter d'abord, refuser en nommant le nombre, supprimer
ensuite. Le nombre est **dans le message**, pas seulement dans le code de retour,
pour la raison que #115 écrit noir sur blanc : « conflit » ne se corrige pas.

**L'absence de cascade est la moitié de la règle.** Une `relationship(members,
cascade="all, delete-orphan")` sur `Group` viderait la table sans le dire dès que
quelqu'un contournerait le service — le refus ne tiendrait plus que par le
chemin. `Role` ne cascade pas non plus vers ses porteurs, pour ce motif exact.

**Le miroir est vrai et voulu** : `User.groups` **cascade**, lui (AC5).
Supprimer un utilisateur emporte ses appartenances ; supprimer un groupe n'emporte
rien. La dissymétrie n'est pas une inconséquence — un utilisateur supprimé n'a
plus d'appartenance possible, là où un groupe supprimé effacerait la composition
d'une commission.

---

## D7 — Ce qui n'est pas fait, et pourquoi

**Pas d'`ondelete` sur les clés étrangères.** Convention du dépôt depuis #114,
répétée par #115 : `core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`, une
contrainte `ondelete` serait donc **inerte en SQLite** (dev et tests) et
**active en PostgreSQL**. Deux comportements pour un même code est pire que pas
de cascade du tout. La cascade ORM fait le travail des deux côtés.

**Pas d'extension du méta-test `TABLES_DE_POUVOIR`.** Il interdit à un router
d'écrire `Role`, `RolePermission` ou `UserRole` directement, parce qu'une telle
écriture contournerait la non-amplification et l'invariant du dernier
administrateur. **Ces deux règles n'existent pas pour les groupes** (FR-018,
FR-019) : y ajouter `Group` protégerait de rien et ferait croire à un enjeu de
privilège là où il n'y en a aucun. La règle « les routers délèguent » reste tenue
par le Principe II.

**Pas de semis, pas d'`is_system`.** #197 énumère les colonnes du groupe et n'y
met ni l'un ni l'autre. Semer « Codir » serait deviner la composition d'un CA ;
`is_system` protégerait de la suppression un groupe que personne n'a livré.

**Pas de pagination.** `users` est borné par `AUTH_ALLOWED_EMAILS` et les groupes
d'un club se comptent sur les doigts — raison exacte pour laquelle
`GET /admin/users` n'en a pas.

**Pas de table d'audit.** Journaux applicatifs, `logger.info` au format de #115
(`Group created: actor=… group=…`), en anglais et sans secret.

---

## D8 — Comment AC6 se prouve : deux tests, deux natures

**Décision** : `tests/test_auth/test_groups_grant_nothing.py`, deux tests
complémentaires — l'un ne suffit pas.

1. **Comportemental** — un utilisateur **sans aucun rôle**, membre de **tous** les
   groupes existants, se voit refuser (403) une ressource gardée, et
   `effective_permissions` le concernant rend l'ensemble vide. C'est la propriété
   qui intéresse le produit, mais elle ne protège que ce qu'elle échantillonne.
2. **Structurel (AST)** — ni `app/api/deps.py` ni
   `app/services/auth/authorization.py` ne nomment `Group`, `UserGroup` ou
   `group_repository`. C'est ce test-là qui rougira le jour de la v2, **au bon
   moment** : quand quelqu'un branchera les rôles d'un groupe sur la décision
   d'accès, il devra le supprimer sciemment. Sa mort est le signal que #197 a
   rempli son office et que la borne est levée.

**Alternative écartée** : se contenter du test comportemental. Il resterait vert
si la garde lisait les groupes pour n'en rien conclure — c'est-à-dire au moment
précis où la borne commence à céder.
