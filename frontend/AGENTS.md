<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Architecture frontend

Next.js 16 (App Router), TypeScript strict, Tailwind CSS, shadcn/ui, consommant
`/api/v1` du backend. Tests Vitest + RTL verts. Build prod OK.

## Où lire quoi

Ce fichier se charge dès qu'un fichier de `frontend/` est lu : il ne porte que
les règles valables pour **toute** modification du front. Le détail d'un écran
ou d'une feature livrée vit dans `docs/frontend/`, lu sur renvoi. Lire la page
de la ligne concernée **avant** de toucher à ce qu'elle nomme.

| Avant de toucher à | Lire |
| --- | --- |
| `app/(public_restricted)/`, `acces`, `login`, `admin/acces`, textes légaux (`components/legal/`) | `docs/frontend/acces-et-routes.md` |
| `not-found.tsx`, `error.tsx`, `global-error.tsx`, `ErrorScreen`, un `loading.tsx` de fiche | `docs/frontend/ecrans-erreur.md` |
| `admin/droits`, `FeedbackTable`, `AdminIndex`, sous-sections et pastilles du sommaire, `MutationCache` d'`app/providers.tsx`, palette ⌘K (`AthletePicker`) | `docs/frontend/back-office.md` |
| `nav.config.ts`, `AppNav`, rail, barre basse mobile, tiroir, cookie `tcn-nav-expanded` (`app/layout.tsx`) | `docs/frontend/navigation.md` |
| Stock `tcn-athlete`, `useSelectedAthlete`, « Vous », « Ma saison » (`MaSaison`, `RappelPosition`), `AthleteHeaderActions`, `CourseAdminActions`/`CourseAdminPanel` | `docs/frontend/athlete-retenu.md` |
| Un paramètre d'URL (`?rank=`, `?scope`…), `/club`, `lib/api/server.ts` et ses cookies | `docs/frontend/donnees-serveur.md` |
| `TcnScrapeForm`, `useImportStream`, `ImportStreamProvider`, `ManualResultForm`, `ProviderDetector` | `docs/frontend/import.md` |
| Une des six listes publiques (`.tcn-table`, `.tcn-rowlink`), une bascule grille/cartes (`LigneCarte`), `test/setup.ts` (`defaultIgnore`), `test/cartes.ts` | `docs/frontend/tableaux.md` |
| Un graphique SVG (`Histogram`, `RankingEvolutionChart`), `lib/sport-colors.ts` | `docs/frontend/graphiques.md` |
| `next.config.ts` (`headers()`), `proxy.ts`, la CSP, `await connection()` d'`app/layout.tsx` | `docs/frontend/securite-entetes.md` |

## Règles transverses

- **Vocabulaire et registre de la copie publique** (#478) — l'objet que le
  club importe se dit **« épreuve »**, et c'est le seul mot que l'utilisateur
  lit ; `course` reste l'identifiant technique (route `/courses/`, champ
  `course`), il ne doit jamais apparaître dans un libellé. La personne se dit
  **« athlète »** dans toute copie destinée à l'utilisateur, admin et messages
  d'erreur du backend compris, jamais « coureur » (#1082) : le club importe
  aussi triathlons, swimruns et aquathlons. « Participant » reste pour compter
  les inscrits d'une épreuve (#343). Les identifiants (`coureurId`,
  `CACHES_ADMIN.coureurs`…) relèvent de #88, pas de cette règle. **Un lien pris
  dans une phrase est souligné au repos** (`underline underline-offset-2`) :
  `text-accent-ink` ne s'y distingue du texte voisin que par sa teinte
  (1,11:1 mesuré, WCAG 1.4.1). Un lien d'action isolé (« Ajouter une épreuve
  → », « Tout voir ») garde `hover:underline`. Le registre est le
  **vouvoiement** sur tout écran public — jamais de tutoiement dans une copie
  destinée à l'utilisateur.
