# Sondage — waterfall réseau de /dashboard (#425)

**Date** : 2026-08-17 — **Issue** : #425 (« Perf(front) »)

Ce fichier est un **sondage** au sens d'`AGENTS.md` : il consigne ce qui a été
mesuré/observé sur le terrain à la date ci-dessus, et **prime** sur le design,
la spec et le plan en cas de divergence — toute correction se fait en
re-sondant, pas en argumentant. Il ne tranche aucun design : il rapporte trois
constats, leur cause identifiée dans le code, le niveau de confiance de chaque
diagnostic, et une action classée par taille — pas une décision d'implémentation.

## Origine

L'issue #425 rapporte un waterfall réseau capturé sur
`https://data-triathlon-tcn-preview.vercel.app/dashboard` (visiteur anonyme,
Next.js 16 App Router, backend FastAPI sur le plan Render `free` en preview) et
signale trois observations distinctes : (1) 4 requêtes `fetch` vers
`/dashboard?seasons=…&rank=…` alors qu'un seul composant de rang est visible sur
la page, (2) 15-20 requêtes de prefetch spéculatif au simple atterrissage sur la
page, apparemment tirées en double, (3) une des 4 requêtes du point (1) à
1,01 s pour 3,2 ko, très supérieure aux autres (147-779 ms).

## Méthode

Trois investigations indépendantes, en lecture seule, menées en parallèle sur
le code du dépôt (pas de nouvelle capture réseau propre à ce sondage). Chacune
est partie des mêmes faits déjà établis, non re-vérifiés ici :

- `frontend/components/layout/RankTypeToggle.tsx` n'émet **aucun** fetch : le
  changement de `?rank=` passe par `window.history.pushState` pur (commentaire
  de tête, lignes 10-26).
- Le backend preview (`triathlon-backend-preview` dans `render.yaml`) tourne
  sur le plan Render `free`.
- La PR #415 (déjà mergée sur `main`) a déplacé le calcul des compteurs de rang
  (`rank_counters`) côté backend dans `backend/app/services/stats_service.py`,
  pour que `StatCardsRank` n'ait plus à recalculer côté client sur des
  participations brutes.

