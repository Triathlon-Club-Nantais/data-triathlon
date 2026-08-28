# Research: Persist par lot pour l'import de résultats

## Inventaire des allers-retours DB par ligne (état actuel)

Lu dans `backend/app/services/import_service.py` (`_Persister`) et
`backend/app/services/mapping.py` :

1. **`get_or_create_course`** (mapping.py:126) — appelé à **chaque** ligne,
   fait une requête de réconciliation + `get_or_create` + `attach` de source à
   chaque appel. Non retenu dans l'issue #706 comme goulot mesuré — **hors
   périmètre**, cf. Assumptions de `spec.md`.
2. **Chemin dossard apparié** (une ligne dont le dossard existe déjà en base,
   typiquement un re-scrape d'une épreuve déjà importée) : `add()` appelle
   `self._reconcile(scraped, existing)` **inconditionnellement**, qui appelle
   `mapping.resolve_athlete` → `athlete_repository.get_by_identity` — **une
   requête par ligne**, même quand l'identité n'a pas changé (le court-circuit
   n'existe qu'après avoir déjà interrogé la base). C'est la même forme de
   goulot que celle décrite dans l'issue, sur un chemin qu'elle ne nomme pas
   explicitement (le cas dominant en production : re-scrape d'une épreuve en
   cours). **Dans le périmètre** — même cause racine que le point 3.
3. **Chemin dossard neuf / sans dossard** : `mapping.get_or_create_athlete` →
   `athlete_repository.resolve` → `get_by_identity` (1 requête), puis
   `db.add(athlete); db.flush()` si nouveau (1 round-trip de plus). **Dans le
   périmètre**, c'est le cas explicitement cité par l'issue.
4. **`participation_repository.create`** : `db.add(p); db.flush()` — un flush
   par ligne neuve. **Dans le périmètre** (bullet 2 de l'issue).
5. **`_index_course`** : déjà gardé (`if course_id in self._by_bib: return`)
   — une seule requête par course, pas par ligne. Pas un goulot en soi.
6. **`finalize()`** : `participation_repository.list_for_course` — une requête
   *supplémentaire* par course, qui recharge ce que `_index_course` avait déjà
   chargé en début d'import. **Dans le périmètre** (bullet 3 de l'issue) —
   optimisation à l'échelle du nombre de courses, pas des lignes ; gain plus
   modeste que 2/3/4 mais trivial à supprimer.

**Conclusion** : le O(n) réel vient des points 2, 3, 4 — un aller-retour DB par
ligne pour la résolution d'athlète (que la ligne soit un dossard déjà connu ou
neuf) et un flush par participation neuve. Le point 6 est un doublon
d'O(nombre de courses), pas d'O(lignes), mais se corrige avec le même effort.

## Décision — identité athlète en pratique : `birth_date` toujours `None`

`grep birth_date` sur `mapping.py`, `import_service.py` et tous les scrapers
(`app/scrapers/*.py`) : **aucun** appelant du chemin d'import ne renseigne
`birth_date`. `resolve_athlete` (mapping.py:186) appelle
`athlete_repository.resolve` sans le paramètre — il retombe sur son défaut
`None`. L'identité effective pendant un import est donc `(nom, prénom)`
insensible à la casse, avec `birth_date IS NULL` en clause fixe — pas besoin de
grouper par valeur de date de naissance dans la requête de lot.

**Alternative rejetée** : générer la clause de lot sur les trois colonnes
(nom, prénom, birth_date) pour rester générique — inutile ici : aucune ligne
scrapée ne porte de date de naissance, l'ajouter compliquerait la requête sans
cas d'usage réel. Si un scraper venait un jour à fournir `birth_date`, la
clause devra être revue — non couvert par cette feature.

## Décision — requête de résolution par lot

**Choix** : `tuple_(func.lower(Athlete.nom), func.lower(Athlete.prenom)).in_(paires)`
sur une clause combinée à `Athlete.birth_date.is_(None)`, où `paires` est
l'ensemble **dédupliqué** des `(nom.strip().lower(), prénom.strip().lower())`
en attente pour la tranche/course en cours. Le dialecte Postgres (prod,
Supabase) et SQLite ≥ 3.15 (dev/tests, bundlé avec Python 3.13) supportent
tous deux la comparaison de tuples (row values) — à vérifier empiriquement
lors de l'implémentation par un test ciblé sur `db_session` (fixture SQLite)
avant de bâtir le reste dessus, plutôt que par une simple lecture de
changelog SQLite.

**Alternative rejetée — chaîne de `OR(AND(...))`** : fonctionne sur tout
dialecte sans caractéristique de tuple, mais produit une clause `WHERE` de
taille O(tranche) que l'optimiseur planifie moins bien qu'un `IN` de tuples,
et perd la lisibilité. Repli seulement si le test empirique invalide le
support tuple de SQLite en pratique.

