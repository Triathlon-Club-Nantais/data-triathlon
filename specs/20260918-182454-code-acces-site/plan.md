# Implementation Plan: Code d'accès du site : affichage en clair, reword, validité 3 mois

**Branch**: `20260918-182454-code-acces-site` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260918-182454-code-acces-site/spec.md`

## Summary

L'écran `/acces` (gate d'accès au site entier, #509) masque aujourd'hui le
code d'accès saisi (`type="password"`) et emploie le vocabulaire "mot de
passe" alors qu'il s'agit d'un code partagé communiqué hors ligne. La session
posée après validation expire après 7 jours (`SITE_ACCESS_SESSION_TTL_DAYS`).
Cette feature : (1) affiche le code saisi en clair, (2) reword "mot de passe"
→ "code d'accès" sur cet écran uniquement, (3) porte le TTL de session à 90
jours. Aucun changement de schéma DB, aucun changement de contrat API
(`/api/v1/site-access/session` garde son champ JSON `password`), aucune
nouvelle dépendance.

## Technical Context

**Language/Version**: TypeScript 5 (frontend, Next.js 16 App Router) ; Python 3.13 (backend, config uniquement — pas de logique métier nouvelle)

**Primary Dependencies**: shadcn/ui `Input` (frontend, `frontend/components/site-access/SiteAccessGate.tsx`) ; pydantic-settings (`backend/app/core/config.py`, `Settings.site_access_session_ttl_days`)

**Storage**: N/A — aucune migration, la session est un cookie signé HMAC (`shared_password.sign_cookie`/`verify_cookie`), pas une ligne en base

**Testing**: `npm test` (Vitest, `SiteAccessGate.test.tsx`) ; `uv run pytest -m "not integration"` (`test_site_access_gate.py`, `test_admin_site_access_api.py`)

**Target Platform**: Web — front Vercel, backend Render (aucune variable d'environnement `SITE_ACCESS_SESSION_TTL_DAYS` explicite en prod : le défaut code s'applique dans tous les environnements, `docs/ci-cd.md`)

**Project Type**: Web application (monorepo `frontend/` + `backend/` existant)

**Performance Goals**: N/A — pas d'objectif de performance nouveau, changement de texte/attribut HTML et d'une constante entière

**Constraints**: Pas de renommage du champ JSON `password` ni des identifiants techniques (`id="site-password"`) — contrat `/api/v1` publié (Principe IV) ; l'écran `/admin/acces` et le gate bénévoles (#271) restent hors périmètre

**Scale/Scope**: 1 composant frontend (+ son test), 1 constante de configuration backend (+ ses tests), 1 ligne de doc (`docs/ci-cd.md`) à mettre à jour

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Les textes reword restent en français (déjà le cas) ; aucun identifiant technique renommé. |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Aucune requête ni service touché : une constante de config et du texte UI. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests existants (`SiteAccessGate.test.tsx`, `test_site_access_gate.py`) étendus/adaptés avant le code, sans réseau réel. |
| IV | Contrats API et CLI stables | ✅ | Champ JSON `password` et comportement de l'endpoint inchangés ; seul le TTL (déjà un paramètre serveur) et le texte affiché changent. |
| V | Neutralité par défaut des paramètres transverses | N/A | Ne concerne pas un paramètre transverse d'endpoint de lecture (`scope`/`federal_only`/`seasons`). |
| VI | Simplicité / YAGNI | ✅ | Changement de valeur de constante + attribut HTML `type` + libellés, sans nouvelle abstraction (pas de toggle afficher/masquer). |

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
frontend/
├── components/site-access/
│   ├── SiteAccessGate.tsx        # champ en clair + reword (titre, libellé, aide, erreur)
│   └── SiteAccessGate.test.tsx   # sélecteurs /mot de passe/i → /code d'accès/i

backend/
├── app/core/config.py            # site_access_session_ttl_days: 7 → 90
└── tests/
    ├── test_auth/test_site_access_gate.py   # TTL implicite via shared_password.sign_cookie
    └── test_services/test_site_access.py

docs/
└── ci-cd.md                      # ligne SITE_ACCESS_SESSION_TTL_DAYS (défaut 7 j → 90 j)
```

**Structure Decision**: Web application existante (`frontend/` + `backend/`,
Option 2). Aucun nouveau répertoire : la feature modifie un composant
frontend déjà en place et une constante de configuration backend déjà
en place. Pas de `contracts/` (aucune nouvelle interface exposée) ni de
`data-model.md` distinct (aucune nouvelle entité — la session reste un
cookie signé, pas une ligne en base).

## Complexity Tracking

*(vide — aucune violation de la Constitution Check ci-dessus)*
