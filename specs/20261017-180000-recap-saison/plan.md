# Implementation Plan: Récap de saison de l'athlète rattaché

**Branch**: `feat/1372-season-recap` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

## Summary

Page `app/(public_restricted)/dashboard/recap/page.tsx` (serveur : titre, lecture de `?saison=`) qui rend `components/dashboard/SeasonRecap.tsx` (client) : session hydratée, `apiClient.getAthlete(fiche, { seasons })`, chiffres calculés par les règles existantes (`isPodium`, `BestTimesCard`/`bestTimes`), challenges filtrés sur la saison. Lien depuis la carte « Mes objectifs » de l'Accueil.

## Technical Context

**Language/Version**: TypeScript / Next.js 16 · **Dependencies**: aucune nouvelle · **Testing**: vitest + RTL · **Storage**: N/A

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue | ✅ | UI française, identifiants anglais. |
| II | Couches | N/A | Front seul, route existante. |
| III | TDD | ✅ | Tests du composant d'abord. |
| IV | Contrats | ✅ | Aucun contrat touché. |
| V | Neutralité | ✅ | `federal_only` laissé à son défaut neutre. |
| VI | Simplicité | ✅ | Réutilise `isPodium`, `BestTimesCard`, `getAthlete`. |

## Complexity Tracking

Aucune violation.
