# Implementation Plan: Groupes d'appartenance — modéliser avant qu'un groupe porte un droit

**Branch**: `feat-auth-groupes-dappartenance-mod-liser-avant` | **Date**: 2026-08-06 | **Spec**: [spec.md](spec.md)

**Input**: `specs/20260806-143225-auth-groupes-appartenance/spec.md`

## Summary

Poser le modèle d'**appartenance** — deux tables, trois pouvoirs, sept routes —
en réutilisant **intégralement** le mécanisme de #115 et **sans en modifier une
ligne**.

Le patron est celui des rôles, à quatre différences près. Trois sont nommées par
#197 : pas d'`is_superuser`, pas d'invariant du dernier administrateur, pas de
non-amplification. La quatrième est tombée à la clarification du 2026-08-06 :
**`groups.organisation_id` est non nul**, là où `roles.organisation_id` est
nullable. Elle supprime l'index partiel double dialecte qui garde `roles.slug`,
et vide `user_groups` de toute colonne d'organisation.

Trois décisions portent le reste :

1. **Un module de service séparé** — `services/auth/groups.py`, jamais une
   fonction de plus dans `authorization.py`. C'est ce qui rend AC6 (« aucune
   décision d'accès ne consulte les groupes ») vérifiable par **lecture d'AST**
   plutôt que par relecture humaine : le module qui décide ne nomme jamais les
   modèles de groupe.
2. **Rien à modifier dans les deux filets de #115** — *et un troisième, manqué au
   plan, qui a dû l'être : voir `research.md` §D4.*
   `test_public_routes_still_open.py` classe déjà toute route sous
   `/api/v1/admin/` comme devant être gardée — les sept nouvelles y tombent sans
   qu'on les nomme. `test_permissions_catalogue.py` exige que tout pouvoir du
   catalogue garde quelque chose — les trois nouveaux le font. **Aucun de ces
   deux fichiers n'est touché**, et c'est le signe que la feature s'inscrit dans
   le mécanisme au lieu de le plier.
