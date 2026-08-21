<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Architecture frontend

Next.js 16 (App Router), TypeScript strict, Tailwind CSS, shadcn/ui, consommant
`/api/v1` du backend. Tests Vitest + RTL verts. Build prod OK.

- `app/` — App Router. **Mot de passe d'accès au site (#509)** : `app/(public_restricted)/`
  (groupe de routes, invisible dans l'URL — nommé en revue de #513 : ces pages
  restent **publiques côté RBAC**, seule leur porte d'entrée est restreinte, et
  un nom de dossier jamais rendu dans une URL relève de la couche technique)
  accueille tout ce qui exige le mot de
  passe partagé — `dashboard`, `resultats`, `athletes/[id]`, `courses/[id]`,
  `club`, `carte`, `ajouter` — gardé par `app/(public_restricted)/layout.tsx`, un
  appel serveur à `GET /api/v1/site-access/session`. Sur refus, ce layout rend
  `SiteAccessGate` **à la place** des enfants ; il ne redirige pas vers
  `/acces`. Un layout serveur ne reçoit en Next 16 ni le chemin demandé ni les
  `searchParams`, donc la redirection perdait la destination — un lien partagé
  vers `/courses/42` finissait sur le tableau de bord après la saisie du mot de
  passe (relevé en revue de #513). Sur place, l'URL ne bouge pas : le
  `router.refresh()` qui suit la connexion rejoue le layout, cookie en main, et
  rend la page demandée. Il n'y a donc aucun paramètre `next` à transporter, ni
  à valider contre la redirection ouverte. Les deux autres portes étaient
  fermées : `middleware.ts` est exclu par design (il ne constate que la
  présence du cookie, jamais sa validité) et `authInterrupts`/`unauthorized()`
  est encore expérimental en Next 16.3.1. `acces` (formulaire de mot
  de passe), `benevoles`, **`admin` et `login`** restent des routes **sœurs**,
  hors du groupe, jamais soumises à cette garde — `acces` reste le formulaire
  atteint en direct ou après déconnexion, d'où la prop `apres="accueil"` qui
  pousse vers `/` là où le rendu sur place se contente de rafraîchir ;
  `benevoles` garde sa propre garde client (`AccessGate`, #271) — et sa
  recherche d'athlètes passe par `GET /benevoles/athletes`, un jumeau gardé par
  le mot de passe bénévoles, puisqu'un bénévole n'a jamais celui du site (revue
  de #513). **`admin` et
  `login` sont hors du groupe** parce qu'ils forment, à eux deux, le seul chemin
  navigateur qui pose le tout premier mot de passe sur un déploiement neuf
  (`site_access_config` vide, garde fail-closed) : `admin` seul ne suffisait pas
  — sa propre garde renvoie un anonyme vers `/login`, et `login` rangé sous
  le groupe refermait la boucle en `/admin` → `/login` → `/acces` → impasse,
  aucun mot de passe n'existant encore à saisir (relevé en revue de #513, après
  la sortie d'`admin` en revue finale de #509). Le placement des deux côtés est
  désormais tenu par `app/routes-garde-site.test.ts`, un test de structure de
  dossiers : c'est une erreur de rangement, invisible à la lecture d'un fichier.
  Les deux gardent la garde qui les protégeait déjà, indépendante de #509
  (`app/admin/layout.tsx`, SSO/RBAC ; `login` n'expose que des boutons de
  fournisseur). La révocation
  d'urgence (#169) vit **dans** `admin/acces` : par adresse ligne à ligne,
  globale en carte de bas de page. Pas d'écran ni d'entrée de navigation
  dédiés — un unique bouton ne les justifiait pas. Jumelle de la CLI, la
  redondance étant le but : le back-office suppose une session, la CLI non.
- **Composition des rôles** (`admin/droits`, #240) — l'écran **n'invente aucun
  regroupement** : `GET /admin/permissions` rend l'inventaire déjà rangé par
  fonctionnalité, dans son ordre d'affichage, et `PermissionGrid` le reproduit
  tel quel (`<fieldset>`/`<legend>`, cases natives). Cinq pièges à ne pas
  rouvrir :
  - `PATCH` n'envoie que les champs modifiés — `permissions` remplace
    l'ensemble, donc l'envoyer sur un simple renommage purge les codes périmés
    en silence.
  - Un rôle `is_system` est **modifiable**, seule sa suppression est refusée.
  - La non-amplification vaut **aussi dans la modale de création**, et plus
    durement : `create_role` soumet à `assert_may_grant` l'ensemble complet des
    codes, `update_role` seulement la différence symétrique. D'où un `figes`
    calculé une fois pour l'écran et passé aux **deux** grilles.
  - `roles:read` et `roles:write` sont deux pouvoirs distincts. Le rail de
    navigation filtre sur le second mais n'est pas une garde : sans le test
    explicite, un porteur du premier obtient un éditeur d'apparence complète
    dont chaque geste finit en 403.
  - Le panneau compare et affiche `base`, l'état serveur sur lequel il a été
    ouvert — pas la prop. `roles` se rafraîchit sous un panneau resté
    ouvert, et se fier à la prop renvoie l'ensemble figé à l'ouverture, effaçant
    la recomposition d'un autre administrateur.

  Le caractère superutilisateur de l'utilisateur connecté se déduit du
  croisement `session.roles` × liste des rôles, jamais de « il porte tous les
  codes », qui est faux. Et une session **illisible** n'est pas une session sans
  pouvoirs : `useSession` ne réessaie pas, donc son erreur entre dans la garde de
  l'écran plutôt que de figer les cases en affirmant qu'on ne porte rien.
- **Gardes d'écriture du back-office** (#496) — un contrôle qui écrit teste
  **son** code de pouvoir avant de se rendre, jamais celui qui a ouvert l'écran :
  `session.data?.permissions.includes("x:y") ?? false`, puis `{peutX && …}`. Six
  écrans le font — `CoursesAdminTable`, `GroupsTable`, `CourseDuplicatesTable`,
  `AllowedEmailsTable`, `PendingProvidersTable`, `UserRolesTable`, ce dernier par
  le `peutAttribuer` de `lib/roles.ts`, l'unique question posée aux deux guichets
  de `roles:assign`. Une garde n'est **jamais** de la sécurité : elle évite
  d'offrir un geste qui rendrait 403, la règle restant au serveur. Deux suites, et
  leur arbitrage : un écran que la garde rend **entièrement** passif dit « Cet
  écran est en consultation : … demande le pouvoir « X » », avec le libellé de
  `core/permissions.py` — une page muette ne se distingue pas d'une page cassée ;
  une carte qui n'existe **que** pour un geste ne se rend pas du tout
  (`RevokeSessionsCard`, comme son bouton frère par adresse), l'écran restant
  agissant par ailleurs.
- **Navigation** — `components/layout/nav.config.ts` en est la description
  **unique** ; ajouter une destination y tient en une ligne. Deux échelons de
  visibilité, à ne pas confondre : `minRole` ne distingue qu'anonyme et
  connecté — `ROLE.ADMIN` est déclaré mais **inerte**, `rank` ne le vaut jamais,
  donc une entrée à cet échelon est invisible pour tout le monde. La finesse
  au-delà passe par `permission`, un code de `core/permissions.py` confronté à
  `session.permissions` (#115). Une section que le filtrage vide disparaît. Rien
  de tout cela ne garde une donnée : chaque ressource de l'API porte sa propre
  garde, et le rail ne fait qu'éviter d'annoncer un écran qui rendrait 403.
  **Un seul composant `Entree` rend une destination dans les deux états du
  rail** — seuls son style et ses enfants changent avec `expanded` (#428). Deux
  composants (une tuile repliée, une entrée dépliée) faisaient basculer React
  entre deux branches JSX : le `Link` était démonté puis remonté pour la même
  route, et son `IntersectionObserver` neuf retirait un **second prefetch RSC**.
  Le rendu serveur partant toujours du rail replié, la resynchronisation
  `localStorage` du montage suffit à déclencher la bascule. Même raison pour le
  `prefetch={false}` du logo du rail déplié : il double la route de
  « Tableau de bord ». Le test verrouille l'invariant en comptant les
  **montages** de `next/link` par route — le prefetch ne se reflétant sur aucun
  attribut du DOM. Deux bornes à connaître avant de s'y fier :
  - **L'invariant ne porte que sur la section racine.** Repliée, une catégorie
    n'offre qu'une tuile qui déplie, pas ses destinations : leurs `Link`
    n'existent pas, donc l'unification ne peut rien y réutiliser et ils
    remontent à chaque dépliage (mesuré : 2 montages de `/club/athletes` après
    un pliage/dépliage à la main, contre 1 pour `/resultats`). Sans conséquence
    à l'atterrissage, où ils ne montent qu'une fois. Le bouton de catégorie est
    resté hors périmètre de #428.
  - **La barre mobile garde ses doublons.** Son logo (`/dashboard`) et son
    bouton « Ajouter une course » doublent deux entrées du tiroir, exactement
    comme le logo du rail corrigé ici. Hors périmètre de #428 également : sous
    `md` le rail est en `display:none`, le coût réel est celui de l'ouverture
    du tiroir, repayé à chaque ouverture.
- **Sélecteurs d'URL : `pushState` ou `router.push`, et la question qui tranche**
  — *un rendu serveur lit-il ce paramètre ?* `?rank=` ne l'est par aucun, donc
  `RankTypeToggle` écrit l'URL par `window.history.pushState` et les trois
  consommateurs (`StatCardsRank`, `ClubPodiumKpi`, `PodiumsList`) recalculent en
  mémoire : zéro requête (#328). `?scope`, `?sports` et `?seasons` **le sont**
  (`app/club/page.tsx`, `app/dashboard/page.tsx`), donc `ScopeToggle` et
  `DisciplineToggle` gardent `router.push` — les basculer serait un bug
  silencieux, la page continuant de lire l'ancienne valeur sans erreur visible.
  L'asymétrie est voulue ; elle se re-tranche paramètre par paramètre, jamais
  par harmonisation.
- `components/` — `scrape/` (TcnScrapeForm, ProviderDetector, ImportProgress),
  `results/` (ResultCard, ResultsList), `club/` (ClubDashboard, PodiumsList),
  `map/` (MapView), `dashboard/` (StatCardsRank, RecentCourses), plus les deux
  bibliothèques de composants ci-dessous.
- **Deux bibliothèques, une frontière.** `components/tcn/` porte l'identité
  visuelle (tokens `--tcn-*`, Anton/Barlow, dégradé orange) ; `components/ui/`
  porte les primitives complexes bâties sur `@base-ui/react` — `dialog`,
  `select`, `dropdown-menu`, `popover`, `sheet`, `table` — et le back-office,
  qui a besoin de leur densité. **Tout nouvel écran public prend `tcn/` ; une
  primitive accessible sans équivalent TCN se prend dans `ui/`, y compris depuis
  un écran public** (`AppNav` compose `ui/sheet` avec `tcn/Avatar`, `EventList`
  compose `ui/select` avec `tcn/Card` — c'est la composition attendue, pas un
  mélange ; `PendingBadge`, #270, est un nouvel ajout 100 % `tcn/`, exporté
  depuis `components/tcn/index.ts`). La règle vaut pour les **ajouts** : sept
  écrans publics existants tirent encore `ui/{card,button,badge,input}` —
  `app/error.tsx`, `ClubDashboard`, `ResultCard`, `ResultsFilters`,
  `StatusBadge`, `ManualResultForm`, `ProviderDetector`. Dette assumée, pas une
  exception à arbitrer au cas par cas : les basculer coûte 485 lignes de rendu à
  re-vérifier pour zéro gain fonctionnel. `ManualResultForm` reste sur `ui/`
  malgré sa refonte (#270) — ses sélecteurs discipline/format/statut restent des
  `<select>` natifs plutôt que `ui/select`, cohérent avec le seul `<select>` que
  le fichier portait déjà avant la feature.
  Cinq primitives existent des deux côtés (`card`, `button`, `badge`, `input`,
  `dialog`) : ce n'est **pas** un doublon à résorber, elles servent de part et
  d'autre de cette ligne. Les deux qui étaient **100 % publiques** ont été
  basculées et leur version `ui/` supprimée — `initials-avatar` → `tcn/Avatar`,
  `stat` → `tcn/StatCard`. Un nouveau composant ne rejoue donc pas l'arbitrage,
  il lit la frontière. Relevé et mesures :
  `docs/superpowers/specs/2026-08-06-frontend-surengineering-audit.md`.
- `lib/api/` — `client.ts` (appels `/api/v1`, `ApiError` porteur du statut HTTP),
  `server.ts`, `sse.ts` (streaming import SSE). **Les trois fonctions de
  `server.ts` relaient les cookies entrants** (#526) ; ce qui les distingue est
  leur lecture du 401, pas le cookie :
  - `serverFetch` — lève une `ApiError` sur tout non-OK, 401 compris.
  - `serverFetchAuthed` — rend `null` sur 401 (anonyme est un état normal),
    lève sur le reste. Sert `/auth/me`.
  - `serverFetchAuthedRaw` — rend `false` sur 401, `true` sur 200, lève sur le
    reste, pour que la garde site distingue un refus avéré d'une panne.

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
  cookie. Conséquence assumée sur #352 : la clé du Data Cache inclut désormais
  l'en-tête `cookie`, donc la fenêtre de 30 s ne se partage plus entre
  visiteurs — elle profite encore à chacun sur sa propre navigation.
- `lib/types.ts` — types TypeScript partagés.
- **Deux projets vitest, `node` par défaut** (#508) — `vitest.config.ts` ne pose
  plus un environnement global : `jsdom` prend les `.test.tsx` et trois
  `.test.ts` nommés dans `GLOBS_JSDOM`, `node` prend tout le reste (le `include`
  par défaut de vitest **moins** ces globs, pour que la partition soit
  structurelle plutôt que tenue à la main). Un test à DOM oublié dans `node`
  échoue franchement sur « document is not defined » ; c'est le sens de
  l'orientation, l'oubli inverse étant silencieux. `test/environments.test.ts`
  vérifie que chaque fichier est réclamé par **exactement un** projet — ni zéro
  (jamais exécuté), ni deux. Il globe avec les **mêmes options que vitest**
  (`dot: true`), sans quoi un test posé sous un dossier en « . » lui serait
  invisible. #300 est la panne inverse — 52 fichiers *de trop*, ceux d'un
  worktree imbriqué — et c'est `exclude` qui la garde. Cibler un projet :
  `npx vitest run --project node`.
- `next.config.ts` — rewrites (`/api/*`, proxy PostHog) **et** `headers()` : les
  en-têtes de sécurité posés sur `/:path*`, rewrites comprises (#396). Ils ne
  couvrent que ce qui passe par Next : les backends Render étant joignables en
  direct, `backend/app/core/security_headers.py` en est le jumeau. La CSP n'y est
  **pas** — elle vit dans `proxy.ts` (#448) : `headers()` ne sert que des
  constantes, or un nonce se génère par requête.
- `proxy.ts` — le proxy Next (nom que Next 16 donne à l'ancien `middleware.ts`).
  Deux charges, dans cet ordre : la **CSP entière** (#448) et le marquage du
  cookie de présence (#427). Trois pièges :
  - La politique n'est **pas** scindée avec `next.config.ts` : deux en-têtes CSP
    sur une réponse se cumulent **par intersection**, chacun évalué séparément —
    ce serait deux sources de vérité et des rapports en double.
  - Elle est posée sur les en-têtes de la **requête** transmise au renderer,
    autant que sur la réponse : c'est là que Next lit le nonce. N'écrire que la
    réponse donne une politique correcte et un HTML sans nonce.
  - La CSP est le **tronc** de la fonction, le cookie un effet de bord : une
    sortie précoce la court-circuiterait pour la majorité des visiteurs.

  En `Content-Security-Policy-Report-Only` pour l'instant — le nonce est injecté
  quand même, donc l'observation vaut mesure ; le passage en mode bloquant est
  une issue de suite. Corollaire : `await connection()` dans `app/layout.tsx`
  rend **toute** route dynamique, un nonce ne pouvant exister dans une page
  générée au build. Ne pas y substituer `dynamic = "force-dynamic"`, qui
  annulerait le cache de fetch de #352.
- Déploiement : Vercel, variables `BACKEND_URL` + `API_URL`.

