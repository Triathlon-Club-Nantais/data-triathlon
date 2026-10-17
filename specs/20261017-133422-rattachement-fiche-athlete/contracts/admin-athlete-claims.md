# Contrat : file des rattachements (back-office)

Gardé route par route par `require_permission(P.ATHLETE_CLAIMS_REVIEW)` (`athlete_claims:review`) : 401 sans session, 403 sans le pouvoir.

## `GET /api/v1/admin/athlete-claims`

Les demandes **en attente**, plus anciennes d'abord.

```json
[
  {
    "id": 7,
    "created_at": "2026-10-17T12:00:00Z",
    "user": {"id": 12, "display_name": "Léa M.", "email": "lea@example.org"},
    "athlete": {"id": 42, "prenom": "Léa", "nom": "Martin", "club": "TRIATHLON CLUB NANTAIS"},
    "licensee": {"prenom": "Léa", "nom": "MARTIN", "season": 2026},
    "email_on_member_list": true,
    "linked_accounts": 0
  }
]
```

`licensee` : `null` sans licencié de la saison en cours rattaché à la fiche.

## `POST /api/v1/admin/athlete-claims/{claim_id}/approve`

**204**. Rattache le compte à la fiche, supprime la demande, journalise `athlete_claim.approve` (`entity_type: "user"`, `payload: {"athlete_id", "claim_id"}`). **404** si la demande n'existe pas ou n'est plus en attente.

## `POST /api/v1/admin/athlete-claims/{claim_id}/reject`

**204**. Passe la demande en `rejected`, journalise `athlete_claim.reject`. **404** si elle n'existe pas ou n'est plus en attente.

## `GET /api/v1/admin/badge-counts` (clé additive)

`"claims": <nombre de demandes en attente>`, rendue aux seuls porteurs d'`athlete_claims:review`.
