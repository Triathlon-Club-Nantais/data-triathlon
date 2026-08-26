# Phase 0 — Research : les 13 questions que l'app ne sait pas montrer

Recherche menée contre l'état réel du code du worktree (2026-08-26), pas
seulement les citations de l'issue #466 qui datent du 20 août et ont
partiellement bougé. Une US par question ; les corrections par rapport à
l'issue sont signalées explicitement.

## US1 — Progression individuelle

- **Decision**: calcul entièrement côté client, aucune extension API.
- **Rationale**: `GET /athletes/{id}` charge déjà `data.participations` en
  entier (`rank_overall`, `course_finishers`, `course.event_date`).
  `rankRatio(p)` (`frontend/lib/utils/ranking.ts:29-42`) est une fonction pure
  appelable par participation — seule `bestRatio(validated)`
  (`athletes/[id]/page.tsx:53`) réduit la série à un scalaire aujourd'hui.
- **Alternatives considered**: exposer une route `/athletes/{id}/progression`
  dédiée — rejetée, la donnée est déjà en mémoire côté client, ce serait un
  aller-retour réseau superflu.

## US2 — Histogramme des temps + repère athlète

- **Decision**: sur le détail de participation, fetch `getCourseSummary` en
  parallèle (même patron que `courses/[id]/page.tsx:60-64`), calculer le
  bucket de l'athlète côté client à partir de `start_sec`/`bucket_sec`.
- **Rationale**: `summary.histogram` (`GET /courses/{id}/summary`,
  `backend/app/schemas/course.py:102-111`) porte déjà tous les buckets ; le
  détail participation ne le charge simplement pas aujourd'hui.
- **Alternatives considered**: exposer le bucket de l'athlète depuis le
  backend (`ParticipationOut.histogram_bucket`) — rejeté, calcul trivial côté
  client une fois `summary` chargé, évite une extension de schéma pour une
  dérivation locale.

## US3 — Classement en catégorie avec dénominateur

- **Decision**: mutualiser le fetch `getCourseSummary` de l'US2 (US2 et US3
  vivent sur le même écran) ; lire `summary.categories`/`categories_total`
  pour l'effectif de la catégorie de l'athlète.
- **Rationale**: `rank_category` est déjà sur `Participation`
  (`backend/app/schemas/participation.py:24`), mais aucun champ d'effectif
  n'est servi par `GET /participations/{id}`. `CourseSummary` le porte déjà.
- **Alternatives considered**: ajouter `category_finishers` à
  `ParticipationOut` sur le modèle de `course_finishers` — rejeté au profit du
  fetch mutualisé avec US2, plus simple (YAGNI, principe VI).

## US4 — Écarts par segment + récurrence

- **Decision**: étendre `ComparisonRow` (`backend/app/schemas/
  participation_stats.py`) avec les écarts en secondes déjà calculés par
  `_comparison` (`participation_stats_service.py:94-96`) ; la récurrence par
  saison s'agrège côté client depuis `participation.splits`, déjà chargé.
- **Rationale**: le service calcule déjà `mine`/`theirs` en secondes avant de
  les réduire en pourcentage pour `ComparisonTable` — extension additive sans
  nouveau calcul.
- **Alternatives considered**: nouveau endpoint dédié aux écarts — rejeté,
  extension additive du schéma existant suffit (principe IV : additif, pas de
  v2 nécessaire).

## US5 — Temps cumulés / allure

- **Decision**: ajouter `cumulative_seconds: int | None` à
  `RankingEvolutionStep` (`backend/app/schemas/participation_stats.py`).
- **Rationale**: `_cumulative_seconds`/`_ranking_evolution`
  (`participation_stats_service.py:107-166`) calculent déjà les secondes
  cumulées pour classer, puis ne gardent que le rang — champ de sortie
  supplémentaire, zéro nouveau calcul.
- **Alternatives considered**: nouveau graphique séparé consommant un nouvel
  endpoint — rejeté, extension additive du schéma existant.

## US6 — Comparaison athlète vs athlète

