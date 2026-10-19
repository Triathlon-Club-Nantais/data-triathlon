# Implementation Plan: Relevé et rappel des effacements Entra

**Branch**: `epic/1312-member-accounts` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

## Summary

`admin_action_log_repository.list_action_since`, `accounts.pending_entra_deletions(db, since)` (oid non vides, plus anciens d'abord), commande `entra-deletions [--since] [--count]`. Dans `batch.yml`, une étape planifiée lance `--count` sur 7 jours et publie le total en sortie de job ; un job `entra-reminder` (`issues: write`) ouvre ou complète l'issue `ops`, sur le patron de `notify-failure.yml`.

## Technical Context

Python 3.13, Typer, GitHub Actions · aucune dépendance · pytest · aucune migration

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue | ✅ | Sorties françaises, titre d'issue anglais (jeton machine). |
| II | Couches | ✅ | Requête en repository, sélection en service, CLI mince. |
| III | TDD | ✅ | Tests service et CLI d'abord ; le workflow n'est pas testable localement. |
| IV | Contrats | ✅ | Commande nouvelle. |
| V | Neutralité | N/A | |
| VI | Simplicité | ✅ | Réutilise la reprise planifiée et le patron d'issue `ops`. |

## Complexity Tracking

Aucune violation.
