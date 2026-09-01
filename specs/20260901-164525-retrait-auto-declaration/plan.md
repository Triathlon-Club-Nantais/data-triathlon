# Implementation Plan: Retrait de l'auto-déclaration de bénévolat

**Branch**: `816-retrait-auto-declaration` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260901-164525-retrait-auto-declaration/spec.md`

## Summary

Retire intégralement le domaine `VolunteerDeclaration` (#751,
auto-déclaration de bénévolat) — routes, service, repository, schémas,
modèle et table, pouvoirs `benevolat:read`/`benevolat:manage`, composants
frontend, hooks, entrées de client API, entrées de navigation. `/benevolat`
ne porte plus que la section de crédit d'un athlète (#778/#809).
`/admin/benevolat` est reconstruite dans la même fenêtre de travail par
#817, pour ne jamais traverser d'état vide en production (research.md D3).

## Technical Context

**Language/Version**: Python 3.13 (backend) + TypeScript strict / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic ; TanStack Query

**Storage**: PostgreSQL (prod) / SQLite (dev) — migration Alembic (`op.drop_table`)

**Testing**: pytest (retrait de tests avec le code qu'ils couvraient) ; vitest

**Target Platform**: web

**Project Type**: web application (backend + frontend)

**Performance Goals**: aucun objectif dédié

**Constraints**: `/admin/benevolat` ne doit jamais rendre une page vide sur une branche partagée — #817 est implémentée dans la même fenêtre ; `VolunteerAction` (#778/#779/#781/#809) reste inchangé

**Scale/Scope**: suppression de 7 routes, 1 service, 1 repository, 1 schéma, 1 table (+ migration), 2 pouvoirs + 1 feature de catalogue orpheline, 4 composants frontend (+ leurs tests), 1 fichier de hooks entier, 4 hooks dans un fichier partagé, 2 clés de cache, 7 méthodes client, 4 interfaces TypeScript, 2 entrées de navigation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Suppression pure, aucun nouvel identifiant |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Suppression symétrique sur les trois couches, rien ne saute de niveau |
| III | TDD sans réseau (non-négociable) | ✅ | Tests retirés avec le code qu'ils couvraient, suite verte à chaque étape ; #817 (livrée dans la même fenêtre) suit son propre cycle TDD pour son code neuf |
| IV | Contrats API et CLI stables | ⚠️ | Retrait de 7 routes `/api/v1` — justifié en Complexity Tracking |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` concerné |
| VI | Simplicité / YAGNI | ✅ | Raison d'être de la sous-issue — retire un domaine redondant plutôt que de le garder par prudence |

## Project Structure

### Documentation (this feature)

```text
specs/20260901-164525-retrait-auto-declaration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── removed-endpoints.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/volunteer_declarations.py              # DELETED
│   ├── api/v1/admin_volunteer_declarations.py        # DELETED
│   ├── api/v1/router.py                              # MODIFIED — retrait des deux enregistrements
│   ├── api/v1/volunteer_actions.py                   # MODIFIED — commentaire corrigé (D5)
│   ├── services/volunteer_declaration_service.py     # DELETED
│   ├── repositories/volunteer_declaration_repository.py  # DELETED
│   ├── schemas/volunteer_declaration.py              # DELETED
│   ├── models/volunteer_declaration.py               # DELETED
│   ├── models/__init__.py                            # MODIFIED — retrait import/export
│   └── core/permissions.py                           # MODIFIED — BENEVOLAT_READ/MANAGE/FEATURE_VOLUNTEERING retirés
├── alembic/versions/                                  # NEW — migration drop_table
└── tests/
    ├── test_api/test_volunteer_declarations_api.py         # DELETED
    ├── test_api/test_admin_volunteer_declarations_api.py   # DELETED
    ├── test_api/test_admin_volunteer_actions_api.py        # MODIFIED — commentaire corrigé (D5)
    ├── test_repositories/test_volunteer_declaration_repository.py  # DELETED
    ├── test_core/test_permissions.py                       # MODIFIED — CODES_ATTENDUS
    └── test_auth/test_public_routes_still_open.py           # MODIFIED — ROUTES_VOLUNTEER_DECLARATIONS_FERMEES retiré

frontend/
├── app/(public_restricted)/benevolat/page.tsx         # MODIFIED — section auto-déclaration retirée
├── components/benevolat/
│   ├── VolunteerDeclarationForm.tsx (+.test.tsx)       # DELETED
│   ├── VolunteerDeclarationList.tsx (+.test.tsx)       # DELETED
│   ├── AdminVolunteerDeclarationCreateForm.tsx (+.test.tsx)  # DELETED
│   ├── AdminVolunteerDeclarationTable.tsx (+.test.tsx) # DELETED
│   └── VolunteerActionForm.tsx                         # MODIFIED — commentaire corrigé (D5)
├── lib/
│   ├── queries/volunteer-declarations.ts               # DELETED
│   ├── queries/admin.ts                                # MODIFIED — 4 hooks retirés
│   ├── queries/keys.ts                                 # MODIFIED — 2 clés retirées
│   ├── api/client.ts                                   # MODIFIED — 7 méthodes retirées
│   └── types.ts                                        # MODIFIED — 4 interfaces retirées
└── components/layout/nav.config.ts                     # MODIFIED — 2 entrées retirées
```

**Structure Decision**: Web application existante — suppression pure sur
backend et frontend, aucun nouveau fichier hors artefacts `specs/` et la
migration Alembic. #817 (écran de validation) s'ajoute dans la même
fenêtre de travail, avant tout partage de branche.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Retrait de 7 routes `/api/v1` (Principe IV) | Domaine fonctionnellement redondant avec `VolunteerAction` (#778/#779/#809), décision produit explicite de consolider sur ce dernier | Garder les routes « au cas où » : c'est exactement le chemin mort que le Principe VI proscrit — aucun appelant frontend après le retrait des composants qui les utilisaient, et jamais un contrat externe documenté au sens du Principe IV |
