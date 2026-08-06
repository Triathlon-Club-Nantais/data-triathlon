# Phase 1 — Modèle de données : groupes d'appartenance (#197)

**Deux tables neuves, aucune table existante modifiée.** `users` gagne une
`relationship` — un attribut Python, aucun DDL.

---

## `groups` — un nom d'appartenance dans un club

| Colonne | Type | Contraintes | Pourquoi |
| --- | --- | --- | --- |
| `id` | `int` | PK | |
| `organisation_id` | `int` | FK `organisations.id`, **NOT NULL**, indexée | Un groupe est celui d'un club. « Codir » sans club ne désigne rien (research §D2). |
| `slug` | `str` | `^[a-z][a-z0-9-]*$`, **immuable** | Le nom stable, celui d'une URL et d'un futur script. Immuable, donc `PATCH {"slug": …}` est un **422** et non un renommage silencieux — patron de `RoleUpdate`. |
| `name` | `str` | non nul | Le libellé français affiché. Renommable sans rien perdre (FR-006). |
| `description` | `str` | non nul, défaut `""` | Facultatif au sens produit, jamais `NULL` au sens colonne — patron de `roles.description`. |
| `created_at` | `datetime` | défaut `utcnow` | Naïf en UTC, comme partout ailleurs. |

**Contrainte de table** : `UniqueConstraint("organisation_id", "slug")`,
nommée `uq_group_org_slug`.

**Et rien d'autre.** Pas d'index partiel double dialecte : il garde `roles.slug`
parce que `roles.organisation_id` est nullable et que deux `NULL` sont distincts
pour SQLite comme pour PostgreSQL. Ici la colonne est non nulle, donc la
contrainte simple couvre tout — c'est la conséquence directe de D2, pas une
omission.

**Ce que la table ne porte pas, et ne portera pas en v1** :

- **pas d'`is_superuser`** — un groupe n'accorde rien (FR-017) ;
- **pas d'`is_system`** — aucun groupe n'est livré avec l'application (FR-005) ;
- **pas de `parent_id`** — les groupes imbriqués sont hors périmètre ;
- **pas de lien vers `roles`** — c'est la v2, et c'est ce qui ferait entrer les
  groupes dans la décision d'accès (FR-016).

---

## `user_groups` — cette personne est membre de ce groupe

| Colonne | Type | Contraintes | Pourquoi |
| --- | --- | --- | --- |
| `id` | `int` | PK | |
| `user_id` | `int` | FK `users.id`, non nul, indexée | |
| `group_id` | `int` | FK `groups.id`, non nul, indexée | |
| `joined_at` | `datetime` | défaut `utcnow` | Depuis quand, pas jusqu'à quand : une appartenance ne se périme pas (spec §Assumptions). |

**Contrainte de table** : `UniqueConstraint("user_id", "group_id")`, nommée
`uq_user_group`.

**Pas de colonne `organisation_id`**, et c'est la deuxième conséquence de D2 :
`user_roles` en porte une parce qu'un rôle **global** doit dire dans quel club il
s'applique. Un groupe porte déjà la sienne ; la répéter ici créerait un état
incohérent possible (`user_groups.organisation_id ≠ groups.organisation_id`)
qu'aucune contrainte portable ne fermerait.

**C'est la contrainte qui rend l'appartenance idempotente**, pas une lecture
préalable — deux exploitants simultanés franchiraient un `SELECT`, jamais un
`UNIQUE`. Le repository tente l'insertion sous `begin_nested()` (SAVEPOINT) et
rattrape l'`IntegrityError` : reprise **exacte** de `user_role_repository.grant`,
qui documente ce raisonnement.

---

## Relations et cascades

```text
Organisation ──1:N──> Group ──1:N──> UserGroup <──N:1── User
```

| Relation | Cascade | Pourquoi |
| --- | --- | --- |
| `User.groups` → `UserGroup` | `all, delete-orphan` | **AC5** : supprimer un utilisateur emporte ses appartenances, jamais les groupes. Patron exact de `User.roles`, `User.identities`, `User.sessions`. |
| `Group` → `UserGroup` | **aucune** | Supprimer un groupe peuplé est **refusé** (FR-011). Une cascade viderait la table dès qu'un chemin contournerait le service : le refus ne tiendrait plus que par le chemin. `Role` ne cascade pas non plus vers ses porteurs. |
| `UserGroup.user`, `UserGroup.group` | `relationship` de lecture | Servent la liste nominative des membres (FR-012) et `GET /auth/me`. |

**Aucun `ondelete` sur les clés étrangères** — convention du dépôt depuis #114 :
`core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`, une contrainte
`ondelete` serait donc inerte en SQLite (dev, tests) et active en PostgreSQL.

---

## Migration Alembic

Une révision, `down_revision = "f6a7b8c9d0e1"` (tête actuelle, celle de #115) :

1. `create_table("groups", …)` avec sa contrainte d'unicité nommée ;
2. `create_table("user_groups", …)` avec la sienne ;
3. les index des colonnes de clé étrangère.

**Aucun semis, aucune donnée écrite, aucun `UPDATE`.** Le `downgrade` supprime
les deux tables dans l'ordre inverse.

Procédure : `uv run alembic revision --autogenerate -m "groups and memberships"`
puis **relecture manuelle** de la révision produite (contrainte constitutionnelle
« Additional Constraints »). L'autogénération nomme mal les contraintes ; les
noms attendus sont `uq_group_org_slug` et `uq_user_group`.

---

## Ce qu'aucune table n'enregistre

- **Qui a ajouté qui, et quand il l'a retiré.** L'audit vit dans les journaux
  applicatifs, décision de #115 que cette feature ne rouvre pas.
- **Une date de fin d'appartenance.** Pas de « membre du Codir jusqu'en juin » :
  une appartenance dure jusqu'à son retrait, même arbitrage que pour les
  attributions de rôle.
- **Un rang dans le groupe.** « Président du Codir » est un autre objet ; un
  groupe dit qui en est, pas qui y fait quoi.
