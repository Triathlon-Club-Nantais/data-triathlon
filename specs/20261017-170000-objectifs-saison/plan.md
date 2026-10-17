# Implementation Plan: Objectifs de saison de l'athlète rattaché

**Branch**: `feat/1373-season-goals` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

## Summary

Table `season_goals` (possédée par le compte, ajoutée à `_OWNED_TABLES`), `season_goal_repository`, service `services/season_goals.py` (règles, progression), routes `GET/POST /auth/me/goals`, `PUT/DELETE /auth/me/goals/{goal_id}` sous la session (404 hors propriétaire). La progression lit les résultats de la fiche rattachée par `participation_repository` (`carried_by`, `validated_clause`, bornes de saison). Front : carte « Mes objectifs » sur l'Accueil pour un compte rattaché.

## Technical Context

**Language/Version**: Python 3.13, TypeScript / Next.js 16 · **Dependencies**: aucune nouvelle · **Storage**: une table, une migration · **Testing**: pytest, vitest · **Constraints**: écritures sous `origin_guard` ; aucune donnée lisible par un tiers ; durée « H:MM:SS » validée comme ailleurs (`ManualResultForm`, `DUREE`)

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue | ✅ | Identifiants anglais, messages et UI français. |
| II | Couches | ✅ | Requêtes en repositories, règles et calcul en service, routes fines. |
| III | TDD | ✅ | Tests repository, service, API, composant d'abord. |
| IV | Contrats | ✅ | Routes nouvelles seulement. |
| V | Neutralité | N/A | |
| VI | Simplicité | ✅ | Progression calculée à la lecture, aucune table d'état ; deux sortes seulement. |

## Project Structure

Backend : `models/season_goal.py`, migration, `repositories/season_goal_repository.py`, ajouts à `participation_repository` (lectures de progression), `services/season_goals.py`, `schemas/season_goal.py`, routes dans `api/v1/auth.py`. Frontend : types, client, hooks, `components/dashboard/SeasonGoals.tsx`, pose sur l'Accueil, politique de confidentialité. Docs : `backend/app/models/AGENTS.md`.

## Complexity Tracking

Aucune violation.