Chaque investigation a cherché ses preuves par lecture de code (grep ciblés,
lecture des composants de navigation et de `app/dashboard/page.tsx`, lecture de
`backend/app/services/stats_service.py` et `backend/app/repositories/
participation_repository.py`, et pour le constat 2, la documentation Next.js
embarquée dans `node_modules/next/dist/docs/`) et par recoupement avec le
sondage antérieur `2026-08-14-perf-frontend-sondage.md`, dont les correctifs
(#350, #351, #352) sont déjà mergés dans l'arbre courant.

## Constat 1 — Fetch storm sur `?rank=`

### Ce qui a été observé

4 requêtes `fetch` distinctes vers `/dashboard?seasons=2025%2C2024&rank=…`
(une avec `rank=ge…`, trois avec `rank=all…`), temps 147-779 ms sauf une à
1,01 s (traitée au constat 3), alors que `RankTypeToggle` — le seul composant
qui manipule `?rank=` — n'émet lui-même aucun fetch.

### Cause identifiée

Le coupable n'est pas `RankTypeToggle` mais **`DisciplineToggle`**, rendu juste
à côté de lui sur `/dashboard`, `/club` et `/club/athletes`.

`frontend/components/layout/DisciplineToggle.tsx:22` clone l'intégralité du
querystring courant avant un vrai `router.push` :

```ts
const params = new URLSearchParams(sp.toString());   // clone TOUT le querystring, y compris ?rank=
...
startTransition(() => router.push(`${pathname}${qs ? `?${qs}` : ""}`));   // ligne 26 — vraie navigation App Router
```

`sp.toString()` inclut `?rank=…` dès que l'utilisateur a touché
`RankTypeToggle` avant de cocher/décocher « Inclure les autres disciplines ».
Or ni `frontend/app/dashboard/page.tsx:22-27` ni `frontend/app/club/page.tsx:
15-17` ne lisent jamais `sp.rank` côté serveur — `rank` est un paramètre
strictement client (`frontend/lib/rank.ts`, consommé uniquement par
`StatCardsRank`, `ClubPodiumKpi`, `PodiumsList` via `useSearchParams`).
`/dashboard` étant entièrement dynamique, l'App Router traite chaque valeur
distincte de `rank` comme une URL de route différente au moment d'un
`router.push` réel : chaque combinaison rank×sports déclenche donc un nouveau
fetch RSC vers le serveur, alors que le rendu serveur produit est strictement
identique pour toute valeur de `rank`.

Les 4 requêtes correspondent donc à des navigations **réelles** déclenchées par
`DisciplineToggle` (coché/décoché plusieurs fois pendant la session de test),
chacune traînant la valeur de `rank` active à cet instant — pas à un
`<Link>` ni à un prefetch spéculatif. Les deux `<Link href="/dashboard">`
d'`AppNav` (`frontend/components/layout/AppNav.tsx:182`, `:251`) pointent vers
une URL statique sans querystring et sont écartés comme source.

Ce n'est **pas** une régression de #415 : cette PR n'a fait que déplacer le
calcul de `rank_counters` côté backend, sans toucher à `DisciplineToggle` ni à
`sp.toString()`. Le couplage existe depuis l'introduction conjointe de
`RankTypeToggle` (#104) et `DisciplineToggle` (#76) — préexistant.

### Preuves (fichier:ligne)

| Fichier | Ligne | Constat |
| --- | --- | --- |
| `frontend/components/layout/DisciplineToggle.tsx` | 22 | `new URLSearchParams(sp.toString())` clone tout le querystring, y compris `?rank=` |
| `frontend/components/layout/DisciplineToggle.tsx` | 26 | `router.push` réel dans `startTransition` |
| `frontend/components/layout/RankTypeToggle.tsx` | 51 | `pushState` pur confirmé, aucun fetch |
| `frontend/app/dashboard/page.tsx` | 22 | `sp = await searchParams` ; seules `sp.seasons` (l.25) et `sp.sports` (l.27) sont lues |
| `frontend/app/dashboard/page.tsx` | 58 | `DisciplineToggle` rendu juste à côté de `RankTypeToggle` (l.57) |
| `frontend/app/club/page.tsx` | 36 | même coexistence sur `/club` |
| `frontend/components/layout/AppNav.tsx` | 182 | `<Link href="/dashboard">` statique, sans querystring — écarté |
| `frontend/components/club/PodiumsList.tsx` | 54 | seul `<Link>` du composant, pointe vers `/athletes/[id]`, jamais `/dashboard` — écarté |
| `frontend/components/dashboard/SeasonSelector.tsx` | 25 | `buildSeasonsHref` ne propage pas `rank` — écarté |

### Niveau de confiance

**Élevé.** Mécanisme retracé de bout en bout dans le code, cohérent avec le
fait déjà établi que `RankTypeToggle` n'émet aucun fetch.

### Action proposée — corrigeable en l'état

Un seul fichier : `frontend/components/layout/DisciplineToggle.tsx`. Exclure
le paramètre de rang (et plus généralement tout paramètre purement client)
avant le `router.push` — par exemple `params.delete(RANK_PARAM)` juste après
la construction de `params`, à l'image de ce que fait déjà `buildSeasonsHref`
dans `SeasonSelector.tsx`, qui ne propage pas `rank`. Bénéficie aux trois pages
qui composent `DisciplineToggle` avec `RankTypeToggle`.

## Constat 2 — Storm de prefetch de navigation

### Ce qui a été observé

~15-20 requêtes de prefetch RSC vers d'autres routes (`/resultats`,
`/athletes/664`, `/ajouter`, `/club/athletes`, plusieurs `/courses/{id}`) au
simple atterrissage sur `/dashboard` en visiteur anonyme, apparemment tirées en
double (deux jeux de requêtes avec des `_rsc` différents, ex.
`_rsc=IOe_mmh6jQxP6_Ru` puis `_rsc=j79Vj4yH5aoiafxS`).

### Cause identifiée

Deux phénomènes distincts, tous deux liés au comportement de `next/link`, pas
au backend.

**Le volume brut est le comportement par défaut de `next/link`.** Aucun des
liens en cause ne passe `prefetch={false}`. Sont en cause : les entrées
`/dashboard`, `/resultats`, `/club/athletes` de
`frontend/components/layout/nav.config.ts:67-68,86` (section `root:true` et
section « Club », toutes deux `minRole: ROLE.ANON`) ; les liens de navigation
d'`frontend/components/layout/AppNav.tsx` (« Ajouter une course » lignes
348-376, logo vers `/dashboard` lignes 182-186 et 251-254, tuiles du rail
lignes 515-529 et 532-575) ; la tuile « Mon profil » → `/athletes/{id}`
(lignes 443-464, rendue seulement si `readAthlete()` renvoie un athlète mémorisé
en `localStorage`, ce qui explique `/athletes/664`) ; et jusqu'à 6
`<Link href={`/courses/${e.id}`}>` dans `frontend/app/dashboard/page.tsx:96-102`
(carte « Épreuves préférées », visible sans scroll). Tous ces liens sont
au-dessus de la ligne de flottaison sur `/dashboard`, donc chacun déclenche le
prefetch automatique documenté par Next.js (« As each `<Link>` enters the
viewport, Next.js prefetches the route behind it »).

