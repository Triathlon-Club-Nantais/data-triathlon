# Implementation Plan: Suppression d'une déclaration de crédit de bénévolat

**Branch**: `818-suppression-declaration-benevolat` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260901-175006-suppression-declaration-benevolat/spec.md`

## Summary

Ajouter le chemin de suppression manquant de `VolunteerAction` (#818) :
`repository.delete()` → `service.delete()` (journalisé, patron
`accept`/`reject` déjà en place) → `DELETE /admin/volunteer-actions/{id}`
gardée par `athletes:volunteer_validate`. Côté front, le geste est exposé sur
les deux seuls écrans qui affichent une déclaration — la file d'attente admin
(#817, sous `/admin`) et la liste des actions validées de la fiche athlète
(#781, page publique restreinte) — chacun avec le mécanisme de confirmation
adapté à son contexte de montage.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2 · TanStack Query, shadcn/ui, `components/admin/DangerConfirm.tsx`

**Storage**: PostgreSQL (prod, Supabase) / SQLite (dev) — table `volunteer_actions` existante, aucune migration de schéma (suppression de ligne, pas de nouvelle colonne)

**Testing**: pytest (`uv run pytest -m "not integration"`), Vitest + RTL (`npm test`)

**Target Platform**: Web (Render backend, Vercel frontend)

**Project Type**: web-service + frontend (app existante)

**Performance Goals**: N/A — geste d'administration ponctuel, pas de contrainte de débit

**Constraints**: TDD sans réseau (Principe III) ; aucune modification de contrat API existant, uniquement additive (Principe IV)

**Scale/Scope**: 1 méthode repository, 1 méthode service, 1 route API, 1 endpoint client front, 2 points d'exposition UI (file d'attente + fiche athlète), leurs tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants et tests en anglais (`delete`, `test_delete_*`), messages d'erreur et libellés UI en français, sur le patron déjà en place d'`accept`/`reject`. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `volunteer_action_repository.delete()` est la seule à toucher la Session pour construire la requête ; `volunteer_action_service.delete()` orchestre + journalise, ne requête jamais directement. |
| III | TDD sans réseau (non-négociable) | ✅ | Aucun appel réseau dans ce périmètre (pas de scraping) ; tests repository/service/API/composants suivent le rouge → vert habituel. |
| IV | Contrats API et CLI stables | ✅ | Nouvelle route `DELETE /admin/volunteer-actions/{id}`, additive — aucun contrat `/api/v1` existant modifié. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse de lecture (`scope`, `federal_only`, `seasons`) concerné — geste d'écriture ponctuel sur une ressource par id. |
| VI | Simplicité / YAGNI | ✅ | Pas de soft-delete ni de corbeille (hors périmètre, cf. spec §Assumptions) ; réutilise le pouvoir existant plutôt que d'en créer un nouveau ; réutilise `DangerConfirm` existant. |

Aucune violation — pas de Complexity Tracking à remplir.

## Project Structure

### Documentation (this feature)

```text
specs/20260901-175006-suppression-declaration-benevolat/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   └── delete-volunteer-action.md
└── tasks.md              # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── repositories/
│   │   └── volunteer_action_repository.py   # + delete(db, action)
│   ├── services/
│   │   └── volunteer_action_service.py       # + delete(db, admin_user_id, action_id)
│   └── api/v1/
│       └── admin_volunteer_actions.py        # + DELETE /admin/volunteer-actions/{id}
└── tests/
    ├── test_repositories/test_volunteer_action_repository.py
    ├── test_services/test_volunteer_action_service.py
    └── test_api/test_admin_volunteer_actions_api.py   # (peut ne pas exister encore — à vérifier en tasks)

frontend/
├── lib/
│   ├── api/client.ts                          # + deleteVolunteerAction(id)
│   └── queries/admin.ts                       # + useDeleteVolunteerAction()
├── components/
│   ├── benevolat/AdminVolunteerActionsTable.tsx   # + geste suppression (useDangerConfirm)
│   └── athletes/VolunteerActionsList.tsx          # + geste suppression (<DangerConfirm> déclaratif)
└── tests (fichiers `.test.tsx` jumeaux des composants ci-dessus)
```

**Structure Decision**: Web application existante (backend FastAPI + frontend
Next.js). Aucun nouveau module : la feature s'insère dans les fichiers déjà
en place pour `VolunteerAction` (repository, service, router, deux
composants front), sans nouvelle couche ni nouveau répertoire.

## Complexity Tracking

*Aucune entrée — Constitution Check entièrement ✅/N/A.*
