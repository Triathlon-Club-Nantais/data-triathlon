# Data Model: Appel de présence jeunes

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

Deux colonnes ajoutées à des tables existantes (#868). Aucune nouvelle table.

## `Entrainement` (table `entrainements_jeunes`) — colonne ajoutée

| Colonne | Type | Contrainte | Note |
|---|---|---|---|
| `note` | `Text` | `NOT NULL`, défaut `""` | Note de séance en texte libre (rapport/observations de l'encadrant, US3) — distincte du journal de bord d'un jeune, qui reste sur `ProfileLogEntry` (#867). Écrite via le `PATCH` d'entraînement déjà existant, même patron sentinelle que `lieu`/`type_seance`. |

Les autres colonnes (`date`, `heure_debut`, `lieu`, `type_seance`,
`created_at`) et la relation `participants` sont posées par #868 et ne
changent pas.

## `EntrainementParticipant` (table `entrainement_participants`) — colonne ajoutée

| Colonne | Type | Contrainte | Note |
|---|---|---|---|
| `present` | `Boolean` | nullable, défaut `NULL` | Statut de l'appel de **début** pour ce jeune, à cette séance. `NULL` = pas encore pointé, `True` = présent, `False` = absent. Le dernier statut écrit fait foi (FR-005) — aucune colonne d'historique. |

`id`, `entrainement_id`, `jeune_id`, `created_at` et la contrainte
`UNIQUE(entrainement_id, jeune_id)` sont posés par #868 et ne changent pas.
`present` partage le cycle de vie de la ligne : supprimer l'inscription
(désinscrire un jeune, `remove_participant` déjà existant) supprime son statut
de présence avec elle — aucun état orphelin possible.

## L'appel de fin : aucune donnée persistée

L'appel de fin (US2) ne porte **aucune** table ni colonne : il recalcule, en
mémoire côté frontend, un sous-ensemble des participants déjà chargés par
`GET /admin/jeunes/entrainements/{id}` (ceux dont `present === true`), et garde
la liste des jeunes « retrouvés » dans l'état local du composant React
`AppelFin.tsx`, jamais transmis au serveur (D2 de `research.md`). Ce n'est pas
une omission — la spec (FR-007) l'exige.

## Validation

- `EntrainementUpdate.note` : `str | None`, optionnel — absent du `PATCH`
  n'écrase rien (même patron que `lieu`/`type_seance`, sentinelle `...` côté
  repository). Fourni vide (`""`), efface la note existante — cohérent avec le
  reste des champs texte libre du modèle (`Course.format_label`, par exemple)
  et avec l'edge case « note vide non significative » traité côté frontend
  (formulaire qui n'envoie pas de `PATCH` sur un champ resté vide, plutôt
  qu'une règle serveur qui distinguerait « vide » de « absent »).
- `ParticipantAdd.present` : `bool | None`, défaut `None` — absent ou `null`
  laisse la ligne créée à son défaut (`present = NULL`, pas encore pointé),
  cohérent avec l'usage actuel de cette route depuis l'écran calendrier
  (#868), qui n'envoie jamais ce champ.
- `PresenceUpdate.present` : `bool`, obligatoire — la route dédiée
  (`PATCH .../presence`) sert exactement à passer d'un état à un autre
  (présent ↔ absent) ; elle ne sert jamais à remettre `present` à `NULL`,
  transition non demandée par la spec (FR-005 ne demande que la correction
  entre présent/absent, jamais un retour à « pas pointé »).
- Existence du jeune (`jeune_id`) : déjà vérifiée en Python par
  `_jeune_existant` (`services/jeunes/entrainements.py`, #868) sur le seul
  chemin d'écriture qui la nécessite, `add_participant` — `set_presence` ne
  crée aucune ligne, elle en modifie une déjà existante trouvée par
  `find_participant`, donc n'a pas besoin de la revérifier (404 si
  l'inscription elle-même n'existe pas, patron de `remove_participant`).

## État / transitions

`present` connaît exactement trois états et deux transitions possibles depuis
l'écran d'appel, l'une comme l'autre réversible sans limite :

```
NULL (pas pointé) ──set_presence(True)──► True (présent)
NULL (pas pointé) ──set_presence(False)─► False (absent)
True  ◄──────────────set_presence(●)────────────► False
```

Aucune transition ne ramène `present` à `NULL` après un premier pointage —
non demandé par la spec, et sans cas d'usage identifié (corriger une erreur de
pointage se fait en basculant vers l'autre valeur, jamais en « dépointant »).
