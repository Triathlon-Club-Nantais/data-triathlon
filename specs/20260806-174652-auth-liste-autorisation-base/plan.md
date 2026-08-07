# Implementation Plan: Liste d'autorisation en base, gérée depuis le back-office

**Branch**: `auth-liste-dautorisation-en-base-et-gestion-depu` | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260806-174652-auth-liste-autorisation-base/spec.md`

## Summary

La liste des adresses autorisées quitte `AUTH_ALLOWED_EMAILS` pour une table
`allowed_emails`, relue à chaque tentative de connexion. Trois ressources sous
`/api/v1/admin/`, gardées par **un** pouvoir du catalogue (`allowed_emails:manage`),
un écran `/admin/acces`, et une commande `allow-email` jumelle de
`grant-role` pour l'amorçage. Le retrait d'une adresse **désactive** ses
titulaires, ce qui fait tomber leurs sessions par l'invariant de jointure déjà
en place ; l'ajout les réactive, symétriquement. La reprise de production est une
**migration de données** qui lit la variable d'environnement au moment du
`alembic upgrade head` déjà présent dans le `startCommand` — pas de fenêtre, pas
de geste manuel.

Le point d'architecture ouvert par l'issue est tranché : `Settings.auth_is_configured`
cesse de compter la liste, `GET /auth/methods` n'interroge aucune table, et le
fail-closed reste appliqué au seul endroit où il décide, le retour de parcours.
C'est le seul écart au Principe IV, justifié en Complexity Tracking.

## Technical Context

**Language/Version**: Python 3.13 (backend) ; TypeScript 5 / Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic, Typer ; TanStack Query, shadcn/ui. **Aucune dépendance nouvelle** — `EmailStr` s'appuie sur `email-validator`, déjà installé par `fastapi[standard]`.

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en test.

**Testing**: pytest (`uv run pytest -m "not integration"`), Vitest + RTL (`npm test`).

**Target Platform**: Render (backend, `startCommand` = `alembic upgrade head && uvicorn`), Vercel (frontend).

**Project Type**: web — `backend/` + `frontend/`.

**Performance Goals**: **zéro requête ajoutée sur le chemin authentifié chaud** (`session.resolve` est inchangé) ; **+1 `SELECT`** par tentative de connexion, sur un parcours déjà réseau-lié ; **zéro requête** sur `/auth/methods`, route publique.

**Constraints**: aucune fenêtre pendant laquelle un contributeur autorisé se verrait refuser la connexion au déploiement (SC-005) ; aucune route publique existante ne se ferme (FR-019) ; le méta-test AST de `tests/test_permissions_catalogue.py` exige qu'un pouvoir ajouté garde au moins une ressource ; `tests/test_auth/test_public_routes_still_open.py` exige que toute ressource sous `/api/v1/admin/` soit gardée ou déclarée publique nommément.

**Scale/Scope**: quelques dizaines d'adresses — pas de pagination, pas de recherche. 1 table, 1 migration, 3 ressources HTTP, 1 commande CLI, 1 composant d'écran.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants, tests et logs en anglais (`allowed_emails`, `AllowedEmail`, `allow-email`) ; UI, messages `DomainError` et textes CLI en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `allowed_email_repository` est la seule couche à toucher `Session` ; `provisioning._is_allowed(db, email)` l'appelle, il ne construit aucune requête. Aucune exemption nouvelle au Principe II. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque tâche de `tasks.md` posera son test rouge d'abord. Aucun réseau : la feature n'a aucune sortie HTTP. |
| IV | Contrats API et CLI stables | ⚠️ | `GET /auth/methods` change de **condition d'émission** (voir Complexity Tracking). Le reste est additif : trois ressources nouvelles, une commande nouvelle, aucun champ retiré. |
| V | Neutralité par défaut des paramètres transverses | N/A | La feature n'introduit aucun paramètre transverse de lecture (`scope`, `federal_only`, `seasons`). |
| VI | Simplicité / YAGNI | ✅ | **Un** pouvoir plutôt qu'une paire `read`/`write` ; réutilisation de `administrateurs_preserves()` et de `user_repository.find_by_email()` plutôt qu'un invariant réécrit ; un bloc d'écran plutôt qu'une navigation de back-office ; aucune dépendance ajoutée. |

**Re-check après Phase 1** : les quatre artefacts de conception ne déplacent
aucun statut. Le seul point qui aurait pu basculer le Principe II est la
désactivation en cascade du retrait — elle passe par `user_repository`, pas par
une requête écrite dans le service. Le seul qui aurait pu basculer le Principe VI
est le champ `created_by_user_id` : il est conservé parce que l'écran l'affiche
(« ajoutée le … par … »), donc il n'est pas de la donnée morte.

## Project Structure

### Documentation (this feature)

```text
specs/20260806-174652-auth-liste-autorisation-base/
├── plan.md              # Ce fichier
├── research.md          # Phase 0 — les huit décisions et leurs alternatives rejetées
├── data-model.md        # Phase 1 — la table, ses invariants, ce qu'elle n'enregistre pas
├── quickstart.md        # Phase 1 — validation de bout en bout, dev et production
├── contracts/
│   ├── admin-api.md     # Les trois ressources HTTP
│   └── cli.md           # La commande `allow-email`
├── checklists/
│   └── requirements.md  # Qualité de la spec (déjà produit)
└── tasks.md             # Phase 2 — /speckit-tasks, PAS produit ici
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── <rev>_allowed_emails.py          # NOUVEAU : table + reprise depuis l'environnement
├── app/
│   ├── core/
│   │   ├── config.py                    # MODIFIÉ : réglage supprimé, garde allégé
│   │   └── permissions.py               # MODIFIÉ : + P.ALLOWED_EMAILS_MANAGE dans ALL
│   ├── main.py                          # MODIFIÉ : l'avertissement de démarrage ne cite plus le réglage
│   ├── models/
│   │   └── allowed_email.py             # NOUVEAU
│   ├── repositories/
│   │   ├── allowed_email_repository.py  # NOUVEAU
│   │   └── user_repository.py           # MODIFIÉ : set_active(), docstring de list_all
│   ├── schemas/
│   │   └── admin.py                     # MODIFIÉ : AllowedEmailRead / AllowedEmailCreate
│   ├── services/auth/
│   │   ├── allowed_emails.py            # NOUVEAU : liste / ajout / retrait, invariants
│   │   └── provisioning.py              # MODIFIÉ : _is_allowed(db, email)
│   ├── api/v1/
│   │   ├── admin_allowed_emails.py      # NOUVEAU : les trois ressources
│   │   └── router.py                    # MODIFIÉ : montage
│   └── cli/
│       ├── __init__.py                  # MODIFIÉ : enregistrement de la commande
│       └── commands/allow_email.py      # NOUVEAU
└── tests/
    ├── test_config.py                   # MODIFIÉ : les 4 tests du réglage disparaissent
    ├── test_repositories/test_allowed_email_repository.py   # NOUVEAU
    ├── test_services/test_allowed_emails.py                 # NOUVEAU
    ├── test_api/test_admin_allowed_emails.py                # NOUVEAU
    ├── test_cli/test_allow_email.py                         # NOUVEAU
    ├── test_migrations.py               # MODIFIÉ : la reprise depuis l'environnement s'y teste
    └── test_auth/                       # MODIFIÉ : conftest, provisioning, api_methods,
                                         #   not_configured, startup_warning, flow,
                                         #   identity_rejection, public_routes_still_open

