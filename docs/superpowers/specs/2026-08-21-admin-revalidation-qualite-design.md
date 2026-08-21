# Écran de revalidation qualité — design

**Issue** : #119 (sous-issue de l'épique #81, Panel Admin)
**Date** : 2026-08-21
**Voie** : Superpowers (brainstorming → writing-plans → exécution)

## Le problème

L'indice de fiabilité (`services/quality.py`) relève les anomalies d'une épreuve
à l'import et les range dans `Course.quality_issues`. Rien ne les **montre** :
une épreuve douteuse le reste jusqu'à ce que quelqu'un tombe dessus par hasard
depuis le catalogue. Il manque l'écran qui les rassemble et le geste qui les
sort de la file.

## Ce que l'issue demandait à tort

L'issue #119 a été rédigée avant #115, #117 et #118. Trois de ses demandes sont
périmées, et le recadrage est publié en commentaire de l'issue :

- **`to_review` n'existe pas.** #48 ne l'a jamais livré et la refonte des sources
  d'URL a emporté le reste. La file se réduit à `is_reliable = false`.
- **`POST /admin/courses/{id}/quality/clear` ferait doublon** avec
  `PATCH /admin/courses/{id}/reliability`, livré par #115, qui pose et lève déjà
  l'avis humain sous le pouvoir `quality:override`.
- **`GET /admin/quality-queue` ferait doublon** avec `GET /courses` et
  `GET /courses/count`, qui paginent, trient par date décroissante et exposent
  déjà `is_reliable` et `quality_issues` dans `CourseBrief`.

Conséquence hors périmètre, à noter : **#79** (dossard orphelin Vertou) dépendait
de `to_review` et reste donc à re-spécifier sur une autre base.

## Ce qui existe déjà et qu'on réutilise

| Brique | Emplacement |
| --- | --- |
| `Course.is_reliable` = `coalesce(reliability_override, is_reliable_computed)`, avec son `@expression` SQL | `models/course.py` |
| `PATCH /api/v1/admin/courses/{id}/reliability`, gardé par `quality:override` | `api/v1/admin.py` |
| `course_review.set_override()` | `services/course_review.py` |
| Filtres, pagination et comptage du catalogue | `repositories/course_repository.py` (`_filtered`, `list_all`, `count_all`) |
| Libellés français des 6 codes d'anomalie | `frontend/lib/quality.ts` (`describeQualityIssues`) |
| Correction d'une épreuve | `components/admin/EditCourseDialog.tsx` |
| Re-scrape avec progression SSE | `hooks/useRescrapeStream.ts` |
| Entrée de navigation déclarée (`soon`) avec son pouvoir | `components/layout/nav.config.ts` (`a-quality`) |
| Journal des gestes administratifs | `models/admin_action_log.py`, `repositories/admin_action_log_repository.py` |

## Architecture

Quatre unités, chacune indépendante des autres.

### 1. Le filtre de fiabilité (backend)

`course_repository._filtered()` reçoit `unreliable: bool = False`. Quand il est
vrai : `q.filter(Course.is_reliable == False)`. L'`@expression` du `coalesce`
fait tout le travail — aucune branche Python, aucune seconde chaîne de filtres.

Trois conséquences voulues de cette écriture :

- **`NULL` sort de la file.** « Jamais évaluée » n'est pas « douteuse » ;
  l'y inclure y ferait tomber toute la base antérieure à l'indice.
- **Une épreuve qu'un humain a déclarée douteuse reste dans la file.** C'est du
  travail en attente, pas une décision close.
- **L'avis humain favorable la sort**, sans recalcul ni écriture sur
  `is_reliable_computed`.

Le paramètre remonte sur `GET /courses` et `GET /courses/count`, optionnel et
faux par défaut : **aucun appelant existant ne change de réponse**, l'ajout est
additif et ne touche donc pas au contrat v1 (Principe IV). Il n'expose rien de
neuf non plus — `CourseBrief` rend `is_reliable` et `quality_issues` sur ces
routes publiques depuis leur origine.

### 2. La trace du verdict (backend, AC3)

Aujourd'hui le `PATCH reliability` n'écrit **rien** dans `admin_action_log` :
c'est le seul manque backend réel de l'issue.

`course_review.set_override()` reçoit `user_id: int` et `notes: str | None`, et
journalise par `admin_action_log_repository`, en respectant les trois règles du
contrat commun d'`admin_actions.py` :

1. aucune `Session` touchée directement — tout passe par un repository ;
2. `flush`, jamais `commit` — la route clôt la transaction, ce qui rend le geste
   et sa trace indissociables ;
3. **le journal n'enregistre que ce qui a changé** — reposer le verdict déjà en
   place n'est pas un geste, et n'écrit pas de ligne.

Forme de la trace : `action="course.reliability"`, `entity_type="course"`,
payload `{avant, après, calculé, notes}`. Les trois valeurs, parce qu'elles ne se
déduisent pas l'une de l'autre — c'est déjà l'argument de la route pour sa
réponse.

`CourseReliabilityUpdate` gagne `notes: str | None`, borné en longueur : la route
est authentifiée, mais un champ texte libre écrit en base se borne.

### 3. L'écran `/admin/quality` (front)

Un composant dédié, `QualityQueueTable`, et **non** un mode de
`CoursesAdminTable` : celle-ci fait déjà 446 lignes, et ses colonnes comme ses
actions sont autres. Deux personnalités dans un composant, c'est une branche par
ligne de rendu et un test par branche.

