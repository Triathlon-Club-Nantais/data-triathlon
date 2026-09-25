# Data Model: Calendrier des entraînements jeunes

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

## `Entrainement` (table `entrainements_jeunes`)

Une séance d'entraînement jeunes.

| Colonne | Type | Contrainte | Note |
|---|---|---|---|
| `id` | `Integer` | PK | |
| `date` | `Date` | `NOT NULL` | jour de la séance |
| `heure_debut` | `Time` | nullable | optionnel — cf. `research.md` |
| `lieu` | `String` | nullable | texte libre |
| `type_seance` | `String` | nullable | texte libre |
| `created_at` | `DateTime` | `NOT NULL`, `default=utcnow` | |

Relation : `participants: list["EntrainementParticipant"]`, `back_populates`,
`cascade="all, delete-orphan"` — supprimer une séance supprime ses
inscriptions (aucune signification hors de la séance qui les porte, même
raisonnement que `Course.sources`).

Pas d'index dédié au-delà de la PK : le volume (quelques dizaines de séances
par saison) ne le justifie pas, et le tri se fait en base sur `date`/
`heure_debut` sans filtre sélectif à accélérer.

## `EntrainementParticipant` (table `entrainement_participants`)

Une inscription : ce jeune est inscrit à cette séance.

| Colonne | Type | Contrainte | Note |
|---|---|---|---|
| `id` | `Integer` | PK | |
| `entrainement_id` | `Integer` | FK `entrainements_jeunes.id`, `NOT NULL`, indexé | |
| `jeune_id` | `Integer` | FK `personal_profiles.id` (#867), `NOT NULL`, indexé | resserrée après le merge de #867 — cf. `research.md` §Dépendance |
| `created_at` | `DateTime` | `NOT NULL`, `default=utcnow` | date d'inscription |

`UNIQUE(entrainement_id, jeune_id)` (`uq_entrainement_participant`) — rend
l'inscription idempotente sous concurrence, sur le patron exact de
`UserGroup.uq_user_group`.

Pas d'`ondelete` sur la FK `entrainement_id`, comme partout ailleurs dans le
dépôt (`core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`) : la cascade
est portée par `Entrainement.participants` (`delete-orphan`), côté ORM.

## Validation

- `EntrainementCreate`/`EntrainementUpdate` (Pydantic) : `date` obligatoire à
  la création, les trois autres champs optionnels. `PATCH` n'accepte que les
  champs fournis (mêmes règles que `GroupUpdate` — un champ absent du corps
  n'est pas écrasé).
- `ParticipantAdd` : `jeune_id: int`, positif. L'existence du profil référencé
  est vérifiée en Python (`profile_repository.get`) avant l'écriture, dans
  `services/jeunes/entrainements.add_participant` — jamais laissée à la seule
  contrainte SQL, muette en SQLite (`core/database.py` n'active
  `PRAGMA foreign_keys=ON` sur aucun moteur) et un 500 non attrapé en
  PostgreSQL sinon. Un `jeune_id` inconnu rend 404 — voir `spec.md` Edge Cases.

## État / transitions

Aucune machine à états dans ce lot : une séance existe ou non, une inscription
existe ou non. Le statut présent/absent (#869) n'est pas un champ de
`EntrainementParticipant` posé ici — il sera ajouté par #869 sans
modification de ce qui est posé maintenant (FR-010).
