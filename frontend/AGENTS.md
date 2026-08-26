<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Architecture frontend

Next.js 16 (App Router), TypeScript strict, Tailwind CSS, shadcn/ui, consommant
`/api/v1` du backend. Tests Vitest + RTL verts. Build prod OK.

- **Vocabulaire et registre de la copie publique** (#478) — l'objet que le
  club importe se dit **« épreuve »**, et c'est le seul mot que l'utilisateur
  lit ; `course` reste l'identifiant technique (route `/courses/`, champ
  `course`), il ne doit jamais apparaître dans un libellé. Le registre est le
  **vouvoiement** sur tout écran public — jamais de tutoiement dans une copie
  destinée à l'utilisateur.
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
- **Trois écrans d'absence et de panne** (#464, `ETAT-1`) — `app/not-found.tsx`,
  `app/error.tsx`, `app/global-error.tsx`, la microcopie tenue une seule fois
  dans `components/tcn/ErrorScreen.tsx` que les deux derniers partagent. Quatre
  points qui se re-cassent facilement :
  - **`retry()`, pas `reset()`** (prop stable en Next 16.3). `reset()` re-rend
    sans refaire le fetch, donc « Réessayer » ne pouvait pas guérir la panne la
    plus fréquente ici, le réveil à froid du backend Render.
  - **`error.message` ne s'affiche jamais.** Next.js y substitue un paragraphe
    anglais en production, et il peut porter des détails serveur en
    développement. Seul le `digest` sort, nommé « code de l'incident » pour
    qu'un signalement soit rattachable.
  - **`FeedbackButton` seulement dans `global-error.tsx`.** Le layout racine
    survit à `error.tsx` et à `not-found.tsx`, son bouton flottant y est donc
    déjà ; il ne survit pas à `global-error.tsx`, qui le remplace — d'où aussi
    l'import explicite de `globals.css`, le `<html lang="fr">`, et les trois
    variables `--font-*` redéclarées : `--tcn-font-body` vaut
    `var(--font-barlow), system-ui, …`, et sans `--font-barlow` **toute** la
    déclaration devient invalide à la substitution (la queue `system-ui` n'est
    jamais atteinte), donc le dernier filet du site s'afficherait en serif.
  - **La sortie de l'écran de panne est un `<a>`, et pas vers `/dashboard`.** La
    frontière ne se vide que si le **chemin change** ; `/dashboard` est l'accueil
    (`app/page.tsx` y redirige) et la page la plus sujette au réveil à froid, donc
    un `next/link` vers elle depuis sa propre panne serait un clic sans effet.
  - **`not-found.tsx` sert deux cas** : les `notFound()` des trois routes
    dynamiques *et* toute URL non matchée. Sa copie doit rester vraie des deux,
    donc « cette page », et l'épreuve supprimée en cause probable et non
    affirmée. Ses sorties évitent `/carte`, masquée du rail (#10, #28) — à
    rouvrir quand ces deux-là lèvent le masque.

  Ce que ces trois écrans ne couvrent pas : la coquille 500 statique de Next
  (`_global-error.html`), qui reste son texte anglais sans `lang`, et un rendu
  serveur en échec dont le corps HTML part vide, les frontières étant rendues
  côté client.
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
- **Retours utilisateurs : une file, pas une liste** (#500, ADM-10) —
  `FeedbackTable` ouvre sur « Nouveau » seul et filtre **côté serveur**
  (`?status=`), les décomptes venant de `GET /admin/feedback/counts`. Quatre
  points qui se re-cassent séparément :
  - **La barre de filtres reste montée dans tous les états** — chargement,
    refus, résultat vide —, patron de `CoursesAdminTable` : la vue par défaut
    est filtrée, donc la retirer enfermerait un administrateur sans nouveaux
    signalements hors des trois autres statuts.
  - **Le compteur, c'est le nombre porté par chaque entrée de la barre**, pas
    une phrase au-dessus : celle-ci redirait le même chiffre, et pour un statut
    sur quatre seulement.
  - **Un seul contrôle de statut par ligne, et il est coloré.** Qui porte
    `feedback:manage` voit un `<select>` habillé du couple aplat/encre du
    statut ; les autres, un `Badge` du même couple. Un badge *et* un sélecteur
    côte à côte diraient deux fois la même valeur — et sans couleur du tout,
    « Nouveau » et « Ignoré » ont exactement le même poids visuel, ce que
    l'audit reprochait. Les couples viennent du thème pour la raison de
    `BatchRunList` : les variantes génériques de `Badge` ne tiennent pas 4,5:1
    sous 12 px.
  - **La modale de détail est rendue hors de la cascade d'états**, pas dans la
    seule branche nominale : instruire depuis elle le dernier signalement d'un
    filtre vide la liste, et la modale disparaîtrait sous les doigts avant la
    promotion en issue. Symétriquement, « aucun retour utilisateur » ne
    s'affirme que si les décomptes le disent — une vue **filtrée** vide ne
    prouve rien sur la base, et le comptage peut échouer.
  - **Le contrôle en ligne n'est jamais `disabled` pendant sa requête** —
    `aria-busy` et une opacité, la ré-entrée gardée dans le gestionnaire : un
    navigateur retire le focus d'un contrôle désactivé, et l'écran existe pour
    enchaîner les gestes au clavier. Quand le changement fait quitter la vue
    filtrée à la ligne, le focus est reposé sur la puce du filtre courant.
  - **`--tcn-fill` ne sert pas de survol** : il vaut exactement `--background`
    (`#f4f3f0`), donc un survol à 1,00:1 — même piège que le `bg-muted` des
    squelettes. Les puces prennent `--tcn-orange-08`, et `cursor-pointer`,
    norme de `ui/button.tsx`.
  - **`queryKeys.feedbackCounts()` vit sous le préfixe `["admin-feedback"]`**,
    celui de la liste : un changement de statut périme les deux, et
    l'invalidation existante les emporte alors d'un seul geste.
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

  Deux exceptions à la couleur portée par le `variant` plein, chacune
  commentée sur place : la croix de retrait de rôle d'`UserRolesTable`, `ghost`
  au repos et `destructive` au survol et au focus — une croix par badge,
  plusieurs badges par ligne ; un bouton-icône dans un tableau dense qui pose
  la couleur destructive par une teinte posée à la main plutôt que par le
  variant plein, pour ne pas écraser ses voisins (`CoursesAdminTable`, la
  corbeille et son crayon jumeau). Un critère à part, de rayon d'action et non
  de rendu : un geste réparable mais dont la portée est l'ensemble des comptes
  se signale en destructif malgré tout, variant plein compris
  (`RevokeSessionsCard`, « Fermer toutes les sessions », qui déconnecte tout le
  monde, vous compris — face à « Fermer les sessions » d'une seule adresse, qui
  reste neutre).

  Les gestes sans retour dont la portée est la base entière vivent sur
  `/admin/maintenance`, jamais au pied d'un écran d'édition.

- **Sommaire `/admin` et source unique des titres** (#497, ADM-2/ADM-6) —
  `/admin` n'est plus une impasse : `AdminIndex` rend une tuile par écran du
  back-office, filtrée par `estVisible`, **la même règle que le rail** — un
  écran annoncé d'un côté et tu de l'autre est un écran dont on ne sait plus à
  qui il s'adresse. Le titre **et** la phrase d'un écran d'administration vivent
  une seule fois, dans `nav.config.ts`, et sont rendus aux deux endroits par
  `ecran(href)` : la page les passe à son `PageHeader`, la tuile les affiche.
  Les tenir en double les avait déjà fait diverger (le rail annonçait « Gestion
  des courses » quand l'écran s'intitulait « Épreuves »). `ecran()` **lève** sur
  une entrée sans phrase : c'est une erreur de configuration, pas un cas à
  couvrir en silence, et `nav.config.test.ts` la rattrape avant l'écran.
  Corollaire du même lot : plus aucune entrée d'administration sans
  `permission`, « Épreuves » ayant été la dernière — donc la seule proposée à
  qui n'y peut rien faire. Enfin, `/admin/batches` **est** l'écran de
  `batch:run`, et c'est `BatchRunList` qui porte la garde de `batch:read` : sans
  ce pouvoir, la liste dit ce qui manque au lieu de partir en 403, et
  `BatchLauncher` **dit** qu'il lance à l'aveugle plutôt que de laisser
  `enCours` valoir silencieusement `false` — le refus du second lancement reste
  au serveur (409). Trois points relevés en `ui-ux-review` du même lot, valables
  bien au-delà : le **surtitre** vient lui aussi de la section (`ecran()` le
  rend), sans quoi quatre écrans rangés sous « Administration » annonçaient
  « Maintenance » ou « Exploitation » à l'arrivée ; un anneau de focus se pose
  en **trait opaque** `--tcn-orange` (3,32:1 sur `--tcn-paper`), jamais en halo
  `ring-ring/50` seul, qui tombe à 1,86:1 ; et `Skeleton` porte
  `--tcn-grey-300` depuis que `bg-muted` s'est révélé être **exactement**
  `--background` (`--tcn-fill` = `--tcn-paper` = `#f4f3f0`, ratio 1,00:1) —
  `animate-pulse` n'animant que l'opacité, tous les squelettes du front étaient
  invisibles.
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
- **L'athlète retenu ne franchit pas la frontière serveur : pas de cookie
  miroir** (#467 — arbitrage du cluster, il vaut aussi pour #502, #503, #504).
  Le stock `tcn-athlete` vit en `localStorage` ; un écran qui s'y adapte le lit
  **côté client** par `useIsSelectedAthlete(id)`
  (`components/layout/AthletePicker.tsx`, à côté du stock), jamais par une copie
  en cookie relue en rendu serveur. Trois raisons, dans cet ordre.
  - **Aucun rendu serveur n'en a besoin.** Les quatre usages du cluster sont de
    la mise en avant (pastille, liseré, ancre) et un rapprochement de chiffres
    que l'API publique sert déjà : rien ne se filtre, ne se trie ni ne se
    récupère sur cette valeur. Un cookie serait un transport sans destinataire.
  - **Le coût de cache est réel dès qu'on sort du profil.** Ce n'est pas
    `/athletes/[id]` qui le paierait — le build le donne `ƒ`, `serverFetch`
    l'appelant en `no-store` —, c'est le cookie **en tant que transport** :
    `/dashboard`, `/club` et `/ajouter` tournent sur la fenêtre de revalidation
    de 30 s mesurée par #352, et un rendu qui dépend d'un cookie par visiteur
    n'est plus partageable. C'est le même raisonnement qui a déjà valu à
    `serverFetch` de ne pas relayer les cookies (voir son commentaire dans
    `lib/api/server.ts`) : #502 est exactement la page concernée.
  - **Un miroir, c'est deux stocks à tenir synchronisés**, dont un éditable par
    l'utilisateur et un envoyé au serveur à chaque requête, sans qu'aucune
    donnée personnelle n'ait à y aller.

  Le prix, assumé : `useSyncExternalStore` rend `false` au serveur, donc le
  signifiant d'état n'est **jamais dans le HTML initial** et apparaît à
  l'hydratation — la boîte qui le porte réserve sa place (`.tcn-avatar-frame`)
  pour que son apparition ne déplace rien. Seul un besoin **serveur** authentique
  — une requête API qui dépendrait de l'athlète retenu — rouvrirait
  l'arbitrage ; de la mise en avant, non.
- **Les trois surfaces qui propagent l'athlète retenu** (#503) — la pastille
  « Mes résultats » de `/resultats`, la ligne marquée « Vous » et le bouton
  « Aller à ma ligne » du classement d'épreuve, le raccourci de la tuile du
  rail. Les deux surfaces de contenu — `/resultats` et le classement — lisent
  `useSelectedAthlete()` (`components/layout/AthletePicker.tsx`, à côté de
  `useIsSelectedAthlete`) ; `AppNav` garde sa propre lecture (`useState` +
  `readAthlete()` + l'écouteur de `ATHLETE_CHANGED_EVENT`), son état portant
  aussi `expanded` et le raccourci clavier — une duplication assumée, non
  résorbée, hors du périmètre de #503. Le snapshot de `useSelectedAthlete()`
  est **mémorisé sur la chaîne brute du stock** :
  `readAthlete()` reconstruit un objet à chaque lecture, et le rendre tel quel
  fait rendre `useSyncExternalStore` en boucle. Trois invariants :
  **aucun filtre n'est appliqué au chargement** — chaque geste demande un clic
  et se révoque par une commande déjà à l'écran (le chip `Athlète : … ✕`, le
  bandeau « … · Effacer » de #485) ; **le liseré orange gauche du classement
  reste réservé à `is_tcn`**, d'où le fond `--tcn-orange-08` et le chip
  « Vous », qui porte le sens que la couleur seule ne peut pas porter
  (WCAG 1.4.1) ; et **« Aller à ma ligne » cherche, il ne saute pas** —
  l'ordre d'affichage est une propriété de la requête SQL depuis #163, le
  front ne sait pas calculer « ma page », et `q` y mène à coût backend nul.

  **Constaté sur #502**, premier consommateur réel de l'arbitrage : la bande
  « Ma saison » lit le stock par `useSelectedAthlete()` — pendant de
  `useIsSelectedAthlete`, ajouté à côté de lui dans `AthletePicker.tsx`,
  mémoïsé sur la chaîne brute du `localStorage` plutôt que sur l'objet
  reconstruit — puis appelle `apiClient.getAthlete(id, { seasons,
  federal_only })`. C'est le **premier appel navigateur** de `/athletes/{id}`,
  jusque-là lue par le seul rendu serveur de la fiche athlète ; les deux
  filtres y ont été ajoutés **optionnels et neutres par défaut**, pour que
  « mes » chiffres se comptent sur exactement la même base que ceux du club
  rendus au-dessus. Le besoin serveur qui aurait rouvert l'arbitrage n'est
  donc pas apparu : le filtrage est passé dans la requête, pas dans le rendu,
  et `/dashboard` garde sa fenêtre de revalidation de 30 s partagée entre tous
  les visiteurs. Une dimension n'est **pas** partagée, elle : le club se
  compte sur `for_stats(club_only=True)` (`tcn_clause`), quand
  `list_for_athlete` n'a délibérément aucune clause de club (FR-019,
  `backend/app/api/AGENTS.md`) — une participation dont le club diffère ou
  est vide compte donc pour l'athlète sans compter pour le club. Assumé, pas
  réglé : #503 et #504 en hériteront.

  Deux règles s'attrapent en passant, valables pour #503 et #504 : le podium
  d'un athlète doit se calculer sur le **même `?rank=`** que les compteurs
  club (`lib/utils/club-aggregate.ts`, `bestRank`/`isPodium`, miroir de
  `stats_service._rank_counters` — `ma-saison.ts` y délègue depuis la revue
  finale de #502), et un bloc client monté au-dessus de contenu serveur
  réserve sa hauteur dès l'hydratation — sinon le retour du fetch ajoute un
  **second** décalage au premier.

  Une troisième, trouvée en revue de #502 : une région `AnnonceStatut` se
  monte **inconditionnellement**, texte vide (`""`) quand il n'y a rien à
  annoncer, jamais insérée au moment où son texte apparaît — une région ARIA
  live n'annonce que les changements observés **après** son enregistrement, et
  une région déjà pleine à l'injection est le cas que NVDA, JAWS et VoiceOver
  laissent tomber. Les tests jsdom passent quand même : ils ne vérifient que
  le texte du DOM. Tous les autres consommateurs du dépôt le faisaient déjà
  (`StatCardsRank.tsx`, `PodiumsList.tsx`, `EventList.tsx`,
  `RaceFinishers.tsx`) ; `MaSaison.tsx` avait été le seul à s'en écarter, et la
  revue l'a rattrapé.
- **Rail replié, cookie de largeur, nav mobile** (#482) — le rail replié
  porte désormais un monogramme texte lié à `/dashboard` en plus du bouton de
  pliage (l'en-tête passe en colonne à cet état, faute de place pour les
  deux côte à côte), et ses six `title` sont remplacés par
  `components/ui/tooltip.tsx` (`@base-ui/react/tooltip`, délai ramené à
  0 ms — l'audit reprochait le délai natif d'~1 s, pas seulement son absence
  au clavier/tactile). Une section réduite à une seule destination livrée
  rend directement son `Entree` au lieu du bouton dépliant — « Club » tenait ce
  rôle jusqu'à #487, qui lui a livré `/club` en seconde destination ; la branche
  reste vivante par les pouvoirs (« Administration » s'y réduit pour qui n'en
  porte qu'un). La largeur du rail (`tcn-nav-expanded`) est désormais un
  **cookie**, lu par `app/layout.tsx` avant la peinture plutôt qu'un
  `localStorage` relu au montage — la seule exception documentée au refus de
  miroir cookie de #467, parce que le besoin serveur y est authentique et
  qu'aucun `fetch()` vers `/api/v1` n'est concerné. Sous `md`, une barre
  basse fixe porte les destinations dont `minRole === ROLE.ANON` (calculée
  dynamiquement, jamais en dur) — quatre depuis #487, d'où le `labelCourt` de
  `nav.config.ts` : il ne change que le **texte visible**, le nom accessible du
  lien restant `label`, « Athlètes » ne distinguant pas deux écrans à
  l'oreille ; le hamburger ne garde en priorité que les sections
  `minRole > ROLE.ANON` et les deux actions primaires, **sauf** repli (#621) :
  la barre basse est masquée pendant que le tiroir est ouvert (le `Sheet`
  passe par-dessus), donc un visiteur sans section privée — anonyme, ou
  connecté sans aucun pouvoir d'administration, la quasi-totalité des
  adhérents — se retrouvait sans aucune destination à l'écran une fois le
  tiroir ouvert. `sectionsTiroir` (`AppNav.tsx`) retombe sur l'ensemble des
  sections dès que `sectionsPrivees` est vide, pour ne jamais présenter un
  tiroir sans catégorie ; le doublon avec la barre basse ne se produit donc
  que pour ce cas-là, jamais pour qui a déjà une section privée à y voir. Le
  pied du tiroir ne ferme plus au clic : `UserMenu` ferme lui-même via
  `onNavigate`, au moment où la navigation a réellement lieu (immédiat pour la
  connexion, après le succès de la mutation pour la déconnexion) — jamais au
  clic de « Se déconnecter » seul, qui couperait l'affichage de son état
  d'attente.
- **`/club` n'envoie plus les participations dans la charge RSC** (#487 → #581) —
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
- **Ce que l'import dit pendant, et après** (#491) — trois points qui se
  re-cassent séparément, et qui tiennent tous à une seule donnée : la **cause**
  de l'échec, que `importEventStream` jette dans une `ApiError` plutôt que dans
  une `Error` nue.
  - `useImportStream` expose `errorStatus` : `null` = le flux s'est ouvert
    avant d'annoncer l'échec, donc la page **est** en cause ; `0` = coupure
    réseau ; sinon le statut HTTP du refus. `TcnScrapeForm` en tire trois
    écrans — plafond de débit (décompte sur `retryAfter`, l'en-tête
    `Retry-After` de `deps.py`), service muet (« Réessayer »), lecture
    impossible (saisie manuelle). **`reportPendingProvider` n'est appelé que
    dans le troisième** : signaler un lien Klikego parfaitement supporté au
    back-office parce que le plafond horaire était atteint polluait
    `pending-providers` sans qu'aucun écran ne le dise.
  - Le bilan rend les **cinq** chiffres (`imported`, `updated`, `skipped`, et
    les séries du fan-out) et la liste des `failures`. Une série perdue dégrade
    le statut de l'alerte en `warning` : un import où 3 séries sur 12 ont
    échoué ne s'annonce pas en vert. `ImportProgress`, qui savait déjà tout
    afficher mais qu'aucun écran n'importait, a été **supprimé** plutôt que
    remis en service — son rendu était en `ui/` quand l'écran est en `tcn/`.
  - Quatre pièges relevés en revue, qui se re-cassent séparément. La garde du
    signalement porte sur l'URL **soumise** (`soumiseRef`), jamais sur l'état
    vivant du champ : corriger son adresse après un échec envoyait sinon un
    `reportPendingProvider` **par frappe**. L'horloge de la minuterie sert aussi
    le décompte du 429, `running` étant déjà `false` quand l'alerte s'affiche —
    sans quoi « Réessayez dans 3 minutes » l'affirmait encore dix minutes plus
    tard. `isDuplicate` teste `!partiel` en tête, faute de quoi un import tout
    en cache **plus** une série perdue affichait « déjà enregistrés » et
    escamotait la liste des manques. Et `failures[].reason` arrive du backend en
    `str(exc)` — anglais, technique, parfois une URL brute : `causeSerie()` le
    traduit en l'une des quatre causes qui changent le geste, le texte d'origine
    restant aux logs.
  - Le scrape n'a **rien** à rapporter avant son premier participant : barre
    indéterminée (`.tcn-barre-indeterminee`) **et** minuterie, la seconde
    restant la seule preuve de vie sous `prefers-reduced-motion`, qui fige la
    première. « Annuler l'import » coupe le flux par `AbortController`, et
    `cancel()` lève le verrou sans attendre que le flux veuille bien finir —
    un scrape muet retiendrait sinon le formulaire indéfiniment. Un
    `beforeunload` prévient tant que l'import tourne : fermer l'onglet coupe
    la SSE à mi-course.
- **Le champ URL et le verdict qui vit sous lui** (#492) — trois points à ne pas
  rouvrir séparément :
  - **La taille de police d'un champ TCN vit dans `.tcn-input`, jamais en
    ligne.** 16px sous `md`, 15px au-delà : sous 16px, iOS Safari zoome à la
    mise au point et l'écran fait un bond sur le geste fondateur de l'app. Une
    valeur en ligne rendrait la media query inerte sans que rien ne bronche —
    `app/globals.test.ts` garde les deux crans.
  - **Un seul verdict, à un seul endroit.** `ProviderDetector` **est** la ligne
    sous le champ, et ses trois états s'excluent : au repos les chronométreurs
    pris en charge (depuis `useProviders()`, jamais une liste tenue à la main —
    la précédente avait divergé), sinon le fournisseur reconnu ou l'absence de
    reconnaissance avec sa sortie « Saisir à la main ». Le badge rouge et
    l'alerte jaune disaient le même verdict en même temps, pendant que le bouton
    principal restait actif et promettait l'inverse. Sa hauteur est réservée
    (`minHeight`), sans quoi le débounce déplace le bouton pendant la frappe.
  - **`providerUnsupported` garde le bouton *et* `submit()`.** Le `disabled` seul
    laisse la touche Entrée lancer l'import que le verdict vient d'exclure.
- `components/` — `scrape/` (TcnScrapeForm, ProviderDetector),
  `results/` (ResultCard, ResultsList), `club/` (ClubDashboard, PodiumsList),
  `map/` (MapView), `dashboard/` (StatCardsRank, RecentCourses),
  `athletes/` (AthleteAdminPanel, ParticipationAdminActions — les gestes
  d'administration posés sur la page publique d'un coureur, #439 : ils prennent
  `tcn/` parce que c'est un écran public, et décident leur visibilité **dans le
  navigateur**, pouvoir par pouvoir, pour que la page reste rendue sans cookies),
  plus les deux bibliothèques de composants ci-dessous.
- **« La géométrie dans le SVG, les textes en HTML »** (#480, RESP-2) — pour
  tout `viewBox` fixe étiré à `width: 100%` (`Histogram`, `RankingEvolutionChart`) :
  aucune unité CSS ne fige la taille d'un `<text>` SVG dans ce cas, il est mis à
  l'échelle avec le `viewBox` et tombe à ~3,5 px sur un iPhone SE. D'où
  `preserveAspectRatio="none"` + une hauteur en px, et les libellés posés en
  HTML autour. Corollaire qui a coûté une ronde de correction : une abscisse
  HTML s'exprime en **pourcentage d'une rangée absolue dont la largeur épouse
  celle du SVG**, jamais du conteneur — celui-ci porte la gouttière des
  graduations, contre laquelle un `%` se résoudrait, gouttière comprise.
- **Les six listes publiques sont des tableaux dont la géométrie reste une
  grille** (#481, `A11Y-3`) — `RaceFinishers`, `EventList`, `EventsTable`,
  « Derniers résultats enregistrés » (`ajouter`), `RecentCourses` et « Top
  clubs » (`courses/[id]`). Quatre points qui se re-cassent séparément.
  - **Les rôles ARIA doublent les balises, et ce n'est pas décoratif.**
    `.tcn-table` (`globals.css`) surcharge `display` sur `<table>`, `<thead>`,
    `<tbody>` — la géométrie mêle pistes fixes, pistes souples et `column-gap`,
    qu'une disposition de tableau native n'a pas, et la retraduire rouvrirait le
    dessin des six listes. Or surcharger `display` peut retirer la sémantique de
    tableau à l'aide technique : les `role="table"/"rowgroup"/"row"/
    "columnheader"/"cell"` la redéclarent. Les retirer casse WCAG 1.3.1 sans
    qu'aucun test de rendu bronche.
  - **La ligne n'est jamais la cible.** Un rôle ARIA **remplace** le rôle
    implicite : un `<a role="row">` cesserait d'être annoncé comme un lien —
    exactement le défaut que #481 corrige sur le classement, où la ligne était un
    `role="button"` + `router.push` (donc aucun `href` dans le HTML, aucun
    partage, aucun nouvel onglet). La cible vit dans la cellule qui porte le nom
    de la ligne et couvre la ligne par le `::after` de `.tcn-rowlink__cible` ;
    `.tcn-rowlink` est passée du lien au `<tr>`, qui porte `position: relative`,
    le survol et l'anneau de focus (`:has(.tcn-rowlink__cible:focus-visible)`).
    **Un seul arrêt clavier par `<tr>`**, jamais un `href` par cellule — c'est
    testé liste par liste. La ligne de groupe d'`EventList` reste un
    `<button aria-expanded>` : elle déplie, elle ne navigue pas.
  - **Aucun `overflow: hidden` sur une cellule qui porte la cible.** Il rogne les
    deux voiles absolus (couverture du lien, attente), et la ligne cesse d'être
    cliquable hors du mot. La cellule prend `minWidth: 0` — même effet sur la
    piste `1fr` — et l'ellipsis descend sur un `<span>` intérieur.
  - **Les états vides suivent le comportement d'origine, liste par liste.**
    `RaceFinishers`, `ajouter` et « Top clubs » gardent leur en-tête et rendent
    l'`EmptyState` **après** le `</table>` ; `RecentCourses`, `EventsTable` et
    `EventList` ne rendent aucun tableau, ils masquaient déjà leur en-tête. Ne
    pas harmoniser : faire apparaître ou disparaître une en-tête est un
    changement d'apparence.

  Deux corollaires. `EventsTable` groupe chaque entrée dans **son** `<tbody>`,
  qui reprend le trait de séparation porté jusque-là par un `<div>` enveloppant
  qu'un tableau n'autorise plus — l'invariant de #270 (pas de trait pour une
  ligne en attente sans sous-ligne) y survit tel quel ; et
  `ParticipationAdminActions` porte lui-même sa `<tr>` via `colonnes`, sinon un
  visiteur sans pouvoir hériterait d'une ligne vide par épreuve.

  **L'attente de la ligne cliquée n'existe que sur le classement**, et c'est
  assumé : c'est la seule des six listes dont la destination est une route
  dynamique lente (0,67 à 1,43 s mesurées). Elle vient de `useLinkStatus()` lu
  par un enfant du `<Link>`, ce qui **impose** `prefetch={false}` — la phase
  d'attente est sautée sur une route déjà préchargée. Et c'est un **filet en
  pied de ligne**, jamais une nappe par-dessus : un descendant positionné passe
  au-dessus du contenu en flux de toutes les cellules, et la première version
  faisait tomber le texte à 2,50:1 (`--tcn-ink`) et 1,74:1 (colonne Club), sous
  le plancher WCAG 1.4.3 — tout en étant **invisible** sur la ligne survolée,
  dont le `:hover` pose déjà ce fond. Étendre l'attente aux cinq autres listes
  demande de refaire ce calcul, pas de recopier le composant.

  Design complet : `specs/20260825-103900-tables-liees/`.

- **Tableaux repliés en cartes sous leur seuil** (#461, `RESP-1`) — quatre
  écrans rendent **deux arbres**, la grille et une liste de cartes, que deux
  classes Tailwind font alterner en CSS pure : `hidden min-[Npx]:block`/
  `min-[Npx]:hidden` pour le classement (plancher 1 080 px, seuil 1 237 px), la
  fiche athlète (988 px, seuil 1 145 px) et `/resultats` (948 px, seuil
  1 105 px) ; `sm` pour `/ajouter` (480 px, tient déjà sous 640 px une fois le
  chrome ajouté). Le dessin de la carte vit une seule fois, dans
  `components/tcn/LigneCarte.tsx` — **sans état, donc sans `"use client"`**, ce
  qui laisse `/ajouter` en Server Component. Cinq points qui se re-cassent :
  - **Le seuil n'est pas le cran Tailwind par défaut** (`lg:` 1024, `md:` 768)
    mais `plancher + CHROME_RAIL_REPLIE` (`lib/utils/table.ts`, 157 px = rail
    replié + gouttières `PageShell`) — sans ce chrome, la grille s'affichait
    avant d'avoir la place de tenir et redéfilait à l'horizontale sur une bande
    réelle (1024–1237 px sur le classement, mesuré en revue UI/UX), le défaut
    même que #461 corrige. Le rail **déplié** (288 px, cookie #482) n'est pas
    couvert par ce chrome ; le résiduel est documenté sur la constante, et
    atténué par `role="region"`/`tabIndex` sur chaque grille scrollable, pour
    qu'elle reste au moins atteignable au clavier si la bande réapparaît. Le
    test `plancher de bascule grille/cartes` de `table.test.ts` est le
    garde-fou : Tailwind ne scanne que du texte littéral, donc rien d'autre
    n'empêche un écran de gagner une colonne sans que son seuil soit relevé.
  - **Le dépliant et les actions sont frères de la zone cliquable**, jamais
    enfants : un `<a>` ou un `<button>` dans un `<a>` est du HTML invalide.
  - **jsdom ne charge aucune CSS**, donc les deux arbres coexistent en test.
    `test/setup.ts` retire l'arbre carte des requêtes **texte** via
    `configure({ defaultIgnore })`, et le sélecteur porte
    `[data-affichage="cartes"] *` en plus du conteneur : `defaultIgnore` filtre
    par `node.matches()`, donc sans le `*` il n'écarterait que le conteneur, et
    la parade ne filtrerait rien. `test/affichage-cartes.test.tsx` verrouille la
    règle. Deux angles morts : `getByRole` n'utilise pas `ignore` (une requête
    de rôle visant l'intérieur d'une ligne se scope à la main), et **`within` ne
    lève pas l'exclusion** — un test qui vise les cartes passe par
    `dansLesCartes(testId)` de `test/cartes.ts`, dont `texte()` porte le
    `{ ignore: false }`. L'oublier ne se lit pas : la requête dit « unable to
    find an element », comme si la carte n'existait pas.
  - **`ParticipationAdminActions` est monté deux fois par ligne**, une fois par
    arbre. Accepté : `useSession` a une clé de cache unique, donc aucun appel
    supplémentaire, et l'arbre masqué n'est ni cliquable ni atteignable au
    clavier.
  - **Le helper partagé entre les deux arbres rend le JSX, pas la donnée** :
    c'est au niveau du rendu que la dérive s'est produite, deux fois — le
    compteur du club d'une compétition (`CartesCompetition`, revue #461) et le
    chip « Vous » (`RaceFinishers`, revue finale #461), tous deux calculés côté
    grille et oubliés côté carte tant que le calcul restait à refaire à la main
    plutôt que rendu par une fonction commune.

  Les deux matrices du détail de participation (`ComparisonTable`,
  `ImprovementMatrix`) ne suivent **pas** ce patron : ce sont de vrais
  `<table>`, que WCAG 1.4.10 exempte, et qu'une carte par ligne priverait de
  leur comparaison colonne à colonne. Elles réduisent leurs colonnes sous `sm:`,
  et c'est de la lisibilité, pas de la conformité.
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
- `lib/api/` — `client.ts` (appels `/api/v1`, `ApiError` porteur du statut HTTP),
  `server.ts`, `sse.ts` (streaming import SSE). **Les trois fonctions de
  `server.ts` relaient un cookie d'accès entrant** (#526) ; ce qui les distingue
  est leur lecture du 401, et quels cookies elles envoient :
  - `serverFetch` — lève une `ApiError` sur tout non-OK, 401 compris. Relais
    **minimal** depuis #586 : seul le cookie de session d'accès au site part,
    le reste du jar (SSO, bénévoles, PostHog…) est ignoré — voir plus bas.
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
- `lib/types.ts` — types TypeScript partagés.
- **`lib/sport-colors.ts` est la source unique de l'échelle des disciplines**
  (#480) — la redoubler ailleurs *est* le bug, et c'est déjà arrivé une fois
  (`lib/utils/format.ts` en portait une seconde, avec d'autres familles et
  d'autres couleurs). Elle est gardée par deux tests de contraste :
  `FAMILY_ORDER` sur ses paires adjacentes (1,6:1, dans la barre empilée) et,
  depuis #480, le couple encre/aplat de chaque famille (4,5:1, WCAG 1.4.3 sur le
  libellé de segment) — réordonner `FAMILY_ORDER` ou retoucher un token casse
  l'un des deux en silence. Le premier des deux ne vaut que **les six familles
  au complet**, et la barre n'en rend que les familles présentes : une famille
  absente en rapproche deux que la palette ne sépare pas (1,11:1 au pire,
  mesuré). Ce qui tient WCAG 1.4.1 quel que soit le sous-ensemble n'est donc pas
  la couleur mais le filet, le nom écrit dans le segment et la légende — ne pas
  les retirer au motif que « les couleurs se distinguent ».
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