**Le doublon vient de `frontend/components/layout/AppNav.tsx:36-65`.** Le rendu
serveur part délibérément de `expanded:false, athlete:null` (commentaire lignes
42-48 : « le rendu serveur part du rail replié, sans athlète »). L'effet de
montage (lignes 50-65) lit `localStorage` et appelle `setClient`
inconditionnellement juste après le premier paint. Si l'état persisté du
navigateur diffère (nav déjà dépliée et/ou un athlète déjà épinglé — les deux
indépendants de toute connexion), ce `setState` fait basculer `NavContent`
entre deux branches JSX mutuellement exclusives et structurellement
différentes (`!expanded` → `Tuile`, ligne 489 ; `expanded` → `Entree`, ligne
499), et fait apparaître le bloc « Mon profil » (lignes 429-466), absent du
premier rendu. React démonte les anciens noeuds et monte de nouveaux
`Link`/`IntersectionObserver` pour les mêmes routes, déjà dans le viewport —
d'où un second `_rsc`. Rien n'amortit ce second passage : `frontend/next.config.ts`
ne définit ni `staleTimes.dynamic` ni `partialPrefetching`/`cacheComponents`, et
le TTL client par défaut des routes dynamiques est documenté « Off » par Next.js.

Pistes explicitement écartées : Strict Mode (ne s'applique qu'à `next dev`, pas
à un build de preview Vercel, et `reactStrictMode` n'est même pas positionné
dans `next.config.ts`) ; double montage du rail desktop et de la barre mobile
(mutuellement exclusifs via `hidden md:flex` / `flex md:hidden`, un seul a une
boîte non nulle à la fois) ; le tiroir mobile (`Sheet`, base-ui `Dialog.Popup`/
`Portal`, non monté dans le DOM tant que `open=false`) ; la redirection de `/`
(`app/page.tsx:4`, un 307 HTTP pur, `AppNav` ne monte donc qu'une fois pour
`/dashboard`).

### Preuves (fichier:ligne)

| Fichier | Ligne | Constat |
| --- | --- | --- |
| `frontend/components/layout/AppNav.tsx` | 44 | état client par défaut délibérément différent du localStorage persisté |
| `frontend/components/layout/AppNav.tsx` | 60 | `setClient` inconditionnel au montage |
| `frontend/components/layout/AppNav.tsx` | 489 | branche JSX `!expanded` (Tuile), démontée si `expanded` passe à `true` |
| `frontend/components/layout/AppNav.tsx` | 499 | branche JSX `expanded` (Entree), nouveaux noeuds `Link` montés |
| `frontend/components/layout/AppNav.tsx` | 429 | tuile « Mon profil », absente du premier rendu SSR |
| `frontend/app/dashboard/page.tsx` | 96 | 6 `Link` vers `/courses/{id}`, aucun `prefetch={false}`, visibles sans scroll |
| `frontend/components/layout/nav.config.ts` | 67 | section root ANON : `/dashboard`, `/resultats` |
| `frontend/components/layout/nav.config.ts` | 86 | `/club/athletes`, `minRole` ANON |
| `frontend/app/page.tsx` | 4 | `redirect('/dashboard')` en 307 pur — pas de double montage via ce chemin |
| `frontend/components/ui/sheet.tsx` | 42 | `Dialog.Popup`/`Portal` non monté tant que `open=false` — écarté |
| `frontend/next.config.ts` | 1 | aucun `staleTimes.dynamic` ni `partialPrefetching`/`cacheComponents` configuré |

### Niveau de confiance

**Moyen.** Le volume brut (comportement `next/link` par défaut) est établi avec
certitude à la lecture de la doc Next.js embarquée. Le mécanisme du doublon
(resynchronisation `localStorage` → changement de branche JSX → remontage des
`Link`) est cohérent et retracé ligne à ligne, mais n'a pas été confirmé par
une capture réseau en direct dans le cadre de ce sondage — c'est un mécanisme
plausible et documenté, pas observé en train de se produire.

