# Phase 0 — Research

Aucun `[NEEDS CLARIFICATION]` ne subsistait à l'issue de `/speckit-specify` :
le cadrage de l'issue #274 avait déjà tranché les points ouverts. Cette phase
documente les décisions techniques prises en lisant le code existant plutôt
que des inconnues à défricher.

## Décision : agrégat en lecture, pas de nouvelle table

**Choix** : la donnée « nombre d'épreuves par athlète sur une saison » est
calculée à la volée par une requête groupée (`JOIN Athlete → Participation →
Course`, filtrée saison + club, `GROUP BY Athlete.id`), jamais stockée.

**Rationale** : `athlete_repository.search_admin()` fait déjà exactement ce
calcul (join + `func.count(Participation.id)` + `group_by`) pour un besoin
voisin (recherche admin avec compteur de participations, `backend/app/repositories/athlete_repository.py`).
Le volume — dizaines d'athlètes actifs par saison — ne justifie aucune
matérialisation ni cache dédié.

**Alternative rejetée** : une colonne dénormalisée `participation_count` sur
`Athlete`, mise à jour à l'import. Rejetée : elle introduirait un état à
resynchroniser à chaque scrape/fusion/suppression (cf. `delete_orphans`,
`rescrape_service`), pour un gain de performance non mesuré sur un volume de
cet ordre — violerait le Principe VI (YAGNI).

## Décision : filtre saison réutilise `core/season.py` tel quel

**Choix** : le nouvel endpoint accepte `seasons=` (CSV d'années de début),
parsé par `parse_seasons()` existant, et filtre via le même motif que
`participation_repository._season_clause()` (`Course.event_date` entre les
bornes de `season_bounds(year)`).

**Rationale** : c'est la définition de saison exacte demandée dans l'issue
(1er septembre → 31 août), déjà implémentée, testée et utilisée par
`/stats`, `/stats/seasons`, `/participations`. La réimplémenter serait un
doublon interdit par le Principe II.

**Alternative rejetée** : nouvelle notion de « saison active » côté front
uniquement (calcul de bornes en JS). Rejetée : dupliquerait une règle métier
déjà centralisée, avec un risque de divergence (le péché originel de #76 sur
le critère club, rejoué sur le critère saison).

## Décision : filtre club réutilise `tcn_clause(Participation.club)`

**Choix** : comme `_apply_filters()` (`participation_repository.py`), le
filtre club porte sur `Participation.club` (le club **au moment de la
course**), pas sur `Athlete.club` (le club **actuel** affiché sur la fiche).

**Rationale** : c'est le filtre déjà utilisé par tous les agrégats de saison
existants (`for_stats`, `distinct_seasons`, `events_page`) — l'incohérence
entre deux définitions de « membre du club » sur deux endpoints voisins serait
elle-même un bug du type #76.

## Décision : tri géré côté client, pas de paramètre serveur

**Choix** : l'endpoint rend une liste triée par défaut (`nom`, `prenom`,
comme `search`/`search_admin`) ; le tri par nombre d'épreuves ou par nom de
famille est recalculé en mémoire côté client sur la liste déjà chargée en
entier.

**Rationale** : c'est exactement le précédent documenté dans
`frontend/AGENTS.md` pour `RankTypeToggle` (`?rank=`) — *aucun rendu serveur
ne lit ce paramètre*, donc `pushState` + recalcul en mémoire, sans aller-retour
réseau. La page ne pagine pas (cf. Assomptions du spec), donc la liste entière
est déjà en mémoire au moment du tri.

**Alternative rejetée** : paramètre `sort=` sur l'endpoint, lu par le rendu
serveur (comme `?scope`/`?seasons`). Rejetée : un aller-retour réseau pour
re-trier une liste déjà entièrement chargée est un coût sans bénéfice, et
introduirait un paramètre transverse de plus à documenter (Principe VI).

## Décision : nouvel endpoint additif, pas d'extension de `GET /athletes`

**Choix** : `GET /athletes/season-activity` est une route dédiée, distincte
de `GET /athletes` (recherche paginée par nom, consommée par
`AthleteSearchPicker`/`AthletePicker` en admin).

**Rationale** : les deux besoins divergent structurellement — `GET /athletes`
pagine et cherche par nom sans notion de saison ; le nouvel endpoint groupe
par saison/club et ne pagine pas. Les fusionner sous un seul endpoint
conditionnel (`if seasons: ...`) aurait introduit une branche de comportement
dans une route consommée par des écrans admin sans lien avec cette feature —
le contraire de la séparation des responsabilités (Principe II, VI).

## Décision : page `/club/athletes`, entrée de nav dans la section « Club »

**Choix** : la page vit sous `/club/athletes`, avec une entrée ajoutée dans
`nav.config.ts` (section `club`, déjà porteuse d'un item `vueclub` similaire).

**Rationale** : l'issue demande une page « distincte de `/club` », pas hors
du regroupement thématique club. `nav.config.ts` est la description unique de
la navigation (`frontend/AGENTS.md`) — ajouter une destination y tient en une
ligne, sans toucher `AppNav`.