- **Decision (implémentée)** : recherche via `apiClient.searchAthletes`
  (`GET /athletes/search`, #484, déjà public — la même route que la palette
  ⌘K) plutôt que `listParticipations` filtré, puis `apiClient.getAthlete(id)`
  pour récupérer **toutes** les participations du second athlète en un seul
  appel — exactement le même patron que celui déjà utilisé pour « mes »
  participations sur cette page. Plus simple que filtrer `listParticipations`
  côté client sur un `athlete_id` (paramètre qui, vérification faite,
  n'existe même pas sur `ParticipationFilters` côté frontend).
- **Correction vs. l'issue**: `page_size` de `listParticipations` est
  plafonné à **5000** (`backend/app/api/v1/participations.py`, `le=5000`),
  pas 1000 comme l'énonçait l'issue #466 — corrigé dans `spec.md`, bien que
  cette route ne soit finalement pas celle utilisée par l'implémentation.
- **Alternatives considered**: endpoint dédié `/athletes/{id}/compare/{id2}`
  — rejeté, aucun nouveau contrat API nécessaire, deux appels déjà existants
  suffisent.

## US7 — Répartition disciplines/distances par saison

- **Decision**: calcul côté client depuis `data.participations`, déjà chargé
  en entier sur `/athletes/[id]` (`event_type`/`distance_km`/`event_date` par
  ligne).
- **Correction vs. l'issue**: `listAthleteSeasonActivity`
  (`AthleteSeasonActivity`, `backend/app/schemas/athlete.py:24-35`) ne porte
  **pas** de discipline — seulement un compte de participations par saison —
  et n'alimente que `/club/athletes`, pas la page profil. Piste écartée après
  vérification ; `spec.md` corrigé en conséquence.
- **Alternatives considered**: étendre `AthleteSeasonActivity` avec une
  discipline — rejeté, `data.participations` porte déjà tout le nécessaire.

## US8 — Performance collective par saison

- **Decision**: nouveau graphique consommant `rank_counters` (déjà servi par
  `GET /stats`, `stats_service.py:38-134`), piloté par le `SeasonSelector`
  déjà existant. Aucune extension backend.
- **Rationale**: `MonthlyTrend.tsx` consomme déjà `by_month` mais en volume
  uniquement ; `rank_counters` n'est consommé par aucun graphique de
  performance côté dashboard.

## US9 — Composition du club

- **Decision**: ajouter `category` à `RosterEntry` (`frontend/lib/utils/
  club-aggregate.ts`), agrégé côté client depuis `Participation.category`
  déjà chargé (`gender` y est déjà agrégé, `category` manque).
- **Rationale**: aucune extension API — la donnée est déjà chargée par la
  route consommée par `buildRoster`.
- **Alternatives considered**: réutiliser `GenderDonut.tsx` tel quel pour la
  catégorie — le composant est réutilisable en **pattern** (donut sur
  répartition catégorielle) mais pas en instance directe, ses props sont
  spécifiques au genre.

## US10 — Performance du club par discipline

- **Decision**: étendre l'agrégation client (`club-aggregate.ts`) pour croiser
  `podiumsByScope` (déjà calculé par athlète) avec la discipline dérivée de
  `formatToken`, avant affichage. Aucune extension backend.
- **Rationale**: `podiumsByScope` existe déjà (lignes 94, 118, 126-129) mais
  n'est jamais groupé par discipline — extension d'agrégation, pas de nouveau
  champ API.

## US11 — Couverture temporelle des épreuves

- **Decision (implémentée)** : `monthlyCoverage()` (`frontend/lib/utils/
  coverage.ts`) agrège mois/année côté serveur (page `resultats/page.tsx`),
  à partir d'une boucle de pages sur `GET /courses/events` (`page_size=200`,
  son plafond réel — voir correction ci-dessous). Nouveau composant
  `CoverageTimeline` plutôt que `MonthlyTrend` réutilisé tel quel (voir
  correction). La couverture porte sur **toutes** les épreuves (seul `scope`
  respecté, pas les filtres de recherche ponctuels) : c'est une vue
  d'ensemble qui précède le filtrage, pas un résumé du résultat filtré.
