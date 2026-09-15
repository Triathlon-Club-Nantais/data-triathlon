# Implementation Plan: Guide utilisateur intégré

**Branch**: `865-guide-utilisateur` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260915-125111-guide-utilisateur/spec.md`

## Summary

Ajouter deux pages de guide statiques dans l'application : `/guide` (6 sections
ancrées, une par fonctionnalité membre) et `/admin/guide` (15 sections ancrées,
une par fonctionnalité admin), chacune atteignable en un clic depuis la
navigation existante et directement par URL (`/guide#club`, etc.). Contenu
100% statique en dur dans le dépôt (pas de CMS, pas de nouvelle table DB) :
chaque section porte un titre, des étapes concises, un cas d'usage et au moins
une capture d'écran servie depuis `public/guide/`. Réutilise le pattern de
navigation existant (`nav.config.ts`, `ecran()`, `estVisible()`) plutôt que
d'en créer un nouveau. Feature frontend uniquement, aucun changement backend.

## Technical Context

**Language/Version**: TypeScript strict (Next.js 16 App Router), cohérent avec le reste de `frontend/`

**Primary Dependencies**: Next.js 16 (App Router, `next/image`), React, Tailwind CSS, shadcn/ui, `lucide-react` (icône de nav) — toutes déjà présentes, aucune nouvelle dépendance

**Storage**: N/A côté données (pas de DB) ; captures d'écran en fichiers statiques sous `frontend/public/guide/`

**Testing**: Vitest + React Testing Library (convention existante du dépôt, projet `jsdom`)

**Target Platform**: Web, Vercel — responsive jusqu'à ~400px (contrainte artefact standard du dépôt)

**Project Type**: Web application (monorepo backend+frontend existant) — cette feature ne touche que `frontend/`

**Performance Goals**: Aucun objectif chiffré spécifique ; pages statiques, donc alignées sur les autres pages de contenu du dépôt (pas de fetch API bloquant)

**Constraints**: Contenu en français (Principe I) ; aucune modification de l'API `/api/v1` (Principe IV, hors périmètre) ; captures d'écran maintenues manuellement (assumption documentée dans spec.md, pas de détection d'obsolescence automatique)

**Scale/Scope**: 21 sections de guide (6 membres + 15 admin) réparties sur 2 pages, chacune avec ≥1 capture d'écran

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.2.0).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Contenu du guide (visible utilisateur) en français ; identifiants de composants/routes en anglais |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Feature 100% frontend, aucun backend/DB touché |
| III | TDD sans réseau (non-négociable) | ✅ | Tests Vitest/RTL sur le rendu des sections et la garde admin ; contenu statique, aucun appel réseau à mocker |
| IV | Contrats API et CLI stables | N/A | Aucun contrat API ni CLI modifié |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` concerné |
| VI | Simplicité / YAGNI | ✅ | Contenu statique en dur, réutilisation intégrale du pattern de nav existant — pas de CMS, pas d'abstraction nouvelle |

Aucune violation : la section « Complexity Tracking » reste vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260915-125111-guide-utilisateur/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

Pas de `contracts/` : la feature n'expose aucune interface externe (pas d'API,
pas de CLI) — voir research.md.

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── (public_restricted)/
│   │   └── guide/
│   │       ├── page.tsx              # Guide membre : sommaire + 6 sections ancrées
│   │       └── page.test.tsx
│   └── admin/
│       └── guide/
│           ├── page.tsx              # Guide admin : sommaire + 15 sections ancrées
│           └── page.test.tsx
├── components/
│   ├── guide/
│   │   ├── GuideSection.tsx          # Rendu d'une section (titre, étapes, cas d'usage, capture)
│   │   ├── GuideSommaire.tsx         # Table des matières / liens d'ancre
│   │   ├── guide-content.membre.ts   # Contenu des 6 sections membres
│   │   ├── guide-content.admin.ts    # Contenu des 15 sections admin
│   │   └── guide-content.test.ts     # Chaque section a bien ≥1 capture + contenu non vide
│   └── layout/
│       └── nav.config.ts             # + 1 entrée : "Guide" (section consulter) — le lien admin vit dans app/admin/layout.tsx, voir research.md
└── public/
    └── guide/
        ├── membre/*.png              # Captures d'écran des 6 sections membres
        └── admin/*.png               # Captures d'écran des 15 sections admin
```

**Structure Decision**: Deux pages (une par audience) plutôt que 21 routes
dédiées — chaque section reste atteignable directement via une ancre
(`/guide#club`), ce qui satisfait FR-010 sans multiplier les fichiers de
route. Le guide admin vit sous `app/admin/` pour hériter de la garde de
session déjà posée par `app/admin/layout.tsx` (FR-011) ; le guide membre vit
sous `app/(public_restricted)/` comme les autres pages membres, gardé par le
même mot de passe de site. Le contenu (`guide-content.*.ts`) est séparé du
rendu (`GuideSection.tsx`) pour que le test de complétude (FR-006, FR-007)
porte sur la donnée plutôt que sur le DOM rendu.

## Complexity Tracking

*Aucune violation de la Constitution Check — section vide.*
