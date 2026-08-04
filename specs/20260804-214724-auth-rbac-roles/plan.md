# Implementation Plan: RBAC — rôles composables et protection des ressources d'administration

**Branch**: `feat-auth-rbac-r-les-administrateur-validateur-e` | **Date**: 2026-08-04 (v2) | **Spec**: [spec.md](spec.md)

**Input**: `specs/20260804-214724-auth-rbac-roles/spec.md`

## Summary

Poser un système de droits **composable à chaud** et fermer les ressources
d'administration, sans toucher au site public.

Quatre tables — `organisations`, `roles`, `role_permissions`, `user_roles` — un
catalogue de pouvoirs qui vit **dans l'application** et non en base, une garde
`require_permission(P.X)` qui nomme un pouvoir et compose `current_user` de #114,
et deux garde-fous qui rendent l'édition à chaud sûre : l'invariant « il reste un
administrateur actif », vérifié sur l'**état** et non par chemin, et la règle de
non-amplification.

Trois faits de terrain structurent le reste :

1. **Le préfixe `/admin/` ne décrit pas l'audience** — `POST /admin/pending-providers`
   est le signalement anonyme du formulaire public. La garde se pose route par route.
2. **Deux routes destructives sont ouvertes à Internet** — `POST /participations`
   et `DELETE /participations/{id}`. Elles sont fermées ici.
