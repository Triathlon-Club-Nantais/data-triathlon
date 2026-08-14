# Phase 1 — Data Model

## Aucune nouvelle entité persistée

Cette feature n'ajoute ni ne modifie de table, colonne ou migration. Elle lit
le modèle normalisé existant (`backend/app/models/`) :

- **`Athlete`** (`athletes`) : `id`, `nom`, `prenom`, `club` — inchangé.
- **`Course`** (`courses`) : `event_date` — utilisé pour dater la saison via
  `season_bounds()`, inchangé.
- **`Participation`** (`participations`) : `athlete_id`, `course_id`, `club`
  (club au moment de la course, utilisé par `tcn_clause`) — inchangé.

## Vue agrégée (calculée, non persistée)

Le seul « objet » que cette feature introduit est une projection en mémoire,
rendue par le nouvel endpoint et consommée par le front :

| Champ | Type | Origine |
|---|---|---|
| `id` | int | `Athlete.id` |
| `nom` | str | `Athlete.nom` |
| `prenom` | str | `Athlete.prenom` |
| `participation_count` | int | `COUNT(Participation.id)` groupé par athlète, filtré saison + club |

Contraintes dérivées de la spec :
- Seuls les athlètes avec `participation_count >= 1` sur la saison filtrée
  apparaissent (jointure **interne** `Athlete → Participation`, pas de
  `LEFT OUTER JOIN` — à la différence de `search_admin` qui, lui, veut
  justement voir les athlètes à 0).
- Tri par défaut au niveau requête : `nom`, `prenom` (ordre secondaire stable,
  cf. Edge Cases du spec — égalité sur `participation_count`).

## Schéma Pydantic (DTO de sortie)

`backend/app/schemas/athlete.py` — nouveau modèle, additif :

```python
class AthleteSeasonActivity(BaseModel):
    model_config = ConfigDict(from_attributes=False)  # construit depuis un tuple (Athlete, count)

    id: int
    nom: str
    prenom: str = ""
    participation_count: int
```

Pas de champ `club` : la page est déjà scopée club par construction
(`scope=club` imposé côté appelant, cf. research.md), l'exposer serait un
champ mort sur cette route précise — à la différence d'`AthleteBrief`, réutilisé
tel quel par des écrans qui, eux, en ont besoin.
