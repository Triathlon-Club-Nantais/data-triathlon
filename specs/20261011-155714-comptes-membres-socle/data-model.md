# Data Model: Comptes membres, socle

## `member_emails` (nouvelle, #1334)

| Colonne | Type | Contraintes | Note |
|---|---|---|---|
| `id` | Integer | PK | |
| `email` | String(320) | non nul | normalisée : `core.email.normalize_email` (`strip().lower()`) |
| `season` | Integer | non nul, index | année de début de saison (`core.season.season_of`), bornée par `SEASON_MIN`/`SEASON_MAX` |
| `source` | String(16) | non nul | `"import"` ou `"manual"` (constantes `SOURCE_IMPORT`, `SOURCE_MANUAL`) |
| `created_at` | DateTime | non nul, défaut `utcnow` | |

- `UniqueConstraint("email", "season")` : une adresse au plus une fois par saison ; sert aussi d'index de recherche du statut adhérent.
- Aucune clé étrangère : la liste ne connaît ni `users` ni `club_members` (rapprochement par l'adresse retenue du compte, à la lecture).
- Aucune autre donnée de l'export (nom, téléphone, adresse postale) n'est stockée.

### Règles

- **Import** d'une saison : `import` absentes du fichier → supprimées ; nouvelles → insérées en `import` ; présentes → inchangées ; `manual` → jamais touchées par un import. Fichier sans colonne reconnue ou sans adresse valide → refus 422, aucune écriture.
- **Ajout manuel** : insère en `manual` ; si l'adresse existe déjà en `import` pour la saison, elle passe en `manual` (elle survit alors aux imports suivants). Déjà `manual` → 409.
- **Retrait** : supprime l'entrée, quelle que soit son origine.
- **Saison qui compte** à la date `d` : `season_of(d)` si elle a au moins une entrée `import`, sinon `season_of(d) - 1`. Une adresse compte si elle figure dans la saison qui compte **ou** dans `season_of(d)` : avant le premier import, la saison en cours ne porte que des entrées `manual`, qui comptent en plus de la liste précédente sans la faire basculer.
- **Purge** (`purge-retention`) : supprime les entrées de `season < season_of(today) - 1`.

## `users` (existante, inchangée en schéma)

- `email` : désormais l'adresse retenue selon FR-016 (liste d'autorisation, puis liste d'adhérents, puis principale).
- **Statut adhérent dérivé** (jamais stocké) : `is_active` et `email != SYSTEM_USER_EMAIL` et `email` présente dans la saison qui compte.

## `identities` (existante, inchangée)

- Nouvelle valeur de `provider` : `"entra"`, `subject` = claim `oid` du jeton Entra (stable dans le tenant ; `sub` dépend de l'inscription d'application, revue de #1346).

## `allowed_emails` (existante, inchangée en schéma)

- Ne conditionne plus l'ouverture d'un compte. Garde : rôle du premier jour (`role_id`, réclamé à la création), et le retrait d'une adresse continue de désactiver les comptes qui la portent (`is_active = False`), ce qui refuse leur connexion.

## Migration

- Une révision Alembic `member_emails`, `down_revision = "3c751af1cc83"` (head au 2026-10-11) ; `downgrade` supprime la table.
