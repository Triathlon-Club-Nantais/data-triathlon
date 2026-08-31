# Data Model: Workflow de validation admin des actions de bénévolat (#779)

## `VolunteerAction` (existant depuis #778, aucune nouvelle colonne)

`status` prend désormais un sens à la lecture : trois valeurs
significatives au lieu d'un champ posé sans être jamais relu.

| Valeur | Posée par | Transition |
|---|---|---|
| `"en_attente"` | défaut DB ; création self-service (#778) ou admin (#709) | → `"validee"` (accept) ou `"refusee"` (reject) |
| `"validee"` | `accept()` | → `"refusee"` (reject, US3 Scenario 3) ; idempotent sur `accept()` |
| `"refusee"` | `reject()` | idempotent sur `reject()` ; pas de retour vers `"validee"` (hors périmètre) |

```
        création (self-service #778 ou admin #709)
                        │
                        ▼
                 "en_attente" ──────► admin accept ──────► "validee"
                        │                                      │
                        └──────────► admin reject ◄────────────┘
                                     "refusee"
```

### Validation rules (FR ↔ code)

- FR-003/FR-004 : `accept()` — `"en_attente"` → `"validee"` ; no-op si déjà
  `"validee"`.
- FR-005/FR-006 : `reject()` — `"en_attente"` ou `"validee"` → `"refusee"` ;
  no-op si déjà `"refusee"`.
- FR-008 : `volunteer_action_repository.exists_for_athlete_season` filtre
  désormais `VolunteerAction.status == "validee"` (research.md D3) —
  **seul** point de lecture du quota, un seul appelant
  (`admin_actions.season_quota`).
- FR-001/FR-002/FR-007 : toutes les routes du nouveau router gardées par
  `athletes:volunteer_validate` (research.md D2).

## Permission ajoutée (`app/core/permissions.py`)

| Code | Libellé | Feature |
|---|---|---|
| `athletes:volunteer_validate` | Instruire les déclarations de bénévolat | `FEATURE_ATHLETES` — voisine de `athletes:volunteer_manage`/`athletes:season_validate` |

## Nouveau schéma (`app/schemas/volunteer_action.py`, existant depuis #778)

`AdminVolunteerActionOut` — mêmes champs que `VolunteerActionSelfOut`, mais
`title`/`description` optionnels (`str | None`) pour représenter les lignes
créées par le chemin admin existant (research.md D5).

## Journal d'administration

Réutilise `admin_action_log_repository.create` existant (research.md D7) :

- `action`: `"athlete.volunteer_action.accept"` / `"athlete.volunteer_action.reject"`
- `entity_type`: `"athlete"`
- `entity_id`: `athlete_id` de la déclaration instruite
- `payload`: `{"season": ..., "action_id": ...}`

Aucune entrée si l'opération est un no-op idempotent (cohérent avec
`volunteer_declaration_service.validate`, #751 — qui ne journalise pas non
plus une validation déjà appliquée).
