# Phase 1 — Data Model

## `BenevoleAccessConfig` (nouvelle table, `benevole_access_config`)

Une seule ligne existe à tout instant (research.md §D3). Remplace
`BENEVOLE_SHARED_PASSWORD` (variable d'environnement, #271).

| Champ | Type | Rôle |
|---|---|---|
| `id` | `int` (PK) | Sans signification métier — la ligne unique. |
| `password_hash` | `str` | Empreinte `scrypt` du mot de passe courant (hexadécimal, research.md §D1). |
| `password_salt` | `str` | Sel aléatoire de 16 octets ayant servi à cette empreinte (hexadécimal). Régénéré à chaque remplacement — jamais réutilisé d'un mot de passe à l'autre. |
| `session_secret` | `str` | Clé HMAC de signature des cookies de session bénévole (research.md §D2). Régénéré à chaque remplacement du mot de passe, jamais exposé par aucune route. |
| `updated_at` | `datetime` | Horodatage du dernier remplacement. |
| `updated_by_user_id` | `int` (FK `users.id`, `NOT NULL`) | L'administrateur auteur du dernier remplacement — jamais nul, une ligne n'existe que parce qu'un administrateur l'a créée. |

**Invariants** :
- Absence de ligne ⟺ accès bénévoles non configuré (fail-closed, FR-007,
  même prédicat qu'aujourd'hui).
- `password_hash`/`password_salt` ne permettent de **vérifier** un mot de
  passe soumis, jamais de le retrouver (FR-004) — aucune route, aucun
  export, aucun outil de ce dépôt ne les expose en dehors de la vérification
  de connexion elle-même.
- Un remplacement (saisie ou génération) réécrit **les trois** champs
  `password_hash`/`password_salt`/`session_secret` dans le même geste —
  jamais l'un sans les autres, sous peine de casser soit la vérification du
  mot de passe soit l'invalidation des sessions (FR-006).

**Aucune modification du schéma existant** : `Participation`, `Course`,
`Athlete`, `AdminActionLog`, `User` restent inchangés. `benevole_access.py`
(#271) garde `SYSTEM_USER_EMAIL`/`system_user_id`, sans rapport avec cette
configuration.

**Longueur minimale d'une saisie manuelle** : 8 caractères
(`BenevoleAccessReplaceIn.password`, `schemas/benevole_access.py`) — validée
par le schéma Pydantic, jamais par le service (contracts/api.md). Une valeur
délibérément basse : la génération sécurisée (research.md §D5) reste le
chemin recommandé pour un secret robuste, cette borne n'existe que pour
écarter une saisie manifestement dérisoire (un caractère, une chaîne vide),
pas pour imposer une politique de mot de passe.

## Journalisation (`AdminActionLog`, réutilisé)

Chaque remplacement (saisie ou génération) écrit une entrée sous l'action
`benevole_access.password_replace`, `entity_type="benevole_access_config"`,
`entity_id=1` (la ligne unique) — **le payload ne contient ni le mot de
passe, ni son hachage, ni le sel, ni le secret de session** (FR-009), pour
ne jamais faire du journal d'audit une seconde surface d'exposition. Seul le
fait qu'un remplacement a eu lieu, quand et par qui, est consigné —
l'`updated_by_user_id`/`updated_at` de la table elle-même portent déjà cette
information ; l'entrée de journal la rend seulement visible au même endroit
que les autres gestes d'administration.
