# Contrats API (`/api/v1`, routes admin jeunes)

Garde : lecture `jeunes:read`, écriture `jeunes:write` (401 sans session, 403 sans le pouvoir), comme `admin_profiles.py` et `admin_training_sessions.py`. Erreurs métier en 422 avec message français (`DomainError`), 404 sur ressource absente.

## Groupes

| Méthode | Route | Corps | Réponse |
| --- | --- | --- | --- |
| GET | `/admin/training-groups` | | `[{id, name, member_count}]` trié par nom |
| GET | `/admin/training-groups/{id}` | | `{id, name, members: [ProfileRead]}` |
| POST | `/admin/training-groups` | `{name}` | 201, détail ; 422 nom vide ou déjà pris |
| PATCH | `/admin/training-groups/{id}` | `{name}` | détail ; 422 nom déjà pris |
| DELETE | `/admin/training-groups/{id}` | | 204 |
| POST | `/admin/training-groups/{id}/members` | `{profile_id}` | détail ; idempotent ; 404 profil absent ; resynchronise les séances concernées (R3) |
| DELETE | `/admin/training-groups/{id}/members/{profile_id}` | | détail ; resynchronise |

## Séances (existantes, étendues)

- `TrainingSessionRead` et `TrainingSessionDetailRead` gagnent `group_ids: [int]`, `recurrence_id: int | null`, `detached: bool`.
- Participant : gagne `added_manually: bool` et `category: str | null` (catégorie FFTri du profil).
- `POST /admin/training-sessions` et `PATCH /admin/training-sessions/{id}` acceptent `group_ids: [int]` (optionnel ; absent = inchangé au PATCH, vide au POST) ; la réponse reflète les inscriptions d'office. Un PATCH sur une séance issue d'une récurrence la passe `detached=true`.
- `POST /admin/training-sessions/{id}/participants` (ajout manuel) : inchangé en entrée, pose `added_manually=true`.

## Récurrences

| Méthode | Route | Corps | Réponse |
| --- | --- | --- | --- |
| GET | `/admin/training-recurrences` | | `[{id, weekday, start_time, location, session_type, starts_on, ends_on, group_ids, upcoming_session_count}]` |
| POST | `/admin/training-recurrences/preview` | même corps que la création | `{occurrence_count, dates: [date]}` ; 422 si 0 ou plus de 53 (FR-011, FR-012) |
| POST | `/admin/training-recurrences` | `{weekday, start_time?, location?, session_type?, starts_on, ends_on, group_ids}` | 201, récurrence + `created_session_count` |
| PATCH | `/admin/training-recurrences/{id}` | mêmes champs, tous optionnels | récurrence ; applique R4 aux séances synchronisables non détachées |
| DELETE | `/admin/training-recurrences/{id}` | | `{deleted_session_count, kept_session_count}` |

## Profils (existants, étendus)

- `ProfileRead` / `ProfileDetailRead` gagnent `category: str | null` (libellé FFTri ; `null` sans date de naissance).
- `ProfileDetailRead` gagne `groups: [{id, name}]`.

Toutes ces évolutions sont des **ajouts** de champs et de routes : aucun champ existant ne change de sens (Principe IV).