### Action proposée — mixte : une partie corrigeable en l'état, une partie à investiguer

Deux volets, de granularité différente :

1. **Corrigeable en l'état** (gain immédiat, sans changer la navigation) :
   passer `prefetch={false}` sur les liens vers des ressources dynamiques peu
   susceptibles d'être visitées au hasard — les 6 `<Link href={`/courses/${e.id}`}>`
   de `frontend/app/dashboard/page.tsx:96` et la tuile « Mon profil »
   `/athletes/{id}` de `frontend/components/layout/AppNav.tsx:443-464` —
   conformément au pattern documenté par Next.js pour les listes de liens
   (« Preventing too many prefetches »).
2. **Nécessite investigation/décision supplémentaire** : éliminer le doublon
   suppose un choix de design non tranché ici — soit accepter un flash de
   contenu (rendre le SSR déjà conscient de l'état via un cookie lu côté
   serveur plutôt que `localStorage`), soit fusionner `Tuile`/`Entree` en un
   seul composant dont seul le style change avec `expanded`, pour que React
   réutilise le même noeud `Link`/`IntersectionObserver` plutôt que d'en
   remonter un nouveau. Ni `nav.config.ts`, ni `layout.tsx`, ni la redirection
   de `/` ne sont en cause et n'ont besoin d'être touchés.

## Constat 3 — Requête lente à 1,01 s

### Ce qui a été observé

Une des 4 requêtes `/dashboard?seasons=…&rank=…` du constat 1 met 1,01 s pour
3,2 ko, contre 147-779 ms pour les trois autres.

### Cause identifiée

Les deux causes algorithmiques que le sondage `2026-08-14-perf-frontend-sondage.md`
avait chiffrées à 1,5-1,8 s sur `/dashboard` sont déjà corrigées dans l'arbre
courant, et n'expliquent donc plus ce pic :

