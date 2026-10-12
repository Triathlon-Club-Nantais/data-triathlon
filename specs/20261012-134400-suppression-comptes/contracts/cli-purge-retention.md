# Contrat : `purge-retention` (ajouts)

Commande existante, options inchangées (`--dry-run`, `--json`). Ajouts seulement.

**Sortie `--json`** : deux champs de plus, entiers.

```json
{"feedback": 0, "admin_log": 0, "profiles": 0, "club_members": 0, "member_emails": 0,
 "accounts_deleted": 2, "accounts_skipped": 1, "dry_run": false}
```

**Rapport texte** : deux lignes de plus.

```text
Comptes inactifs depuis 5 ans supprimés : 2      (« à supprimer » en passe à blanc)
Comptes inactifs conservés (cités par le club) : 1
```

Codes de sortie inchangés.
