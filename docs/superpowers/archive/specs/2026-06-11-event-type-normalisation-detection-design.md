# Normalisation des `event_type` & détection de disciplines mono-sport

**Date** : 2026-06-11
**Cible** : `backend-v2/` (+ `frontend-v2/`)
**Statut** : spec validée, plan à rédiger

## Contexte & problème

Le graphe « Répartition par discipline » (dashboard, vue club) affiche des
disciplines qui paraissent **identiques** et d'autres **sans taille/catégorie**.
Diagnostic confirmé sur la base de dev :

```
triathlon-m : 3      ← slug normalisé
Triathlon M : 1      ← MÊME discipline, écriture différente  ⚠️ doublon
triathlon   : 4      ← sans taille (fallback de détection)
duathlon    : 2      ← sans taille
aquathlon   : 4
triathlon-s : 2
triathlon-l : 1
```

Deux causes racines :

1. **Doublons « identiques »** — le graphe groupe sur la chaîne brute
   `course.event_type` exacte (`stats_service.py:24-25`). Deux écritures de la
   même discipline (`triathlon-m` vs `Triathlon M`) forment deux groupes. La
   valeur `Triathlon M` vient d'une épreuve sans `source_url` (saisie manuelle /
   test) qui n'est **pas passée par la normalisation en slug**.
2. **Disciplines sans taille** — chaque scraper a **sa propre**
   `_detect_event_type` (5 implémentations divergentes : klikego, timepulse,
   wiclax, prolivesport, sportinnovation). Quand le nom d'épreuve ne contient
   aucun mot-clé de distance reconnu, toutes retombent sur le sport nu
   (`return "triathlon"`). De plus le slug nu `triathlon` n'existe pas dans
   `EVENT_TYPE_LABELS` (`frontend-v2/lib/constants.ts`) → il s'affiche en brut.

Besoin complémentaire : gérer des disciplines **mono-sport** aujourd'hui
absentes (course à pied, trail, cyclisme), aujourd'hui mal classées en
`triathlon` nu.

## Objectifs

- **Une seule source de vérité** pour la classification des disciplines.
- Normaliser tous les `event_type` vers une forme canonique (slug minuscule).
- Améliorer la détection des distances triathlon/duathlon.
- Ajouter les disciplines **course à pied**, **trail**, **cyclisme**.
- Introduire un kilométrage `distance_km` sans re-fragmenter la liste des
  disciplines.
- Corriger l'existant en base (normalisation + re-détection, sans réseau).

Hors périmètre : re-scraping réseau, refonte du modèle de splits, sports non
demandés (marche nordique, VTT, etc.).

## Approche retenue

**Approche A — classifieur unique partagé.** Un module
`app/scrapers/classify.py` concentre toute la logique. Les 5
`_detect_event_type` par scraper deviennent des délégations. La migration
réutilise les mêmes fonctions. C'est la seule approche qui élimine la divergence
des heuristiques (cause n°1) à la racine — déjà signalé dans `registry.py:10`.

## Taxonomie canonique

Forme unique : **minuscules, tirets**, sport en base + suffixe de taille
optionnel. Le kilométrage exact n'entre **jamais** dans le slug (il vit dans
`distance_km`).

| Famille | Slugs |
|---|---|
| Triathlon | `triathlon`, `triathlon-s`, `triathlon-m`, `triathlon-l`, `triathlon-xl` |
| Duathlon | `duathlon`, `duathlon-xs`, `duathlon-s`, `duathlon-m`, `duathlon-l` |
| SwimRun | `swimrun`, `swimrun-s`, `swimrun-m`, `swimrun-l` |
| Aquathlon | `aquathlon` |
| Aquarun | `aquarun` |
| Bike & Run | `bike-run` |
| **Course à pied** *(nouv.)* | `course-a-pied`, `course-a-pied-5k`, `course-a-pied-10k`, `course-a-pied-semi`, `course-a-pied-marathon` |
| **Trail** *(nouv.)* | `trail` *(distance via `distance_km`)* |
| **Cyclisme** *(nouv.)* | `cyclisme`, `cyclisme-route`, `cyclisme-clm` *(distance via `distance_km`)* |

Choix de granularité :
- **Course à pied** : formats nommés (distances canoniques de la route).
- **Trail** : un seul slug `trail` (pas de S/M/L) ; les trails ont des distances
  hétérogènes → `distance_km` est la bonne dimension.
- **Cyclisme** : distinction `route` / `clm` (contre-la-montre) + `distance_km`.

## Modèle de données

Nouveau champ sur `Course` :

```python
distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
```

- N'entre **pas** dans la clé d'unicité `(name, event_date, event_type)`.
- Renseigné de façon opportuniste quand un kilométrage est extractible du texte
  (surtout utile pour trail/cyclisme ; optionnel ailleurs).

`ScrapedResult` (`app/scrapers/base.py`) gagne `distance_km: float | None = None`.

## Composants

### `app/scrapers/classify.py` (nouveau) — source de vérité

Fonctions publiques :

- `classify_event_type(text: str) -> str` — prend n'importe quel texte (nom
  d'épreuve, `heat + " " + slug` Klikego, `p_attr` Wiclax…) et renvoie un slug
  canonique de la taxonomie.
