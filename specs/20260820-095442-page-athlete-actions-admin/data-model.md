# Phase 1 — Modèle de données

**Feature** : actions d'administration sur la page d'un coureur (#439)

Trois entités sont en jeu, **une seule change** : `Athlete` gagne une colonne.
`Participation` et `AdminActionLog` sont utilisées telles quelles.

## `Athlete` — une colonne ajoutée

`backend/app/models/athlete.py`

| Champ | Type | Contrainte | Changement |
| --- | --- | --- | --- |
| `id` | `int` | PK | — |
| `nom` | `str` | `NOT NULL` | — |
| `prenom` | `str` | `NOT NULL`, défaut `""` | — |
| `birth_date` | `date \| None` | nullable | — |
| `gender` | `str` | `NOT NULL`, défaut `""` | — |
| `club` | `str \| None` | nullable — le **club actuel** | valeur désormais modifiable à la main |
| `club_locked` | `bool` | `NOT NULL DEFAULT false` | **NEW** |

`UniqueConstraint("nom", "prenom", "birth_date", name="uq_athlete_identity")` :
inchangée. `club` n'en fait pas partie et ne doit pas y entrer — deux coureurs
homonymes se distinguent par leur date de naissance, pas par leur club.

### `club_locked` — sémantique

> **Faux** (défaut) : le club actuel **suit l'import**. Chaque import portant un
> libellé de club pour ce coureur le met à jour, comme aujourd'hui.
>
> **Vrai** : le club actuel a été **corrigé à la main** et n'est plus réécrit par
> aucun import.

Le drapeau qualifie **la colonne `club`**, pas la ligne — d'où l'absence du
préfixe `is_` que le dépôt réserve aux qualifications de ligne (`is_relay`,
`is_pending_validation`, `is_rejected`, `is_active`).

### Transitions d'état

Une seule transition existe dans cette feature, et elle est **à sens unique** :

```text
  club_locked = false ──(correction manuelle du club)──▶ club_locked = true
        ▲                                                       │
        └──────────────── aucune transition ────────────────────┘
                        (hors périmètre — D3)
```

- **Déclencheur** : `admin_actions.update_athlete` reçoit un champ `club` dans sa
  demande **et** la valeur écrite diffère de l'ancienne.
- **Une correction qui ne change rien** (même libellé) ne pose pas le drapeau —
  même règle que le journal, qui n'écrit rien pour un geste sans effet (FR-014).
- **Corriger le club d'un coureur déjà verrouillé** est légitime et ne change que
  `club` ; le drapeau reste vrai.
- **Créer un coureur** part de `false` : une fiche née d'un import suit l'import.

### Invariants

| # | Invariant | Où il vit | Où il se teste |
| --- | --- | --- | --- |
| INV-1 | `club_locked` vrai ⇒ aucun import ne réécrit `club` | `athlete_repository.resolve` | `tests/test_repositories/test_athlete_repository.py`, `tests/test_services/test_import_service.py` |
| INV-2 | `club_locked` faux ⇒ `club` suit l'import, comportement inchangé | idem | idem |
| INV-3 | Une correction manuelle qui **change** `club` pose `club_locked` | `admin_actions.update_athlete` | `tests/test_services/test_admin_actions.py` |
| INV-4 | Une correction d'identité qui ne touche pas `club` laisse le drapeau tel quel | idem | idem |
| INV-5 | `club_locked` n'apparaît dans aucun DTO d'API | `schemas/athlete.py`, `schemas/admin.py` | `tests/test_api/test_admin_data_api.py` |

`resolve` est **le seul écrivain** de `Athlete.club` après création — vérifié sur
tout `backend/app` (voir research.md, D1). INV-1 n'a donc qu'un point
d'application, et aucun chemin d'import ne peut le contourner :
`import_service`, `bulk_import_service` et `rescrape_service` passent tous par
`resolve` ou `get_or_create`.

### Règles de validation du club

Portées par le DTO, pas par le modèle :

- Le libellé est **détrempé** de ses espaces de bord (`str_strip_whitespace`,
  déjà sur `AdminAthleteUpdate`).
- Un champ **vidé** vaut `NULL`, pas `""` : `club` rejoint donc `_NULLABLES` de
  `AdminAthleteUpdate` (US3-AC2). C'est la seule façon d'exprimer « ce coureur
  n'a pas de club actuel » — un `""` serait un club à part entière pour l'index
  normalisé.
- **Aucune validation contre une liste de clubs** : le champ est libre. Seul
  `core/club.py` juge de l'appartenance au TCN, à l'égalité, et il reste le seul
  juge (#76).

### Migration

Une révision Alembic, `down_revision = "aeb0b98d1a51"` (tête unique constatée par
`uv run alembic heads` le 2026-08-20 — à revérifier si `main` a avancé depuis).

```text
op.add_column("athletes", sa.Column("club_locked", sa.Boolean(),
               nullable=False, server_default=sa.false()))
```

- `server_default` et non `default` : les lignes existantes doivent être
  remplies par la base, pas par Python. **Toutes** partent à `false` — aucun club
  actuel n'a jamais été corrigé à la main avant cette feature, puisque le geste
  n'existait pas.
- `downgrade` : `op.drop_column("athletes", "club_locked")`.
- SQLite (développement) accepte `ADD COLUMN ... NOT NULL DEFAULT false` sans
  batch : pas de contrainte à recréer, pas d'index à reconstruire.
- `tests/test_migrations.py` ne couvre l'aller-retour **que révision par
  révision** : `test_upgrade_head_sur_base_vierge` est générique, mais chaque
  `downgrade` a son propre test nommé
  (`test_downgrade_puis_upgrade_des_tables_d_authentification`,
  `…_de_l_indice_de_fiabilite`). Cette révision doit donc **ajouter le sien** —
  sans quoi son `downgrade` n'est jamais exécuté. C'est une exigence du Principe
  III, portée par une tâche de `tasks.md`.

## `Participation` — inchangée

Aucun champ ajouté ni modifié. Deux points de vigilance portés par la spec :

- `club` de la participation est **le club au moment de la course** : distinct de
  `Athlete.club`, jamais réécrit par un changement de club actuel (FR-013).
- La suppression d'un résultat **ne supprime pas** son coureur, même devenu sans
  résultat (FR-012). Contrairement à `reassign_participation`, aucune purge des
  fiches orphelines n'est déclenchée (research.md, D5).

Le repository gagne une fonction, sœur des `delete_all` / `delete_for_course`
existantes :

```text
participation_repository.delete(db, participation) -> None
```

## `AdminActionLog` — inchangée

`user_id`, `action`, `entity_type`, `entity_id`, `payload` (JSON). Les quatre
gestes de la feature s'y écrivent, dont **un nouveau** :

| Geste | `action` | `entity_type` | `entity_id` | `payload` | État |
| --- | --- | --- | --- | --- | --- |
| Correction d'identité ou de club | `athlete.update` | `athlete` | id du coureur | `{before, after}` sur nom, prénom, date de naissance **et club** | existant, `club` ajouté à l'instantané |
| Suppression d'un résultat | `participation.delete` | `participation` | id du résultat | identité de ce qui disparaît (coureur, épreuve, place, temps) | **NEW** |
| Réattribution d'un résultat | `participation.reassign` | `participation` | id du résultat | `{from, to}` | existant, inchangé |

`payload` de `participation.delete` porte de quoi **lire** ce qui a disparu : le
geste est irréversible et le journal est tout ce qui en reste (FR-014, hypothèse
« aucune corbeille »). Un id seul ne se relit pas — la ligne visée n'existe plus.

Deux règles déjà tenues par les gestes existants et exigées du nouveau :

- **Un geste sans effet n'écrit rien** : `update_athlete` compare son instantané
  avant/après et retourne sans journaliser si rien n'a changé ;
  `reassign_participation` est idempotent.
- **Un geste refusé n'écrit rien et ne modifie rien** : le conflit d'identité est
  détecté par **lecture préalable** et non par l'`IntegrityError` de
  `uq_athlete_identity`, qui invaliderait la transaction (FR-010).

## Ce que la feature n'ajoute pas

- Aucune table.
- Aucun pouvoir : `athletes:read`, `athletes:write`, `participations:delete` et
  `participations:reassign` sont déjà à l'inventaire de `core/permissions.py`.
- Aucun index : `club_locked` n'est jamais un critère de filtre, seulement une
  lecture sur une ligne déjà chargée.
