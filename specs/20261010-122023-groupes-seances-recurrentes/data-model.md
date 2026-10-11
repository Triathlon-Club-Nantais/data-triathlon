# Data model

Toutes les nouvelles tables sont génériques (FR-015) ; pas d'`ondelete` en base, nettoyage par l'ORM ou par service, comme le reste du dépôt.

## `training_groups` (nouvelle)

| Colonne | Type | Règle |
| --- | --- | --- |
| id | int PK | |
| organisation_id | int FK `organisations.id`, non nul | patron `PersonalProfile` |
| name | str, non nul | nettoyé (espaces de bord), non vide ; `UNIQUE(organisation_id, name)` |
| created_at | datetime | |

Suppression : cascade ORM sur `training_group_members`, `training_session_groups`, `training_recurrence_groups`. Les inscriptions déjà produites restent (spec, Edge Cases).

## `training_group_members` (nouvelle)

| Colonne | Type | Règle |
| --- | --- | --- |
| id | int PK | |
| training_group_id | FK `training_groups.id`, index | |
| profile_id | FK `personal_profiles.id`, index | |
| created_at | datetime | |

`UNIQUE(training_group_id, profile_id)` : ajout idempotent sous concurrence (patron `uq_training_participant`).

## `training_recurrences` (nouvelle)

| Colonne | Type | Règle |
| --- | --- | --- |
| id | int PK | |
| weekday | int, non nul | 0 (lundi) à 6 |
| start_time | time, nullable | heure locale |
| location | str, nullable | |
| session_type | str, nullable | |
| starts_on | date, non nul | |
| ends_on | date, non nul | `ends_on >= starts_on` ; 1 à 53 occurrences |
| created_at | datetime | |

## `training_recurrence_groups` et `training_session_groups` (nouvelles)

Tables d'association `(recurrence_id, training_group_id)` et `(training_session_id, training_group_id)`, chacune avec sa contrainte d'unicité.

## `training_sessions` (existante, modifiée)

| Colonne ajoutée | Type | Règle |
| --- | --- | --- |
| recurrence_id | FK `training_recurrences.id`, nullable, index | posée à la génération ; remise à NULL quand la récurrence est supprimée et que la séance est conservée |
| detached | bool, non nul, défaut faux | vrai dès qu'une séance générée est modifiée seule (date, heure, lieu, type ou groupes) |

Relation `groups` (via `training_session_groups`).

## `training_participants` (existante, modifiée)

| Colonne ajoutée | Type | Règle |
| --- | --- | --- |
| added_manually | bool, non nul, défaut vrai | les lignes existantes viennent toutes d'un ajout manuel ; l'inscription d'office écrit faux ; un ajout manuel d'un jeune déjà inscrit d'office passe la ligne à vrai |

## États dérivés (non stockés)

- **Séance à venir** : `date >= date du jour`.
- **Appel commencé** : au moins un participant avec `present` non nul.
- **Séance synchronisable** : à venir et appel non commencé (R3).
- **Membre actif à une date** : `membership_ended_on` nul ou postérieur ou égal à cette date (FR-017).
- **Catégorie FFTri** : calculée depuis `birth_date` et la date du jour (R1), exposée dans les vues profil.
