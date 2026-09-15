# Data Model: Calendrier des entraînements jeunes

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
| `jeune_id` | `Integer` | `NOT NULL`, indexé | **sans FK pour ce lot** — cf. `research.md` §Dépendance |
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
- `ParticipantAdd` : `jeune_id: int`, positif. Aucune vérification d'existence
  du jeune référencé n'est possible dans ce lot tant que la table `jeunes`
  n'existe pas (#867) — documenté comme limite temporaire assumée dans
  `research.md`. **Dès que #867 aura mergé sa table de profils et que la
  contrainte de clé étrangère aura été resserrée** (migration de suivi), une
  tentative d'inscription d'un `jeune_id` inexistant remontera naturellement
  en 404/422 depuis cette contrainte — voir `spec.md` Edge Cases, qui anticipe
  ce comportement final.

## État / transitions

Aucune machine à états dans ce lot : une séance existe ou non, une inscription
existe ou non. Le statut présent/absent (#869) n'est pas un champ de
`EntrainementParticipant` posé ici — il sera ajouté par #869 sans
modification de ce qui est posé maintenant (FR-010).
