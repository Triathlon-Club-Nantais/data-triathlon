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

- **Decision**: nouveau composant de sélection + comparaison, en s'appuyant
  sur `apiClient.listParticipations` existant.
- **Correction vs. l'issue**: `page_size` est plafonné à **5000**
  (`backend/app/api/v1/participations.py`, `le=5000`), pas 1000 comme
  l'énonçait l'issue #466 — corrigé dans `spec.md`.
- **Alternatives considered**: endpoint dédié `/athletes/{id}/compare/{id2}`
  — rejeté pour cette itération, `listParticipations` filtré côté client sur
  une épreuve commune suffit sans nouveau contrat API.

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

- **Decision**: réutiliser la liste d'épreuves déjà exposée par l'API
  (`page_size=all`, exception contractuelle documentée dans `AGENTS.md` /
  Principe IV) et agréger mois/année côté client à partir de
  `course.event_date`, en réutilisant `MonthlyTrend.tsx` (existant dans
  `components/charts/`, non utilisé aujourd'hui sur `/resultats`).
- **Rationale**: `GET /stats` (`rank_counters`/`by_month`) est scopé au club
  et aux participations, pas à l'ensemble des 273 épreuves tous fournisseurs
  confondus qu'affiche `/resultats` — il faut une agrégation par `Course`, pas
  par `Participation`. La liste d'épreuves existante porte déjà `event_date`.
- **Alternatives considered**: nouvel endpoint d'agrégat mensuel dédié aux
  épreuves — rejeté pour cette itération, `page_size=all` + agrégation client
  suffit à l'échelle de 273 épreuves (pas de pagination lourde à ce volume).

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
