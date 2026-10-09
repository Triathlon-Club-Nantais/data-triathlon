# Contract: routes `/api/v1/benevoles/*` (#1272)

Aucun chemin, corps ni code de réponse ne change. Seule la règle d'admission des routes gardées s'élargit.

## Routes gardées (inchangées dans leur forme)

`GET /benevoles/queue`, `GET /benevoles/queue/count`, `GET /benevoles/queue/history`, `GET /benevoles/athletes`, `GET /benevoles/rejected`, `PATCH /benevoles/courses/{id}`, `POST /benevoles/participations/{id}/reassign`, `POST /benevoles/participations/{id}/validate`, `POST /benevoles/participations/{id}/reject`, `POST /benevoles/participations/{id}/unreject`, `PATCH /benevoles/participations/{id}`.

## Règle d'admission

| Appelant | Avant | Après |
|---|---|---|
| Anonyme, sans cookie bénévoles | 401 | 401 (identique) |
| Anonyme, cookie bénévoles valide | admis | admis |
| Connecté sans `benevole_access:manage`, sans cookie | 401 | 401 (identique, jamais 403) |
| Connecté sans le pouvoir, cookie valide | admis | admis |
| Connecté avec le pouvoir (ou superutilisateur), sans cookie | 401 | **admis** |
| Configuration absente, appelant sans le pouvoir | 401 | 401 (identique) |

Le corps du 401 reste celui de `NotAuthenticatedError` (« Vous devez être connecté pour accéder à cette ressource. »).

## Journal

Les six routes d'écriture inscrivent l'administrateur admis par pouvoir comme acteur ; l'admission au cookie seul inscrit le compte système, comme avant.

## Non modifiées

`POST /benevoles/session` et `DELETE /benevoles/session` : inchangées, non gardées.
