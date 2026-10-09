# Data Model

Aucune table ni colonne nouvelle, aucune migration.

## Participation (existant)

| Champ | Rôle ici |
| --- | --- |
| `is_pending_validation` | `True` : déclaré, non validé. Toujours `True` sur une entrée refusée. |
| `is_rejected` | `True` : refusé par un bénévole. Exclut la ligne de l'affichage. |

États d'affichage dérivés :

| État | Condition | Page épreuve | Listes d'épreuves | Comptes |
| --- | --- | --- | --- | --- |
| validé | `is_pending_validation = false` | classement, rang | compte `total` | oui |
| en attente | `is_pending_validation = true AND is_rejected = false` | fin de classement, sans rang | `pending_count` | **non** |
| refusé | `is_pending_validation = true AND is_rejected = true` | absent | absent | non |

Transitions inchangées : validation (en attente → validé), refus et dé-refus
(en attente ↔ refusé), suppression.

## Projections ajoutées

- `CourseParticipationPage.pending_participations: list[ParticipationOut]` (défaut `[]`).
- `EventOut.pending_count: int` (défaut `0`) : nombre de résultats en attente non
  refusés de l'épreuve, aux filtres de la requête. Jamais additionné à `total`.