3. **Le frottement du redéploiement est documenté par le propriétaire** (#170,
   #95, `autoDeploy: false`). Une matrice de droits en dur le reconduirait sur
   l'objet le plus susceptible de changer.

> **v2 — ce qui a changé.** La v1 modélisait deux rôles figés en `StrEnum`, sans
> organisation, avec `require_role(*roles)`. Trois arbitrages produit du
> 2026-08-04 (multi-club, plus de trois rôles, édition à chaud) l'ont annulée.
> La différence de forme tient en un mot : **`role_id` au lieu de `role`**.
> Le détail est en fin de document, §Genèse de la révision.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic,
Typer. **Aucune dépendance nouvelle** — ni bibliothèque RBAC, ni moteur de
politiques. Cinq options ont été instruites et écartées sur mesures
(research.md §D1, §D2).

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en
test. Quatre tables nouvelles, une colonne renommée, une ajoutée.

**Testing**: pytest (`-m "not integration"`), Vitest + RTL. Aucun réseau, aucun
Docker — c'est l'une des raisons du refus des PDP externes.

**Target Platform**: Render (backend, `autoDeploy: false`), Vercel (frontend).

**Project Type**: application web, backend et frontend séparés.

**Performance Goals**: une requête indexée supplémentaire par requête protégée
(jointure sur trois tables, `LIMIT 1`). **Zéro requête ajoutée sur le site
public** : aucune route publique n'appelle la garde.

**Constraints**: décision prise à chaque requête, jamais mise en cache (FR-016).
Toutes les routes du projet sont `def` et le limiteur AnyIO est mesuré à 40 : la
garde doit rester une lecture indexée.

**Scale/Scope**: `users` est borné par `AUTH_ALLOWED_EMAILS` — de l'ordre de la
dizaine. C'est ce qui autorise `GET /admin/users` sans pagination.

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue métier français / technique English | ✅ | Codes de pouvoirs, slugs, identifiants, tests et journaux en anglais. Libellés du catalogue, messages de `DomainError` et rapports CLI en français — le Principe I range explicitement les `DomainError` dans le « français utilisateur ». |
| II | Architecture en couches | ✅ | `require_permission` (api) → `services/auth/authorization` → `repositories/user_role_repository`. Motif exact de `deps.current_user` → `services/auth/session`. Aucune couche sautée. Le catalogue est dans `core/`, sans état ni session. |
| III | TDD sans réseau (non-négociable) | ✅ | Aucun réseau sur ce périmètre. Les tests fabriquent sessions et rôles en base. C'est aussi le principe qui a disqualifié les PDP externes, dont la voie de test officielle passe par Docker. |
| IV | Contrats API et CLI stables | ✅ | Aucun champ retiré, aucune sémantique inversée. Le renommage de colonne est **interne** (la `hybrid_property` rend `is_reliable` inchangé) ; `GET /auth/me` est enrichi de façon additive. Quatre routes passent d'ouvertes à protégées — c'est l'objet de la feature, et deux fermaient une anomalie. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse de lecture ajouté. |
| VI | Simplicité / YAGNI | ⚠️ | Voir Complexity Tracking. |

## Project Structure

### Documentation

```text
specs/20260804-214724-auth-rbac-roles/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/{admin-api.md, cli.md}
└── checklists/requirements.md
```

### Source Code

```text
backend/
├── alembic/versions/
│   └── <rev>_rbac_and_manual_reliability.py   # 4 tables + seed + 2 colonnes
├── app/
│   ├── core/permissions.py                # NOUVEAU — catalogue (dataclass gelée)
│   ├── api/
│   │   ├── deps.py                        # + require_permission, InsufficientPermissionError
│   │   └── v1/
│   │       ├── admin.py                   # gardes + reliability
│   │       ├── admin_roles.py             # NOUVEAU — 7 routes (permissions, roles, users)
│   │       ├── participations.py          # gardes sur POST et DELETE
│   │       └── auth.py                    # /auth/me + permissions (additif)
│   ├── models/
│   │   ├── organisation.py · role.py · role_permission.py · user_role.py   # NOUVEAUX
│   │   ├── user.py                        # + relationship roles
│   │   └── course.py                      # renommage + reliability_override + hybrid
│   ├── repositories/
│   │   ├── role_repository.py · user_role_repository.py    # NOUVEAUX
│   │   └── user_repository.py             # + list_all, find_by_email
│   ├── schemas/admin.py                   # NOUVEAU
│   ├── services/
│   │   ├── auth/authorization.py          # NOUVEAU — décision, CRUD, invariants
│   │   ├── course_review.py               # NOUVEAU
│   │   └── import_service.py              # 1 ligne : nom de la colonne écrite
│   └── cli/commands/grant_role.py         # NOUVEAU
└── tests/
    ├── test_auth/
    │   ├── test_public_routes_still_open.py   # change de nature (FR-025)
    │   ├── test_require_permission.py · test_admin_roles_api.py
    │   └── test_lockout_invariant.py · test_no_privilege_escalation.py
    ├── test_permissions_catalogue.py          # lecteur d'AST (FR-026)
    ├── test_migrations.py                     # 3 assertions : nom de colonne
    ├── test_cli/test_grant_role.py
    └── test_services/{test_authorization.py, test_course_review.py}

frontend/
├── components/admin/PendingProvidersTable.tsx   # affiche le refus 403
└── lib/api/server.ts                            # − listPendingProviders (morte)
```

**Structure Decision**: application web existante. La feature est backend ;
l'interface ne reçoit qu'un correctif d'affichage et une suppression de code
mort. Les trois écrans d'administration des rôles relèvent de la sous-issue
d'interface de #81 — une fois ce modèle en place, ce sont des PR front pures.

## Ordre d'implémentation — quatre couches, chacune livrable

### Couche 1 — un porteur de rôle franchit une porte fermée

Migration (4 tables + seed d'une organisation et de deux rôles système) →
`core/permissions.py` → repositories → `services/auth/authorization` →
`require_permission` → gardes sur `GET`/`DELETE /admin/pending-providers`,
`POST`/`DELETE /participations` → évolution du filet → test de catalogue →
`grant-role`.

`grant-role` est **dans** cette couche : sans elle, la porte est fermée et
personne ne peut la franchir. Le filet change de nature **dans la même tâche**
que la première route fermée — un filet rouge qu'on tolère est un filet mort.

**Livrée seule** : les ressources d'administration et les deux routes
destructives sont protégées, le signalement public fonctionne, l'exploitant
s'attribue un rôle depuis le serveur. US1 et US2.

### Couche 2 — les rôles se composent sans redéploiement

`admin_roles.py` (7 routes), `services/auth/authorization` (CRUD, invariant de
verrouillage, non-amplification), `GET /auth/me` enrichi.

**Livrée seule** : US3 et US4. C'est l'exigence produit qui a rouvert la spec.

### Couche 3 — le pouvoir de qualité

Renommage de colonne + `reliability_override` + `hybrid_property` →
`services/course_review` → `PATCH .../reliability`.

Indépendante des couches 2 et 4 ; ne dépend de la couche 1 que par la garde.
US5.

### Couche 4 — l'écran cesse de mentir

`PendingProvidersTable` affiche le refus 403 ; `apiServer.listPendingProviders`
supprimée. Dépend de la couche 1 pour être observable.

Les couches 2, 3 et 4 sont indépendantes entre elles et ne partagent aucun
fichier.

## Risques et points de vigilance

| Risque | Parade |
| --- | --- |
| Fermer `POST /admin/pending-providers` et supprimer le signalement public | Le filet **classe** cette route comme publique ; le quickstart la vérifie sans cookie. |
| Le filet devient aveugle au lieu de changer de nature | Toute ressource `/admin/*` non classée fait rougir la suite, en nommant la route. |
| Un pouvoir déclaré que rien ne vérifie, ou une garde citant un code inexistant | Test lisant l'AST, dans les deux sens (patron de `test_core_http.py`). |
| Se verrouiller dehors par un chemin non prévu | Invariant sur l'**état d'arrivée**, pas par chemin. Quatre sites d'appel, une définition. |
| `roles:write` devenant `root` | Non-amplification : on ne distribue que ce qu'on porte. `is_superuser` posable seulement par un superutilisateur. |
| Deux rôles globaux de même slug | Index partiel `WHERE organisation_id IS NULL`, déclaré pour **les deux** dialectes — sinon index complet sur l'autre moteur. |
| Un index invisible des tests | `tests/conftest.py` construit le schéma par `create_all` : les index vivent dans `__table_args__`, pas seulement dans la migration. |
| Confondre 401 et 403 | La garde compose `current_user` : ordre structurel. |
| Le renommage `is_reliable` casse un consommateur | Surface relevée : une écriture, une déclaration, trois assertions de migration. Le DTO et le front lisent la `hybrid_property`. |
| PostgreSQL non éprouvé | Consigné au quickstart, comme `unaccent` de #163. |

## Complexity Tracking

| Violation | Pourquoi | Alternative rejetée |
| --- | --- | --- |
| **Principe VI** — 4 tables et un catalogue là où 1 table suffirait au besoin littéral de l'issue #115 (2 rôles, 6 routes) | Le besoin a changé le 2026-08-04 : plus de trois rôles, permissions par fonctionnalité, **édition à chaud**. Le Principe VI interdit l'abstraction « au cas où », pas la satisfaction d'une exigence exprimée. Le frottement visé est documenté par le propriétaire dans deux issues ouvertes (#170, #95) et par `autoDeploy: false`. | Livrer le modèle v1 (`user_roles(user_id, role)`) puis migrer. Chiffré : **+50 %** si la migration suit immédiatement, **+120 %** après l'épique #81 — chaque sous-issue ajoutant des routes gardées *et* ~50 lignes de tests écrits contre des rôles. |
| **Principe VI** — `organisations` créée avec une seule ligne, `organisation_id` jamais lue par une règle | Décision produit explicite (« modèle maintenant, usage plus tard »). Gain technique secondaire : `user_roles.organisation_id` non nul, donc pas d'index partiel à maintenir. | Ne rien créer. **L'argument technique qui la justifiait a été réfuté** : l'ajout après coup coûte 6 lignes et 8,1 ms (`render_as_batch=True` déjà actif, 5 révisions sur 8 l'emploient). Retenue sur la décision produit seule, ce qui est dit ici plutôt que déguisé en contrainte. |

**Deux inclusions qui ne sont pas de la spéculation** : `GET /admin/users` (sans
lui, attribuer un rôle exige un identifiant qu'aucune ressource n'expose) et
`reliability_override` (sans elle, le geste du validateur est effacé au premier
re-scrape — `import_service.py:311-320` réécrit le verdict à chaque import).

## Genèse de la révision (2026-08-04)

Cinq instructions parallèles : Casbin, modèle relationnel, moteurs externes, puis
deux adversaires — l'un chargé de démolir le consensus obtenu, l'autre de prendre
au mot l'exigence produit.

**Ce que la confrontation a établi** :

- la convergence des trois premières était un **artefact** — les trois ont
  recopié la même erreur documentaire (`Course` unique par 3 colonnes, alors que
  le modèle en porte 4). Ce qui a été confronté au code tient ; ce qui a été
  déduit du corpus, non ;
- les trois avaient **refusé l'exigence d'édition à chaud** en la présentant
  comme une impossibilité physique. Elle ne l'est que pour les *points de
  contrôle*, pas pour la composition des rôles ;
- l'argument « créer `organisations` maintenant, sinon `batch_alter_table` » est
  **faux**, mesuré ;
- Casbin et les cinq moteurs externes restent écartés, et cette fois sur des
  mesures reproductibles plutôt que sur une intuition.

**Ce qui a survécu de la v1** : la distinction 401/403, la garde route par route,
le refus d'une garde de préfixe, `POST /admin/pending-providers` publique, la
commande d'amorçage, et le modèle du verdict de fiabilité.
