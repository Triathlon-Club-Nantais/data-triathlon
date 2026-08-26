# Phase 1 — Modèle de données

Feature : [Portée des compteurs configurable](./spec.md) · Décisions : [research.md](./research.md)

## Table `counter_scope_entries`

Une entrée = une chaîne appartenant à l'un des deux ensembles qui bornent les compteurs.

| Colonne | Type | Contraintes | Rôle |
| --- | --- | --- | --- |
| `id` | `Integer` | PK | |
| `kind` | `String(32)` | `NOT NULL`, indexée | Nature de l'entrée : `non_federal_discipline` ou `tcn_club_label` |
| `value` | `String(120)` | `NOT NULL` | La chaîne, **sous sa forme comparable** (cf. « Forme stockée » ci-dessous) |
| `created_at` | `DateTime` | `NOT NULL`, défaut `utcnow` | Date d'ajout (FR-016) |
| `created_by_user_id` | `Integer` | FK `users.id`, **nullable** | Auteur de l'ajout (FR-016). `NULL` pour les lignes posées par la migration d'amorçage — affichées « Configuration initiale » |

**Unicité** : `UNIQUE (kind, value)`. C'est elle qui rend FR-009 (refus du doublon) infaillible même si deux administrateurs écrivent en même temps — la validation applicative répond joliment, la contrainte répond toujours.

**Index** : celui de la contrainte d'unicité suffit. La table fait douze lignes et est lue une fois par processus ; aucun autre index n'a de justification.

**Pas de colonne `is_active`, pas de suppression logique, pas d'historique de versions.** Retirer une entrée la supprime. Le journal d'administration (`admin_action_log`) porte déjà la trace de qui a retiré quoi et quand (FR-013) : un second historique dans cette table ferait doublon.

### Les deux natures

| `kind` | Ce que `value` contient | Validation à l'écriture |
| --- | --- | --- |
| `non_federal_discipline` | Un slug canonique de discipline, tel que `app/scrapers/classify.CANONICAL_TYPES` les définit — `trail`, `cyclisme-route`, `course-a-pied-semi`… | Minuscules, sans espaces de bord. Un slug hors de `CANONICAL_TYPES` est **accepté avec avertissement**, jamais refusé (FR-011) |
| `tcn_club_label` | Un libellé du club sous sa forme normalisée par `core.club.normalize_club` — `triathlon club nantais`, `tcn`… | Refusé si vide une fois normalisé, refusé si déjà présent (FR-009). Le retrait est refusé s'il viderait la liste (FR-010) |

### Forme stockée

`value` porte la forme **comparable**, pas la saisie brute. Un administrateur qui tape « TRIATHLON  CLUB NANTAIS » enregistre `triathlon club nantais`, et c'est cette forme qui lui est réaffichée.

La raison est le miroir SQL : `tcn_clause` compare `_normalise_sql(column)` à l'ensemble des valeurs, et `is_tcn` compare `normalize_club(club)` au même ensemble. Stocker la saisie brute obligerait à normaliser à la lecture des deux côtés — deux occasions de plus de diverger, pour un affichage à peine plus fidèle.

Conséquence à assumer dans l'écran : la casse saisie n'est pas conservée. FR-015 demande déjà que la règle soit expliquée ; l'écran dit que la comparaison ignore casse et espaces.

### Amorçage (FR-002)

La migration Alembic insère les douze valeurs aujourd'hui en dur, `created_by_user_id` à `NULL` :

- `non_federal_discipline` (9) : `trail`, `cyclisme`, `cyclisme-route`, `cyclisme-clm`, `course-a-pied`, `course-a-pied-5k`, `course-a-pied-10k`, `course-a-pied-semi`, `course-a-pied-marathon` — l'actuel `core.discipline.NON_FEDERAL_TYPES`.
- `tcn_club_label` (3) : `triathlon club nantais`, `tri club nantais`, `tcn` — l'actuel `core.club.TCN_CLUB_LABELS`.

Les valeurs sont **écrites en littéral** dans la migration, jamais importées depuis `app.core` : une migration doit rester lisible telle quelle des années après, indépendamment de ce que le code est devenu.

Le risque de divergence entre ces littéraux et les défauts du registre est neutralisé par un test qui applique les migrations sur une base vierge et compare les lignes obtenues aux défauts de `core/counter_scope.py`.

## Registre en mémoire — `core/counter_scope.py`

