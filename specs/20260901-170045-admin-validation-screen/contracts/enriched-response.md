# Contract: Écran de validation admin des déclarations de crédit d'athlète (#817)

Ce document décrit un élargissement de réponse sur des routes existantes —
pas un nouvel endpoint, pas de rupture de contrat.

## `AdminVolunteerActionOut` — deux champs ajoutés

**Avant** : `id`, `athlete_id`, `season`, `title`, `description`, `status`,
`declared_by_user_id`, `created_at`.

**Après** : les mêmes champs, plus `athlete_nom: string` et
`athlete_prenom: string`.

Concerne les trois routes qui rendent ce schéma, sans changement de leur
garde ni de leur sémantique :

- `GET /api/v1/admin/volunteer-actions/pending`
- `POST /api/v1/admin/volunteer-actions/{id}/accept`
- `POST /api/v1/admin/volunteer-actions/{id}/reject`
- `GET /api/v1/admin/athletes/{athlete_id}/volunteer-actions/validated`

**Justification (Principe IV)** : un élargissement additif de réponse — deux
champs qui apparaissent, aucun retiré, aucun renommé — n'est pas une
rupture de contrat. Un appelant existant qui ignore ces champs continue de
fonctionner à l'identique.

## Ce qui reste, sans changement

- Tout le reste du contrat `/api/v1` — aucune autre route touchée.
