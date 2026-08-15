# Sondage — remesure de /dashboard et /club après #350/#351, décision pour #352

**Date** : 2026-08-15

**Contexte** : le sondage du 2026-08-14
(`2026-08-14-perf-frontend-sondage.md`) a identifié deux causes de lenteur sur
`/dashboard` et `/club` (N+1 sur `Course.sources`, #350 ; balayage non
indexable de `scope=club`, #351) et a ouvert #352 (revalidate court sur
`serverFetch`) en **priorité basse**, conditionnée à une remesure : « ne
poursuivre cette issue que si un écart significatif au budget cible subsiste »
une fois #350/#351 en place. Les deux sont fusionnées (PR #354, #356). Ce
sondage fait cette remesure, tranche #352, puis l'implémente.

## Méthode

Identique au sondage du 2026-08-14 : `uv run python scripts/dev_server.py`
avec `SQL_QUERY_STATS=true`/`SQL_SLOW_QUERY_MS=50`, front en build de
production (`npm run build && npm start`) pointé sur ce backend local, base de
dev à ~20 300 participations / ~18 600 athlètes / ~101 épreuves (dérive
mineure par rapport au 2026-08-14, ordre de grandeur inchangé). 5 tirs `curl`
par route, lecture du journal `app.sql` en regard.

## Remesure — le gap subsiste

| Page | Avant #350/#351 (sondage 08-14) | Après #350/#351 (ce sondage, avant #352) | Cible |
| --- | --- | --- | --- |
| `/dashboard` | 1,5 – 1,8 s | **0,94 – 1,00 s** | < 300 ms |
| `/club` | 0,4 – 0,6 s | **0,15 – 0,17 s** | < 150 ms |

`/club` est désormais **conforme** à sa cible (150-166 ms, au ras du seuil).
`/dashboard`, non : #350/#351 ont éliminé le N+1 et le balayage non indexable
(confirmé dans le journal SQL — la requête `course_sources` est passée d'une
vingtaine d'allers-retours à un seul `SELECT ... IN (...)`), mais un **tiers
défaut** domine maintenant, propre à `/dashboard` et absent de `/club` : la
combinaison `scope=club` **et** `seasons=2025` sur `courses/events`
(3 requêtes, 857-971 ms) et `participations` (2 requêtes, 857-910 ms) reste
lente, alors que les mêmes appels sans `seasons` (ceux de `/club`) sont
rapides. Piste pour une éventuelle issue fille : `_season_clause` (OR de
plages `Course.event_date`) combinée à `tcn_clause` sur `Participation.club`
pourrait ne pas composer avec l'index fonctionnel de #351 aussi bien que
`tcn_clause` seul — non instruit ici, hors périmètre de #352.

**Conclusion pour #352** : le gap sur `/dashboard` (0,94-1,00 s contre
< 300 ms) est significatif — la condition posée par #352 pour continuer est
remplie. `/club` est déjà sous sa cible, mais l'appliquer aux deux pages
reste cohérent avec la piste retenue par #352 (un seul mécanisme, deux pages,
plutôt qu'un traitement à part pour une page qui n'en a *presque* plus
besoin).

## Implémentation

- `serverFetch` (`frontend/lib/api/server.ts`) accepte désormais un second
  paramètre optionnel `{ revalidateSeconds }` : absent, comportement inchangé
  (`cache: "no-store"`) ; présent, bascule sur `fetch(..., { next: {
  revalidate } })`. Les fonctions `getStats`, `listEvents`,
  `listParticipations`, `listSeasons` le propagent.
- Seuls `/dashboard` (les 4 appels) et `/club` (les 2 appels) le renseignent,
  à `SHORT_REVALIDATE_SECONDS = 30` — une constante exportée, pas une valeur
  arbitraire dupliquée. Les trois autres consommateurs de `listEvents`/
  `listParticipations` (`/resultats`, `/ajouter`, `/courses/[id]`,
  `/athletes/[id]`) ne changent pas d'un octet : ils continuent d'appeler ces
  mêmes fonctions **sans** le second paramètre, donc gardent `no-store`.
- Fenêtre choisie sur la base de la fréquence réelle des imports — des batches
  de plusieurs dizaines de minutes (`docs/ci-cd.md`), jamais du temps réel :
  30 s masque le coût de chargement pour l'écrasante majorité des visites
  sans retarder la visibilité d'un import terminé au-delà de ce qu'un
  visiteur tolère.

## Vérification de l'effet

Sur un process frontend relancé (cache Next vidé), un premier passage sur
`/dashboard` coûte toujours le plein tarif backend (897 ms sur
`courses/events`, 471 ms sur `participations`, confirmé dans le journal SQL
au même horodatage) — le `revalidate` ne change rien au **premier** appel
dans la fenêtre, ce qui est attendu. Les appels suivants, dans les 30 s,
tombent à 30-90 ms : aucun aller-retour au backend, servis depuis le Data
Cache de Next. C'est le mécanisme visé par #352, confirmé plutôt que supposé.

## Ce qui n'a pas été mesuré

- Le troisième défaut identifié ci-dessus (`seasons` + `scope=club` combinés)
  n'a pas été instruit au-delà du constat — pas dans le périmètre de #352,
  à ouvrir séparément si jugé utile compte tenu du gain déjà apporté par le
  `revalidate`.
- Preview (Vercel + Render) : non remesuré, comme pour le sondage du 08-14.
