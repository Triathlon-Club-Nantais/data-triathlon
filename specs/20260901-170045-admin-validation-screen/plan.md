# Implementation Plan: Écran de validation admin des déclarations de crédit d'athlète

**Branch**: `816-retrait-auto-declaration` (implémentée avec #816) | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260901-170045-admin-validation-screen/spec.md`

## Summary

Construit le premier écran frontend pour le workflow de validation admin
des déclarations de crédit d'athlète (#779), dont l'API existe déjà mais
n'a jamais eu de consommateur. `/admin/benevolat` (vidé de son ancien
contenu par #816) reçoit son contenu définitif : liste des déclarations en
attente, accepter/refuser. Comble au passage l'absence de nom d'athlète
dans `AdminVolunteerActionOut` par une relation ORM et deux champs de
réponse additifs (research.md D1).

## Technical Context

**Language/Version**: Python 3.13 (backend) + TypeScript strict / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2 ; TanStack Query, shadcn/ui (`ui/table`)

**Storage**: aucun changement de schéma — relation ORM pure

**Testing**: pytest (TDD rouge→vert pour le code neuf) ; vitest

**Target Platform**: web

**Project Type**: web application (backend + frontend)

**Performance Goals**: aucun objectif dédié — volume de déclarations en attente faible

**Constraints**: aucune nouvelle garde d'accès — `athletes:volunteer_validate` (#779) reste la seule ; aucune régression sur #778/#809/#781

**Scale/Scope**: 1 relation ORM + 2 propriétés de lecture, 2 champs de schéma additifs, 1 requête enrichie (`selectinload`), 1 composant frontend neuf, 3 hooks, 1 clé de cache, 3 méthodes client, 2 champs de type, 1 entrée de navigation, contenu définitif d'une page déjà existante

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | UI et libellés en français, identifiants techniques en anglais, cohérent avec l'existant |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | La relation et son eager-load restent dans le modèle/repository ; le service et la route existants (#779) ne changent pas |
| III | TDD sans réseau (non-négociable) | ✅ | Tests backend (propriété du modèle, requête enrichie) et frontend (composant, hooks) écrits avant l'implémentation |
| IV | Contrats API et CLI stables | ✅ | Élargissement additif de réponse uniquement (research.md/contracts) — aucune rupture |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` concerné |
| VI | Simplicité / YAGNI | ✅ | Reprend un patron existant (`AdminVolunteerDeclarationTable.tsx`) plutôt que d'en inventer un nouveau ; pas de nouvel endpoint pour combler l'absence de nom d'athlète |

## Project Structure

### Documentation (this feature)

```text
specs/20260901-170045-admin-validation-screen/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── enriched-response.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/volunteer_action.py                    # MODIFIED — relation athlete + propriétés
│   ├── schemas/volunteer_action.py                    # MODIFIED — AdminVolunteerActionOut enrichi
│   └── repositories/volunteer_action_repository.py    # MODIFIED — selectinload dans list_pending()
└── tests/
    ├── test_repositories/test_volunteer_action_repository.py  # MODIFIED — assertion sur athlete_nom/prenom
    └── test_api/test_admin_volunteer_actions_api.py            # MODIFIED — assertion sur les deux champs

frontend/
├── app/admin/benevolat/page.tsx                        # MODIFIED — contenu définitif
├── components/benevolat/
│   └── AdminVolunteerActionsTable.tsx (+.test.tsx)     # NEW
├── lib/
│   ├── queries/admin.ts                                # MODIFIED — 3 hooks ajoutés
│   ├── queries/keys.ts                                 # MODIFIED — 1 clé ajoutée
│   ├── api/client.ts                                   # MODIFIED — 3 méthodes ajoutées
│   └── types.ts                                        # MODIFIED — AdminVolunteerActionOut enrichi
└── components/layout/nav.config.ts                     # MODIFIED — entrée admin ajoutée
```

**Structure Decision**: Web application existante — aucun nouveau fichier
backend, un seul composant frontend neuf, le reste enrichit des fichiers
déjà en place. Implémentée dans la continuité directe de #816, même
branche, avant tout push (research.md D3 de #816).

## Complexity Tracking

*Aucune violation à justifier — tous les principes passent ✅ ou N/A.*
