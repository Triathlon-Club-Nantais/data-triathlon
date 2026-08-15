# Contract: `GET /api/v1/courses/{course_id}/summary`

Route existante (`backend/app/api/v1/courses.py:150`), inchangée dans sa
signature (aucun nouveau paramètre, aucun code de retour modifié). Seul le
corps de la réponse gagne trois champs.

## Réponse — avant cette feature

```json
{
  "total": 120,
  "finishers": 110,
  "non_finishers": 8,
  "unknown": 2,
  "tcn_count": 15,
  "male": 90,
  "female": 30,
  "categories": [...],
  "categories_total": 120,
  "clubs": [...],
  "histogram": {...},
  "split_keys": [...]
}
```

## Réponse — après cette feature (additive)

```json
{
  "total": 120,
  "finishers": 110,
  "non_finishers": 8,
  "dnf": 5,
  "dns": 2,
  "dsq": 1,
  "unknown": 2,
  "tcn_count": 15,
  "male": 90,
  "female": 30,
  "categories": [...],
  "categories_total": 120,
  "clubs": [...],
  "histogram": {...},
  "split_keys": [...]
}
```

## Garanties de compatibilité (Principe IV)

- `non_finishers` conserve sa valeur et sa sémantique — un appelant qui ignore
  `dnf`/`dns`/`dsq` continue de fonctionner à l'identique.
- Aucun champ existant n'est retiré, renommé, ni ne change de type.
- `dnf + dns + dsq == non_finishers` est garanti par construction (les quatre
  compteurs sont incrémentés dans la même boucle sur les mêmes lignes,
  `backend/app/services/stats_service.py::course_summary`).
- Pas de nouvelle route, pas de v2 : le changement est additif au sens du
  Principe IV, donc reste sur `/api/v1`.
