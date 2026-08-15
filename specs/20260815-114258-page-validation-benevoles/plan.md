# Implementation Plan: Page de vérification des résultats par les bénévoles

**Branch**: `20260815-114258-page-validation-benevoles` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260815-114258-page-validation-benevoles/spec.md`

**Note**: Cadrage seul. Implémentation **non commencée**, bloquée par la
fusion de #270 (dépendance dure). #330 (reprise des résultats manuels
antérieurs) est fermée `not_planned` — aucun stock à reprendre, cette
dépendance est levée. Ce plan documente la conception, il ne l'exécute pas.

## Summary

Une page protégée par un mot de passe partagé (5-6 bénévoles, sans SSO
individuel) présente la file des résultats saisis manuellement en attente de
validation (`Participation.is_pending_validation = true`, produit par #270),
permet de renommer l'épreuve associée, de réattribuer le résultat à un autre
athlète, puis de le valider. Deux des trois écritures (renommage,
réattribution) **réutilisent** des fonctions de service déjà livrées
(`admin_actions.update_course`, `admin_actions.reassign_participation`) sous un
`user_id` de compte système dédié ; seule la validation elle-même est une
logique nouvelle. Le mécanisme d'accès est un cookie de session signé par HMAC
avec le mot de passe comme clé — aucune nouvelle table d'authentification,
aucune touche au socle SSO/RBAC existant (#114/#115).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16
App Router (frontend) — inchangé, pas de déviation de stack.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2,
Alembic (backend, tous déjà présents) ; `hmac`/`hashlib`/`secrets` (stdlib,
pas de nouvelle dépendance) pour le cookie signé. Next.js 16, Tailwind,
shadcn/ui + `@base-ui/react` (front, déjà présents).

**Storage**: PostgreSQL (Supabase) / SQLite dev — aucun nouveau schéma, une
seule ligne de données ajoutée (`users`, compte système, cf. `data-model.md`).

**Testing**: pytest (backend, `-m "not integration"`), Vitest + RTL (front) —
inchangé.

**Target Platform**: Web (Render/Vercel), inchangé.

**Project Type**: Application web (backend + frontend), option 2 du template.

**Performance Goals**: Aucune exigence chiffrée au-delà des standards déjà en
place (pas de volume massif attendu, cf. spec § Assumptions — dizaine à
centaine de résultats en attente).

**Constraints**: Le mécanisme d'accès ne doit toucher aucune des quatre tables
du socle SSO (`users` en écriture pure ajout d'une ligne de compte système
excepté, `identities`, `user_sessions`, `allowed_emails`). Aucune migration de
schéma pour le champ pivot (`is_pending_validation`), qui appartient à #270.

**Scale/Scope**: 5-6 bénévoles, un stock de résultats en attente de l'ordre de
la dizaine à la centaine à un instant donné.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | UI et messages d'erreur en français ; nouveaux identifiants (`benevole_access`, `require_benevole_access`, `participation.validate`) en anglais technique, cohérent avec l'existant (`admin_actions`, `admin_action_log`). |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Nouveau routeur `api/v1/benevoles.py` (couche mince) → service (nouveau pour la validation, réutilisé pour renommage/réattribution) → repositories existants. Aucune session touchée hors `app/repositories/`. |
| III | TDD sans réseau (non-négociable) | ✅ | Aucune dépendance réseau introduite (cookie HMAC local, pas d'appel externe) ; tests unitaires attendus pour chaque geste avant code, portés par `tasks.md`. |
| IV | Contrats API et CLI stables | ✅ | Nouvelles routes sous `/api/v1/benevoles/*`, aucune modification d'un contrat `/api/v1` existant. |
| V | Neutralité par défaut des paramètres transverses | N/A | La file n'expose aucun paramètre `scope`/`federal_only` — elle est délibérément non filtrée par club (cf. `research.md` §D5), et ce n'est pas un paramètre transverse au sens du principe (pas de défaut à neutraliser, la feature n'en introduit aucun). |
| VI | Simplicité / YAGNI | ✅ | Pas de nouvelle table d'authentification (cookie HMAC dérivé du mot de passe), réutilisation de `admin_actions`/`core/validation.py` plutôt que duplication. |

Aucune violation à justifier — la section Complexity Tracking reste vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260815-114258-page-validation-benevoles/
├── plan.md              # Ce fichier
├── research.md          # Phase 0 — 5 décisions (D1-D5)
├── data-model.md         # Phase 1 — entités consommées, compte système
├── quickstart.md        # Phase 1 — scénarios de validation
├── contracts/
│   └── api.md            # Phase 1 — 5 routes /api/v1/benevoles/*
└── tasks.md             # Phase 2 (/speckit-tasks) — pas encore généré
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/
│   │   ├── config.py                 # + benevole_shared_password: str = ""
│   │   └── validation.py             # RÉUTILISÉ (produit par #270) — pas modifié ici
│   ├── services/
│   │   ├── benevole_access.py        # NOUVEAU — cookie HMAC : sign/verify, pas de session en base
│   │   └── admin_actions.py          # RÉUTILISÉ — update_course, reassign_participation (user_id = compte système)
│   │                                  # + validate_participation (NOUVEAU, même module, même patron de journalisation)
│   ├── repositories/
│   │   └── participation_repository.py  # + list_pending (filtre is_pending_validation=True) — NOUVEAU, aux côtés des filtres existants
│   ├── api/
│   │   ├── deps.py                   # + require_benevole_access (NOUVEAU, distincte de require_permission)
│   │   └── v1/
│   │       ├── benevoles.py          # NOUVEAU — 5 routes (cf. contracts/api.md)
│   │       └── router.py             # + montage du nouveau routeur
│   └── models/                       # Aucune modification de schéma — une ligne de données (migration)
│       └── (alembic/versions/*)      # NOUVELLE migration de données : compte système « bénévoles »
└── tests/
    ├── test_services/test_benevole_access.py     # NOUVEAU
    ├── test_services/test_admin_actions.py       # + cas validate_participation
    ├── test_repositories/test_participation_repository.py  # + list_pending
    └── test_api/test_benevoles_api.py            # NOUVEAU — les 5 routes, gardées/non gardées

frontend/
├── app/
│   └── benevoles/                    # NOUVEAU — écran hors `/admin/*`, hors nav.config.ts (accès direct par URL + mot de passe)
│       └── page.tsx
├── components/
│   ├── benevoles/                    # NOUVEAU — ValidationQueue, ParticipationPanel
│   │                                  # composent components/ui/{table,dialog,select} + components/tcn/{Card} (cf. research.md §D3)
│   └── (ui/, tcn/ existants, non modifiés)
└── lib/api/
    └── client.ts                      # + appels des 5 routes /benevoles/*
```

**Structure Decision** : application web existante (backend/ + frontend/),
aucune nouvelle app ni service séparé. La feature ajoute un routeur API, un
service d'accès isolé, une extension de repository, et un écran front hors du
périmètre `/admin/*` (accès par mot de passe, pas par SSO — donc pas
d'entrée dans `nav.config.ts`, cohérent avec un accès direct par URL
communiquée aux bénévoles).

## Complexity Tracking

*Aucune entrée — pas de violation de la Constitution Check à justifier.*
