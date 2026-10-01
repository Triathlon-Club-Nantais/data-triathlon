# Implementation Plan: Textes légaux du site (mentions légales, confidentialité, CGU)

**Branch**: `feat/332-333-legal-basis-and-pages` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/20261001-150009-legal-pages/spec.md`

## Summary

Trois pages de contenu statique (`/mentions-legales`, `/confidentialite`,
`/cgu`), rangées **hors** du groupe gardé `app/(public_restricted)/` pour rester
lisibles sans code d'accès, et trois liens ajoutés au pied de page déjà rendu
par le layout racine sur toutes les routes. Chaque texte est un module TSX
versionné (titre, date de mise à jour, rubriques), rendu par un gabarit commun.
Les faits juridiques viennent de la décision #332
(`docs/superpowers/specs/2026-10-01-base-legale-decision.md`). Aucun changement
backend.

## Technical Context

**Language/Version**: TypeScript 5, React 19
**Primary Dependencies**: Next.js 16 (App Router), Tailwind, composants `@/components/tcn` et `@/components/layout` (`PageShell`, `PageHeader`)
**Storage**: N/A (contenu versionné dans le dépôt)
**Testing**: vitest + Testing Library (jsdom pour `*.test.tsx`)
**Target Platform**: navigateur, rendu serveur Vercel
**Project Type**: web application (frontend seul pour cette feature)
**Performance Goals**: pages statiques, aucun appel API supplémentaire
**Constraints**: hors garde d'accès (#509) ; aucune dépendance nouvelle (pas de moteur markdown) ; WCAG AA (contraste des liens, titre de document, sommaire navigable)
**Scale/Scope**: 3 pages, 1 composant de liens, 1 gabarit

## Constitution Check

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.2.0).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Textes et libellés en français ; identifiants (`LegalDocument`, `LegalLinks`, `updatedAt`) en anglais ; descriptions de tests en français comme le reste du front. |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Aucun code backend. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests écrits avant chaque page et avant les liens du pied de page ; aucun appel réseau (le seul fetch du pied de page, la version, est déjà mocké). |
| IV | Contrats API et CLI stables | N/A | Aucun endpoint ni sortie CLI touchés. Trois routes front nouvelles, aucune modifiée. |
| V | Neutralité par défaut des paramètres transverses | N/A | Pas de paramètre transverse. |
| VI | Simplicité / YAGNI | ✅ | Contenu en TSX plutôt qu'un moteur markdown (aucune dépendance, liens et tableaux rendus nativement) ; un seul gabarit pour trois pages ; pas de système de versions multiples, l'historique du dépôt en tient lieu. |

## Project Structure

### Documentation (this feature)

```text
specs/20261001-150009-legal-pages/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/routes.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── mentions-legales/page.tsx        # route sœur, hors groupe gardé
│   ├── confidentialite/page.tsx
│   ├── cgu/page.tsx
│   ├── routes-garde-site.test.ts        # + les trois routes, hors groupe gardé
│   └── page-titles.test.tsx             # + les trois titres
└── components/
    ├── layout/VersionFooter.tsx         # rend <LegalLinks /> dans son <footer>
    └── legal/
        ├── types.ts                     # LegalDocument, LegalSection
        ├── legal-routes.ts              # source unique des trois chemins et libellés
        ├── LegalPage.tsx (+ test)       # gabarit : en-tête, date, sommaire, rubriques
        ├── LegalLinks.tsx (+ test)      # les trois liens du pied de page
        └── content/
            ├── mentions-legales.tsx (+ test)
            ├── confidentialite.tsx (+ test)
            └── cgu.tsx (+ test)
```

**Structure Decision**: frontend seul. Les trois routes sont des dossiers
sœurs de `acces/` et `login/` à la racine d'`app/`, ce qui suffit à les sortir
de la garde (`app/(public_restricted)/layout.tsx`) ; le test de placement
existant est étendu pour l'empêcher de régresser. Le pied de page étant rendu
par `app/layout.tsx`, l'ajouter à `VersionFooter` couvre toutes les routes
d'un coup, administration et espace bénévoles compris.

## Complexity Tracking

Aucune violation.
