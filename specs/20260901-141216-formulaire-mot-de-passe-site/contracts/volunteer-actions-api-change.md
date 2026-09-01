# Contract: Ouvrir le formulaire de crédit d'un athlète au mot de passe du site (#809)

Ce document décrit un changement de contrat sur une route existante — pas
un nouvel endpoint.

## `POST /api/v1/volunteer-actions` — garde individuelle retirée

**Avant** (#778) : exige une session SSO individuelle
(`Depends(current_user)`) en plus du mot de passe partagé du site. Sans
session, `401`.

**Après** (#809) : `Depends(optional_user)`. Le mot de passe partagé du
site (`require_site_access`, posé en amont sur tout le routeur) reste
l'unique garde requise. Une session SSO, si présente, continue d'être
résolue et tracée normalement (`declared_by_user_id`) ; son absence ne
bloque plus la requête.

**Justification du changement, pas une dépréciation silencieuse (Principe
IV)** : cette route n'a jamais été un contrat public stable au sens du
Principe IV — c'est un formulaire self-service livré il y a moins d'une
semaine (#778), jamais documenté comme garantie externe, et ce changement
**élargit** l'accès (moins de garde, jamais plus) sans retirer aucune
capacité existante : un appelant déjà connecté via SSO continue de
fonctionner à l'identique (spec.md FR-005).

## Corps et réponse — inchangés

`VolunteerActionSelfCreate` (`athlete_id`, `title`, `description`) ne
change pas. `VolunteerActionSelfOut.declared_by_user_id` passe de `int` à
`int | null` dans la réponse JSON — un champ qui apparaissait toujours comme
un entier peut désormais apparaître `null`. Aucun appelant existant ne lit
ce champ (grep frontend vérifié, research.md D5) : élargissement de type
sans rupture observable.

## Ce qui reste, sans changement

- `GET /admin/volunteer-actions/pending`, `POST .../{id}/accept`,
  `POST .../{id}/reject` (#779) — toujours gardées par
  `athletes:volunteer_validate`, session SSO obligatoire.
- `GET /admin/athletes/{athlete_id}/volunteer-actions/validated` (#781) —
  inchangée.
- `GET /athletes` (recherche d'athlète) — déjà sans garde SSO, inchangée.
