# Implementation Plan: Carte résultat à télécharger

**Branch**: `feat/1371-result-card` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

## Summary

`frontend/lib/result-card.ts` : `resultCardModel(participation)` (données affichées, pures et testables) et `drawResultCard(ctx, model, fonts)` (dessin sur un contexte 2D, testable avec un contexte factice), plus `downloadResultCard(model, fileName)` (canvas hors DOM, `toBlob`, lien de téléchargement). `components/participations/ResultCardDownload.tsx` décide de l'affichage (session hydratée, fiche rattachée = athlète du résultat, validé, non relais) et appelle le module. Posé dans les actions du `PageHeader` de la page détail.

## Technical Context

**Language/Version**: TypeScript / Next.js 16 · **Dependencies**: aucune nouvelle (Canvas 2D natif) · **Testing**: vitest + RTL, contexte 2D factice · **Storage**: N/A · **Constraints**: page rendue côté serveur, session lue par `useHydratedSession` (#1090)

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue | ✅ | Libellés français, identifiants anglais. |
| II | Couches | N/A | Front seul, aucune route. |
| III | TDD | ✅ | Modèle, dessin et composant testés d'abord. |
| IV | Contrats | ✅ | Aucun contrat touché. |
| V | Neutralité | N/A | |
| VI | Simplicité | ✅ | Canvas natif plutôt qu'une bibliothèque de capture ; modèle séparé du dessin, seule abstraction, exigée par FR-004. |

## Project Structure

`frontend/lib/result-card.ts` (+ test), `frontend/components/participations/ResultCardDownload.tsx` (+ test), page `app/(public_restricted)/courses/[id]/participations/[participationId]/page.tsx`, `docs/frontend/athlete-retenu.md`.

## Complexity Tracking

Aucune violation.
