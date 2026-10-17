# Données : URL, rendu serveur et cache

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## Sélecteurs d'URL : `pushState` ou `router.push`

**Sélecteurs d'URL : `pushState` ou `router.push`, et la question qui tranche**
— *un rendu serveur lit-il ce paramètre ?* `?rank=` ne l'est par aucun, donc
`RankTypeToggle` écrit l'URL par `window.history.pushState` et les trois
consommateurs (`MaSaison`, `ClubPodiumKpi`, `PodiumsList`) recalculent en
mémoire : zéro requête (#328). `?scope`, `?sports` et `?seasons` **le sont**
(`app/club/page.tsx`, `app/(public_restricted)/mon-espace/page.tsx`), donc `ScopeToggle` et
`DisciplineToggle` gardent `router.push` — les basculer serait un bug
silencieux, la page continuant de lire l'ancienne valeur sans erreur visible.
L'asymétrie est voulue ; elle se re-tranche paramètre par paramètre, jamais
par harmonisation. `?season=` et `?discipline=`, les deux filtres du tableau
d'`/athletes/[id]` (#489), tombent du côté `pushState` : `GET /athletes/{id}`
rend **toutes** les participations en un appel, donc `EventsTable` filtre en
mémoire et un `push` ne referait ce fetch que pour redonner ce que le client
tient déjà. Leurs jumeaux de `/club/athletes` n'ont pas pu être réemployés :
le défaut de `SeasonSelector` est la saison en cours, celui de
`DisciplineToggle` la seule fédération triathlon — sur un profil qui s'annonce
« Toutes les épreuves », ces défauts escamotent neuf saisons sur dix et tout
le hors-triathlon sans que personne l'ait demandé. Ici le défaut est « tout »,
et une valeur d'URL qui ne correspond à aucune épreuve y retombe en silence.

## `/club` et sa charge RSC (#487, #581)

**`/club` n'envoie plus les participations dans la charge RSC** (#487 → #581) —
`ClubPodiumKpi` et `PodiumsList` restent deux composants **client** qui
recalculent sur `?rank=` sans re-fetch (#132), mais ce qu'ils reçoivent est
désormais pré-agrégé : `rank_counters` (`GET /stats`) pour le KPI, un
`ClubPodiums` à quatre buckets (`GET /club/summary`) pour la liste. Le
transport de la page est passé de ~2,1 Mo à ~32 ko et ne croît plus avec le
nombre de participations, mais avec le seul nombre de podiums. Le roster est
plafonné à 12 **côté SQL** (`athlete_repository.club_roster`), plus par une
troncature d'affichage — d'où la disparition du bandeau « les N derniers
résultats importés » : plus rien n'est tronqué en silence.
Corollaire de lecture qui, lui, tient toujours : `list_participations` trie
par `created_at desc` hors détail d'épreuve — la date d'**import**, jamais
celle de l'épreuve. Les 6 « Résultats récents » de `/club` sont donc les 6
derniers **importés**, cohérents avec `/resultats?scope=club` où mène
« Tout voir ».

Deux features livrées après #581 avaient rouvert une brèche dans ce
transport réduit — corrigée par #641/#642, à ne pas rouvrir : le rappel
épinglé de l'athlète retenu (#504, `RosterApercu`) et les onglets
« Performance »/« Composition » (#466, `DisciplinePerformance`/
`ClubComposition`) avaient tous les deux été conçus sur l'ancienne
architecture (`participations` complet en prop, ou un fetch client de la
liste entière via `GET /participations?scope=club`). Le premier est
résolu par `GET /club/roster/rank/{athlete_id}` (`athlete_repository.
club_rank`, chargé à la demande, seulement quand l'athlète retenu est hors
de l'aperçu de 12 — `null` sur 404, un état normal). Les seconds par deux
champs supplémentaires de `ClubSummary`, agrégés en SQL/Python côté
service (`club_service._bucket_podiums_by_discipline`/
`_bucket_composition`, `athlete_repository.club_composition`) :
`podiums_by_discipline` (par `event_type` **brut** — la famille normalisée,
`disciplineOf`, se recalcule côté client sur ce dictionnaire à quelques
entrées, jamais sur des participations) et `composition` (un couple
genre/catégorie par athlète du club entier, la catégorie venant de sa
participation la plus récente — `row_number()` en SQL, pas un maximum
calculé sur toutes ses participations chargées). Aucune des deux features
ne rouvre `/club` au transport intégral.

## `lib/api/` et le relais de cookies (#526, #586)

`lib/api/` — `client.ts` (appels `/api/v1`, `ApiError` porteur du statut HTTP),
`server.ts`, `sse.ts` (streaming import SSE). **Les trois fonctions de
`server.ts` relaient un cookie d'accès entrant** (#526) ; ce qui les distingue
est leur lecture du 401, et quels cookies elles envoient :

- `serverFetch` — lève une `ApiError` sur tout non-OK, 401 compris. Relais
  **minimal** depuis #586 : le cookie de session d'accès au site part, et
  depuis #1519 le cookie bénévoles (une saisie en attente n'est rendue qu'à
  lui) ; le reste du jar (SSO, PostHog…) est ignoré, voir plus bas.
  Conséquence : en rendu serveur, un bénévole n'est reconnu **que** par
  `tcn_benevole_session`. Un compte SSO qui porte `benevole_access:manage`
  sans ce cookie ne voit pas les saisies en attente sur `/courses/[id]` ni
  `/athletes/[id]`, et reçoit un 404 sur `/courses/[id]/participations/[pid]`
  d'une saisie en attente : la session SSO n'est pas relayée, pour ne pas faire
  varier la clé du Data Cache (#586). Il les voit toujours dans la file de
  validation, lue côté client par le rewrite `/api/*`.
- `serverFetchAuthed` — rend `null` sur 401 (anonyme est un état normal),
  lève sur le reste. Sert `/auth/me`, donc relaie le jar entier (hors
  `NAV_WIDTH_COOKIE`) : c'est la session SSO qu'elle a besoin de lire.
- `serverFetchAuthedRaw` — rend `false` sur 401, `true` sur 200, lève sur le
  reste, pour que la garde site distingue un refus avéré d'une panne. Relaie
  aussi le jar entier, par simplicité (pas de fenêtre de revalidation ici,
  donc pas de coût de cardinalité de clé de cache à réduire).

`serverFetch` a été cookie-libre jusqu'à #526, au nom du prérendu statique de
six pages publiques. #509 a rendu cette justification caduque (ces pages
vivent sous `app/(public_restricted)/`, dont le layout lit déjà le cookie
au-dessus d'elles : elles sont dynamiques de toute façon) **et** le relais
obligatoire — `require_site_access` garde `athletes`, `courses`,
`participations` et `stats`, fail-closed. Le relais manquant a fait planter
les six pages en 401 pendant la passe de rendu serveur dès qu'un mot de passe
site était configuré, soit React #441 / `app/error.tsx` sur tout le site
(#526, constaté sur la preview après la fusion de #513). Ne pas rouvrir
l'arbitrage « et si on remettait `serverFetch` sans cookie » : la seule route
qu'il vise et qui soit exemptée de la garde est `/auth/methods`, et son
caractère public tient à ce qu'elle **répond** sans session (FR-036 — c'est ce
qui permet à la garde `/admin` de distinguer « pas connecté » de « aucune
connexion possible »), pas à ce que l'appelant s'abstienne d'envoyer un
cookie.

Conséquence assumée sur #352 : relayer le jar entier faisait varier la clé du
Data Cache sur **chaque** cookie du navigateur, y compris ceux dont l'API ne
fait jamais rien (session SSO, PostHog…) — cassant, pour un même visiteur
rechargeant sa propre page, jusqu'au partage *intra-visiteur* que #526 avait
laissé intact. #586 réduit `serverFetch` au seul cookie que `require_site_access`
lit (`siteAccessCookieHeader` dans `server.ts`), ce qui restaure ce partage
intra-visiteur mais **ne restaure pas** le partage inter-visiteurs des 30 s :
le cookie de session d'accès au site porte lui-même l'horodatage de son
émission (`shared_password.sign_cookie`), donc reste unique par visiteur quel
que soit le filtrage côté front. Le résoudre demande de découpler la garde
d'accès de la clé de cache côté backend — une frontière de sécurité, à
concevoir avec soin et à mesurer avant d'y toucher (#586 en détaille les
pistes, aucune tranchée).
