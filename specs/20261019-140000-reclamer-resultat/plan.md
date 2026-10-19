# Implementation Plan: Réclamer un résultat rangé sur une autre fiche

**Branch**: `epic/1360-personal-space` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

## Summary

Table `result_claims` (`user_id` possédé, `participation_id` en `ON DELETE CASCADE`, `UNIQUE(user_id, participation_id)`), `result_claim_repository`, service `services/result_claims.py` (demande, annulation, liste des siennes, file avec indices, validation par `reassign_participation`, refus). Routes `GET/POST /auth/me/result-claims`, `DELETE /auth/me/result-claims/{id}` ; `GET /admin/result-claims`, `POST .../{id}/approve|reject`. Pastille `claims` = demandes de fiche + réclamations de résultat. Front : `ResultClaimAction` sur la page détail du résultat ; `ResultClaimsTable` dans une section dédiée de `/admin/rattachements`, distincte par titre, pastille de sorte, explication et verbes.

## Technical Context

Python 3.13, FastAPI, Alembic ; Next.js 16 · aucune dépendance · une migration · pytest, vitest

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue | ✅ | |
| II | Couches | ✅ | Requêtes en repository, règles en service, validation par le geste admin existant. |
| III | TDD | ✅ | Tests d'abord à chaque couche. |
| IV | Contrats | ✅ | Routes nouvelles ; la pastille `claims` garde sa forme, son compte s'élargit. |
| V | Neutralité | N/A | |
| VI | Simplicité | ✅ | Réutilise `reassign_participation`, la purge d'orphelins, le pouvoir et l'écran existants. |

## Complexity Tracking

Aucune violation.
