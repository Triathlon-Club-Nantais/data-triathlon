# Data Model: Formulaire public de déclaration de bénévolat (#778)

## `VolunteerAction` (existant, étendu)

Trois colonnes ajoutées à `volunteer_actions` (migration Alembic, cf.
research.md D3/D4). Reste indépendante de `VolunteerDeclaration` (#751).

| Colonne | Type | Contraintes | Notes |
|---|---|---|---|
| `id` | `Integer` | PK | *(existant)* |
| `athlete_id` | `Integer` | FK `athletes.id`, index | *(existant)* |
| `season` | `Integer` | index | *(existant)* — dérivé côté serveur pour le nouveau chemin (research.md D5), transmis par le client pour l'ancien (inchangé) |
| `declared_by_user_id` | `Integer` | FK `users.id` | *(existant)* — le membre connecté qui déclare, quel que soit l'athlète crédité |
| `created_at` | `DateTime` | default `utcnow` | *(existant)* |
| `title` | `String` | **NEW**, nullable | Obligatoire (1-200 caractères) par le schéma Pydantic du nouveau endpoint (FR-001/FR-004) ; `NULL` pour les lignes du bouton admin existant (FR-008) |
| `description` | `Text` | **NEW**, nullable | Obligatoire (1-10 000 caractères) par le même schéma ; `NULL` pour les lignes existantes, mêmes bornes que `VolunteerDeclarationCreate` (#751) pour rester cohérent dans le domaine « bénévolat » |
| `status` | `String` | **NEW**, `NOT NULL`, `server_default="en_attente"` | `"en_attente"` uniquement dans le périmètre de #778 — la transition vers `"validee"`/refus est #779 |

Pas de contrainte d'unicité nouvelle : plusieurs lignes peuvent coexister
pour le même `(athlete_id, season)`, comme aujourd'hui (docstring du modèle —
c'est un journal).

### Validation rules (FR ↔ colonnes)

- FR-001/FR-004 : `title` (1-200) / `description` (1-10 000) non vides et
  bornés — validé par `VolunteerActionSelfCreate` (nouveau schéma dédié, pas
  `VolunteerActionCreate` de `admin.py` — noms distincts pour éviter toute
  ambiguïté d'import entre les deux, cf. `/speckit-analyze` finding C1),
  jamais au niveau DB (colonnes nullable, research.md D3).
- FR-002 : idem, message d'erreur explicite sur corps invalide ou trop long
  (422 Pydantic).
- FR-003/FR-005 : création réservée à un `current_user` valide, aucune
  vérification de pouvoir RBAC.
- FR-009 : `status` posé à `"en_attente"` par le service, jamais transmis par
  le client (pas de champ `status` dans `VolunteerActionSelfCreate`).

### Ce que #778 ne modifie pas

- `volunteer_action_repository.create()` (utilisée par l'endpoint admin
  existant) reste inchangée — nouvelle fonction distincte pour le chemin
  self-service (voir contracts/).
- `admin_actions.declare_volunteer_action` et
  `POST /admin/athletes/{athlete_id}/volunteer-actions` restent inchangés
  (FR-008).
- `has_volunteer_action` (quota de saison,
  `volunteer_action_repository.exists_for_athlete_season`) reste une simple
  vérification d'existence, indifférente à `status` (assumption spec.md —
  #779 branchera le filtre).

## Aucune nouvelle permission

Le nouveau endpoint ne porte aucun pouvoir RBAC — `current_user` suffit
(comme `volunteer_declarations.py`, distinct de `admin_data.py` qui reste
gardé par `athletes:volunteer_manage`).
