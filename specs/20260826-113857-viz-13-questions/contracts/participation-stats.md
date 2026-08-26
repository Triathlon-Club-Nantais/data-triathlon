# Contrat — champ `stats` de `GET /api/v1/participations/{id}`

**Correction post-implémentation (US4)** : il n'existe pas de route
`/stats` séparée — `ParticipationStatsOut` est le champ `stats` de la
réponse de `GET /api/v1/participations/{id}` (`backend/app/schemas/
participation_stats.py`). Extension **additive**, aucun champ retiré, aucune
sémantique changée : reste `/api/v1`, pas de v2 (Principe IV).

## `RankingEvolutionStep` — US5

Forme réelle (`segment`, pas `segment_label`) :

```diff
 class RankingEvolutionStep(BaseModel):
     segment: str
     scratch_position: int
     segment_position: int
+    cumulative_seconds: int | None
```

`cumulative_seconds` : temps cumulé de l'athlète à ce segment, en secondes.
Valeur déjà calculée par `_cumulative_seconds` (`participation_stats_
service.py`), simplement non exposée. `None` quand le segment n'a pas de
temps de passage exploitable.

## `ComparisonRow` — US4 (implémenté)

**Forme réelle** : un dictionnaire par clé de segment (pas un scalaire par
ligne comme le supposait la première version de ce contrat) :

```diff
 class ComparisonRow(BaseModel):
     position_label: str
     rank: int
     percentages: dict[str, float]
+    mine_seconds: dict[str, int] = Field(default_factory=dict)
+    theirs_seconds: dict[str, int] = Field(default_factory=dict)
```

`mine_seconds`/`theirs_seconds` : écart de temps brut par segment (mêmes clés
que `percentages`), déjà calculé par `_comparison` avant réduction en
pourcentage. Une clé absente du dict signifie une valeur non exploitable pour
ce segment (même condition que l'absence dans `percentages`).

## Compatibilité

- Consommateurs existants (`ComparisonTable.tsx`, `RankingEvolutionChart.tsx`)
  ignorent les nouveaux champs sans modification — additif pur.
- Test de contrat : `backend/tests/test_api/test_participations_api.py`
  (US4, livré) ; à étendre pour US5.
