# Implementation Plan: Ouvrir le formulaire de crédit d'un athlète au mot de passe du site

**Branch**: `809-formulaire-mot-de-passe-site` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260901-141216-formulaire-mot-de-passe-site/spec.md`

## Summary

Retire l'exigence de session SSO individuelle sur `POST /volunteer-actions`
(#778) — le mot de passe partagé du site (déjà en place, inchangé) devient
la seule garde. Mécanisme : `Depends(optional_user)` au lieu de
`Depends(current_user)`, patron déjà utilisé par `POST /feedback` (#267).
`declared_by_user_id` devient nullable (migration Alembic) pour accueillir
une déclaration sans identité individuelle, sur le patron de
`UserFeedback.user_id`. Côté front, la section de crédit d'un athlète sort
du bloc conditionné par la session SSO ; le formulaire d'auto-déclaration
(#751) reste inchangé.

## Technical Context

**Language/Version**: Python 3.13 (backend) + TypeScript strict / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic ; TanStack Query

**Storage**: PostgreSQL (prod) / SQLite (dev) — une migration Alembic (colonne rendue nullable)

**Testing**: pytest (backend, TDD rouge→vert) ; vitest (frontend)

**Target Platform**: web

**Project Type**: web application (backend + frontend)

**Performance Goals**: aucun objectif dédié

**Constraints**: `require_site_access` reste l'unique garde de la route ; aucune régression sur le cas connecté (SSO) ; aucun changement au domaine #779 (validation admin) ni #751 (auto-déclaration)

**Scale/Scope**: 1 dépendance de route changée, 1 colonne rendue nullable (+ migration), 2 schémas Pydantic élargis (`int` → `int | None`), 1 fonction service + 1 fonction repository élargies, 1 entrée retirée d'un test d'inventaire de routes, 1 section frontend déplacée hors garde de session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Aucun nouvel identifiant hors norme existante |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Le changement traverse les couches dans le bon sens (schéma → route → service → repository → modèle), rien ne saute de niveau |
| III | TDD sans réseau (non-négociable) | ✅ | Tests d'ouverture de route et de valeur nulle écrits avant l'implémentation, suite verte à chaque étape |
| IV | Contrats API et CLI stables | ⚠️ | Garde individuelle retirée sur une route — justifié en Complexity Tracking |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` concerné |
| VI | Simplicité / YAGNI | ✅ | Réutilise un mécanisme (`optional_user`) et un patron de colonne (`UserFeedback.user_id`) déjà en place, pas de nouvelle abstraction |

## Project Structure

### Documentation (this feature)

```text
specs/20260901-141216-formulaire-mot-de-passe-site/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── volunteer-actions-api-change.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/volunteer_action.py                    # MODIFIED — declared_by_user_id nullable
│   ├── api/v1/volunteer_actions.py                    # MODIFIED — optional_user au lieu de current_user
│   ├── services/volunteer_action_service.py            # MODIFIED — declared_by_user_id: int | None
│   ├── repositories/volunteer_action_repository.py     # MODIFIED — create_pending() : declared_by_user_id: int | None
│   └── schemas/volunteer_action.py                     # MODIFIED — VolunteerActionSelfOut/AdminVolunteerActionOut
├── alembic/versions/                                    # NEW — migration (colonne nullable)
└── tests/
    ├── test_api/test_volunteer_actions_api.py           # MODIFIED — test_sans_session_rend_401 → 201 sans auteur
    └── test_auth/test_public_routes_still_open.py        # MODIFIED — ROUTES_VOLUNTEER_ACTIONS_FERMEES retiré

frontend/
└── app/(public_restricted)/benevolat/page.tsx           # MODIFIED — section crédit d'athlète hors garde de session
```

**Structure Decision**: Web application existante — changement ciblé sur la
chaîne verticale d'une route déjà en place (api→service→repository→modèle)
plus un ajustement d'affichage conditionnel côté front. Aucun nouveau
fichier hors artefacts `specs/` et la migration Alembic.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Retrait de la garde SSO individuelle sur `POST /volunteer-actions` (Principe IV) | Direction produit explicite : le mot de passe du site doit suffire, la SSO est réservée à la validation admin (#779, inchangée) | Garder la garde SSO « pour la stabilité du contrat » irait contre l'intention produit exprimée — et ce n'est pas une rupture de contrat : la route ne perd aucune capacité (un appelant SSO continue de fonctionner à l'identique), elle en gagne une (accès sans SSO), cf. contracts/volunteer-actions-api-change.md |
