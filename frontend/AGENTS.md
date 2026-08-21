<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Architecture frontend

Next.js 16 (App Router), TypeScript strict, Tailwind CSS, shadcn/ui, consommant
`/api/v1` du backend. Tests Vitest + RTL verts. Build prod OK.

- `app/` — App Router. **Mot de passe d'accès au site (#509)** : `app/(protege)/`
  (groupe de routes, invisible dans l'URL) accueille tout ce qui exige le mot de
  passe partagé — `dashboard`, `resultats`, `athletes/[id]`, `courses/[id]`,
  `club`, `carte`, `ajouter` — gardé par `app/(protege)/layout.tsx`, un
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
  `(protege)` refermait la boucle en `/admin` → `/login` → `/acces` → impasse,
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
- **Navigation** — `components/layout/nav.config.ts` en est la description
  **unique** ; ajouter une destination y tient en une ligne. Deux échelons de
  visibilité, à ne pas confondre : `minRole` ne distingue qu'anonyme et
  connecté — `ROLE.ADMIN` est déclaré mais **inerte**, `rank` ne le vaut jamais,
  donc une entrée à cet échelon est invisible pour tout le monde. La finesse
  au-delà passe par `permission`, un code de `core/permissions.py` confronté à
  `session.permissions` (#115). Une section que le filtrage vide disparaît. Rien
  de tout cela ne garde une donnée : chaque ressource de l'API porte sa propre
  garde, et le rail ne fait qu'éviter d'annoncer un écran qui rendrait 403.
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
  `server.ts` (`serverFetch`, plus `serverFetchAuthed`/`serverFetchAuthedRaw`
  qui relaient les cookies), `sse.ts` (streaming import SSE). `serverFetch`
  reste **distinct**, volontairement cookie-libre : la justification d'origine
  (« six pages publiques en rendu serveur, lire les cookies les rendrait
  toutes dynamiques ») est devenue **historique** avec #509 — ces six pages
  vivent désormais sous `app/(protege)/`, dont le layout lit déjà le cookie du
  mot de passe site au-dessus d'elles, donc elles sont dynamiques de toute
  façon. L'exemption elle-même ne bouge pas : `serverFetch` reste la fonction
  à utiliser pour tout appel qui n'a jamais eu besoin de relayer un cookie
  (`/courses`, `/stats`, `/auth/methods`…, cette dernière volontairement
  publique — c'est ce qui permet à la garde `/admin` de distinguer « pas
  connecté » de « aucune connexion possible », FR-036), la distinction portant
  désormais sur le **besoin de cookie**, plus sur le rendu statique.
- `lib/types.ts` — types TypeScript partagés.
- `next.config.ts` — rewrites (`/api/*`, proxy PostHog) **et** `headers()` : les
  en-têtes de sécurité posés sur `/:path*`, rewrites comprises (#396). Ils ne
  couvrent que ce qui passe par Next : les backends Render étant joignables en
  direct, `backend/app/core/security_headers.py` en est le jumeau. La CSP n'y est
  pas — elle demande un `nonce` pour Next.js et PostHog.
- Déploiement : Vercel, variables `BACKEND_URL` + `API_URL`.

