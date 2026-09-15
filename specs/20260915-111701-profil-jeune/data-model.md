# Data Model: Profil individuel jeune (#867)

Deux tables, patron RBAC déjà en place (`Group`, `VolunteerAction`). Choix de
nommage détaillés dans `research.md` (D1, D2).

## `personal_profiles`

| Colonne | Type | Contrainte | Note |
|---|---|---|---|
| `id` | `Integer` | PK | |
| `organisation_id` | `Integer` | FK `organisations.id`, `NOT NULL`, index | Patron `Group.organisation_id` — un profil est celui d'une organisation précise, jamais global. Une seule organisation existe aujourd'hui (`tcn`) ; la colonne existe pour ne pas devoir la migrer plus tard. |
| `first_name` | `String` | `NOT NULL` | |
| `last_name` | `String` | `NOT NULL` | |
| `birth_date` | `Date` | nullable | Optionnelle : un profil peut être créé avant que la date de naissance soit connue (FR edge case de spec.md). L'âge se **calcule** à l'affichage, jamais stocké. |
| `emergency_contact` | `String` | nullable, défaut `""` | Texte libre (nom + téléphone) — pas de structuration en sous-champs, non demandée. |
| `notes` | `Text` | nullable, défaut `""` | Notes libres, distinctes du journal de bord daté. |
| `created_at` | `DateTime` | défaut `utcnow` | |
| `updated_at` | `DateTime` | défaut `utcnow`, `onupdate=utcnow` | |
| `created_by_user_id` | `Integer` | FK `users.id`, nullable, pas d'`ondelete` | Patron `allowed_emails.created_by_user_id` — supprimer l'utilisateur qui a créé un profil ne doit pas effacer ni casser le profil. |

Pas d'`UniqueConstraint` sur `(first_name, last_name)` : deux jeunes homonymes
sont plausibles dans un club, contrairement à `Athlete` qui départage par
`birth_date` toujours connue (ici optionnelle).

## `profile_log_entries`

| Colonne | Type | Contrainte | Note |
|---|---|---|---|
| `id` | `Integer` | PK | |
| `profile_id` | `Integer` | FK `personal_profiles.id`, `NOT NULL`, index | Cascade ORM `delete-orphan` depuis `PersonalProfile.log_entries` (patron `Group.members`, sans `ondelete` DB) |
| `entry_date` | `Date` | `NOT NULL`, défaut date du jour | Date **métier** de l'entrée — cf. research.md D2 |
| `text` | `Text` | `NOT NULL` | Validé non-vide au niveau schéma Pydantic (FR-011) |
| `created_by_user_id` | `Integer` | FK `users.id`, nullable | Qui a écrit l'entrée |
| `created_at` | `DateTime` | défaut `utcnow` | Horodatage technique d'écriture, départage l'ordre d'affichage à `entry_date` égale |

Tri d'affichage : `entry_date desc, created_at desc` (la plus récente en
premier — US2, acceptance scenario 1 de spec.md).

## Relations

```
Organisation 1───N PersonalProfile 1───N ProfileLogEntry
                        │                      │
                        └── created_by_user_id ─┴── created_by_user_id → User (nullable, sans ondelete)
```

## Schémas Pydantic (`app/schemas/profile.py`)

- `ProfileLogEntryCreate` — `text: str` (min_length=1), `entry_date:
  date | None` (défaut : date du jour, posé côté service).
- `ProfileLogEntryRead` — `id`, `entry_date`, `text`, `created_by_name: str |
  None`, `created_at`.
- `ProfileRead` — `id`, `first_name`, `last_name`, `birth_date: date | None`,
  `created_at` — la forme **liste**, sans journal ni contact d'urgence (pas
  nécessaire pour un aperçu, cohérent avec `GroupRead`/`GroupDetailRead`).
- `ProfileDetailRead` — `ProfileRead` + `emergency_contact`, `notes`,
  `log_entries: list[ProfileLogEntryRead]` (triés desc).
- `ProfileCreate` — `first_name: str` (min_length=1), `last_name: str`
  (min_length=1), `birth_date`, `emergency_contact`, `notes` (les trois
  optionnels).
- `ProfileUpdate` — les cinq champs de `ProfileCreate`, tous optionnels
  (`None` = non modifié, patron `GroupUpdate` : PATCH partiel).

## Validation

- `ProfileLogEntryCreate.text` : non vide après `strip()` (Pydantic
  `field_validator`), sans quoi une entrée vide rendrait le journal
  inutilisable (FR-011).
- `ProfileCreate.first_name`/`last_name` : non vides (FR-003 — « au minimum un
  nom et un prénom »).
- Aucune validation de format sur `emergency_contact` : texte libre, comme
  `Course.format_label`.
