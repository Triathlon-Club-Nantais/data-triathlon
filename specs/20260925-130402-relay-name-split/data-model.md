# Data Model : découper à l'import les relais qui nomment leurs équipiers (#895)

**Aucun changement de schéma, aucune migration.** La feature réutilise le modèle livré par
#894 (`specs/20260924-171341-relay-multi-athletes/data-model.md`).

## Entités réutilisées

| Entité | Table | Rôle ici |
| --- | --- | --- |
| `Participation` | `participations` | Le résultat de relais. `athlete_id` = premier équipier (porteur) ; `team_name` = nom publié reconstitué ; `is_relay` inchangé. |
| `ParticipationTeammate` | `participation_teammates` | Une ligne par équipier, `position` 0..N-1 dans l'ordre publié. Le porteur y figure aussi (position 0). |
| `Athlete` | `athletes` | Un équipier. Créé avec `nom` et `prenom` seuls s'il n'existe pas ; retrouvé par (nom, prénom) sans casse sinon. |

## Valeur transitoire (non persistée)

**Équipiers proposés** : `list[tuple[str, str]] | None`, sortie de
`split_relay_teammates` (`contracts/relay-teammates-rule.md`). `None` = la ligne n'est
pas découpée. Portée par `_PendingResolution.teammates` le temps de la résolution par lot.

## Transitions d'état d'un résultat de relais à l'import

```text
ligne relais scrapée
 ├─ dossard apparié, composition déjà posée ─────────────► _upsert seul (inchangé, #894)
 ├─ sans dossard, retrouvée par nom d'équipe (#997) ─────► _upsert seul (inchangé)
 ├─ split_relay_teammates → None ────────────────────────► chemin d'aujourd'hui (fiche d'équipe)
 └─ split_relay_teammates → [(nom, prénom) × 2..8]
     ├─ un équipier a déjà un autre résultat sur la course ► chemin d'aujourd'hui (FR-010)
     ├─ résultat existant sans composition (dossard, ou fiche d'équipe sans dossard)
     │     ► composition posée, porteur = équipier 1, team_name posé,
     │       ancienne fiche d'équipe purgée si orpheline
     └─ aucun résultat existant
           ► participation créée : porteur = équipier 1, team_name, composition
```

## Invariants

- Une ligne découpée ne crée **aucune** fiche au nom de l'équipe (FR-006).
- `teammate_links` non vide ⇒ `athlete_id` = athlète de `position` 0 (invariant #894).
- Un athlète n'apparaît qu'une fois par course, comme porteur ou comme équipier
  (FR-010).
- Hors relais (`is_relay` faux), aucune ligne n'a de composition posée par l'import
  (FR-007).
- Deux imports successifs de la même épreuve donnent le même état (FR-009).
