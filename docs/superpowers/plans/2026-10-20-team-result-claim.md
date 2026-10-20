# Réclamer un résultat d'équipe (#1739)

**Objectif.** Étendre « Ce résultat est à moi » (#1637) aux relais : « Je
faisais partie de cette équipe ». Même file back-office ; à la validation, la
fiche du membre rejoint la composition du relais (#894,
`participation_teammates`). Pas de migration.

## Règles

- **Demande** : un relais (`is_relay` du résultat ou de l'épreuve) devient
  réclamable, sauf si la fiche du compte le porte déjà ou figure dans sa
  composition.
- **Validation, sans composition** : la fiche du membre devient la composition
  (un équipier, porteur). Le nom d'équipe est posé depuis la fiche porteuse s'il
  manque (même formule que `set_teammates`), puis `reassign_participation`
  (verrou, doublon sur l'épreuve, figement, purge de la fiche au nom de
  l'équipe, journal) et `replace_teammates([membre])`. Un deuxième équipier qui
  réclame tombe alors dans le cas suivant.
- **Validation, composition existante** : refus 409 tant que le membre n'y
  figure pas. L'admin complète l'équipe avec « Attribuer aux équipiers »
  (dialogue existant, prérempli composition + membre), puis la réclamation se
  clôt : le membre figurant dans la composition, `approve` supprime la
  réclamation et journalise.
- **File** : `ClaimedResultRead` gagne `is_relay`, `team_name`, `teammates`
  (ajouts, Principe IV).

## Fichiers

- Backend : `services/result_claims.py`, `schemas/athlete_claim.py`,
  `api/v1/admin_athlete_claims.py`, `models/AGENTS.md`.
  Tests : `tests/test_services/test_result_claims.py`,
  `tests/test_api/test_result_claims_api.py`.
- Frontend : `components/participations/ResultClaimAction.tsx` (libellé et
  éligibilité relais), `components/admin/ResultClaimsTable.tsx` (geste par cas),
  `components/athletes/TeammatesDialog.tsx` (rappel `onAttribue` après succès),
  `lib/types.ts`. Tests composant de chacun.

Hors périmètre : guide membre (#1626/#1676, autre session).
