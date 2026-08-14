# Sondage — audit de chargement du front (lot 2 de #328)

**Date** : 2026-08-14

**Contexte** : #328 lot 1 (fusionné, PR #341) a supprimé l'aller-retour serveur
du sélecteur de type de rang. Le lot 2 demande d'aller plus loin : mesurer les
cinq pages publiques, instruire les quatre suspects déjà nommés dans l'issue, et
ouvrir une issue fille par correctif qui ne tient pas dans cette branche.

Ce fichier est un **sondage** au sens d'AGENTS.md : il consigne ce qui a été
mesuré sur le terrain à la date ci-dessus, et **prime** sur la spec, le plan et
le design en cas de divergence — toute correction se fait en re-sondant.

**Ce qu'il découvre** : les suspects nommés par l'issue (agrégats en
`page_size` géant, `no-store` systématique, autres sélecteurs d'URL) ne sont
**pas** la cause principale des lenteurs mesurées. La cause principale est un
**N+1 non détecté**, introduit par #279/#306, sur `Course.provider` /
`Course.source_url` — et une seconde cause, un filtre `scope=club` qui force un
balayage complet de `participations` par une expression SQL non indexable. Les
deux sont documentées, chiffrées, et donnent lieu chacune à une issue fille.

## Méthode

Environnement **local uniquement** — la mesure preview (Vercel/Render) a été
écartée pour ce tour, sur décision explicite : hors du champ de ce sondage,
à refaire séparément si sa valeur ajoutée (réseau réel, cold start Render) se
confirme nécessaire.

- Backend : `uv run python scripts/dev_server.py`, `SQL_QUERY_STATS=true` et
  `SQL_SLOW_QUERY_MS=50` — le bilan agrégé par requête HTTP et le seuil de
  lenteur documentés dans `backend/app/core/AGENTS.md`.
- Frontend : `npm run build` puis `npm start` (build de **production**, pas
  `next dev`) — pointé sur le backend local via `BACKEND_URL`/`API_URL`.
- Base de dev : 20 318 participations, 18 623 athlètes, 98 épreuves, migrée au
  head Alembic.
- 5 tirs `curl` par route (`-w "ttfb / total / taille"`), plus lecture du
  journal `app.sql` sur la même fenêtre pour capter le détail des requêtes
  déclenchées par chaque hit.
- **Cold vs chaud** : pas de redémarrage entre les 5 tirs (`no-store` interdit
  de toute façon tout cache HTTP) — « cold » désigne le 1ᵉʳ tir de la série,
  « chaud » les quatre suivants. Ça mesure l'effet du cache de pages OS/SQLite
  sur des requêtes identiques répétées, pas un redémarrage à froid du process.
- Poids JS : Next 16 n'imprime plus la table `Route / Size / First Load JS` au
  build (rupture déjà signalée en tête de `frontend/AGENTS.md`). Mesuré à la
  place en listant les `<script src="/_next/static/...">` réellement présents
  dans le HTML rendu de chaque page, puis en sommant leur `Content-Length` réel.
  **Octets bruts** — la commande `curl` n'a pas demandé `--compressed` ; le
  transfert réseau réel (gzip/brotli) est plus petit. À corriger si ce chiffre
  sert de budget contractuel.

## Mesures — les cinq pages publiques

| Page | TTFB (1ᵉʳ tir) | TTFB (4 tirs suivants) | Taille HTML | Poids JS (scripts référencés, brut) |
| --- | --- | --- | --- | --- |
| `/dashboard` | 1,98 s | 1,52 – 1,79 s | 303 ko | 954 ko |
| `/club` | 0,84 s | 0,39 – 0,60 s | 735 ko | 967 ko |
| `/resultats` | 28 ms | 11 – 13 ms | 84 ko | 1 005 ko |
| `/courses/57` | 53 ms | 39 – 47 ms | 126 ko | 953 ko |
| `/athletes/10422` | 32 ms | 13 – 14 ms | 39 ko | 929 ko |

**`/dashboard` ne chauffe jamais** : les cinq tirs restent dans la même
fourchette (1,5 – 2,0 s). Ce n'est pas un effet de cache absent côté HTTP
(attendu, `no-store`) — c'est que le **coût des requêtes SQL sous-jacentes ne
change pas d'un tir à l'autre**, pour les deux raisons détaillées plus bas.
`/club` chauffe un peu (0,84 s → ~0,4-0,6 s), cohérent avec un cache de pages
SQLite qui s'échauffe sur un jeu de données plus restreint (scope club).
`/resultats`, `/courses/[id]` et `/athletes/[id]` sont déjà rapides et stables
— aucun défaut à corriger sur ces trois pages.

Le poids JS est **quasi uniforme** (929-1 005 ko) d'une page à l'autre, signe
d'un socle partagé important (framework + vendor chunks) plutôt que d'un poids
spécifique à une page. C'est le chiffre de référence pour #329 : ajouter une
bibliothèque de dataviz ajoutera à ce socle, pas à un delta par page.

**Aparté, hors méthode** : l'URL preview donnée en cours de sondage
(`https://data-triathlon-tcn-preview.vercel.app/dashboard`) répond bien, 200,
1,665 s au tir unique testé — dans le même ordre de grandeur que le local. Un
seul point, non systématique, à ne pas sur-interpréter.

## Cause n°1 (dominante) — N+1 sur `Course.provider` / `Course.source_url`

**C'est la découverte principale de ce sondage**, pas un des quatre suspects
listés dans l'issue.

### Ce qui a été observé

Le bilan SQL du premier hit sur `/dashboard` :

```
GET /api/v1/participations | 28 requêtes | 1240 ms
  x27 SELECT ... FROM course_sources WHERE ? = course_sources.course_id
  x1  SELECT ... FROM participations JOIN athletes JOIN courses ...
```

Sur `/club` (page à `scope=club`, jeu de données plus restreint) : 30 requêtes,
238-336 ms — même défaut, coût proportionnel au nombre de courses distinctes
dans la page.

### La cause, tracée dans le code

`Course.source_url` et `Course.provider` sont des `hybrid_property`
(`backend/app/models/course.py:81-111`) qui lisent `course.sources` **en
mémoire**, sans requête — *si* la collection est déjà chargée :

```python
def _from_active_source(course: "Course", champ: str) -> str:
    """Lit un champ de la source active dans la collection déjà en mémoire.
    Pas de requête : ..."""
    for source in course.sources:
        ...
```

`backend/app/models/AGENTS.md` documente déjà la règle : **`selectinload
(Course.sources)` sur tout chemin qui rend des entités et lit ces champs** —
et énumère les chemins couverts (les recherches par URL, `iter_all`,
`list_all`). **`participation_repository.list_participations` n'y figure
pas**, et de fait :

```python
# backend/app/repositories/participation_repository.py:330-332
q = db.query(Participation).options(
    joinedload(Participation.athlete), joinedload(Participation.course)
)
```

`joinedload(Participation.course)` charge la `Course` elle-même, mais pas sa
collection `sources`. Chaque accès à `course.provider`/`course.source_url`
pendant la sérialisation (`CourseBrief`, consommé par `/api/v1/participations`,
lui-même utilisé par `/dashboard` **et** `/club` pour les compteurs de rang du
lot 1) déclenche donc un lazy-load SQLAlchemy — une requête par `Course`
**distincte** de la page. C'est exactement la règle documentée que ce chemin
n'a pas suivie.

`list_for_athlete` (`:356-363`) et `list_page_for_course` (`:423+`) partagent
la même lacune ; elle ne s'est pas vue sur `/athletes/10422` ni `/courses/57`
dans ce sondage parce que ces deux jeux de données ne traversent qu'un petit
nombre de courses distinctes — le défaut est le même, seul son coût varie avec
le nombre de courses distinctes dans la page.

### Coût estimé du correctif

`/courses/57` (4 requêtes, dont le `joinedload` + son résultat, 13-18 ms) donne
un ordre de grandeur de ce que coûte une poignée de requêtes bien groupées sur
cette base. En ajoutant `selectinload(Course.sources)` à la suite du
`joinedload`, le nombre de requêtes de `/api/v1/participations` tomberait de
28-30 à 2 (la requête principale + une seule requête `IN (...)` groupée pour
toutes les sources des courses distinctes de la page) — le poste qui domine
aujourd'hui le temps de `/dashboard` et `/club` disparaîtrait presque entièrement.

## Cause n°2 — `scope=club` force un balayage non indexable de `participations`

### Ce qui a été observé

Sur `/dashboard` (le seul appelant à passer `scope=club` à `/courses/events`
parmi les cinq pages mesurées) :

```
Requête lente | 876-1906 ms | SELECT count(*) FROM (SELECT courses.id ...
GET /api/v1/courses/events | 3 requêtes | 1482-1906 ms
```

Le même endpoint, appelé par `/resultats` **sans** `scope=club` :

```
GET /api/v1/courses/events | 3 requêtes | 92-109 ms
```

Même nombre de requêtes (3), un facteur **15 à 20** sur leur coût.

### La cause, tracée dans le code

`club_only=True` (`backend/app/repositories/course_repository.py:277-280`) :

```python
if club_only:
    q = (
        q.join(Participation, Participation.course_id == Course.id)
        .filter(tcn_clause(Participation.club))
        .distinct()
    )
```

`tcn_clause` (`backend/app/core/club.py:60-89`) construit une expression SQL de
**huit fonctions imbriquées** (`replace` ×4 pour les blancs non-ASCII, `lower`,
`trim`, `replace` ×3 pour aplatir les espaces) sur `Participation.club`, avant
de comparer le résultat aux trois libellés canoniques. `Participation.club`
(`backend/app/models/participation.py:35`) ne porte **aucun index** — colonne
ni expression. Chacune des ~20 000 lignes de `participations` que la jointure
traverse subit donc l'évaluation complète de la chaîne de fonctions, sans
qu'aucun index ne puisse l'éviter, puis un `DISTINCT` déduplique le résultat.

C'est exactement l'analyse que `backend/app/core/AGENTS.md` annonçait comme
« restant à faire » (« EXPLAIN et audit d'index... dont le livrable sera un
sondage ») — ce sondage en fournit un premier cas concret et chiffré, sans
avoir encore fait tourner `EXPLAIN QUERY PLAN` lui-même (à faire dans l'issue
fille, avec le vrai plan d'exécution, sur SQLite **et** sur Postgres — le
moteur de production, dont le comportement d'indexation par expression diffère
de SQLite).

## Les quatre suspects de l'issue, instruits

1. **`page_size=5000`/`page_size=1000`, agrégats côté front** — **pas un
   défaut, un choix assumé.** `RankTypeToggle` (#104, puis #328 lot 1) a
   précisément pour but de permuter le type de rang **sans** round-trip
   serveur ; ça suppose que le client tienne déjà la liste complète des
   participations de la période. Le vrai coût de ce choix n'est pas la taille
   du transfert (735 ko sur `/club`, mesuré ci-dessus, à comparer au ~1 Mo de
   JS déjà chargé sur chaque page) mais le **temps serveur** pour produire
   cette liste — et ce temps est presque entièrement absorbé par la cause n°1.
   Rien à corriger ici indépendamment du N+1.
2. **`cache: "no-store"` systématique** — **deux points d'entrée seulement**
   (`frontend/lib/api/server.ts:23` et `:51`), pas une dispersion à
   inventorier fichier par fichier. `serverFetchAuthed` (`:51`) relaie les
   cookies de session : `no-store` y est **correct**, une réponse mise en
   cache y fuiterait les données d'un utilisateur vers un autre. `serverFetch`
   (`:23`) est le seul candidat à un `revalidate` court, et sert les cinq
   pages mesurées. Piste retenue pour l'issue fille : un `revalidate` de
   quelques dizaines de secondes sur `/dashboard` et `/club` en priorité —
   les deux pages où le coût mesuré ci-dessus le justifie — plutôt qu'un
   changement uniforme aux cinq pages, dont trois n'en ont pas besoin.
3. **Les autres sélecteurs d'URL (`?scope`, `?sports`, `?seasons`)** — **pas
   de symptôme comparable à `?rank=`.** Ils sont lus **côté serveur**
   (`app/dashboard/page.tsx`, `app/club/page.tsx` consultent `searchParams`
   pour construire leurs appels API), contrairement à `?rank=` qui n'était lu
   que côté client. Un aller-retour serveur y est donc correct, pas un défaut
   — c'est la distinction que `frontend/AGENTS.md` consigne déjà depuis #328
   lot 1 (« un rendu serveur lit-il ce paramètre ? »). Rien à corriger.
4. **Coût SQL côté backend** — instruit **au-delà** de ce que l'issue
   demandait : les causes n°1 et n°2 ci-dessus en sont le résultat direct,
   obtenu avec l'outillage déjà en place (`SQL_QUERY_STATS`,
   `SQL_SLOW_QUERY_MS`) plutôt qu'à construire.

## Budget cible par page

| Page | Aujourd'hui (chaud) | Cible | Condition |
| --- | --- | --- | --- |
| `/dashboard` | 1,5 – 1,8 s | < 300 ms | Causes n°1 et n°2 corrigées |
| `/club` | 0,4 – 0,6 s | < 150 ms | Cause n°1 corrigée |
| `/resultats` | 11 – 13 ms | inchangé | Déjà sous la cible |
| `/courses/[id]` | 39 – 47 ms | inchangé | Déjà sous la cible |
| `/athletes/[id]` | 13 – 14 ms | inchangé | Déjà sous la cible |

La cible `/dashboard` s'appuie sur `/courses/57` (39-53 ms pour 8 requêtes
réparties sur trois endpoints) comme ordre de grandeur d'une page qui
interroge plusieurs endpoints sans défaut de chargement — avec une marge pour
le volume plus grand de `/dashboard` (200 épreuves, jusqu'à 5 000
participations par appel).

