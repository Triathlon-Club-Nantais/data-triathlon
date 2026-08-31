# Data Model: Liste des actions de bénévolat validées sur la fiche athlète (#781)

## Aucune nouvelle colonne, aucune nouvelle table

`VolunteerAction` (existant depuis #778, statut significatif depuis #779)
— cette sous-issue n'en modifie ni le modèle ni le schéma de base.

## Nouvelle fonction repository

`volunteer_action_repository.list_validated_for_athlete(db, *, athlete_id)`
— filtre `athlete_id` + `status == "validee"`, trié `created_at desc`
(research.md D4). Aucun paramètre de saison (FR-004).

## Schéma réponse : `AdminVolunteerActionOut` (#779, inchangé)

Réutilisé tel quel (research.md D3) — `title`/`description` optionnels,
`status` toujours `"validee"` dans cette liste par construction du filtre.

## Frontend : type TS miroir

`AdminVolunteerActionOut` (nouveau côté `lib/types.ts` — n'existait pas
encore, #779 étant backend uniquement) : mêmes champs que le schéma
backend, `title`/`description` en `string | null`.

## Permission (inchangée)

`athletes:volunteer_validate` (#779) — aucun ajout (research.md D6).
