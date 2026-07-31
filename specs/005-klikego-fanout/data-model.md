# Data Model — Fan-out des heats Klikego

**Feature** : 005-klikego-fanout — [plan.md](./plan.md)

Cette feature **ne modifie pas** le modèle de données. Ce document explicite ce qui reste stable et pourquoi, pour éviter les propositions de migration inutiles au moment de `/speckit-tasks`.

## Entités concernées (rappel — aucune modification)

### `Course`

Contrainte d'unicité inchangée : `UNIQUE(name, event_date, event_type)`. Un fan-out crée N `Course` distinctes pour un même événement Klikego dès que N `event_type` diffèrent (par exemple `triathlon-s`, `swimrun-s`, `duathlon-s`). Deux heats du **même** `event_type` d'un même événement (par exemple `triathlon-s-indiv` + `triathlon-s-relais` classés tous deux `triathlon-s`) rentreraient en collision d'unicité — voir « Edge cases » plus bas.

**`source_url`** : reste au niveau du heat (`f"{BASE}/resultats/{slug}/{event_id}?heat={heat}"`), clé de cache TTL. Contrat inchangé.

### `Participation`

Contrainte d'unicité inchangée : `UNIQUE(course_id, bib_number)`. Aucune interaction avec le fan-out : chaque heat produit ses propres participations, aucun croisement inter-heat.

### `Athlete`

Contrainte d'unicité inchangée : `UNIQUE(nom, prenom, birth_date)`. Un athlète qui participe à deux heats du même événement (par exemple un triathlon relais où le même sportif fait deux étapes) est représenté par **une** `Athlete` et **deux** `Participation`. Comportement existant, aucune modification.

## Absence de nouveau modèle

Ce n'est **pas** un oubli. Trois raisons :

1. **Pas d'entité « événement »** dans le catalogue. Un événement Klikego (URL nue) est un concept **amont** au sens du sondage 2026-07-31, il n'a d'existence que pendant l'import comme regroupement de heats. Après import, les N `Course` créées sont autonomes et n'ont aucun lien parent/enfant.
2. **Pas de champ `heat` sur `Course`**. Le heat est **intégré à la source_url** (`?heat=X`) et **classifié en `event_type`**. La spécificité du heat vit dans `Course.name` (dérivé de `heat_label` par le scraper Klikego) et dans `Course.source_url` (pour le rejeu ciblé). Ajouter un champ `heat_slug` séparé introduirait une redondance — YAGNI (Principe VI).
3. **Pas de table d'événement ni de sondage**. Rien de la V1 ne s'appuie sur une liste stable d'événements. Une URL nue est ré-énumérée à chaque import : c'est la source qui fait autorité.

## Contrat de `_Persister._courses`

Aujourd'hui déjà : `_Persister._courses: dict[int, Course]` indexe **toutes** les courses touchées par un import. Le fan-out ne change pas ce contrat — il alimente juste plus d'entrées.

`courses_summary()` (utilisée par le SSE `done`, cf. `import_service.py:395`) rend `[{id, name, event_type}]` dans l'ordre d'insertion. Pour le fan-out, l'ordre correspond à l'ordre des heats dans le `<el-select>` du HTML source (Klikego trie déjà par « ordre de programme »).

## Edge cases sur l'unicité `Course`

- **Deux heats du même `event_type`** dans un même événement : contrainte `UNIQUE(name, event_date, event_type)` s'appuie aussi sur `name`. Le nom d'épreuve inclut typiquement le libellé du heat (`Triathlon S Individuel` vs `Triathlon S Relais`) — deux `Course` distinctes. Si deux heats donnent exactement le même triplet (cas théorique — Klikego jumeau parfait), la seconde `get_or_create_course` retombera sur la première `Course` et **écrasera** ses participations. Comportement à surveiller au premier import réel des gros événements (Ha' Frenchman, Diaoulman). **Contrat existant**, hors scope de cette feature.
- **Événement sans classement publié** (page 200 mais `<el-select>` absent) : `_enumerate_heats` rend `[]`. `klikego.scrape_event_all` ne boucle sur rien, renvoie `[]`. `import_service._require_event_name` échoue avec le message « nom d'épreuve introuvable » — comportement inchangé.

## Migration

**Aucune**. `/speckit-tasks` doit refuser toute tâche de type « nouvelle révision Alembic » pour cette feature. Une tâche de contrôle (`check-no-migration`) sera générée pour figer cet invariant.
