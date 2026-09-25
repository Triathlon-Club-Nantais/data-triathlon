# API Contract: Calendrier des entraînements jeunes

> **Révisé par la revue de la PR #876** : le schéma et l'API ont été rendus
> neutres (sans « jeune ») pour une extension aux adultes. Correspondance :
> `Entrainement` → `TrainingSession`, `EntrainementParticipant` →
> `TrainingParticipant`,
> `entrainements_jeunes` → `training_sessions`, `entrainement_participants` →
> `training_participants`, `entrainement_id` → `training_session_id`,
> `jeune_id` → `profile_id`, `heure_debut` → `start_time`, `lieu` →
> `location`, `type_seance` → `session_type`, `/admin/jeunes/entrainements` →
> `/admin/training-sessions`. La garde reste `jeunes:read`/`jeunes:write`. Le
> reste de ce document garde les noms d'origine.

Toutes les routes sous `/api/v1`, gardées individuellement par
`require_permission` (jamais par préfixe), en plus de la garde `require_site_access`
posée à l'inclusion du router dans `v1/router.py` comme le reste des routers
`/admin/*`.

## `GET /admin/jeunes/entrainements`

Garde : `jeunes:read`.

Liste tous les entraînements, triés par `date` puis `heure_debut` (séances
sans heure en fin de journée), avec le nombre de participants inscrits.

Réponse `200` : `EntrainementRead[]`
```json
[
  {
    "id": 1,
    "date": "2026-09-20",
    "heure_debut": "18:00:00",
    "lieu": "Base nautique",
    "type_seance": "Natation",
    "participant_count": 12
  }
]
```

## `GET /admin/jeunes/entrainements/{id}`

Garde : `jeunes:read`.

Détail d'un entraînement, avec sa liste de participants inscrits.

Réponse `200` : `EntrainementDetailRead` (comme ci-dessus, `+ "participants": [{"jeune_id": 3, "created_at": "..."}]`)

Réponse `404` : entraînement inconnu.

## `POST /admin/jeunes/entrainements`

Garde : `jeunes:write`.

Corps : `EntrainementCreate` — `{"date": "2026-09-20", "heure_debut": null, "lieu": null, "type_seance": null}` (`date` seule obligatoire).

Réponse `201` : `EntrainementDetailRead` (participants vide à la création).

## `PATCH /admin/jeunes/entrainements/{id}`

Garde : `jeunes:write`.

Corps : `EntrainementUpdate` — champs optionnels, seuls ceux fournis sont
modifiés.

Réponse `200` : `EntrainementDetailRead`. `404` si l'entraînement n'existe pas.

## `POST /admin/jeunes/entrainements/{id}/participants`

Garde : `jeunes:write`.

Corps : `{"jeune_id": 3}`.

Réponse `201` : `EntrainementDetailRead`. Idempotent — réinscrire un jeune déjà
inscrit rend `201` sans doublon (même patron que `POST /admin/groups/{id}/members`).

`404` si l'entraînement n'existe pas.

## `DELETE /admin/jeunes/entrainements/{id}/participants/{jeune_id}`

Garde : `jeunes:write`.

Réponse `204`. Idempotent — désinscrire un jeune non inscrit rend `204` sans
erreur. `404` si l'entraînement n'existe pas.
