# Data Model: Persist par lot pour l'import de résultats

Aucune migration Alembic, aucune colonne nouvelle : cette feature ne change
que la **forme** des accès DB dans `app/services/import_service.py`, pas le
schéma. Les entités ci-dessous sont celles déjà déclarées dans
`app/models/` — rappelées pour la clarté des tranches, pas redéfinies.

## Entités existantes concernées

### Athlete (`app/models/athlete.py`)

- Identité de dédoublonnage utilisée par l'import : `(nom, prénom)`
  insensible à la casse, avec `birth_date IS NULL` (cf. `research.md` —
  aucune ligne scrapée ne porte de date de naissance).
- Pas de changement de colonnes. Le seul changement est que la résolution
  d'un lot de lignes interroge cette table **une fois par tranche** au lieu
  d'une fois par ligne.

### Participation (`app/models/participation.py`)

- Unique par `(course_id, bib_number)`.
- Pas de changement de colonnes. Les lignes neuves restent créées comme
  instances ORM (`db.add`), mais leur `db.flush()` est différé à la fin du
  traitement d'une tranche/course plutôt qu'exécuté après chaque `db.add`.

### Course (`app/models/course.py`)

- Non modifiée. Le rechargement de ses participations existantes
  (aujourd'hui fait deux fois : `_index_course` puis `finalize()`) est
  dédupliqué — la liste chargée par `_index_course` est réutilisée par
  `finalize()` au lieu d'être requêtée une seconde fois.

## Structure interne introduite dans `_Persister`

Pas une entité persistée — un état en mémoire, propre au cycle de vie d'un
import (créé dans `__init__`, vidé à `finalize()`) :

- **File d'attente de résolution par course** : les lignes qui ont besoin
  d'une résolution d'athlète (dossard apparié → `_reconcile`, ou dossard
  neuf/sans dossard → `get_or_create_athlete`) sont mises en attente au lieu
  d'être résolues immédiatement. Vidée quand elle atteint la taille de
  tranche (≈500), ou au `finalize()` du persister pour le reliquat.
- **Cache de résolution par tranche** : `dict[(nom_lower, prenom_lower),
  Athlete]`, peuplé par la requête de lot puis consulté en mémoire pour
  chaque ligne en attente de la tranche — remplace l'appel
  `athlete_repository.get_by_identity` par ligne.

Ces structures ne survivent pas au-delà d'un import (`_Persister` est
instancié par appel de service, jamais réutilisé entre deux imports) — pas de
question de invalidation de cache à traiter ici.

## Pas de contrats externes à documenter

Cette feature ne change ni l'API HTTP (`/api/v1/scrape/...`), ni la CLI
(`import-sheet`, `rescrape-db`) : les phases SSE, les champs de réponse et les
compteurs exposés restent identiques (FR-004). Voir `research.md` pour la
justification de pourquoi la granularité de progression SSE (yield tous les 20
items) n'est pas affectée par la mise en lot interne. Pas de dossier
`contracts/` pour cette feature — c'est un refactor de performance interne au
service, pas un changement d'interface.
