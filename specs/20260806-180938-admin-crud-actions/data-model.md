# Phase 1 — Modèle de données

**Feature** : `specs/20260806-180938-admin-crud-actions/`

Une seule table naît de cette feature. Les quatre entités qu'elle manipule
(`Course`, `Athlete`, `Participation`, `User`) ne changent pas d'une colonne.

## Nouvelle entité — `AdminActionLog`

`backend/app/models/admin_action_log.py`, table `admin_action_log`.

| Colonne | Type | Contraintes | Rôle |
| --- | --- | --- | --- |
| `id` | `int` | PK | |
| `user_id` | `int` | FK `users.id`, indexée, **NOT NULL** | l'auteur (AC4) |
| `action` | `str` | NOT NULL, indexée | le geste — voir *Vocabulaire* |
| `entity_type` | `str` | NOT NULL | `"course"` / `"athlete"` / `"participation"` |
| `entity_id` | `int` | NOT NULL, **aucune FK** | l'entité visée |
| `payload` | `JSON` | nullable | le contexte de relecture (FR-013) |
| `created_at` | `datetime` | NOT NULL, `default=utcnow` | l'horodatage (AC4) |

**Index** : `ix_admin_action_log_user_id`, `ix_admin_action_log_action`,
`ix_admin_action_log_created_at`.

### Invariants

1. **`entity_id` ne porte aucune clé étrangère.** FR-014 exige que la trace
   survive à la disparition de ce qu'elle décrit ; une FK vers `courses.id`
   interdirait d'enregistrer la suppression d'une course. Le prix est assumé :
   `entity_id` peut pointer dans le vide, et c'est précisément l'usage.
2. **`user_id` porte une FK, sans `ondelete`** — patron du dépôt
   (`app/models/user.py`, `identities`, `user_sessions`) : `database.py`
   n'active pas `PRAGMA foreign_keys` en SQLite, un `ondelete` serait inerte en
   dev et actif en prod.
3. **Écriture seule.** Aucun `update`, aucun `delete`, aucune route de lecture
   dans ce périmètre. Le repository n'expose que `create` et — pour les tests —
   `list_for_entity`.
4. **Une entrée par geste réussi, aucune par geste refusé** (FR-015). Garanti
   par la transaction unique : le service `flush()`, le router `commit()`. Un
   refus lève avant le `flush`, rien n'est écrit.

### Vocabulaire de `action`

Codes techniques stables, en anglais (Principe I — ils traversent la base) :

| `action` | `entity_type` | `payload` |
| --- | --- | --- |
| `course.delete` | `course` | `{name, event_date, event_type, is_relay, participations_deleted, athletes_purged: [id]}` |
| `course.update` | `course` | `{before: {...}, after: {...}}` — le **quadruplet entier** des deux côtés |
| `athlete.update` | `athlete` | `{before: {...}, after: {...}}` — le **triplet entier** des deux côtés |
| `participation.reassign` | `participation` | `{course_id, from_athlete_id, to_athlete_id, athletes_purged: [id]}` |

`payload` conserve le nom de l'épreuve supprimée : sans lui, une ligne de
journal ne désigne plus qu'un identifiant mort (FR-013).

Les instantanés `before`/`after` portent **tous** les champs d'identité, pas
seulement ceux que la requête a touchés : relire « avant : (DUPOND, Jean, 1988)
→ après : (DUPONT, Jean, 1988) » ne demande aucun contexte, là où « avant :
(nom: DUPOND) » en exige un que le journal n'a pas.

## Entités existantes — ce qui **ne** change **pas**

### `Course` (`courses`)

