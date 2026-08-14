# Data Model — Recherche d'athlète toujours accessible et sélection explicite

Aucune donnée serveur/DB créée ou modifiée par cette feature (front pur,
localStorage). Une seule entité côté client, déjà existante, dont la forme ne
change pas — seuls ses points de lecture/écriture s'étendent.

## Sélection d'athlète retenue (`PickedAthlete`)

| Champ | Type | Origine | Remarque |
|---|---|---|---|
| `id` | `number` | API (`AthleteBrief.id`) | Identifiant athlète |
| `prenom` | `string` | API | Jamais redécoupé depuis `nom` (#264) |
| `nom` | `string` | API | |

- **Stockage** : `localStorage["tcn-athlete"]`, valeur `JSON.stringify(PickedAthlete)`.
- **Lecture défensive** : une valeur absente, invalide, ou de forme différente
  (ex. ancien format `{id, name}` d'avant #264) est traitée comme "aucune
  sélection" — comportement existant, non modifié.
- **États** : deux seulement — `null` (aucun athlète retenu) ou une valeur
  `PickedAthlete` valide. Pas d'état intermédiaire.
- **Transitions** :
  - `null → PickedAthlete` : sélection, via la recherche (`AthletePicker.onPick`)
    ou via le nouveau bouton de la page profil.
  - `PickedAthlete → PickedAthlete` (id différent) : sélection d'un autre
    athlète, mêmes points d'entrée.
  - `PickedAthlete → null` : relâchement, **nouveau** — uniquement via le
    bouton de la page profil (issue #325 laisse le reste hors périmètre).
- **Propagation** : toute transition écrite par `writeAthlete`/`clearAthlete`
  émet un `CustomEvent("tcn-athlete-changed")` sur `window` (cf. `research.md`
  D2 et `contracts/athlete-selection.md`), consommé par `AppNav` pour refléter
  le changement sans rechargement de page.
