# Contract: Retrait de l'auto-déclaration de bénévolat (#816)

Ce document liste ce qui **disparaît** du contrat `/api/v1` — pas une
nouvelle ressource.

## Routes retirées

- `POST /api/v1/volunteer-declarations` — auto-déclaration self-service.
- `GET /api/v1/volunteer-declarations` — mes déclarations.
- `DELETE /api/v1/volunteer-declarations/{declaration_id}` — suppression
  de sa propre déclaration.
- `GET /api/v1/admin/volunteer-declarations` — vue d'ensemble admin.
- `POST /api/v1/admin/volunteer-declarations` — déclaration pour un tiers,
  validée d'office.
- `POST /api/v1/admin/volunteer-declarations/{id}/validate` — validation
  d'une auto-déclaration en attente.
- `DELETE /api/v1/admin/volunteer-declarations/{id}` — suppression admin.

**Justification du retrait, pas une dépréciation silencieuse (Principe
IV)** : ce domaine (#751) est fonctionnellement remplacé par le flux de
crédit d'un athlète (#778/#779/#809), qui couvre le même besoin — tracer
une activité de bénévolat pour le quota de saison — avec en plus un
rattachement explicite à un athlète. Le retrait élimine une redondance
produit assumée, pas une capacité perdue.

## Pouvoirs retirés du catalogue

`benevolat:read`, `benevolat:manage` — plus aucune ressource ne les garde
après ce retrait. Retirés de `P` et `ALL`
(`backend/app/core/permissions.py`).

## Ce qui reste, sans changement

- `POST /api/v1/volunteer-actions` (#778/#809).
- `GET /api/v1/admin/volunteer-actions/pending`,
  `POST .../{id}/accept`, `POST .../{id}/reject` (#779).
- `GET /api/v1/admin/athletes/{athlete_id}/volunteer-actions/validated`
  (#781).
