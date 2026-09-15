# Data Model: Pouvoir « jeunes »

Aucune table, aucune migration. Le seul « modèle » de cette issue est
l'ajout de deux membres à l'énumération Python `core/permissions.py` — la
composition et l'attribution vivent déjà dans `roles` / `role_permissions` /
`user_roles` (#115), inchangées ici.

## `Permission` (existant, non modifié)

Dataclass gelée (`backend/app/core/permissions.py`) :

| Champ | Type | Rôle |
|---|---|---|
| `code` | `str` | Identifiant stable `<domaine>:<geste>`, traverse la base. |
| `label` | `str` | Libellé français, affiché dans l'écran de composition. |
| `description` | `str` | Description française, affichée sous le libellé. |
| `feature` | `str` | Regroupement d'affichage (`FEATURE_*`). |

## Nouvelles entrées

| Constante | `code` | `label` | `feature` |
|---|---|---|---|
| `FEATURE_JEUNES` | — | — | `"Jeunes"` (nouvelle constante de regroupement) |
| `P.JEUNES_READ` | `jeunes:read` | « Consulter les jeunes » | `FEATURE_JEUNES` |
| `P.JEUNES_WRITE` | `jeunes:write` | « Encadrer les jeunes » | `FEATURE_JEUNES` |

`description` de chacune : voir `plan.md` §Summary et `research.md` §Décision 1
pour le texte exact retenu (rédigé en tâche d'implémentation, pas figé ici,
car c'est un détail de formulation, pas de structure).

## Relations avec le modèle existant

```
roles ──< role_permissions >── (code: str, hors clé étrangère — cf. permissions.py)
  │
  └──< user_roles >── users
```

`role_permissions.code` est une chaîne libre comparée à `permissions.CODES` à
la lecture (jamais de clé étrangère vers une table `permissions`, qui
n'existe pas — cf. `backend/app/core/AGENTS.md`, section « Le catalogue de
pouvoirs »). Ajouter `jeunes:read`/`jeunes:write` à `permissions.CODES` suffit
à les rendre attribuables : aucune ligne à insérer dans `roles`,
`role_permissions` ou `user_roles` pour cette issue (FR-006 : aucune
attribution effective n'est faite ici).

## Validation

- `jeunes:read` et `jeunes:write` respectent la forme `<domaine>:<geste>`
  (test paramétré existant, `test_un_code_suit_la_forme_domaine_deux_points_geste`).
- Les deux portent un `label`, une `description` et une `feature` non vides
  (test paramétré existant, `test_un_pouvoir_porte_son_francais_d_affichage`).
- Les deux sont des membres de `P` en plus d'être dans `ALL` (test existant,
  `test_chaque_membre_nomme_de_la_facade_est_dans_le_catalogue`).
