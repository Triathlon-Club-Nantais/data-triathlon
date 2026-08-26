# Contrat — nouvelle route `GET /api/v1/benevoles/queue/history`

**Seule nouvelle route de la feature** (les 18 autres changements sont soit
additifs sur un schéma existant, soit sans changement API). Garde identique
aux 9 routes de `benevoles.py` : `require_benevole_access`
(`api/deps.py`), même patron que `queue`/`rejected` (lecture seule, aucun
scope club/fédéral — les bénévoles traitent tous les clubs).

## Requête

```
GET /api/v1/benevoles/queue/history
```

Aucun paramètre — même choix que `GET /courses/{id}/summary` (Principe VI,
YAGNI : pas de fenêtre glissante configurable tant qu'aucun usage ne la
demande).

## Réponse — nouveau schéma `ValidationQueueHistory`

```python
class ValidationQueueBacklogPoint(BaseModel):
    date: date
    pending_count: int


class ValidationQueueHistory(BaseModel):
    backlog_by_day: list[ValidationQueueBacklogPoint]
    average_resolution_seconds: int | None
```

- `backlog_by_day` : nombre de participations `is_pending_validation=True` à
  la fin de chaque jour, sur l'historique disponible **depuis le déploiement
  de la migration** `validated_at`/`rejected_at` (cf. `data-model.md`) — pas
  d'antériorité reconstructible, `created_at` seul ne suffit pas à établir un
  arriéré fiable pour une entrée déjà résolue avant la migration.
- `average_resolution_seconds` : moyenne de `validated_at - created_at` (ou
  `rejected_at - created_at`) sur les résolutions dont le timestamp existe.
  `None` tant qu'aucune résolution n'a de timestamp — état vide explicite
  côté frontend (edge case déjà posé dans `spec.md`).

## Couche

- `app/repositories/participation_repository.py` : nouvelle fonction de
  lecture (seule couche autorisée à construire la requête SQL).
- `app/services/` : agrégation en `average_resolution_seconds` déléguée à un
  service existant ou nouveau selon la taille — décision d'implémentation
  laissée à `/speckit-tasks`, pas au plan.
- `app/api/v1/benevoles.py` : route fine, `response_model=
  ValidationQueueHistory`, délègue au service — même patron que `queue`.

## Compatibilité

Route entièrement nouvelle : aucun risque de rupture de contrat existant
(Principe IV trivialement respecté).
