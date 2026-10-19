# Implementation Plan: Suppression d'un compte par l'exploitant

**Branch**: `epic/1312-member-accounts` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

## Summary

`user_repository.required_reference_counts` (décompte par colonne) et `reassign_required_references` (UPDATE vers le compte système), lus sur `required_references()` déjà dérivé du schéma. `accounts.force_delete_account(db, user, dry_run)` : refus du compte système, décompte, puis réattribution et `delete_account(origin="operator")`. Commande `delete-account --user-id|--email [--yes]`, couche mince.

## Technical Context

Python 3.13, SQLAlchemy, Typer · aucune dépendance · pytest (`db_session_fk` pour les FK) · aucune migration

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue | ✅ | Sorties CLI en français, identifiants anglais. |
| II | Couches | ✅ | Requêtes en repository, règle en service, CLI mince. |
| III | TDD | ✅ | Tests repository, service, CLI d'abord. |
| IV | Contrats | ✅ | Commande nouvelle ; `Origin` gagne une valeur dans le journal. |
| V | Neutralité | N/A | |
| VI | Simplicité | ✅ | Réutilise l'inventaire des références et `delete_account`. |

## Complexity Tracking

Aucune violation.
