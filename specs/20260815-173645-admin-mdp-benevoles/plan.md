# Implementation Plan: Gestion admin du mot de passe partagé bénévoles

**Branch**: `20260815-173645-admin-mdp-benevoles` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260815-173645-admin-mdp-benevoles/spec.md`

**Note**: Dépend de la branche #271 (non fusionnée) — cette branche en part
directement plutôt que de `main`.

## Summary

Remplace la variable d'environnement `BENEVOLE_SHARED_PASSWORD` (#271) par
une configuration en base, gérée par un administrateur habilité
(`benevole_access:manage`, nouveau pouvoir RBAC) : trois routes
(`GET`/`PUT`/`POST .../generate`) pour consulter l'état, remplacer le mot de
passe par une saisie, ou en générer un sécurisé. Le mot de passe est haché
(`scrypt`, stdlib) et salé, jamais stocké réversible. Le mécanisme de
signature du cookie de session bénévole, qui utilisait le mot de passe en
clair comme clé HMAC (#271), bascule sur un `session_secret` distinct,
régénéré à chaque remplacement — ce qui préserve la propriété « changer le
mot de passe invalide toutes les sessions » sans jamais avoir besoin de
relire le mot de passe en clair.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16
App Router (frontend) — inchangé.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2,
Alembic (backend, tous déjà présents) ; `hashlib`/`secrets`/`hmac` (stdlib,
research.md §D1) pour le hachage et la génération — aucune dépendance
ajoutée. Next.js 16, Tailwind, shadcn/ui (front, déjà présents).

**Storage**: PostgreSQL (Supabase) / SQLite dev — une nouvelle table à une
seule ligne (`benevole_access_config`), aucune modification de schéma
existant.

**Testing**: pytest (backend, `-m "not integration"`), Vitest + RTL (front) —
inchangé.

**Target Platform**: Web (Render/Vercel), inchangé.

**Project Type**: Application web (backend + frontend), option 2 du template.

**Performance Goals**: Aucune exigence chiffrée au-delà des standards déjà en
place — un geste d'administration occasionnel (changement de mot de passe),
pas un chemin de charge.

**Constraints**: Le mécanisme de connexion et de garde côté bénévoles doit
rester fonctionnellement identique pour un bénévole (FR-008) — seule la
source de vérité change, en interne. Aucune régression sur les tests
existants de #271 (`test_benevoles_api.py`, `test_benevole_access.py`).

**Scale/Scope**: Un administrateur à la fois modifie cette configuration en
pratique (5-6 bénévoles, changements occasionnels) ; pas de volume à
anticiper.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Libellés d'écran et messages d'erreur en français ; identifiants techniques (`benevole_access_config`, `BENEVOLE_ACCESS_MANAGE`, `password_hash`, `session_secret`) en anglais, cohérent avec le reste du catalogue de pouvoirs. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Nouveau routeur `admin_benevole_access.py` (couche mince) → `benevole_access.py` étendu (hachage, génération) → nouveau `benevole_config_repository.py` (seule couche qui touche la Session pour cette table). |
| III | TDD sans réseau (non-négociable) | ✅ | Aucune dépendance réseau ; tests unitaires pour le hachage/vérification, la rotation du secret de session, les trois routes admin, et la non-régression du login bénévole existant — tous avant le code, portés par `tasks.md`. |
| IV | Contrats API et CLI stables | ✅ | Nouvelles routes additives sous `/api/v1/admin/benevoles/*` ; les routes bénévoles existantes (#271) gardent leur contrat externe inchangé (FR-008). Aucune CLI concernée. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` impliqué. |
| VI | Simplicité / YAGNI | ✅ | Une seule ligne de configuration, pas d'historique ni de versionnement des mots de passe (non demandé) ; réutilise `hashlib`/`secrets` du stdlib plutôt qu'une dépendance de hachage tierce (research.md §D1). |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/20260815-173645-admin-mdp-benevoles/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── api.md           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   └── benevole_access_config.py      # nouveau : BenevoleAccessConfig
│   ├── repositories/
│   │   └── benevole_config_repository.py  # nouveau : seule couche touchant la Session pour cette table
│   ├── services/
│   │   └── benevole_access.py             # étendu : hash_password/verify_password/generate_password/new_session_secret
│   ├── api/
│   │   ├── deps.py                        # modifié : require_benevole_access lit la config DB
│   │   └── v1/
│   │       ├── benevoles.py               # modifié : open_session vérifie le hash, signe avec session_secret
│   │       └── admin_benevole_access.py    # nouveau : 3 routes (GET/PUT/POST generate)
│   └── core/
│       ├── config.py                      # modifié : retrait de benevole_shared_password
│       └── permissions.py                 # modifié : nouveau P.BENEVOLE_ACCESS_MANAGE
├── alembic/versions/
│   └── <rev>_benevole_access_config.py    # nouveau : migration de schéma (pas data-only)
└── tests/
    ├── services/test_benevole_access.py         # étendu : hachage, rotation du secret
    ├── api/test_admin_benevole_access.py        # nouveau : 3 routes + garde RBAC
    └── api/test_benevoles_api.py                 # étendu : non-régression login bénévole

frontend/
├── app/admin/acces/
│   └── page.tsx                           # étendu : section « Accès bénévoles »
├── components/admin/
│   └── BenevoleAccessConfig.tsx           # nouveau : formulaire remplacement + bouton génération
└── lib/api/
    └── client.ts                          # étendu : getBenevoleAccessConfig/putBenevoleAccessConfig/generateBenevoleAccessPassword
```

**Structure Decision**: Option 2 (application web backend + frontend), déjà
en place dans ce dépôt. Aucune nouvelle couche : la feature s'insère dans
l'architecture en couches existante (`api → services → repositories → DB`),
en ajoutant un repository et un service étendu, jamais en la contournant.

## Complexity Tracking

Aucune violation du Constitution Check — cette section reste vide.
