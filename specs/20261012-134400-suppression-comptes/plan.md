# Implementation Plan: Suppression des comptes (sur demande et après 5 ans d'inactivité)

**Branch**: `feat/1326-account-deletion` (empilée sur `feat/1323-entra-external-id`, cible finale `epic/1312-member-accounts`) | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20261012-134400-suppression-comptes/spec.md`.

## Summary

Une colonne `users.last_seen_at` (posée à l'ouverture de session, repoussée au plus une fois par jour par la résolution de session) et un service `services/auth/accounts.py` qui supprime physiquement un compte : refus si une donnée à référence obligatoire le cite, refus si l'opération fait perdre le dernier administrateur (`administrateurs_preserves`), jamais le compte système. Deux appelants : `DELETE /api/v1/auth/me` (suppression volontaire, efface les cookies, 204) et `retention_service.purge_expired` (comptes sans rôle inactifs depuis 5 ans à la date près, compteurs `accounts_deleted` / `accounts_skipped`). Côté interface, « Supprimer mon compte » dans le menu utilisateur avec une boîte de confirmation. Politique de confidentialité, avenant de base légale et procédure Entra mis à jour.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Typer ; React Query, shadcn/ui (`Dialog` déjà présent) ; aucune dépendance nouvelle

**Storage**: PostgreSQL (prod), SQLite (dev/tests) ; une colonne nouvelle `users.last_seen_at`, une migration Alembic avec rattrapage depuis `created_at`

**Testing**: pytest sans réseau (fixtures `db_session`, `db_session_fk` pour vérifier les FK comme PostgreSQL), vitest + RTL

**Target Platform**: Render (backend), Vercel (frontend)

**Project Type**: application web (backend + frontend)

**Performance Goals**: au plus une écriture par compte et par jour pour l'activité (SC-004) ; la purge parcourt les comptes sans rôle inactifs (≈ 1 000 comptes au plus), une requête d'existence par référence obligatoire et par candidat

**Constraints**: routes `def` ; écritures protégées par `core/origin_guard` (comme `POST /auth/logout`) ; aucune adresse ni nom dans le journal (identifiant, origine et `oid` Entra pseudonymes) ; FK sans `ondelete` (contrainte active en PostgreSQL seulement), donc mise à vide applicative

**Scale/Scope**: ~1 000 comptes, une suppression volontaire occasionnelle, une passe hebdomadaire

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants anglais (`last_seen_at`, `delete_account`, `accounts_deleted`), messages `DomainError`, rapport CLI et UI en français, tests en anglais. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Inventaire des références et requêtes dans `user_repository` ; décision dans `services/auth/accounts.py` ; la route et `retention_service` délèguent. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque tâche de code a sa tâche de test écrite et vue échouer avant ; migration éprouvée par `test_migrations.py` et sur SQLite jetable. |
| IV | Contrats API et CLI stables | ✅ | Ajouts seulement : route `DELETE /auth/me`, deux champs dans la sortie `--json` de `purge-retention`, deux lignes dans son rapport texte. Aucun schéma existant modifié. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse touché. |
| VI | Simplicité / YAGNI | ✅ | Inventaire des FK lu dans `Base.metadata` plutôt qu'une liste tenue à la main ; une colonne, pas de table d'activité ; pas d'appel Graph à Entra. |

Re-check post-design : inchangé.

## Project Structure

### Documentation (this feature)

```text
specs/20261012-134400-suppression-comptes/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── auth-delete-me.md
│   └── cli-purge-retention.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/<rev>_users_last_seen_at.py
├── app/
│   ├── models/user.py                       # last_seen_at
│   ├── repositories/user_repository.py      # références, mise à vide, touch, candidats inactifs
│   ├── services/auth/accounts.py            # delete_account, purge_inactive (nouveau)
│   ├── services/auth/session.py             # pose et repousse last_seen_at
│   ├── services/retention_service.py        # accounts_deleted, accounts_skipped
│   ├── api/v1/auth.py                       # DELETE /auth/me
│   └── cli/reports.py, cli/commands/purge_retention.py
└── tests/ (test_auth, test_services, test_cli, test_migrations.py)

frontend/
├── components/auth/UserMenu.tsx, DeleteAccountDialog.tsx (nouveau)
├── lib/api/client.ts, lib/queries/auth.ts
├── lib/admin-action-log.ts                   # account.delete, origin, entra_oids, auteur « Système »
└── components/legal/content/confidentialite.tsx

docs/
├── superpowers/specs/2026-10-01-base-legale-decision.md  # avenant
└── auth/membres.md ou backend/app/services/auth/AGENTS.md
infra/entra-external-id/AGENTS.md                         # rappel de l'étape manuelle
```

**Structure Decision**: application web existante ; un module de service nouveau dans `services/auth/`, à côté de `session.py` et `provisioning.py`, parce que le compte est l'objet du socle d'authentification.

## Livraison

Une PR, `feat/1326-account-deletion` → `epic/1312-member-accounts` (après rebase sur l'epic une fois #1323 fusionnée), portant `Refs #1312` et `Refs #1326`. La PR parapluie gagne `Closes #1326`.

## Complexity Tracking

Aucune violation.