3. **Aucune migration ne recompose un rôle semé** (FR-041 de #115).
   L'administrateur atteint les trois pouvoirs neufs par `is_superuser`, le jour
   du déploiement, sans recochage ; `validator` et `moderator` ne les reçoivent
   pas — un exploitant les leur donnera s'il le veut.

## Technical Context

**Language/Version**: Python 3.13 (backend). **Aucune modification du frontend**
dans cette feature — aucun écran n'est livré (spec §Assumptions).

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic.
**Aucune dépendance nouvelle** : tout ce dont la feature a besoin existe déjà
dans #115.

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en
test. **Deux tables nouvelles**, aucune existante modifiée — pas même `users`,
qui gagne une `relationship` (aucun DDL).

**Testing**: pytest (`-m "not integration"`). Aucun réseau sur ce périmètre.

**Target Platform**: Render (backend, `autoDeploy: false`).

**Project Type**: application web ; seul le backend est touché.

**Performance Goals**: **zéro requête ajoutée sur le site public** et **zéro sur
le chemin de décision d'accès** — c'est AC6 pris au mot : la garde ne lit pas les
groupes, donc `require_permission` coûte exactement ce qu'elle coûtait hier.
`GET /auth/me` gagne une lecture indexée sur `user_groups`.

**Constraints**: `users` est borné par `AUTH_ALLOWED_EMAILS` (de l'ordre de la
dizaine), et un club aura de l'ordre de la dizaine de groupes. Aucune pagination,
pour la raison exacte qui l'écarte sur `GET /admin/users`.

**Scale/Scope**: 2 tables, 3 pouvoirs, 1 router de 7 routes, 1 module de service,
1 module de repository, 1 migration, **5 fichiers de test neufs et 1 modifié**
(`test_migrations.py`).

## Constitution Check

*GATE: passé avant Phase 0, re-vérifié après Phase 1 — inchangé.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Tables, colonnes, codes de pouvoir, **identifiants et noms de tests en anglais** (`groups`, `user_groups`, `groups:assign`, `joined_at`, `test_a_group_is_born_empty`). Libellés du catalogue, messages de `DomainError` et docstrings de règle métier en français — le Principe I range explicitement les `DomainError` dans le « français utilisateur ». **Corrigé après revue** : la première rédaction cochait cette case alors que le code portait `groupe`, `cible`, `vue` et des tests en français, par mimétisme avec #115. La revue l'a relevé ; arbitrage de l'utilisateur du 2026-08-06 : renommer plutôt que déroger — le code neuf n'a pas à grossir la dette que la campagne #88 résorbe. |
| II | Architecture en couches | ✅ | `api/v1/admin_groups.py` → `services/auth/groups.py` → `repositories/group_repository.py` → DB. Aucune couche sautée, aucune `Session` hors du repository. Motif identique à `admin_roles → authorization → role_repository`. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests d'abord, à chaque tâche ; aucun appel réseau sur ce périmètre. `tasks.md` en portera la trace tâche par tâche. |
| IV | Contrats API stables | ✅ | Aucun champ retiré, aucune sémantique inversée, aucun code de retour modifié. `GET /auth/me` gagne `groups`, **strictement additif** — le précédent est `permissions`/`roles` ajoutés par #115 au même endroit. Les sept routes sont neuves. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre de lecture transverse (`scope`, `federal_only`, `seasons`) n'est ajouté ni lu. |
| VI | Simplicité / YAGNI | ✅ | Deux tables et rien d'autre : pas de groupes imbriqués, pas de rôle-dans-le-groupe, pas de semis, pas d'`is_system`, pas de table d'audit. Le lien groupe → rôles, seule vraie complexité du sujet, est hors périmètre **et verrouillé par un test**. |

Aucun principe en ⚠️ : la section **Complexity Tracking** reste vide, et c'est le
résultat attendu d'une feature qui ne fait qu'instancier un patron existant.

## Project Structure

### Documentation (this feature)

```text
specs/20260806-143225-auth-groupes-appartenance/
├── plan.md              # ce fichier
├── spec.md
├── research.md          # Phase 0 — 8 décisions
├── data-model.md        # Phase 1 — 2 tables, contraintes, cascades
├── quickstart.md        # Phase 1 — vérification de bout en bout
├── contracts/
│   └── admin-groups-api.md
├── checklists/requirements.md
└── tasks.md             # Phase 2 — produit par /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── <rev>_groups_and_memberships.py     # NOUVEAU — 2 tables, aucun semis
├── app/
│   ├── core/permissions.py                 # + FEATURE_GROUPS et 3 pouvoirs
│   ├── api/v1/
│   │   ├── admin_groups.py                 # NOUVEAU — 7 routes, 7 gardes
│   │   ├── router.py                       # + include_router(admin_groups)
│   │   └── auth.py                         # /auth/me : + groups (additif)
│   ├── models/
│   │   ├── group.py · user_group.py        # NOUVEAUX
│   │   ├── user.py                         # + relationship groups (cascade, aucun DDL)
│   │   └── __init__.py                     # + 2 exports
│   ├── repositories/group_repository.py    # NOUVEAU
│   ├── schemas/
│   │   ├── admin.py                        # + DTO des groupes
│   │   └── auth.py                         # + SessionGroupRead
│   └── services/auth/
│       ├── groups.py                       # NOUVEAU — CRUD, appartenances, erreurs
│       └── AGENTS.md                       # + section #197
└── tests/
    ├── test_auth/
    │   ├── test_group_models.py            # NOUVEAU — contraintes, cascades
    │   ├── test_group_repository.py        # NOUVEAU — idempotence par SAVEPOINT, tri des membres
    │   ├── test_admin_groups_api.py        # NOUVEAU — 7 routes, 401/403, 409, idempotence, journaux
    │   ├── test_groups_grant_nothing.py    # NOUVEAU — AC6, comportemental + AST
    │   └── test_me_groups.py               # NOUVEAU — champ additif
    └── test_migrations.py                  # MODIFIÉ — 2 tables de plus après upgrade head
```

**Structure Decision**: aucune structure nouvelle. La feature se pose dans les
couches existantes du backend, au même endroit et sous le même nom que son
jumeau #115 — un fichier par couche, préfixé `group`. Le frontend n'est pas
touché.

**Le seul choix d'emplacement qui se discute** est `services/auth/groups.py` : un
groupe de la v1 ne relève ni de l'authentification ni de l'autorisation. Il y est
placé quand même, pour trois raisons instruites en `research.md` §D1 — il agit
sur `User` et `Organisation`, il est gardé par le catalogue de #115, et la v2 le
fera basculer dans la décision d'accès pour de bon. La tension est réelle ; c'est
le test d'AC6, et non le nom du dossier, qui tient la frontière.

## Traçabilité — les 6 AC de #197

| AC | Où il est tenu | Vérifié par |
|----|----------------|-------------|
| AC1 — les deux tables, organisation portée par le groupe | `models/group.py`, `models/user_group.py`, migration | `test_group_models.py`, `test_migrations.py` |
| AC2 — cinq ressources gardées, classées par le filet | `api/v1/admin_groups.py` | `test_admin_groups_api.py` + `test_public_routes_still_open.py` (**inchangé**) |
| AC3 — trois pouvoirs au catalogue, chacun gardant une ressource | `core/permissions.py` | `test_permissions_catalogue.py` (**inchangé**, paramétré sur `permissions.ALL`) |
| AC4 — `/auth/me` rend les groupes | `api/v1/auth.py`, `schemas/auth.py` | `test_me_groups.py` |
| AC5 — supprimer un utilisateur emporte ses appartenances | `models/user.py` (`cascade="all, delete-orphan"`) | `test_group_models.py` |
| AC6 — aucune décision d'accès ne consulte les groupes | absence, par construction | `test_groups_grant_nothing.py` (comportement **et** AST) |

## Complexity Tracking

> Aucune violation à justifier. Section conservée vide, délibérément.