**Budget JS** (pour #329) : ~950 ko bruts de JS partagé par page, mesuré
localement. Toute bibliothèque de dataviz ajoutée s'empile sur ce socle commun
— son poids compte donc une seule fois pour l'ensemble du site, pas par page.

## Issues filles

- **#350 — N+1 `Course.sources`** sur `list_participations`, `list_for_athlete`,
  `list_page_for_course` — priorité haute, correctif net (`selectinload`),
  gain le plus important mesuré ici.
- **#351 — Balayage non indexable de `scope=club`** — `EXPLAIN QUERY PLAN` sur
  SQLite et Postgres, puis un index (fonctionnel ou par colonne normalisée
  matérialisée) ou une restructuration de la requête.
- **#352 — `revalidate` court sur `serverFetch`**, ciblé `/dashboard` et
  `/club` — priorité basse, conditionnée aux deux précédentes : leur
  correction seule ramène déjà les deux pages sous leur budget cible.

## Ce qui n'a pas été mesuré

- **Preview** (Vercel + Render) : écarté pour ce tour, un seul point de
  contrôle pris en aparté. À refaire si le besoin se confirme, avec les mêmes
  cinq pages et la même méthode.
- **LCP** : nécessite un navigateur réel (peinture, pas seulement le
  transfert) — absent de ce dépôt (#102). Non mesuré, comme pour #328 lot 1.
- **Poids JS compressé** (gzip/brotli) : mesuré en octets bruts, `curl` sans
  `--compressed`. Le transfert réseau réel est plus petit ; à corriger si ce
  chiffre sert de budget contractuel pour #329.
- **`EXPLAIN QUERY PLAN`** effectif sur la cause n°2 : la lecture du code
  établit le mécanisme (balayage + fonctions non indexables), pas encore le
  plan d'exécution réel — laissé à l'issue fille, sur les deux moteurs
  (SQLite dev, Postgres prod).
