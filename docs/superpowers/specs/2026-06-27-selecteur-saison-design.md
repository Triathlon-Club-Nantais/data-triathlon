# Sélecteur de saison sur le tableau de bord — design

**Date** : 2026-06-27
**Cible** : `backend/`, `frontend/`
**Statut** : proposé, en attente de validation (issue [#7](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/7))
**Branche cible** : `claude/issue-7-specification-f1db8t` → PR Draft vers `main`

## Contexte & problème

Sur le tableau de bord (écran d'accueil, `frontend/app/dashboard/page.tsx`), le
titre **« Saison 2025 — 2026 » est codé en dur** (`page.tsx:45`) et **aucune
donnée n'est filtrée par saison**. Les trois appels servant la page agrègent la
**totalité** de l'historique, toutes saisons confondues :

```ts
// frontend/app/dashboard/page.tsx:27-31
apiServer.getStats(club)                          // dossards, athlètes, by_type, récents
apiServer.listEvents({ club, page_size: 200 })    // épreuves préférées
apiServer.listParticipations({ club, page_size: 5000 })  // victoires / podiums / top 10
```

L'issue #7 demande :

1. Arriver **par défaut sur la saison en cours**.
2. Pouvoir **sélectionner une ou plusieurs autres saisons**, **uniquement parmi
   celles qui ont des résultats**.

**Définition de saison** (commentaire de l'issue, Vinzzou) : du **1ᵉʳ septembre
au 31 août**. Une saison débutant en septembre `Y` couvre donc
`[Y-09-01, (Y+1)-08-31]` et s'affiche « Saison `Y` — `Y+1` ».

### État du filtrage existant

- **Épreuves** (`/courses/events`, `participation_repository._grouped_events_query`)
  acceptent déjà `date_from` / `date_to` (`participation_repository.py:181-203`).
- **Stats** (`/stats` → `stats_service.get_stats` → `participation_repository.for_stats`,
  `participation_repository.py:162-171`) **n'acceptent aucun filtre de date** :
  c'est le principal manque côté backend.
- **Aucune notion de « saison »** n'existe nulle part (ni modèle, ni service, ni
  front). `Course.event_date` (`models/course.py:21`, `date | None`) est la seule
  donnée temporelle.

### Pourquoi un simple `date_from`/`date_to` ne suffit pas

L'issue autorise la sélection de **plusieurs** saisons, potentiellement **non
contiguës** (ex. 2023-24 **et** 2025-26 sans 2024-25). Une plage unique
`date_from`/`date_to` engloberait la saison intermédiaire. Il faut donc un filtre
exprimé comme une **liste de saisons** (OU de plages), pas une plage unique.

## Décisions actées

| Décision | Choix |
|----------|-------|
| Identifiant de saison | L'**année de début** `Y` (entier). Saison `Y` = `[Y-09-01, (Y+1)-08-31]`. Libellé « Saison `Y` — `Y+1` ». |
| Bascule de saison | `season_of(d)` = `d.year` si `d.month >= 9`, sinon `d.year - 1`. Bornes incluses : 31 août → saison `Y-1`, 1ᵉʳ sept → saison `Y`. |
| Sélection multiple | Filtre **liste** `seasons` (années de début, ex. `2025,2023`) propagé de bout en bout. Plusieurs saisons → **OU** de plages de dates. |
| Défaut | Aucun paramètre `seasons` → **saison en cours uniquement** (calculée depuis `app/core/time.now()` côté serveur). |
| Options du sélecteur | Saisons **ayant des résultats** (≥ 1 participation sur une épreuve datée), **plus** la saison en cours toujours présente (même à 0 résultat, pour matérialiser le défaut). |
| Épreuves sans date | `Course.event_date IS NULL` → **non rattachables** à une saison : exclues de toute vue filtrée par saison et d'aucun décompte de saison. Documenté comme limite. |
| Source de vérité de l'UI | L'URL (`?seasons=2025,2023`), à l'image du filtrage `date_from`/`date_to` de `ResultsFilters`. La page dashboard reste un Server Component. |

## Périmètre — backend (`backend/`)

### 1. Helpers de saison — `app/core/season.py` (nouveau)

Module pur (aucune dépendance DB), testable isolément :

- `season_of(d: date) -> int` — année de début de la saison contenant `d`.
- `season_bounds(start_year: int) -> tuple[date, date]` — `(Y-09-01, (Y+1)-08-31)`.
- `current_season() -> int` — `season_of(app.core.time.now().date())` (réutilise
  l'horloge centralisée `app/core/time.py`, pas `date.today()` direct, pour
  rester testable/figeable).
- `season_label(start_year: int) -> str` — `"Saison {Y} — {Y+1}"`.
- `parse_seasons(raw: str | None) -> list[int]` — parse `"2025,2023"` → `[2025, 2023]`
  (tolère espaces, ignore les valeurs non entières, dédoublonne).

### 2. Filtrage par saisons dans le repository

`app/repositories/participation_repository.py` :

- **`_apply_filters(...)`** (`:64-97`) — ajouter un paramètre
  `seasons: list[int] | None`. S'il est fourni, ajouter une clause
  `or_(*[and_(Course.event_date >= start, Course.event_date <= end) for (start, end) in bounds])`
  (les `bounds` issus de `season_bounds`). Combiné en `AND` avec les filtres
  existants. `event_date IS NULL` est naturellement exclu par la comparaison.
- Propager `seasons` dans `_grouped_events_query`, `events_with_counts`,
  `events_page` (et donc `/courses/events` et la carte géo) — gratuit une fois
  `_apply_filters` étendu.
- **`for_stats(...)`** (`:162-171`) — ajouter `seasons: list[int] | None` et
  appliquer la même clause OU-de-plages sur `Course.event_date` (jointure déjà
  présente via `joinedload`; ajouter un `.join(Course)` filtrant si nécessaire).
- **`distinct_seasons(db, club=None) -> list[dict]`** (nouveau) — saisons
  présentes : requête des `Course.event_date` non nulles ayant ≥ 1 participation
  (filtrées club optionnel), repliées en Python via `season_of` en
  `[{start_year, event_count, participation_count}]`. Repli Python (et non SQL)
  pour rester portable SQLite/Postgres sans fonctions de date spécifiques. Le
  volume de données reste modeste.

### 3. Service — `app/services/stats_service.py`

- `get_stats(db, club=None, seasons=None)` (`:12`) — passer `seasons` à
  `for_stats`. Le reste de l'agrégation (`by_type`, `by_month`, `recent`,
  compteurs) est inchangé : il opère sur le sous-ensemble déjà filtré.
- `list_seasons(db, club=None) -> list[dict]` (nouveau) — appelle
  `distinct_seasons`, garantit la présence de la **saison en cours**
  (`current_season()`, à 0 si absente), trie par `start_year` **décroissant**,
  enrichit chaque entrée de `label` et `is_current`.

### 4. API — `app/api/v1/`

- **`stats.py`** :
  - `GET /stats` (`:12`) — nouveau query param `seasons: str | None`
    (CSV d'années) → `season.parse_seasons` → `stats_service.get_stats(..., seasons=...)`.
  - `GET /stats/seasons` (nouveau) — `club: str | None` → `list_seasons` →
    `list[SeasonOut]`. Sert le sélecteur.
- **`courses.py`** : `GET /courses/events` (`:26`) — ajouter `seasons: str | None`,
  parser et passer à `stats_service.list_events`. (`date_from`/`date_to`
  conservés et cumulables.)
- **`participations.py`** : l'endpoint listant les participations (utilisé par le
  dashboard pour victoires/podiums/top 10) — ajouter `seasons: str | None` et le
  propager jusqu'au repository.

### 5. Schémas — `app/schemas/`

- `SeasonOut` (nouveau, `schemas/stats.py` ou `schemas/season.py`) :
  `start_year: int`, `label: str`, `event_count: int`,
  `participation_count: int`, `is_current: bool`.
- Formes de réponse de `/stats`, `/courses/events`, `/participations`
  **inchangées** (seul le sous-ensemble filtré change).

### 6. Migration Alembic

**Aucune** : aucune colonne ajoutée. La saison est dérivée de `Course.event_date`.

## Périmètre — frontend (`frontend/`)

### 7. Utilitaires — `lib/utils/season.ts` (nouveau)

Miroir des helpers backend, pour le défaut et l'affichage côté client :
`currentSeason()`, `seasonOf(iso: string)`, `seasonLabel(y)`,
`parseSeasonsParam(raw?: string): number[]`, `serializeSeasons(years: number[]): string`.

### 8. Types & client API

- `lib/types.ts` : ajouter `seasons?: number[]` à `ParticipationFilters`
  (`:146-157`) ; ajouter le type `Season` (miroir de `SeasonOut`).
- `lib/api/client.ts` + `lib/api/server.ts` :
  - `toQuery()` (`client.ts:29-36`) — sérialiser `seasons` en CSV (`"2025,2023"`).
  - `listSeasons(club?)` (nouveau) → `GET /stats/seasons` → `Season[]`.
  - `getStats`, `listEvents`, `listParticipations` — accepter/propager `seasons`.

### 9. Sélecteur — `components/dashboard/SeasonSelector.tsx` (nouveau, client)

- Reçoit la liste des saisons disponibles (`Season[]`) et la sélection courante
  (depuis l'URL).
- **Multi-sélection** (« une ou plusieurs ») : popover + liste de cases à cocher
  (réutiliser `components/ui/select.tsx` en mode multiple, ou un `Popover` +
  `Command`/checkbox déjà présents dans `components/ui/`). Saison en cours
  pré-cochée par défaut.
- Affiche des **chips** des saisons sélectionnées (réutiliser `components/ui/badge.tsx`,
  motif des chips actives de `ResultsFilters.tsx:65-75`).
- À chaque changement : `router.push` en mettant à jour `?seasons=` (en
  préservant `scope`), à l'image de `ResultsFilters`. Désélection totale →
  retour implicite à la saison en cours (paramètre retiré).

### 10. Page dashboard — `app/dashboard/page.tsx`

- Lire `sp.seasons` ; calculer `selected = parseSeasonsParam(sp.seasons)` ;
  si vide → `[currentSeason()]`.
- Récupérer en parallèle `apiServer.listSeasons(club)` pour alimenter le
  sélecteur.
- Propager `seasons: selected` aux trois appels existants (`getStats`,
  `listEvents`, `listParticipations`).
- Remplacer le titre **codé en dur** (`:45`) par un libellé dynamique :
  1 saison → « Saison `Y` — `Y+1` » ; plusieurs → ex. « `N` saisons
  sélectionnées » (ou liste compacte des libellés).
- Insérer `<SeasonSelector>` dans l'en-tête, à côté de `<ScopeToggle>`.

## Vérification (critères de succès)

- **Backend** (`cd backend`) :
  - `pytest -m "not integration"` vert, **+ nouveaux tests** :
    - `season_of` aux bornes (31 août `Y` → `Y-1` ; 1ᵉʳ sept `Y` → `Y`),
      `season_bounds`, `current_season` (horloge figée).
    - `distinct_seasons` / `list_seasons` : saisons présentes + présence forcée
      de la saison en cours + tri décroissant.
    - `/stats?seasons=...`, `/courses/events?seasons=...` : filtrage correct,
      multi-saisons non contiguës, épreuves sans date exclues.
  - `ruff check .` propre.
- **Frontend** (`cd frontend`) :
  - `npm test` (Vitest) vert, **+ tests** des utilitaires `season.ts` (bornes,
    parse/serialize) et du `SeasonSelector` (défaut saison en cours, sync URL).
  - `npm run build` OK (TS strict + RSC).
  - `npm run lint` propre.
- **Manuel** : dashboard sans paramètre → saison en cours ; sélection d'une autre
  saison → cartes/disciplines/épreuves/podiums recalculés ; sélection de deux
  saisons non contiguës → union correcte ; seules les saisons avec résultats (+
  la courante) apparaissent dans le sélecteur.

## Hors périmètre

- Sélecteur de saison sur les **autres écrans** (résultats, club, athlète,
  carte). L'issue ne vise que l'accueil ; l'infrastructure backend (`seasons`)
  étant générique, ces écrans pourront le réutiliser ultérieurement.
- **Rattachement des épreuves sans `event_date`** à une saison (saisie manuelle /
  imports incomplets) : elles restent hors saison. Une amélioration future
  pourrait imposer/inférer une date.
- Persistance d'une préférence de saison par utilisateur (l'état vit dans l'URL).

## Notes

- La saison en cours au 2026-06-27 a pour année de début **2025** (1ᵉʳ sept 2025 →
  31 août 2026), ce qui **coïncide** avec le libellé « Saison 2025 — 2026 »
  aujourd'hui codé en dur — la bascule vers le calcul dynamique est donc neutre
  visuellement à date.
- Helpers dupliqués backend (`core/season.py`) / frontend (`utils/season.ts`) :
  duplication assumée et minime, cohérente avec l'architecture (le front ne
  partage pas de code Python). Les deux sont couverts par des tests de bornes
  pour éviter toute dérive.
- Filtre `seasons` exprimé en **CSV d'années de début** dans l'URL et les query
  params : compact, lisible, et aligné sur le style des filtres existants.
