# Data Model: Déclaration de bénévolat

## `VolunteerDeclaration`

Nouvelle table `volunteer_declarations`. Indépendante de `volunteer_actions`
(#709) — voir research.md D1/D2.

| Colonne | Type | Contraintes | Notes |
|---|---|---|---|
| `id` | `Integer` | PK | |
| `title` | `String` | `NOT NULL` | Refusé si vide (FR-002) |
| `description` | `Text` | `NOT NULL` | Refusé si vide (FR-002) |
| `beneficiary_user_id` | `Integer` | FK `users.id`, `NOT NULL`, index | Le membre dont l'activité est tracée. Égal à `author_user_id` pour une auto-déclaration. |
| `author_user_id` | `Integer` | FK `users.id`, `NOT NULL` | Qui a créé l'entrée — peut différer du bénéficiaire quand un admin déclare pour un tiers (FR-004). |
| `status` | `String` | `NOT NULL`, default `"en_attente"` | `"en_attente"` \| `"validee"` (research.md D5). |
| `created_at` | `DateTime` | default `utcnow` | |

Pas de colonne `updated_at` : aucune mise à jour de `title`/`description`
n'est prévue (FR-011) ; le seul changement d'état est `status`, dont la
transition n'a pas besoin d'être datée séparément pour cette itération
(pas de FR/SC qui l'exige).

Pas d'`ondelete` sur les deux FK — patron uniforme du dépôt
(`database.py` n'active `PRAGMA foreign_keys` sur aucun moteur ; cf.
`UserFeedback`, `AdminActionLog`, `VolunteerAction`).

### Validation states

```
   création par un membre (auteur == bénéficiaire)
                    │
                    ▼
            "en_attente" ──────► admin valide ──────► "validee"
                    │                                     │
                    └──────────► admin/auteur supprime ◄──┘
                                  (DELETE réel, FR-008)

   création par un admin (bénéficiaire quelconque)
                    │
                    ▼
              "validee" (directement, FR-004)
```

### Validation rules (FR ↔ colonnes)

- FR-001/FR-002 : `title` et `description` non vides à la création — validé
  au niveau schéma Pydantic (`VolunteerDeclarationCreate`), pas seulement en
  base.
- FR-003/FR-004 : `beneficiary_user_id != author_user_id` n'est possible que
  si l'appelant porte `benevolat:manage` — vérifié en service, pas en
  contrainte SQL (la contrainte ne connaît pas l'appelant).
- FR-005 : transition `status` `"en_attente"` → `"validee"` réservée à
  `benevolat:manage`.
- FR-006/FR-007 : suppression ouverte à `author_user_id == current_user.id`
  ou à `benevolat:manage` — vérifié en service.
- FR-009/FR-010 : lecture filtrée par `beneficiary_user_id == current_user.id`
  pour un membre standard ; sans filtre pour `benevolat:read`/`benevolat:manage`.

### Index

- `beneficiary_user_id` : liste personnelle d'un membre (FR-009).
- Pas d'index composite sur `status` : le volume attendu (déclarations de
  bénévolat d'un club) ne justifie pas d'optimisation au-delà de l'index PK
  et de l'index simple ci-dessus (Principe VI).

## Permissions ajoutées (`app/core/permissions.py`)

| Code | Libellé | Feature |
|---|---|---|
| `benevolat:read` | Consulter les déclarations de bénévolat | `FEATURE_VOLUNTEERING = "Déclarations de bénévolat"` |
| `benevolat:manage` | Instruire les déclarations de bénévolat | `FEATURE_VOLUNTEERING` |

Voir research.md D3 pour le choix de séparer `read`/`manage`.

## Pas de nouvelle entité côté `AdminActionLog`

Réutilise `admin_action_log_repository.create` existant, avec :
- `action`: `"volunteer_declaration.create_for_other"` /
  `"volunteer_declaration.validate"` / `"volunteer_declaration.delete"`
- `entity_type`: `"volunteer_declaration"`
- `entity_id`: `VolunteerDeclaration.id`
- `payload`: `{"beneficiary_user_id": ...}` (create-for-other) ou `{}` (les
  deux autres — l'entité déjà nommée par `entity_id` suffit).
