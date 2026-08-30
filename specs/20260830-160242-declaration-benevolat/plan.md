# Implementation Plan: Déclaration de bénévolat

**Branch**: `20260830-160242-declaration-benevolat` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260830-160242-declaration-benevolat/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Permettre à un membre connecté de déclarer sa propre activité de bénévolat
(titre + description), en attente de validation par un admin ; un admin peut
déclarer pour n'importe quel membre (validée d'office), valider une
déclaration en attente, et supprimer n'importe quelle déclaration — l'auteur
peut aussi supprimer la sienne. Nouvelle table `volunteer_declarations`
(voir data-model.md), indépendante du `VolunteerAction` du quota de saison
(#709/#741, décision actée avec l'utilisateur — research.md D2). Deux
nouveaux pouvoirs RBAC (`benevolat:read`, `benevolat:manage`), deux routers
API (self-service + admin, patron `feedback.py`/`admin_feedback.py`), deux
pages front (self-service + admin).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 App Router (frontend) — stack existante, aucune déviation.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic (backend) ; React, Tailwind, shadcn/ui, `@tanstack/react-query` (patron `lib/queries/admin.ts`) côté front.

**Storage**: PostgreSQL (Supabase) en prod, SQLite en dev — une nouvelle table `volunteer_declarations` via migration Alembic.

**Testing**: `pytest` (backend, `-m "not integration"`, aucun réseau ici — feature 100 % interne) ; `vitest` (frontend).

**Target Platform**: Backend Render (Linux), frontend Vercel — sans changement d'infra.

**Project Type**: Web application (backend + frontend), patron déjà en place.

**Performance Goals**: Aucun objectif chiffré spécifique — volume attendu (déclarations de bénévolat d'un club) sans commune mesure avec les endpoints de résultats de course.

**Constraints**: Contrat `/api/v1` — nouvelles routes uniquement, aucune modification de contrat existant (Principe IV). Suppression physique, jamais de soft-delete (FR-008, research.md D6).

**Scale/Scope**: 2 nouveaux endpoints self-service, 4 nouveaux endpoints admin, 1 table, 2 pouvoirs RBAC, 2 pages front (self-service + admin).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Table/colonnes/endpoints en anglais (`volunteer_declarations`, `title`, `status`), UI et messages d'erreur en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `volunteer_declaration_repository.py` seul à construire des requêtes ; `volunteer_declaration_service.py` orchestre (transactions), les deux routers ne touchent pas la `Session`. |
| III | TDD sans réseau (non-négociable) | ✅ | Feature 100 % interne (pas de réseau tiers) — tests unitaires classiques, pas de marker `integration`. |
| IV | Contrats API et CLI stables | ✅ | Nouvelles routes uniquement sous `/api/v1` et `/admin` ; aucune route existante modifiée. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse de lecture (`scope`, `federal_only`…) sur cette feature — le filtrage self-service/admin est une question d'autorisation, pas de portée de comptage. |
| VI | Simplicité / YAGNI | ✅ | Pas de soft-delete, pas d'état « rejetée » distinct, pas de lien avec le quota de saison — cf. research.md D2/D5/D6. |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   └── volunteer_declaration.py          # nouveau (data-model.md)
│   ├── schemas/
│   │   └── volunteer_declaration.py          # nouveau — Create/Out/AdminCreate/AdminOut
│   ├── repositories/
│   │   └── volunteer_declaration_repository.py  # nouveau — seule couche Session
│   ├── services/
│   │   └── volunteer_declaration_service.py  # nouveau — create/list/delete/validate/create_for_other
│   ├── api/v1/
│   │   ├── volunteer_declarations.py         # nouveau — self-service (current_user)
│   │   └── admin_volunteer_declarations.py   # nouveau — admin (benevolat:read/manage)
│   │   └── router.py                         # modifié — enregistrer les 2 routers
│   └── core/
│       └── permissions.py                    # modifié — FEATURE_VOLUNTEERING, benevolat:read/manage
├── migrations/versions/
│   └── <rev>_add_volunteer_declarations.py   # nouveau — Alembic autogenerate
└── tests/
    ├── test_repositories/
    │   └── test_volunteer_declaration_repository.py # nouveau
    └── test_api/
        ├── test_volunteer_declarations_api.py       # nouveau — self-service
        └── test_admin_volunteer_declarations_api.py # nouveau — admin
        # Le service (create_self/create_for_other/validate/delete_*/list_*)
        # n'a pas de fichier de test dédié : il est exercé exclusivement via
        # ces tests API, patron déjà suivi par admin_actions.declare_volunteer_action
        # (#709) — corrigé après /speckit-analyze (finding I2), qui avait
        # relevé la divergence avec un test_services/ listé puis jamais généré.

frontend/
├── app/
│   ├── (public_restricted)/benevolat/
│   │   └── page.tsx                          # nouveau — self-service : formulaire + liste perso
│   └── admin/benevolat/
│       └── page.tsx                          # nouveau — vue d'ensemble + validation + création pour tiers
├── components/
│   └── benevolat/
│       ├── VolunteerDeclarationForm.tsx      # nouveau
│       ├── VolunteerDeclarationList.tsx      # nouveau
│       └── AdminVolunteerDeclarationTable.tsx  # nouveau — patron PendingProvidersTable
├── lib/
│   ├── api/client.ts                         # modifié — appels des 6 endpoints
│   ├── queries/
│   │   ├── volunteer-declarations.ts         # nouveau — hooks react-query self-service
│   │   └── admin.ts                          # modifié — hooks admin (patron feedback)
│   └── types.ts                              # modifié — VolunteerDeclaration, statuts
└── (tests co-localisés *.test.tsx, patron existant)
```

**Structure Decision**: Web application (Option 2), patron déjà en place —
aucune nouvelle app ni changement de topologie. Deux routers backend
(self-service/admin) au lieu d'un seul, sur le patron exact
`feedback.py`/`admin_feedback.py` (« le chemin dit qui peut appeler »). Deux
pages front, sous `(public_restricted)/benevolat` (nouveau, distinct de
`app/benevoles` — vérification de résultats, sans rapport) et `admin/benevolat`
(patron `admin/retours-utilisateurs`).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucune violation — tous les principes sont ✅ ou N/A (voir Constitution Check
ci-dessus). Rien à justifier ici.