- `normalize_event_type(value: str) -> str` — canonicalise une valeur existante.
  Implémenté comme `classify_event_type` appliqué à la chaîne stockée :
  `"Triathlon M"` → `triathlon-m` ; un slug déjà propre (`triathlon-l`) reste
  lui-même (**idempotent**).
- `extract_distance_km(text: str) -> float | None` — regex `nombre + km/k`
  (`23 km`, `23km`, `42,2 km`, `42.2 km`). Renvoie `None` si absent.

**Ordre de détection** (du plus spécifique au plus générique — critique pour
éviter les faux positifs) :

1. Multisports composites d'abord (sous-mots piégeux) :
   `swimrun` → `bike-run` → `aquathlon` → `aquarun` → `duathlon` (+ taille).
2. **Mono-sports nouveaux, AVANT les distances triathlon génériques** :
   - `trail` ;
   - course à pied : `marathon` / `semi` / `half` / `10 km`/`10k` / `5 km`/`5k`
     / `course sur route` / `course à pied` / `running` ;
   - `cyclisme` : `cyclo` / `contre-la-montre` / `clm` / `route` → `cyclisme-route`
     ou `cyclisme-clm`.
3. Distances triathlon (XL/L/M/S) en dernier, avec les contrôles de frontière de
   segment existants (`-m-`, fin `-l`, `_seg()`…).
4. Repli : `triathlon` nu (comportement historique conservé).

Le classifieur **fusionne** les deux familles d'heuristiques aujourd'hui
éparpillées : frontières de slug (style Klikego) + mots-clés de nom humain
(style TimePulse), afin que `test_klikego.py` / `test_timepulse.py` restent
verts.

### Intégration scrapers

Les `_detect_event_type` de `klikego.py`, `timepulse.py`, `wiclax.py`,
`prolivesport.py`, `sportinnovation.py` deviennent des délégations d'une ligne
vers `classify_event_type`, en passant leur texte source. Chaque scraper
renseigne aussi `distance_km` via `extract_distance_km` sur le même texte.

### `app/services/mapping.py`

- `_SPLIT_KEYS_BY_SPORT` : ajout de `course-a-pied` → `{run}`, `trail` →
  `{run}`, `cyclisme` → `{bike}`.
- `_sport_base` : généraliser le cas spécial `bike-run` à un ensemble de bases
  multi-mots (`bike-run`, `course-a-pied`) pour que
  `_sport_base("course-a-pied-10k")` renvoie `course-a-pied` (et non `course`).
- `get_or_create_course` : transmettre `scraped.distance_km` à `Course`.

### Migration Alembic (schéma + données)

Une révision qui :

1. **Schéma** : `ADD COLUMN distance_km FLOAT NULL` sur `courses`.
2. **Données** : logique extraite dans une fonction testable
   `reclassify_existing(session)` (dans `app/services/` ou un module dédié),
   **importée** par le fichier Alembic — pas de logique métier noyée dans la
   migration. Pour chaque course :
   - `event_type ← normalize_event_type(event_type)` ;
   - si le résultat est un sport nu reclassable, tenter
     `classify_event_type(course.name)` et prendre le plus spécifique de la même
     famille ;
   - `distance_km ← extract_distance_km(course.name)` si vide.
   - Pas de réseau. **Idempotent** (re-jouable sans dégât).

### Frontend (`frontend-v2/`)

- `lib/constants.ts` : compléter `EVENT_TYPE_LABELS` — **ajouter les slugs nus
  `triathlon` / `duathlon` / `swimrun`** (corrige l'affichage brut) + tous les
  nouveaux slugs (`course-a-pied*`, `trail`, `cyclisme*`).
- Helper `disciplineLabel(course)` = libellé + ` 23 km` si `distance_km` présent.
  Utilisé partout où la discipline est affichée.
- `lib/sport-colors.ts` : `trail` / `course-a-pied` → couleur *run* ;
  `cyclisme*` → couleur *bike*.
- `lib/types.ts` : ajouter `distance_km?: number | null` à `Course`.
- `ManualResultForm` récupère les nouvelles options automatiquement (via
  `EVENT_TYPE_OPTIONS`).

## Tests

- **`test_classify.py`** (nouveau, backend) : taxonomie complète ; ordre de
  détection (anti-faux-positifs : `Marathon de Nantes` → `course-a-pied-marathon`
  et non triathlon ; `Trail du Mont … L` → `trail` et non `triathlon-l`) ;
  idempotence de `normalize_event_type` ; extraction `distance_km`.
- **`test_klikego.py` / `test_timepulse.py`** : restent verts (délégation) ;
  assertions ajustées seulement si un cas change réellement.
- **`reclassify_existing`** : test de service sur une base seedée avec données
  sales (`Triathlon M`, `triathlon` nu, trail sans type) → vérifie normalisation
  + reclassement + backfill `distance_km`.
- **Front (Vitest)** : `disciplineLabel` (avec/sans km) + présence des libellés
  des nouveaux slugs et des slugs nus.

## Critères de réussite

- Plus aucune paire « identique » dans le graphe (toutes les valeurs sont des
  slugs canoniques).
- Les slugs nus s'affichent avec un libellé propre (« Triathlon », « Duathlon »).
- Course à pied, trail et cyclisme sont détectés et classés correctement.
- `distance_km` affiché à côté de la discipline quand disponible.
- Migration appliquée : l'existant est normalisé et re-classé sans perte.
- Suite de tests verte (backend + front).