Pas une entité persistée : l'image en mémoire des deux ensembles, lue par les prédicats.

```
DEFAULT_NON_FEDERAL_DISCIPLINES : frozenset[str]   # les 9 valeurs d'aujourd'hui
DEFAULT_TCN_CLUB_LABELS         : frozenset[str]   # les 3 valeurs d'aujourd'hui

non_federal_disciplines() -> frozenset[str]
tcn_club_labels()         -> frozenset[str]
load(disciplines, labels) -> None    # remplace les deux ensembles d'un seul geste
reset()                   -> None    # retour aux défauts — fixture de test, rien d'autre
```

Trois propriétés à tenir :

- **Aucune Session, aucun import d'une couche supérieure.** C'est ce qui autorise ce module dans `core/` (Principe II).
- **Les deux ensembles se remplacent ensemble, et par rebinding.** `load()` prend les deux et **réassigne** les deux noms sur de nouveaux `frozenset` — jamais un `.add()`, `.discard()` ou `.clear()` sur l'ensemble en place. La raison est concrète : l'import d'épreuve tourne dans un **thread d'arrière-plan** (le scrape SSE de `import_service`) et appelle `is_tcn` ligne par ligne pendant qu'un administrateur peut écrire. Une réassignation de nom est atomique du point de vue d'un autre thread ; une mutation en place expose un ensemble à moitié écrit, et le résultat serait quelques lignes mal classées, sans erreur ni trace.
- **Les accesseurs rendent un `frozenset`**, jamais l'ensemble mutable lui-même — un appelant ne modifie pas la configuration par accident.

## Ce que deviennent `core/club.py` et `core/discipline.py`

Les deux modules gardent la règle, perdent les données.

| Avant | Après |
| --- | --- |
| `TCN_CLUB_LABELS: frozenset[str] = frozenset({...})` | supprimé — les valeurs deviennent `DEFAULT_TCN_CLUB_LABELS` dans le registre |
| `is_tcn(club)` compare à `TCN_CLUB_LABELS` | compare à `counter_scope.tcn_club_labels()` |
| `tcn_clause(column)` : `.in_(sorted(TCN_CLUB_LABELS))` | `.in_(sorted(counter_scope.tcn_club_labels()))` |
| `NON_FEDERAL_TYPES: frozenset[str] = frozenset({...})` | supprimé — deviennent `DEFAULT_NON_FEDERAL_DISCIPLINES` |
| `is_federal(event_type)` : `not in NON_FEDERAL_TYPES` | `not in counter_scope.non_federal_disciplines()` |
| `federal_clause(column)` : `.notin_(sorted(NON_FEDERAL_TYPES))` | `.notin_(sorted(counter_scope.non_federal_disciplines()))` |

Restent **strictement inchangés** : `normalize_club`, `_normalise_sql`, `CLUB_NORMALIZED_INDEX_EXPRESSION`, `TCN_CANONICAL_NAME`, `SCOPE_CLUB`, `is_club_scope`. La normalisation ne bouge pas (research.md §6), et le nom canonique du club n'est pas une règle de comptage.

Les docstrings des deux modules doivent suivre : elles décrivent aujourd'hui des listes figées dans le code, et cette description devient fausse. Elles gardent en revanche ce qui reste vrai et qui compte le plus — liste d'**exclusion** pour les disciplines, match à l'**égalité** pour le club, garantie que Python et SQL comparent des chaînes entières des deux côtés.

## Relations

`counter_scope_entries.created_by_user_id` → `users.id`, nullable, sans `relationship` inverse sur `User` : rien ne remonte d'un utilisateur vers ses entrées, et une relation dans ce sens serait chargée pour personne. Le routeur charge l'auteur par `joinedload` pour l'affichage, sur le patron de `site_access_config_repository.get_config(with_updated_by=...)`.

## Journal d'administration

Chaque écriture pose une ligne dans `admin_action_log` (FR-013), via `admin_action_log_repository.create` :

| Champ | Valeur |
| --- | --- |
| `action` | `counter_scope.entry_add` / `counter_scope.entry_remove` |
| `entity_type` | `counter_scope_entry` |
| `entity_id` | l'`id` de l'entrée ajoutée ou retirée |

Pour un retrait, l'`id` référence une ligne qui n'existe plus — c'est déjà le cas des autres suppressions journalisées, et c'est le sens d'un journal.