Ce qu'il rend, par ligne : l'épreuve, sa date, et ses anomalies décodées par
`describeQualityIssues`.

Pas de colonne « Verdict » — retirée en cours de route, et c'est délibéré. La
file n'est par construction que l'ensemble `is_reliable === false` : une
colonne calquée dessus afficherait la même valeur sur chaque ligne. Distinguer
le calculé de l'humain demanderait `is_reliable_computed` et
`reliability_override`, que `CourseBrief` ne porte pas — seule
`CourseReliability`, la réponse du `PATCH`, les porte, et l'élargir au contrat
de lecture publique est un changement de schéma qu'on n'a pas fait pour un
affichage de liste.

**Limite assumée qui en découle** : la file, telle qu'elle est aujourd'hui, ne
distingue pas une épreuve qu'un humain a déjà tranchée « douteuse » d'une
épreuve jamais examinée — les deux y apparaissent de façon identique. Et une
épreuve ainsi tranchée y reste **définitivement** : aucun re-scrape ne la fait
sortir de `is_reliable === false`, seul le geste « Revenir à l'avis calculé »
le peut. Le jour où cette distinction compte, elle se rétablit côté écran sans
toucher au contrat public de `GET /courses` : la route de détail —
`PATCH /admin/courses/{id}/reliability`, qui rend `CourseReliability` — porte
déjà les trois valeurs, il n'y a qu'à les afficher.

Les gestes, chacun masqué si le pouvoir manque (le serveur reste seul juge, ces
tests évitent d'offrir un bouton qui rendrait 403) :

- « Marquer OK » → `reliability_override = true`
- « Marquer douteuse » → `false`
- « Revenir à l'avis calculé » → `null`
- « Re-scraper » (#118) et « Éditer » (#117), par réutilisation directe

Les trois gestes de verdict passent par un même dialogue de confirmation qui
porte le champ **notes**. Après succès, l'invalidation de la requête suffit à
faire sortir la ligne de la file (AC4) : rien à retirer à la main.

**Filtres** : nom et dates dans l'URL, comme le catalogue admin — une page reste
partageable et compatible avec le bouton Retour. Le filtre **par code
d'anomalie** agit côté client sur les lignes de la page : `quality_issues` est
une colonne JSON, et la filtrer en SQL divergerait entre SQLite (dev) et
PostgreSQL (prod). Limite assumée : il affine la page courante, il ne cherche pas
au-delà. À rouvrir le jour où la file dépasse durablement une page — le prix
serait alors une table d'anomalies et un second chemin d'écriture à tenir aligné
avec `services/quality.py`.

`nav.config.ts` : poser `href: "/admin/quality"`, retirer `soon`.

### 4. Les badges de navigation (front, AC5)

`NavItem` gagne `badge?: string` : une **clé** de compteur, jamais un nombre —
une table de configuration ne fait pas de requête.

Un hook `useNavBadges(pouvoirs)` fait la correspondance clé → requête, et
n'émet que celles dont le pouvoir est porté par la session. `AppNav` rend le
nombre à droite du libellé, **masqué à zéro** : un badge « 0 » est du bruit.

Une seule clé est renseignée dans cette livraison : `"quality"` →
`useAdminCoursesCount({ unreliable: true })`. Le mécanisme est ouvert, et
brancher « Doublons » ou « Retours utilisateurs » tiendra en une ligne de config
plus une entrée de map — mais ces entrées rendent aujourd'hui des listes
complètes sans route de comptage, ce qui les met hors du périmètre de #119.

Coût assumé : une requête de comptage supplémentaire au chargement, **pour les
seuls porteurs de `quality:override`**.

## Tests

**Backend (pytest, sans réseau)**

- le filtre `unreliable` : `false` dedans ; `NULL` et `true` dehors ;
  `reliability_override` respecté dans les deux sens ;
- `count_all` rend le même ensemble que `list_all` sous le même filtre ;
- absence du paramètre = réponse inchangée sur les deux routes ;
- la trace : écrite avec les notes dans son payload ; **non** écrite quand le
  verdict demandé est celui déjà en place ;
- la trace et le verdict sont écrits ou absents ensemble (une seule transaction) ;
- `403` sans `quality:override`.

**Front (Vitest)**

- la file rend les anomalies en libellés français ;
- « Marquer OK » retire la ligne après invalidation ;
- les trois gestes de verdict transmettent bien les notes saisies ;
- aucun bouton de verdict sans le pouvoir ;
- le filtre par code d'anomalie restreint les lignes affichées ;
- le badge : nombre affiché, absent à zéro, absent sans le pouvoir.

## Acceptance criteria (corrigés)

- **AC1** : la file liste les épreuves `is_reliable = false` — avis humain
  compris via le `coalesce` — triées par date la plus récente, `NULL` exclu.
- **AC2** : chaque item affiche ses anomalies décodées en libellés lisibles.
- **AC3** : les gestes de verdict écrivent dans `admin_action_log` avec les notes.
- **AC4** : après « Marquer OK », l'épreuve sort de la file.
- **AC5** : le compteur de la file s'affiche en badge sur son entrée de navigation.
- **AC6** : tests API et Vitest.

## Hors périmètre

- La filtration SQL par code d'anomalie (table dédiée, migration).
- Les badges des autres entrées instruisables (Doublons, Retours, Fournisseurs).
- Tout nouveau pouvoir : `quality:override` (#115) est celui de l'écran, et il
  s'attribue à un rôle bénévole comme à un rôle administrateur — ce qui répond au
  fil de discussion de l'issue.
- La re-spécification de #79, orpheline de `to_review`.
