# Groupes d'appartenance (#197)

Renvoyé depuis `backend/app/services/auth/AGENTS.md`.

Un **groupe** dit à quoi on **appartient** — Codir, arbitres, commission
bénévolat. Un **rôle** dit ce qu'on **peut faire**. Deux objets, au sens de
GitHub Teams ou d'une OU LDAP. Spec, plan et tâches :
`specs/20260806-143225-auth-groupes-appartenance/`.

**Deux tables, `groups` et `user_groups`, et le patron de #115 à quatre
différences près.** Trois sont énoncées par l'issue, la quatrième est tombée à
l'arbitrage du 2026-08-06 :

- **pas d'`is_superuser`** — un groupe n'accorde rien ;
- **pas d'invariant du dernier membre** — vider un groupe ne verrouille personne
  dehors, à l'inverse du dernier administrateur ;
- **pas de non-amplification** — il n'y a aucun pouvoir à amplifier, et l'appeler
  quand même laisserait croire le contraire ;
- **`groups.organisation_id` est non nul**, là où celui de `roles` est nullable.
  Un rôle **global** est une définition réutilisable — « validateur » a le même
  sens dans deux clubs ; un groupe est une **composition**, celle d'un club
  précis, et « Codir » sans club ne désigne rien. Deux conséquences en cascade :
  cette table n'a pas besoin de l'index partiel `WHERE organisation_id IS NULL`
  à double dialecte qui garde `roles.slug`, et `user_groups` ne porte **aucune**
  colonne d'organisation — la répéter rendrait représentable un état incohérent
  qu'aucune contrainte portable ne fermerait.

**`services/auth/groups.py` est un module séparé, et c'est un choix de
vérifiabilité, pas de rangement.** AC6 exige qu'« aucune décision d'accès ne
consulte les groupes », et un test ne sait pas lire une intention. Deux modules
distincts rendent l'énoncé mécanique : ni `api/deps.py` ni `authorization.py` ne
**nomment** `Group`, `UserGroup`, `group_repository` ou `services.auth.groups` —
`tests/test_auth/test_groups_grant_nothing.py` le vérifie par lecture d'AST, et
la faute est éprouvée par mutation. Ce test **doit rougir le jour de la v2**,
quand des rôles portés par un groupe entreront dans la décision d'accès : on le
supprimera alors sciemment, et sa mort sera le signal que #197 a rempli son
office. Le contourner serait faire céder la borne en silence.

**La suppression d'un groupe peuplé est refusée** (409, le nombre dans le
message), et **aucune cascade** ne va de `Group` vers ses membres — la refuser
puis la laisser à l'ORM ferait tenir la règle par le seul chemin. Aucun droit
n'est pourtant perdu : ce qu'on protège est la **composition**, qu'aucune
migration ne reconstitue et qu'aucun autre système ne détient. Le miroir est
voulu : `User.groups` **cascade**, lui — supprimer quelqu'un emporte ses
appartenances, et le groupe survit.

**Trois filets touchent cette feature, et un seul a bougé.**
`test_permissions_catalogue.py` prend les trois pouvoirs neufs automatiquement
(il est paramétré sur `permissions.ALL`) et `test_public_routes_still_open.py`
classe les sept routes par la seule règle du préfixe `/api/v1/admin/` : ni l'un
ni l'autre n'a été modifié. **`tests/test_core/test_permissions.py`, lui, épingle
les codes à la main** et a dû être complété — c'est sa raison d'être : ajouter un
pouvoir doit être un geste conscient, et c'est le seul endroit du dépôt qui s'y
oppose. Le plan de la feature l'avait manqué ; le filet l'a rattrapé.

**Ce que la v1 ne fait pas**, et qui n'est pas un oubli : aucun groupe n'est semé
(la composition d'un CA n'est pas devinable par une migration, d'où l'absence
d'`is_system`), aucun groupe n'est imbriqué, aucune appartenance n'expire, et
aucun rôle n'est attaché à un groupe. Ce dernier point est la v2 — c'est lui qui
ferait entrer les groupes dans la décision d'accès, et il ne se décide pas là.