- Le N+1 sur `Course.provider`/`Course.source_url` (#350) est fermé —
  `backend/app/repositories/participation_repository.py:339-340,368,383,492`
  chaîne désormais `joinedload(Participation.course).selectinload(Course.sources)`
  partout où `CourseBrief` est sérialisé. `for_stats` (`:558-560`) n'en a de
  toute façon jamais eu besoin : `stats_service.get_stats`/`_rank_counters` ne
  lisent que `course.event_type`, `course.event_date`, `course.name`,
  `athlete.gender` — déjà chargés par le `joinedload`.
- Le balayage non indexable de `scope=club` (#351) est fermé par l'index
  fonctionnel `ix_participations_club_normalized` (migration `e9cdbf3a4866`),
  documenté dans `backend/app/core/club.py:92-113`.
- `_rank_counters` (#415, `backend/app/services/stats_service.py:38-62`) est
  une passe Python unique sur les participations déjà en mémoire — coût O(n)
  négligeable, aucune requête ajoutée.
- `frontend/lib/api/server.ts:29-35` documente que le `revalidate` de 30 s
  (#352) n'a été posé qu'une fois #350/#351 réglés, précisément parce que le
  coût backend résiduel attendu tombait sous la cible (< 300 ms).

Il n'existe par ailleurs aucun cache de réponse pour `/stats` — le TTL de
`services/cache.py` couvre la fraîcheur de scraping (`is_fresh`), sans rapport
avec cette route de lecture — donc chaque premier appel après expiration du
`revalidate` (ou avec une combinaison de `seasons` différente) repaie le coût
backend plein, censé être désormais faible.

L'ordre de grandeur observé (~1 s, pas 10+ s) est incompatible avec un cold
start Render complet (le plan `free` se réveille typiquement en plusieurs
secondes à ~1 minute quand le conteneur entier s'est mis en veille) : trop
lent pour être un coût applicatif résiduel identifié dans le code, trop rapide
pour un vrai cold start de conteneur. Le mécanisme qui reste compatible avec
~1 s est une reconnexion DB partielle : `backend/app/core/database.py:55-58`
pose `pool_pre_ping=True` mais ne fixe aucun `pool_recycle`, et le service
tourne sur une base Supabase preview distante (`render.yaml:36,46,135`) — si le
pooler Supabase a fermé une connexion côté serveur avant que `pool_pre_ping` ne
la détecte comme morte, la requête suivante paie une poignée de main à froid
(TCP+TLS+auth vers un Postgres distant), de l'ordre de quelques centaines de ms
à ~1 s, sans que le conteneur Render lui-même ait dû se réveiller. C'est une
hypothèse cohérente avec l'ordre de grandeur mesuré, pas une confirmation.

### Preuves (fichier:ligne)

| Fichier | Ligne | Constat |
| --- | --- | --- |
| `backend/app/repositories/participation_repository.py` | 339 | `selectinload(Course.sources)` déjà posé (#350 fermé) |
| `backend/app/repositories/participation_repository.py` | 558 | `for_stats` : `get_stats` ne lit jamais `provider`/`source_url` |
| `backend/app/core/club.py` | 92 | index fonctionnel `ix_participations_club_normalized` (#351 fermé) |
| `backend/app/services/stats_service.py` | 38 | `_rank_counters` : passe Python O(n), aucune requête ajoutée |
| `frontend/lib/api/server.ts` | 29 | commentaire : `revalidate` de 30 s posé une fois #350/#351 corrigés |
| `docs/superpowers/specs/2026-08-14-perf-frontend-sondage.md` | 55 | mesures locales : `/dashboard` 1,98 s puis 1,5-1,8 s avant les deux correctifs |
| `backend/app/core/database.py` | 55 | `pool_pre_ping=True` sans `pool_recycle` |
| `render.yaml` | 135 | service preview sur plan `free`, base Supabase preview distincte |

### Niveau de confiance

**Moyen.** Il est établi avec un niveau de confiance élevé que les causes
connues et déjà corrigées (#350, #351) n'expliquent plus ce pic — c'est vérifié
par lecture directe du code actuel. L'hypothèse de reconnexion de pool DB est
en revanche une déduction par élimination (compatible avec l'ordre de
grandeur, aucune autre explication actuellement identifiée dans le code), pas
une observation directe en production.

### Action proposée — non-problème avéré dans le code actuel, à vérifier en production

Aucune action de code n'est justifiée par ce qui est lisible dans le dépôt : les
deux causes algorithmiques connues et `_rank_counters` (#415) sont déjà
corrigées ou ne coûtent rien. Avant d'ouvrir une action de correction, vérifier
en production, dans cet ordre :

1. Confirmer que la base Supabase preview a bien reçu la migration
   `e9cdbf3a4866` (l'index existe réellement, pas seulement dans le code).
2. Activer temporairement `SQL_QUERY_STATS=true` et `SQL_SLOW_QUERY_MS=50`
   (mécanisme déjà en place, `backend/app/core/AGENTS.md`) sur le service
   preview pour obtenir le bilan par requête HTTP sur un hit lent réel.
3. Croiser l'horodatage du pic à 1,01 s avec les métriques Render (temps de
   réponse par requête, logs de démarrage) pour voir s'il coïncide avec un
   intervalle d'inactivité précédent — signature d'une connexion DB recréée
   plutôt que d'un cold start complet.
4. Si confirmé, fixer un `pool_recycle` sur l'engine
   (`backend/app/core/database.py`) inférieur au délai d'idle-timeout du
   pooler Supabase.

## Résumé

| Constat | Cause identifiée | Confiance | Action | Taille |
| --- | --- | --- | --- | --- |
| 1. Fetch storm sur `rank=` | `DisciplineToggle` clone `sp.toString()` (donc `?rank=`) avant un vrai `router.push` | élevée | `params.delete(RANK_PARAM)` dans `DisciplineToggle.tsx` | corrigeable en l'état — 1 fichier |
| 2. Storm de prefetch de nav | Prefetch par défaut de `next/link` (volume) + resynchronisation `localStorage` après montage qui remonte les `Link` (doublon) | moyenne | `prefetch={false}` sur les liens dynamiques (immédiat) ; unifier `Tuile`/`Entree` ou passer par un cookie SSR pour le doublon | mixte — volet 1 corrigeable en l'état, volet 2 à investiguer/concevoir |
| 3. Requête lente à 1,01 s | Causes connues (#350, #351) déjà corrigées ; hypothèse résiduelle : reconnexion de pool DB après idle-timeout Supabase | moyenne | Aucune action de code justifiée par le dépôt actuel ; vérifier en prod (logs Render/Supabase, `SQL_QUERY_STATS`) avant d'agir | non-problème dans le code actuel — à vérifier en production |