frontend/
├── app/admin/acces/page.tsx             # NOUVEAU : l'écran des accès
├── app/admin/page.tsx                   # MODIFIÉ : n'a plus qu'un sujet
├── components/layout/nav.config.ts      # MODIFIÉ : section « Gestion des utilisateurs »
├── components/layout/AppNav.tsx         # MODIFIÉ : filtrage par pouvoir
├── components/admin/
│   ├── AllowedEmailsTable.tsx           # NOUVEAU
│   └── AllowedEmailsTable.test.tsx      # NOUVEAU
└── lib/
    ├── api/client.ts                    # MODIFIÉ : trois appels
    ├── queries/{admin.ts,keys.ts}       # MODIFIÉ : trois hooks, une clé
    └── types.ts                         # MODIFIÉ : AllowedEmail

# Hors code — la suppression du réglage se propage :
render.yaml, backend/.env.example, backend/README.md, docs/ci-cd.md,
backend/app/services/auth/AGENTS.md (« huit réglages » → sept),
backend/app/cli/commands/grant_role.py (message d'erreur qui cite la variable).
```

**Structure Decision**: application web à deux piles, `backend/` (FastAPI en
couches) et `frontend/` (Next.js App Router). La feature suit les couches
existantes sans en créer : un modèle, un repository, un service, un router, une
commande CLI ; côté front, un composant dans `components/admin/` et trois hooks
dans `lib/queries/admin.ts`, sur le patron exact de `PendingProvidersTable`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principe IV** — `GET /auth/methods` change de condition d'émission : avec une liste d'autorisation vide, il rendait `[]`, il rendra désormais les moyens configurés. La **forme** de la réponse (`[{slug, label}]`) et son code de statut sont inchangés ; c'est la docstring « moyens **effectivement** disponibles » qui s'affaiblit. | La liste d'autorisation cesse d'être une donnée de configuration. La faire peser sur cette route la transformerait en requête base **sur une route publique, non authentifiée, appelée par la page de connexion**. Le limiteur de threads AnyIO est mesuré à 40 et toutes les routes du projet sont `def` : c'est exactement le levier de charge que #114 a fermé sur le retour de parcours. Le seul consommateur de la route est notre propre page de connexion, et le fail-closed n'est pas perdu — il tombe au retour du parcours, en `account_not_allowed`, code déjà contractuel et déjà traduit par l'interface. | **Requête base à chaque appel de `/auth/methods`** : fidèle au comportement actuel, au prix exact décrit ci-contre. **Garde de configuration sur un autre critère** (« au moins un fournisseur configuré ») : c'est déjà ce que fait `registry.enabled_methods()`, le garde deviendrait redondant. **Conserver `AUTH_ALLOWED_EMAILS` en union avec la base** : deux sources de vérité, interdit par FR-012 et par le principe « ne pas préserver la compatibilité ascendante ». |

## Phase 0 — Research

Voir [research.md](./research.md). Huit décisions, toutes closes, aucune
`NEEDS CLARIFICATION` restante :

| # | Décision |
|---|----------|
| R1 | La lecture passe par un repository, sans cache — `provisioning._is_allowed(db, email)` |
| R2 | La reprise de production est une **migration de données** lisant `os.environ` |
| R3 | **Un seul** pouvoir, `allowed_emails:manage`, rangé dans la fonctionnalité « Rôles et accès » existante |
| R4 | Le retrait désactive, l'ajout réactive — et pourquoi la symétrie n'est pas optionnelle |
| R5 | FR-018 réutilise `administrateurs_preserves()` au lieu d'une règle « pas sa propre adresse » |
| R6 | Le garde de configuration perd la liste (⚠️ Principe IV ci-dessus) |
| R7 | L'idempotence des écritures se joue sur la contrainte `UNIQUE`, pas sur une lecture préalable |
| R8 | La validation d'adresse est `EmailStr`, sans dépendance nouvelle |

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — la table `allowed_emails`, ses invariants,
  et ce qu'elle n'enregistre pas.
- [contracts/admin-api.md](./contracts/admin-api.md) — `GET`, `POST`,
  `DELETE /api/v1/admin/allowed-emails`, leurs codes et leurs refus.
- [contracts/cli.md](./contracts/cli.md) — `allow-email`, ses sorties et ses
  codes de retour.
- [quickstart.md](./quickstart.md) — la validation de bout en bout, en
  développement et à la mise en production.
