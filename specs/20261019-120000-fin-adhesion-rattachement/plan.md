# Implementation Plan: Fin du statut adhérent par rattachement, détachement par le club

**Branch**: `epic/1312-member-accounts` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

## Summary

`club_member_repository.is_linked_licensee(db, athlete_id, season)` ; `membership.is_member` l'appelle pour un compte rattaché. `user_repository.list_linked` (comptes à fiche, avec la fiche), `athlete_claims.list_links(db, today)` (ajoute « adhérent cette saison ») et `athlete_claims.admin_detach(db, user_id, actor_id)` (journalisé). Routes `GET /admin/athlete-links`, `DELETE /admin/athlete-links/{user_id}`. Front : section « Comptes rattachés » sous la file, détachement confirmé (`DangerConfirm`).

## Technical Context

Python 3.13, FastAPI ; Next.js 16 · aucune dépendance ni migration · pytest, vitest

## Constitution Check

| # | Principe | Statut | Justification |
|---|----------|--------|---------------|
| I | Langue | ✅ | |
| II | Couches | ✅ | Requêtes en repositories, règles en service. |
| III | TDD | ✅ | Tests d'abord à chaque couche. |
| IV | Contrats | ⚠️ | `is_member` change de sens pour un compte rattaché hors saison : c'est l'objet de l'issue, décidé par le mainteneur ; le champ garde sa forme. |
| V | Neutralité | N/A | |
| VI | Simplicité | ✅ | Réutilise `club_members` et le pouvoir existant. |

## Complexity Tracking

| Écart | Pourquoi | Alternative rejetée |
|---|---|---|
| IV : sémantique d'`is_member` resserrée | Un ancien adhérent gardait la dispense du code sans fin | Détachement manuel seul : dépend d'un geste annuel que personne ne ferait |
