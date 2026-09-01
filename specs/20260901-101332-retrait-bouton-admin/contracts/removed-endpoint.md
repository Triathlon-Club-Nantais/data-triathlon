# Contract: Retrait du bouton admin de déclaration de bénévolat (#780)

Ce document liste ce qui **disparaît** du contrat `/api/v1` — pas une
nouvelle ressource.

## `POST /api/v1/admin/athletes/{athlete_id}/volunteer-actions` — RETIRÉ

Créait une action de bénévolat sans titre ni description, validée
d'office (l'existence suffisait au quota avant #779). Gardé par
`athletes:volunteer_manage`.

**Justification du retrait, pas une dépréciation silencieuse (Principe
IV)** : ce chemin n'a jamais été exposé comme un contrat public stable —
c'est un geste d'administration (#709), au même titre que les autres
ressources de `admin_data.py`, dont la doc backend (`app/api/AGENTS.md`)
liste explicitement le nombre (« les dix ressources de `admin_data.py`
[...] »), pas un contrat versionné garanti aux intégrations externes. Le
formulaire public self-service (#778, `POST /volunteer-actions`, toujours
en place) couvre le même besoin fonctionnel — créer une déclaration pour
un athlète — sans reconduire les lacunes que l'epic #776 corrige (pas de
titre, pas de trace, validée sans instruction).

**Ce qui reste, sans changement** :
- `POST /api/v1/volunteer-actions` (#778, self-service, `current_user`).
- `GET /api/v1/admin/volunteer-actions/pending`,
  `POST .../{id}/accept`, `POST .../{id}/reject` (#779).
- `GET /api/v1/admin/athletes/{athlete_id}/volunteer-actions/validated`
  (#781).
- `GET /api/v1/admin/athletes/{athlete_id}/season-quota` — toujours
  alimenté par `has_volunteer_action` (`exists_for_athlete_season`),
  inchangé.

## Pouvoir retiré du catalogue

`athletes:volunteer_manage` — plus aucune ressource ne le garde après ce
retrait. Retiré de la classe `P` et du tuple `ALL`
(`backend/app/core/permissions.py`). Un rôle qui ne détenait que ce
pouvoir perd un privilège devenu sans objet ; aucune ressource restante
n'en dépend (grep vérifié avant retrait, research.md D1).
