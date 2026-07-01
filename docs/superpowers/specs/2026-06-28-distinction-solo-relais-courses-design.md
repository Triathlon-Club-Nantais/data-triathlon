# Distinguer solo et relais comme deux courses (issue #9)

Date : 2026-06-28
Cible : `backend/`, `frontend/`
Issue : [#9 — Bug sur affichage relais](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/9)

## Problème

Sur la page d'une épreuve, les résultats du **M individuel** et du **M relais**
sont mélangés. Vincent (auteur de l'issue) tranche : *« ce sont deux courses
différentes »* → solo et relais doivent être **distingués**, et ce **pour tous
les fournisseurs**.

### Cause racine

Une `Course` est identifiée par `UNIQUE(name, event_date, event_type)`. Le
classifieur ramène « Triathlon M » individuel et « Triathlon M relais » au même
`event_type` (`triathlon-m`), et `is_relay` **ne fait pas partie de l'identité**.
Les deux fusionnent donc dans la **même** `Course`, et `Course.is_relay` ne
conserve que la valeur du premier import.

Un spec antérieur ([2026-06-15](2026-06-15-relais-par-participation-timepulse-design.md))
avait fait du relais une propriété **par participation** (`Participation.is_relay`)
pour gérer TimePulse, où solos et relais cohabitent dans un même heat. Ce spec-ci
remonte la distinction au niveau **Course** pour tous les fournisseurs, tout en
conservant `Participation.is_relay`.

## Décision d'architecture

Le relais devient une composante de l'**identité** d'une `Course`. Deux épreuves
de même nom/date/type mais l'une solo et l'autre relais deviennent **deux
`Course` distinctes**. Le slug `event_type` reste inchangé (`triathlon-m`) ; la
distinction est portée par la colonne `is_relay` existante.

Conséquence pour TimePulse (heat mixte) : `get_or_create_course` est appelé par
résultat avec le `is_relay` du résultat ; les solos sont routés vers la Course
solo et les relais vers la Course relais. Les deux Courses partagent le même
`source_url` (comme déjà le cas pour les épreuves multi-heats) — aucun impact sur
le cache TTL.

## Changements — Backend

### Modèle & accès données

1. `app/models/course.py` : contrainte d'unicité →
   `UniqueConstraint("name", "event_date", "event_type", "is_relay", name="uq_course_identity")`.
2. `app/repositories/course_repository.py` :
   - `get_by_identity(...)` reçoit `is_relay` et ajoute `Course.is_relay == is_relay`
     au filtre.
   - `get_or_create(...)` transmet `is_relay` au lookup (le paramètre existe déjà
     mais est ignoré à la recherche).
3. `app/services/mapping.py` : `get_or_create_course` passe déjà `scraped.is_relay`
   — **aucun changement**.
4. `Participation.is_relay` est **conservé tel quel**. Il devient redondant avec
   `Course.is_relay` mais alimente le badge et évite une migration de données ;
   sa suppression est hors périmètre.

### Scrapers — audit `is_relay` par fournisseur

- **Klikego** — *à corriger* : déduire le relais depuis le slug `heat` dans
  `_parse_search_row` :
  `result.is_relay = "relais" in (heat or "").lower()`.
  Exemples de heats : `triathlon-m-relais`, `duathlon-s---en-relais` (vs
  `triathlon-m-individuel`). Un heat Klikego est mono-discipline → drapeau
  uniforme sur tous les résultats du heat. La classification n'est pas affectée
  (le « s » final de « relais » n'est pas un token de taille isolé).
- **Breizh Chrono / TimePulse / Wiclax** : renseignent déjà `is_relay` —
  **aucun changement**.
- **Fallback Playwright** : reste à `False` par défaut — acceptable.

## Migration

Migration Alembic **de schéma seul** : recréer la contrainte d'unicité avec
`is_relay`, via `op.batch_alter_table` (compatibilité SQLite en dev, recréation
de table). **Pas de split de données.**

Traitement de l'existant : **reset + re-import**.

- Dev : `python scripts/reset_db.py` (vide + migre + seed).
- Prod (Supabase) : `alembic upgrade head` puis re-scrape des épreuves
  concernées.

## Changements — Frontend

1. Helper partagé `formatEventName(name: string, isRelay: boolean): string` dans
   `frontend/lib/` → renvoie `"<name> (Relais)"` quand `isRelay`, sinon `name`.
2. Appliquer ce helper partout où le nom d'épreuve est affiché : `EventList`,
   détail course (`app/courses/[id]`), vues club, `ResultCard`.
   *Hors périmètre : `MapView`* — `GeoEvent` ne porte pas `is_relay`
   (agrégation côté endpoint), la carte reste donc inchangée.
3. Le badge « Relais » existant (`EventList`, `ResultCard`) est conservé.
4. `lib/types.ts` : `is_relay` est déjà présent sur les types concernés —
   **aucun changement**.

## Tests

- `test_repositories/` : `get_or_create` avec une identité ne différant que par
  `is_relay` → deux `Course` distinctes ; `get_by_identity` discrimine sur
  `is_relay`.
- `test_klikego` : heat `duathlon-s---en-relais` → `is_relay True` et
  `event_type == "duathlon-s"` ; heat `triathlon-m-individuel` → `is_relay False`.
- `test_services/` (mapping) : un lot mêlant un résultat solo et un résultat
  relais (même nom/date/type) → deux courses créées.
- Frontend : test unitaire de `formatEventName` ; `EventList` affiche
  « (Relais) » sur la ligne relais.

## Hors périmètre

- Modélisation propre des équipiers d'un relais (noms type « X/Y Prénom1/Prénom2 »).
- Suppression de `Participation.is_relay`.