Clé d'unicité inchangée : `uq_course_identity (name, event_date, event_type,
is_relay)`. C'est elle que FR-021 protège lors d'une correction.

Relation inchangée :

```python
participations = relationship(back_populates="course", cascade="all, delete-orphan")
```

C'est cette cascade — **ORM, pas DB** — qui réalise FR-002. Aucune migration
n'ajoute d'`ondelete` (voir research.md §D4).

### `Athlete` (`athletes`)

Clé d'unicité inchangée : `uq_athlete_identity (nom, prenom, birth_date)`. C'est
elle que FR-005 protège. Les colonnes `nom` / `prenom` restent en français :
elles sont **gelées par un contrat public** au sens du Principe I (DB + API +
`frontend/lib/types.ts`).

Champs éditables par cette feature : `nom`, `prenom`, `birth_date`, et rien
d'autre.

**`birth_date` est la seule donnée personnelle que la feature expose.** Elle ne
sort que par `GET /admin/athletes`, derrière `athletes:read` (FR-025). Les
schémas publics (`AthleteBrief`) ne la portent pas et ne doivent pas la porter.

### `Participation` (`participations`)

Seul `athlete_id` est modifiable par cette feature (FR-003). Ni les temps, ni
les rangs, ni le statut, ni `course_id` : rattacher un résultat à une **autre
épreuve** n'est pas dans le périmètre.

Contrainte à connaître : `uq_participation_bib (course_id, bib_number)` ne
protège **pas** contre deux participations d'un même athlète sur une même
épreuve. FR-006 est donc une vérification applicative, pas une contrainte.

### `User` (`users`)

Aucun changement. La feature lit `user.id` fourni par `require_permission`.

## Règles de validation

| Règle | Où | Erreur |
| --- | --- | --- |
| Épreuve / coureur / résultat inexistant | service | `NotFoundError` 404 — « Épreuve introuvable. », « Coureur introuvable. », « Résultat introuvable. » |
| Correction rendant deux épreuves identiques | service, via `course_repository.get_by_identity` | `DuplicateError` 409 nommant l'épreuve en conflit |
| Correction rendant deux coureurs identiques | service, via `athlete_repository.get_by_identity` | `DuplicateError` 409 nommant le coureur en conflit |
| Coureur cible déjà classé sur cette épreuve | service, via `participation_repository` | `DuplicateError` 409 |
| `nom` ou `prenom` vide ou blanc | schéma Pydantic : `str_strip_whitespace` **puis** `min_length=1` | 422 |
| `null` sur un champ `NOT NULL` (`nom`, `prenom`, `name`, `event_type`, `is_relay`) | schéma Pydantic (`_NULLABLES`) | 422 — sans ce garde, l'écriture ressortait en **500** (`IntegrityError`) |
| `event_type` hors nomenclature (`classify.CANONICAL_TYPES`) | schéma Pydantic (`field_validator`) | 422 — un slug fautif retirerait l'épreuve des filtres fédéraux et des statistiques, **en silence** |
| Corps de `PATCH` sans aucun champ | schéma Pydantic (validateur) | 422 — « Aucune modification demandée. » |
| Fiche coureur sans résultat après le geste | service → `athlete_repository.delete_orphans_among` | *(pas une erreur : purge, FR-022)* |

## Lectures dérivées (aucune colonne nouvelle)

Deux comptes calculés à la volée, issus des clarifications du 2026-08-06. Ils
vivent dans `repositories/`, ne sont **pas** persistés, et ne sont servis que
derrière un pouvoir.

| Compte | Définition | Où | Sert à |
| --- | --- | --- | --- |
| `deletion_impact.participations` | `count(participations WHERE course_id = ?)` — `participation_repository.count_for_course`, existant | `athlete_repository` / `participation_repository` | FR-017, FR-026 |
| `deletion_impact.athletes` | athlètes dont **toutes** les participations portent ce `course_id` — ceux que la purge emportera | `athlete_repository` | FR-017, FR-022, FR-026 |
| `AdminAthleteRead.participations` | `count(participations WHERE athlete_id = ?)` | `athlete_repository` | FR-024 — départager deux homonymes |

Le second compte et la purge doivent rester **la même définition** : si l'un dit
37 et que l'autre en supprime 38, SC-007 tombe. Un test l'ancre en comparant les
deux sur la même épreuve.

## Migration

Une révision Alembic, générée par `uv run alembic revision --autogenerate -m
"admin action log"` puis **relue à la main** (contrainte de la constitution,
§Additional Constraints).

Contenu attendu : `create_table('admin_action_log')` + trois index. Rien
d'autre — si l'autogenerate propose autre chose, c'est une dérive de modèle à
instruire avant de continuer.

`downgrade` : `drop_table` + `drop_index`.
