# API Contracts: Compteurs de saison distincts + validation humaine du quota club

Toutes les routes sont sous `/api/v1`. Décisions source : `research.md`
D2, D3, D7, D8, D9.

## Modifié — `GET /athletes/season-activity`

Changement **additif uniquement** (Principe IV — D3) : mêmes paramètres
(`scope`, `seasons`, `federal_only`), réponse enrichie.

**Réponse** — `AthleteSeasonActivity[]`, nouveaux champs en gras :

| Champ | Type | Sémantique |
|---|---|---|
| `id`, `nom`, `prenom` | *(inchangés)* | |
| `participation_count` | `int` | *(inchangé — conservé pour compat, valeur identique à `club_affiliated_count`)* |
| **`total_count`** | `int` | Toutes les participations de la saison, sans filtre de validation ni de club (FR-001) |
| **`validated_count`** | `int` | Participations validées (`is_pending_validation=False`) de la saison, sans filtre de club (FR-002) |
| **`club_affiliated_count`** | `int` | Participations validées **et** affiliées au club sur la ligne de résultat (FR-003) |
| **`season_validated`** | `bool \| null` | Statut de validation de la saison (FR-009) — `null` si `seasons` ne désigne pas exactement une saison (D9) |

**Sélection du roster** (`scope=club`) : bascule sur `tcn_clause(Athlete.club)`
au lieu de `tcn_clause(Participation.club)` (D1) — un membre du club dont
aucune participation de la saison ne porte l'affiliation reste dans la
liste.

## Nouveau — `POST /admin/athletes/{athlete_id}/volunteer-actions`

**Pouvoir** : `P.ATHLETES_VOLUNTEER_MANAGE`.

**Requête** :
```json
{ "season": 2025 }
```

**Réponse** `201` :
```json
{ "id": 42, "athlete_id": 7, "season": 2025, "declared_by_user_id": 3, "created_at": "2026-08-28T13:41:00Z" }
```

**Effets de bord** : écrit une entrée `AdminActionLog`
(`action="athlete.volunteer_action.create"`, `entity_type="athlete"`,
`entity_id=athlete_id`, `payload={"season": 2025}`) dans la même transaction
(FR-008).

**Erreurs** : `404` si l'athlète n'existe pas ; `403` sans le pouvoir.

## Nouveau — `POST /admin/athletes/{athlete_id}/season-validations`

**Pouvoir** : `P.ATHLETES_SEASON_VALIDATE`.

**Requête** :
```json
{ "season": 2025 }
```

**Réponse** `201` :
```json
{ "athlete_id": 7, "season": 2025, "validated_by_user_id": 3, "validated_at": "2026-08-28T13:41:00Z" }
```

**Effets de bord** : écrit une entrée `AdminActionLog`
(`action="athlete.season_validation.create"`) dans la même transaction
(FR-013).

**Erreurs** : `404` si l'athlète n'existe pas ; `403` sans le pouvoir ;
`409` si la saison est déjà validée pour cet athlète (pas de double ligne —
cf. `data-model.md`).

## Nouveau — `DELETE /admin/athletes/{athlete_id}/season-validations/{season}`

**Pouvoir** : `P.ATHLETES_SEASON_VALIDATE`.

**Réponse** : `204`.

**Effets de bord** : supprime la ligne `SeasonValidation` et écrit une
entrée `AdminActionLog` (`action="athlete.season_validation.delete"`) dans
la même transaction (FR-013).

**Erreurs** : `404` si l'athlète n'existe pas **ou** si la saison n'est pas
actuellement validée pour cet athlète ; `403` sans le pouvoir.

## Nouveau — `GET /admin/athletes/{athlete_id}/season-quota?season=`

**Pouvoir** : `P.ATHLETES_SEASON_VALIDATE`.

Ajouté en cours d'implémentation (US3) : FR-012 exige que l'interface
indique, au moment de valider, si le barème (3 épreuves validées + 1 action
de bénévolat) est atteint — signal qui n'existait dans aucun endpoint de
lecture existant (`season-activity` ne porte pas l'existence d'un
bénévolat). Ne modifie rien.

**Réponse** `200` :
```json
{ "validated_count": 3, "has_volunteer_action": true, "season_validated": true }
```

## Non modifié

`GET /admin/athletes/{athlete_id}` (`admin_data.py`) reste inchangé dans
cette itération — le détail des actions de bénévolat et de l'historique de
validation d'un athlète (au-delà du statut courant déjà porté par
`season-activity`) n'est pas requis par la spec ; à envisager en tâche
suiveuse si le besoin apparaît en usage réel.