**Taille de tranche** : 500 lignes, reprise de l'ordre de grandeur cité par
l'issue — assez petit pour rester sous les limites de paramètres liées d'un
driver, assez grand pour effacer le coût par ligne. Détail d'implémentation,
pas un critère d'acceptation (`spec.md` → Assumptions).

## Décision — écriture des participations neuves : flush unique différé, pas `bulk_insert_mappings`

**Choix retenu** : conserver `db.add(Participation(**fields))` par ligne (les
objets restent des instances ORM, nécessaires pour que `_by_bib`/`_without_bib`
continuent d'y référer directement — utilisé plus loin par `_upsert` en cas de
rencontre d'un doublon **dans le même scrape**), mais **différer le
`db.flush()`** : un seul flush par course (ou par tranche) au lieu d'un flush
par ligne. SQLAlchemy 2.0 compile un flush portant plusieurs objects `pending`
de même classe en un **INSERT multi-lignes** (`insertmanyvalues` sur Postgres
psycopg — un seul aller-retour réseau pour N lignes), donc l'essentiel du gain
de `bulk_insert_mappings` s'obtient sans en payer le coût.

**Alternative rejetée — `bulk_insert_mappings`** (suggestion littérale de
l'issue) : plus rapide en théorie (contourne l'identity map), mais casse deux
invariants du code existant : (1) les objets retournés ne sont pas des
instances suivies par la session — impossible de les référencer ensuite dans
`_by_bib[course.id][bib] = created` sans un rechargement explicite ; (2) pas de
PK auto-remontée de façon portable entre SQLite et Postgres sans un second
aller-retour (`RETURNING` n'est pas exposé par cette API SQLAlchemy 2.0 de la
même façon qu'un `flush()` ORM). Le flush différé atteint le même objectif
(un seul aller-retour réseau pour les lignes neuves d'une course) sans ces
deux régressions — **la feature respecte l'intention de l'issue (borner les
allers-retours), pas sa formulation littérale de l'implémentation**, cohérent
avec `spec.md` qui ne prescrit pas cette API précise.

## Décision — architecture de mise en lot dans `_Persister`

`add()` reste appelée une fois par ligne par les deux appelants (import
« simple » et streaming SSE) — le contrat externe ne change pas (`spec.md`
Assumptions : la SSE doit garder sa granularité de progression). En interne,
`add()` change de mode : au lieu de résoudre l'athlète immédiatement, une ligne
qui a besoin d'une résolution (chemin dossard apparié → `_reconcile`, ou
dossard neuf/sans dossard → `get_or_create_athlete`) est mise en **attente**
dans une file par course ; la résolution par lot (et le flush différé des
participations neuves) se déclenche quand la file atteint la taille de
tranche, ou à `finalize()` pour le reliquat de chaque course.

Les compteurs (`imported`/`updated`/`skipped`/`reconciled`) restent mis à jour
de façon synchrone pendant `add()` — ce sont des entiers Python déductibles
dès qu'on connaît l'issue de la ligne, pas seulement après l'écriture
physique en base. La progression SSE (yield tous les 20 items) n'est donc pas
affectée : elle reflète déjà un état en mémoire, pas un état confirmé en base.

**Alternative rejetée — deux passes complètes (buffer tout, puis tout
résoudre)** : plus simple à écrire, mais route les deux appelants (fonction
« simple » qui a déjà toutes les lignes en mémoire, **et** le générateur SSE
qui reçoit les lignes une à une) vers deux implémentations différentes de
`_Persister`. La mise en lot par tranche à l'intérieur d'`add()` garde un point
d'entrée unique pour les deux appelants — conforme à la docstring existante de
`_Persister` (« point de persistance unique »).

## Test pattern existant — assertion « le nombre de requêtes ne croît pas »

`backend/tests/test_services/test_course_merge.py::test_the_query_count_does_not_grow_with_the_number_of_results`
instrumente `before_cursor_execute` sur l'engine (pas seulement la requête
principale — sinon un lazy-load resterait invisible) et compare le nombre de
requêtes entre un petit jeu (1 résultat) et un plus gros (20). Même patron
retenu pour valider FR-006 sur `_Persister.add`/`finalize` : le nombre de
requêtes émises pour importer un scrape doit être identique (à la tranche
près) entre 10 et 1000 lignes sur une même course.

## Non-régression comportementale

FR-004 exige des compteurs et un rapport qualité strictement identiques.
La suite de tests existante sur l'import (`backend/tests/test_services/` —
résolution d'athlète, réconciliation `_reconcile`, dédoublonnage de dossard,
`quality.analyze`) sert de filet : aucune assertion de résultat métier ne doit
changer, seule la **forme** de la résolution (par lot plutôt que ligne à
ligne) change. Les nouveaux tests portent uniquement sur le **nombre de
requêtes** et sur les **cas de lot** (tranche > 500, lot avec collision
d'identité entre deux lignes du même scrape, cf. Edge Cases de `spec.md`).
