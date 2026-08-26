# Contrat — `GET /api/v1/participations/{id}/stats`

Extension **additive** du schéma de réponse existant
(`backend/app/schemas/participation_stats.py`). Aucun champ retiré, aucune
sémantique changée : reste `/api/v1`, pas de v2 (Principe IV).

## `RankingEvolutionStep` — US5

```diff
 class RankingEvolutionStep(BaseModel):
     segment_label: str
     scratch_position: int | None
     segment_position: int | None
+    cumulative_seconds: int | None
```

`cumulative_seconds` : temps cumulé de l'athlète à ce segment, en secondes.
Valeur déjà calculée par `_cumulative_seconds` (`participation_stats_
service.py`), simplement non exposée. `None` quand le segment n'a pas de
temps de passage exploitable (même condition que `scratch_position is None`
aujourd'hui).

## `ComparisonRow` — US4

```diff
 class ComparisonRow(BaseModel):
     segment_label: str
     mine_percent: float | None
     theirs_percent: float | None
+    mine_seconds: int | None
+    theirs_seconds: int | None
```

`mine_seconds`/`theirs_seconds` : écart de temps brut par segment, déjà
calculé par `_comparison` avant réduction en pourcentage. Mêmes conditions de
nullabilité que les champs `*_percent` existants.

## Compatibilité

- Consommateurs existants (`ComparisonTable.tsx`, `RankingEvolutionChart.tsx`)
  ignorent les nouveaux champs sans modification — additif pur.
- Test de contrat : étendre le test existant qui verrouille la forme JSON de
  cette route (si un tel test existe déjà — sinon, TDD : écrire le test rouge
  sur les nouveaux champs avant l'implémentation, cf. Principe III).