- **Correction vs. la première version de ce document** : `page_size=all`
  n'existe **que** sur `GET /courses/{id}` (classement d'une épreuve unique,
  `backend/app/api/v1/courses.py:138-164`) — `GET /courses/events` (liste des
  épreuves) plafonne `page_size` à **200** (`Query(30, ge=1, le=200)`,
  `courses.py:46`), sans échappatoire « all ». La boucle de pages reste bon
  marché à l'échelle actuelle (~2 requêtes pour 273 épreuves).
- **Correction vs. la première version** : `MonthlyTrend.tsx` ne convient
  **pas** tel quel — il ne montre que les 12 derniers mois glissants
  (`entries.slice(-12)`) et n'affiche jamais un mois à zéro comme un « trou »
  visible (un mois absent de son `byMonth` est simplement omis, pas marqué).
  US11 demande l'historique complet (potentiellement plusieurs années) avec
  les mois sans épreuve **visibles**, pas un résumé glissant. `CoverageTimeline`
  reprend le même style visuel (barres, labels toujours rendus, `role="img"`)
  mais sans le plafond de 12 mois, avec un défilement horizontal propre et un
  marquage visuel distinct (bordure en pointillés) pour les mois à zéro.
- **Alternatives considered**: nouvel endpoint d'agrégat mensuel dédié aux
  épreuves — rejeté pour cette itération, la boucle de pages + agrégation
  serveur suffit à l'échelle de 273 épreuves (pas de pagination lourde à ce
  volume) ; étendre `MonthlyTrend` avec une prop désactivant le plafond de 12
  mois — rejeté, ça aurait changé la sémantique d'un composant déjà utilisé
  ailleurs (dashboard) pour un besoin différent (glissant vs. historique
  complet), plus risqué qu'un composant dédié de 60 lignes.

## US12 — Carte : filtre à venir + distance

- **Decision**: filtre "à venir" par comparaison `event_date` ↔ date du jour,
  et tri/filtre par distance via une formule haversine côté client, à partir
  d'un point de référence statique (commune du club — cf. Assumptions de
  `spec.md`).
- **Rationale**: `lat`/`lon` sont déjà présents sur le type d'événement de
  carte (`frontend/lib/types.ts:171-172`) — aucune donnée manquante, aucun
  appel API supplémentaire.

## US13 — File de validation bénévole

- **Decision**: migration Alembic ajoutant un ou deux timestamps de
  résolution nullable(s) sur `Participation` (`validated_at`/`rejected_at`),
  remplis par le service au moment de la transition d'état ; nouveau
  graphique consommant l'historique pour l'arriéré dans le temps et le délai
  moyen.
- **Rationale**: `is_pending_validation`, `is_rejected`, `created_at` existent
  déjà (`backend/app/models/participation.py:88-99`), mais aucun timestamp de
  résolution — un délai moyen de traitement est **mathématiquement impossible
  à calculer sans cette colonne**. C'est la seule US des 13 qui bloque sans
  changement de schéma DB.
- **Alternatives considered**: dériver un délai approximatif depuis les logs
  d'audit (`#501`, journal admin) — rejeté, hors garantie de couverture (le
  journal ne couvre pas nécessairement 100% des validations) et plus complexe
  que d'ajouter un timestamp au modèle qui porte déjà l'état.

## Synthèse — étendue des changements backend

Une seule extension de **modèle** (US13, migration Alembic), trois extensions
**additives de schéma Pydantic** (US4, US5 sur `participation_stats.py`),
aucune nouvelle route. Tout le reste (US1, US2, US3, US6, US7, US8, US9, US10,
US11, US12) se résout par réutilisation de données déjà servies et
d'agrégation côté client — cohérent avec le principe VI (YAGNI) et le constat
répété de l'audit : « une donnée déjà calculée puis jetée ».
