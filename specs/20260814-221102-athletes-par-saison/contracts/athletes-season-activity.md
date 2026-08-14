# Contrat : `GET /api/v1/athletes/season-activity`

Endpoint **additif** sous `/api/v1` (Principe IV) — aucun contrat existant
modifié.

## Requête

```
GET /api/v1/athletes/season-activity?scope=club&seasons=2025
```

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `scope` | `str \| null` | `null` (neutre) | `"club"` restreint aux membres du TCN (Principe V — comportement identique à `/stats`, `/athletes`). |
| `seasons` | `str \| null` (CSV d'années de début) | `null` (neutre, toutes saisons confondues) | Parsé par `parse_seasons()` existant. La page appelante impose la saison en cours par défaut — l'API, elle, reste neutre. |

## Réponse `200`

```json
[
  { "id": 42, "nom": "Martin", "prenom": "Julie", "participation_count": 3 },
  { "id": 17, "nom": "Durand", "prenom": "Paul", "participation_count": 1 }
]
```

- `response_model=list[AthleteSeasonActivity]`.
- Triée par `nom`, `prenom` (ordre secondaire stable — le tri par
  `participation_count` est recalculé côté client, cf. research.md).
- Aucun athlète à `participation_count == 0` : la jointure est **interne**.
- Liste vide (`[]`) si aucune participation sur le filtre demandé — le front
  distingue ce cas pour afficher l'état vide de FR-007, pas d'objet
  d'erreur.

## Erreurs

Aucun cas d'erreur métier propre à cette route — `seasons` invalide est
toléré silencieusement par `parse_seasons()` (valeurs non entières ignorées,
comme sur `/stats`), pas de `400`.