- **Un squelette sur `isPending`, pas sur `isLoading`** (#1290). Après un échec
  (backend endormi), React Query suspend la relance tant que l'onglet n'a pas
  le focus ou que le réseau manque : `fetchStatus` passe à `paused`,
  `isLoading` retombe à `false` sans `error` ni `data`, et un écran qui teste
  `isLoading` puis `!data` affirme « aucun jeune » ou offre de créer une séance
  du jour qui existe. Tout écran à état vide teste `isPending` (#1294) ; son
  test le prouve avec `rendreAvecRelanceSuspendue` (`test/requete-suspendue.tsx`),
  ou hors ligne (`onlineManager`) pour une requête en `retry: false`, qui ne se
  suspend que là. Une requête soumise à `enabled` reste `isPending` tant
  qu'elle est désactivée : `isPending` n'y convient que si ce cas sort plus tôt
  ou démonte l'écran (`useBatchRuns`, `useBatchReport`, `useGroup`), sinon le
  squelette tourne à jamais. `isLoading` ne reste que là où aucun état vide
  n'en dépend.
- **Session lue sur un écran public rendu côté serveur : `useHydratedSession`**
  (#1090), jamais `useSession`. Le serveur n'a pas la session, mais React Query
  rend le cache dès le premier rendu client : si `/auth/me` a répondu avant une
  page streamée (fiches athlète et épreuve), les gestes réservés apparaissaient
  à l'hydratation et levaient l'erreur #418. Le rail, `UserMenu` et les écrans
  `/admin` (rendus client) gardent `useSession`.
- **Session et pouvoirs** (#240, #954). Le caractère superutilisateur de l'utilisateur connecté se déduit du
  croisement `session.roles` × liste des rôles, jamais de « il porte tous les
  codes », qui est faux. Et une session **illisible** n'est pas une session sans
  pouvoirs : l'erreur de `useSession` entre dans la garde de l'écran plutôt que
  de figer les cases en affirmant qu'on ne porte rien. Même règle pour le rail
  et `UserMenu` (#954) : ni « Se connecter » ni sections retirées sur une panne,
  le dernier état connu restant affiché. La query session ne réessaie que les
  pannes passagères (5xx, 429 court, réseau), trois fois au plus, par
  `SESSION_QUERY_DEFAULTS` que `Providers` pose via `setQueryDefaults` : les
  clients de test, en `retry: false`, n'en héritent pas.
- **Accessibilité et rendu, pièges déjà payés** (rappel ; le détail reste sur la
  page citée). Un anneau de focus est un trait opaque `--tcn-orange`, jamais le
  halo `ring-ring/50` seul (1,86:1). `bg-muted` et `--tcn-fill` valent
  exactement `--background` : ni squelette (`Skeleton` porte `--tcn-grey-300`)
  ni survol (prendre `--tcn-orange-08`) ne s'y voient (`back-office.md`). Une
  région `AnnonceStatut` se monte inconditionnellement, texte `""` au repos
  (`athlete-retenu.md`). La taille de police d'un champ TCN vit dans
  `.tcn-input`, jamais en ligne, sous peine de zoom iOS (`import.md`).
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
- **Gestes destructifs** (#499) — la couleur destructive **et** confirmation
  dès qu'un geste ferme un accès ou détruit une donnée. Neutre et sans
  confirmation pour tout ce qui se refait. La confirmation passe par
  `components/admin/DangerConfirm.tsx`, jamais par `window.confirm` — ce
  dernier n'est ni traduisible, ni stylable, ni testable au même titre. Deux
  formes d'appel : `<DangerConfirm>` quand le geste chiffre son impact avant
  d'agir, `useDangerConfirm()` — une promesse — pour les autres. La règle vaut
  **hors** back-office aussi : `app/benevoles/page.tsx` appelait `window.confirm`
  pour son garde-fou de brouillon sale jusqu'à #490 (revue UI/UX), qui l'a
  corrigé et a monté un second `DangerConfirmProvider` propre à cette route
  (`app/benevoles/layout.tsx`) — celui d'`app/admin/layout.tsx` ne couvre que
  le back-office.

  Quand le serveur refusera le geste et que le front le sait, **le dire avant
  le clic** : bouton inerte et raison visible, patron de `GroupsTable` et de
  `raisonDeNonSuppression` dans `RolePermissionsEditor`. Ne pas recalculer côté
  front une règle métier serveur qu'on ne fait que deviner : dans ce cas,
  laisser le message du refus faire le travail.

  Deux exceptions à la couleur du `variant` plein (`UserRolesTable`,
  `CoursesAdminTable`) et le critère de rayon d'action (`RevokeSessionsCard`) :
  `docs/frontend/back-office.md`.

  Les gestes sans retour dont la portée est la base entière vivent sur
  `/admin/maintenance`, jamais au pied d'un écran d'édition.

- **Deux bibliothèques, une frontière.** `components/tcn/` porte l'identité
  visuelle (tokens `--tcn-*`, Anton/Barlow, dégradé orange) ; `components/ui/`
  porte les primitives complexes bâties sur `@base-ui/react` — `dialog`,
  `select`, `dropdown-menu`, `popover`, `sheet`, `table`, `tooltip` — et le back-office,
  qui a besoin de leur densité. **Tout nouvel écran public prend `tcn/` ; une
  primitive accessible sans équivalent TCN se prend dans `ui/`, y compris depuis
  un écran public** (`AppNav` compose `ui/sheet` avec `tcn/Avatar`, `EventList`
  compose `ui/select` avec `tcn/Card` — c'est la composition attendue, pas un
  mélange ; `PendingBadge`, #270, est un nouvel ajout 100 % `tcn/`, exporté
  depuis `components/tcn/index.ts`, comme `ErrorScreen`, #464). La règle vaut
  pour les **ajouts** : **cinq** écrans publics existants tirent encore
  `ui/{card,button,badge,input}` — `ClubDashboard`, `ResultCard`,
  `ResultsFilters`, `StatusBadge`, `ManualResultForm`. Ils étaient sept
  (`app/error.tsx` en est sorti avec #464, sa réécriture déléguant à
  `tcn/ErrorScreen` ; `ProviderDetector` avec #492, qui lui a retiré son dernier
  `ui/badge`). Dette assumée, pas une
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

## Arborescence

- `app/` : App Router. Le groupe `app/(public_restricted)/` porte toutes les
  pages gardées par le mot de passe du site ; ses routes sœurs et leurs
  raisons sont dans `docs/frontend/acces-et-routes.md`.
- `components/` — `scrape/` (TcnScrapeForm, ProviderDetector),
  `results/` (ResultCard, ResultsList), `club/` (ClubDashboard, PodiumsList),
  `map/` (MapView), `dashboard/` (MaSaison, RecentCourses),
  `athletes/` (AthleteAdminPanel, ParticipationAdminActions — les gestes
  d'administration posés sur la page publique d'un athlète, #439 : ils prennent
  `tcn/` parce que c'est un écran public, et décident leur visibilité **dans le
  navigateur**, pouvoir par pouvoir, pour que la page reste rendue sans cookies),
  plus les deux bibliothèques de composants (règle « Deux bibliothèques, une frontière » plus haut).
- `lib/api/` — `client.ts` (appels `/api/v1`, `ApiError` porteur du statut HTTP),
  `server.ts`, `sse.ts` (streaming import SSE). Les trois fonctions de
  `server.ts` et les cookies qu'elles relaient : `docs/frontend/donnees-serveur.md`.
- `lib/types.ts` — types TypeScript partagés.
- `next.config.ts` et `proxy.ts` : en-têtes de sécurité et CSP, détaillés dans
  `docs/frontend/securite-entetes.md`.
- Déploiement : Vercel, variables `BACKEND_URL` + `API_URL`.
