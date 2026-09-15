# Contract: `/api/v1/admin/profiles`

Cinq routes, patron `admin_groups.py` (garde individuelle par route, jamais
par préfixe — voir `backend/app/api/AGENTS.md` §Protéger une ressource).

## `GET /admin/profiles`

**Garde** : `jeunes:read`

**Réponse 200** : `list[ProfileRead]`, triée par `last_name, first_name`.

## `GET /admin/profiles/{profile_id}`

**Garde** : `jeunes:read`

**Réponse 200** : `ProfileDetailRead` (profil + `log_entries` triées
`entry_date desc, created_at desc`).

**Réponse 404** : profil inexistant.

## `POST /admin/profiles`

**Garde** : `jeunes:write`

**Corps** : `ProfileCreate`

**Réponse 201** : `ProfileDetailRead` (journal vide à la création).

**Réponse 422** : `first_name`/`last_name` vide.

## `PATCH /admin/profiles/{profile_id}`

**Garde** : `jeunes:write`

**Corps** : `ProfileUpdate` (champs omis = non modifiés)

**Réponse 200** : `ProfileDetailRead`

**Réponse 404** : profil inexistant.

## `POST /admin/profiles/{profile_id}/log-entries`

**Garde** : `jeunes:write`

**Corps** : `ProfileLogEntryCreate`

**Réponse 201** : `ProfileDetailRead` (patron `add_member` de
`admin_groups.py` — rend le détail complet, pas seulement l'entrée créée, pour
que le front n'ait besoin que d'un seul appel après l'ajout).

**Réponse 404** : profil inexistant.

**Réponse 422** : `text` vide.

## Hors contrat (explicitement, cf. spec.md §Assumptions)

- Aucune route `DELETE` sur un profil ni sur une entrée de journal.
- Aucun paramètre `scope`/`federal_only`/pagination : l'effectif visé ne le
  justifie pas (Principe VI).
