# API Contract: Appel de présence jeunes

Toutes les routes sous `/api/v1`, gardées individuellement par
`require_permission` (jamais par préfixe), en plus de la garde
`require_site_access` posée à l'inclusion du router dans `v1/router.py` comme
le reste des routers `/admin/*`. Cette feature étend deux contrats existants
(`admin_jeunes_entrainements.py`, #868) et n'en modifie aucun de façon non
additive (Principe IV) ; elle n'ajoute qu'**une seule** route nouvelle.

## Extensions additives des contrats existants (#868)

### `EntrainementRead` / `EntrainementDetailRead`

`+ "note": string` (défaut `""`).

### `ParticipantRead`

`+ "present": boolean | null` (`null` = pas encore pointé).

### `EntrainementCreate` / `EntrainementUpdate`

`+ "note": string | null` (optionnel — absent du `PATCH` n'écrase rien, même
patron sentinelle que `lieu`/`type_seance`).

### `POST /admin/jeunes/entrainements/{id}/participants` (`ParticipantAdd`)

Corps étendu : `{"jeune_id": 3, "present": true}` — `present` optionnel,
défaut `null`. Permet d'inscrire un jeune non encore enregistré et de le
pointer présent en un seul appel, pendant l'appel de début (FR-004, D4 de
`research.md`). Un appelant qui omet `present` (l'écran calendrier existant,
#868) obtient exactement le comportement actuel.

## `PATCH /admin/jeunes/entrainements/{id}/participants/{jeune_id}/presence` (nouvelle route)

Garde : `jeunes:write`.

Corps : `PresenceUpdate` — `{"present": true}` (booléen obligatoire, jamais
`null` : cette route ne sert qu'à basculer entre présent et absent, jamais à
revenir à « pas pointé »).

Réponse `200` : `EntrainementDetailRead` (même forme que les routes
`participants` existantes — le front n'a besoin que d'un seul appel après
l'écriture).

`404` si l'entraînement n'existe pas, ou si le jeune n'est pas inscrit à cette
séance (`find_participant` introuvable — cohérent avec le comportement de
`DELETE .../participants/{jeune_id}`, à ceci près que celui-ci est idempotent
sur l'absence quand `PATCH .../presence` la rend en 404 : il n'y a rien de
sensé à « basculer » sur une inscription qui n'existe pas).

Exemple :

```json
// PATCH /admin/jeunes/entrainements/12/participants/3/presence
{ "present": true }
```

```json
// 200
{
  "id": 12,
  "date": "2026-09-20",
  "heure_debut": "18:00:00",
  "lieu": "Base nautique",
  "type_seance": "Natation",
  "note": "",
  "participant_count": 12,
  "participants": [
    { "jeune_id": 3, "present": true, "created_at": "2026-09-15T10:00:00Z" }
  ]
}
```

## L'appel de fin : aucune route

FR-007 et D2 de `research.md` : l'appel de fin ne porte aucune route. Le
front recalcule, à partir de la réponse déjà rendue par
`GET /admin/jeunes/entrainements/{id}`, le sous-ensemble des participants dont
`present === true`, et garde son propre pointage de vérification en mémoire.
Aucune écriture réseau n'est associée à ce flux.

## Note sur un jeune pendant l'appel : route existante réutilisée telle quelle

`POST /admin/profiles/{profile_id}/log-entries` (#867,
`contracts/admin-profiles.md` de `specs/20260915-111701-profil-jeune/`) —
aucune modification, aucun nouveau champ. L'écran d'appel y délègue
directement l'ajout d'une note sur un jeune (FR-009).
