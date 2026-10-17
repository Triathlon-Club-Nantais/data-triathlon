# Implementation Plan: Marquer les adhérents dans PostHog

**Branch**: `feat/1374-posthog-member` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

## Summary

Deux propriétés ajoutées à l'`identify()` de `PostHogSessionSync` (`frontend/app/providers.tsx`), lues sur la session (`is_member`, `athlete !== null`). Aucun changement backend : la propriété serveur `is_staff` reste posée à la connexion, sous le même consentement.

## Technical Context

**Language/Version**: TypeScript / Next.js 16 · **Dependencies**: posthog-js (présent) · **Testing**: vitest · **Storage**: N/A · **Constraints**: consentement (#1159) ; aucune donnée nominative

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue | ✅ | Propriétés techniques en anglais, doc en français. |
| II | Couches | N/A | Front seul. |
| III | TDD | ✅ | Test `providers.test.tsx` écrit d'abord. |
| IV | Contrats | ✅ | Aucun contrat d'API touché. |
| V | Neutralité | N/A | |
| VI | Simplicité | ✅ | Pas d'écriture serveur : l'`identify` existant suffit. |

## Project Structure

`frontend/app/providers.tsx`, `frontend/app/providers.test.tsx`, `docs/analytics-posthog.md`.

## Complexity Tracking

Aucune violation.
