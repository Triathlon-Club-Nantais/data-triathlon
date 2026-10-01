# Contrat API admin : fusion et revue d'identité (#1146)

Sous `/api/v1`. Tous les ajouts sont **additifs** (Principe IV) : aucune route ni aucun champ existant ne change de sens. Permission vérifiée par route (`require_permission`), 401 avant 403. Les routes de lecture ne lisent pas ; les routes d'écriture commitent dans le routeur, le service ne fait que `flush`.

## Fusion

### `GET /admin/athletes/{kept_id}/merge-impact?absorbed_id={id}`

Permission : `athletes:write`. Lecture seule.

```json
{
  "kept":     {"id": 54184, "nom": "JUMEAUX", "prenom": "Adrien", "club": "Triathlon Club Nantais", "participations": 14},
  "absorbed": {"id": 129483, "nom": "JUMEAUX, ADRIEN", "prenom": "", "club": null, "participations": 1},
  "moves": {"participations": 1, "teammates": 0, "volunteer_actions": 0, "season_validations": 0, "users": 0},
  "alias_added": true,
  "blocking_reason": null
}
```

`blocking_reason` : `null` ou un code parmi `same_athlete`, `distinct_users`, `same_course_bibs`, `same_participation`, `distinct_birth_dates`, avec `blocking_label` (texte français affichable). 404 si l'une des fiches n'existe pas.

### `POST /admin/athletes/{kept_id}/merge`

Permission : `athletes:write`. Corps : `{"absorbed_id": 129483}` (`StrictInt`).

- **200** : `AdminAthleteRead` de la fiche conservée.
- **404** : fiche inconnue.
- **409** : refus métier (`blocking_reason` non nul, message français), ou épreuve en cours de rescrape (`CourseRescrapeAlreadyRunningError`, existant).
- Journal : `athlete.merge`, `entity_type="athlete"`, `entity_id=kept_id`, payload sans `birth_date` (`research.md` R7).

### `PATCH /admin/athletes/{id}` (existante, corps 409 étendu)

En cas d'identité déjà portée par une autre fiche (clé normalisée ou variante), le 409 garde son message et **ajoute** `conflicting_athlete_id` pour que le front propose la fusion.

## Revue d'identité

Modèle : revue des épreuves en doublon (`docs/api/admin-donnees.md`, #288/#754).

### `GET /admin/athletes/identity-review`

Permission : `athletes:write`. Sans pagination (volume borné : cas du club et reliquat de la reprise).

```json
{
  "candidates": [
    {
      "reason": "same_course_bibs",
      "reason_label": "Deux dossards sur une même épreuve",
      "athletes": [
        {"id": 66856, "nom": "…", "prenom": "…", "club": "…", "gender": "M", "categories": ["M25-29", "M30-34"], "participations": 4, "homonym_rank": 0}
      ],
      "conflicts": [
        {"course_id": 407, "course_name": "IRONMAN Tours", "event_date": "2025-06-01",
         "entries": [{"participation_id": 97161, "athlete_id": 66856, "bib": "2348", "category": "M25-29", "total_time": "11:19:24"}]}
      ]
    }
  ]
}
```

`reason` ∈ `same_course_bibs`, `club_homonym`, `swapped`, `concatenated`, `alias_collision`. Pour `same_course_bibs`, `athletes` porte une seule fiche ; pour les autres, deux. Ordre stable (raison, puis plus petit id).

### `GET /admin/athletes/identity-review/count`

Permission : `athletes:write`. `{"total": 12}`, pour le badge de navigation.

### `POST /admin/athletes/identity-review/ignore`

Permission : `athletes:write`. Corps `{"athlete_id_a": 1, "athlete_id_b": 2}` (`StrictInt`).

- **201** `{"athlete_id_a", "athlete_id_b", "ignored_at"}` ; journal `athlete_identity.ignore`, `entity_id=min(a, b)`.
- **400** si `a == b` ; **404** si une fiche manque ; **409** si la paire est déjà écartée.
- Un cas `same_course_bibs` ne s'écarte pas : il se règle par réattribution.

## Import (rapport, additif)

Le rapport de `persist_results` et l'événement SSE `done` gagnent `ambiguous_identities: [{course_id, athlete_id, candidate_ids}]` (PR 1 : la fiche créée faute de repli unique, et les fiches candidates) puis `homonyms_created: [{course_id, bib, athlete_id, homonym_of}]` (PR 4). Les clés existantes (`imported`, `updated`, `skipped`, `reconciled`, …) gardent leur sens.
