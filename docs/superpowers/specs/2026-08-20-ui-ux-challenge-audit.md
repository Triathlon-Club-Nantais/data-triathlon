# Passe UI/UX exploratoire — backlog d'idées (#325)

**Date** : 2026-08-20 · **Nature** : audit exploratoire, *challenge* du produit existant.
**Cible mesurée** : `https://data-triathlon-tcn-preview.vercel.app` (préproduction) + le
code de `frontend/` au commit `1eef442`.

Ce document est un **backlog d'idées**, pas une spec ni un plan. Il n'ordonne aucune
modification : la branche qui le porte ne touche pas `frontend/`. Chaque idée retenue
devient une issue fille, qui suivra alors la voie de son choix (§ *Suite*).

Nature au sens d'`AGENTS.md` : c'est un **rapport de terrain**. Ce qui y est mesuré
(comptages, contrastes calculés, octets, temps de réponse) prime sur le design et la
spec ; toute divergence se tranche en re-mesurant, pas en argumentant.

---

## 1. Ce qui n'est pas rejugé

Deux contraintes de la demande, reprises mot pour mot, et tenues :

- **« l'identité est arbitrée : ni palette, ni couple typographique, ni dégradé remis en
  cause (`--tcn-*`, Anton/Barlow) »** — aucune idée ci-dessous ne propose une couleur, une
  police ou un dégradé nouveau. L'unique idée qui touche à une couleur, `A11Y-4`, remplace
  un token de la palette par **un autre token de la même palette, déjà défini**
  (`--tcn-orange` → `--tcn-orange-deeper`), et seulement là où l'orange porte du texte.
  L'aplat, la barre, la bordure et le dégradé restent intacts.
- **« la frontière `components/tcn/` vs `components/ui/` de `frontend/AGENTS.md` n'est pas
  rejugée »** — les six lots ont tous écarté explicitement les migrations `ui/` → `tcn/`.
  La seule recommandation qui nomme `ui/` (`ETAT-3`, réutiliser `ui/empty-state` sur les
  écrans publics) applique la règle déjà écrite — primitive accessible sans équivalent TCN
  — au lieu de la contredire.

Cette passe est aussi **l'inverse du sous-agent `ui-ux-review`** : celui-ci juge un
`git diff` de branche contre une grille de conformité et ne rouvre jamais l'identité
visuelle ; celle-ci balaie le site entier et **a le droit de proposer**.

## 2. Méthode, et ce qu'elle ne couvre pas

**Fan-out à six agents**, un par domaine indépendant, chacun instruit sur le même format
de sortie (une idée = titre + écran + problème observé + proposition + référence externe
+ impact + effort) et sur les deux invariants ci-dessus. Méthode choisie par l'utilisateur
— `AGENTS.md` interdit à l'agent de déclencher seul un fan-out.

| Lot | Périmètre | Idées |
| --- | --- | --- |
| `NAV` | coquille, navigation, `/dashboard`, palette `⌘K` | 10 |
| `RES` | `/resultats`, `/courses/[id]`, détail de participation | 12 |
| `PROF` | `/athletes/[id]`, `/club`, `/club/athletes`, `/benevoles` | 11 |
| `ACT` | `/ajouter`, `/carte`, `/login`, écrans d'erreur | 11 |
| `ADM` | les 11 routes `/admin/*` | 11 |
| `ETAT`/`A11Y`/`COPY`/`RESP`/`VIZ` | passe transversale : états d'écran, accessibilité, microcopie, responsive, dataviz | 14 |

**69 idées brutes**, ramenées à **63 entrées** après fusion des recoupements (§ 12).
Les identifiants d'origine sont conservés comme clés de traçabilité.

Six affirmations à fort impact, chacune issue d'un agent différent, ont été **vérifiées
indépendamment** avant d'entrer ici (règle « spot check » du skill de fan-out) : `ADM-1`
(`lib/roles.ts` expose bien `peutAttribuer`, non consommé), `A11Y-2`/`NAV-1` (aucune balise
de titre dans le HTML servi de `/dashboard`), `RES-1` (la garde de la page de détail jette
`rank_overall` et `splits` qui sont sur l'objet), `RES-10` (`is_reliable` publié et lu par
personne sur la page course), `PROF-1` (`nav.config.ts:82` sans `href`), `ACT-1`
(`participations.py:55` force `is_pending_validation=True`).

**Limites, à connaître avant d'utiliser ce document :**

1. **Aucun outil de rendu navigateur n'était branché sur cette session.** Les agents ont
   mesuré le HTML servi (`curl`), le code et les tokens CSS — pas le rendu peint. Le rendu
   a été couvert autrement : **8 captures d'écran fournies par l'utilisateur** (mobile
   Brave, plus une capture desktop du rail replié), dépouillées en § 3. Tout ce qui relève
   du pixel peint hors de ces 8 captures est donc **inféré du code**, jamais vu.
2. **`batoreh/awesome-ux` est périmé.** Le dépôt cité par la demande est daté (2016), et
   une partie de ses liens sont morts ; son `README` est vide sur `main` et ne se lit que
   sur `master`. Seules ses références encore canoniques sont citées ici : Laws of UX,
   Krug *Don't Make Me Think*, Norman *The Design of Everyday Things*, Wroblewski *Web
   Form Design*, usability.gov, Really Good UX. `maxbogo/awesome-ai-tools-for-ui` a servi
   de source d'inspiration d'outillage, pas de norme : aucune idée ne dépend d'un outil de
   cette liste.
3. **Les volumes mesurés sont ceux de la préproduction** (820 participations, 350 membres,
   273 épreuves, 849 finishers sur la course 340). Les seuils de gêne changeront avec la
   base de production.

## 3. Ce que les captures ont apporté

Huit captures, dépouillées après les six lots. Elles ont **confirmé** dix constats issus du
code et **ajouté six constats qu'aucune lecture de code n'aurait produits**. Les ajouts sont
versés dans les idées correspondantes ci-dessous ; on les récapitule ici parce qu'ils sont
la seule partie de l'audit fondée sur le rendu peint.

| Capture | Confirme | Ajoute |
| --- | --- | --- |
| Rail replié, desktop | `NAV-2` : 8 icônes empilées, aucun logo, aucun mot. **Nuance** : la pastille active *est* teintée orange, donc le desktop répond bien à « où suis-je » — le défaut de `NAV-4` est propre au mobile. | ~150 px de vide dans les deux cartes basses du `/dashboard` **aussi sur desktop**, pas seulement en mobile |
| `/dashboard` mobile | `NAV-5` (barre d'outils : `Général│Catégorie│Genre│Tous` + case sans libellé + saison), `NAV-7` (aucune date sur la page), `VIZ-1` (pastilles Triathlon/Duathlon quasi identiques, Aquathlon à 0,3 % invisible) | — |
| `/club` mobile (haut, 1080 × 13 959) | `PROF-3` **sur un seul écran** : KPI « PODIUMS 12 » avec, juste dessous, « Sherwin MASHAYEKHI 10 courses · 6 podiums » et « Hadrien KERMARREC 8 courses · 3 podiums ». `PROF-2` : « 350 membres », aucune recherche, ~50 hauteurs d'écran de roster | Le `BarList` « Répartition & tendances » s'étend de 1 à 279 sur une échelle **linéaire** : les 8 dernières lignes sur 14 (« Triathlon 21 » … « Triathlon XXL 1 ») rendent une barre invisible ou de 1 px. Et « r'FLEURY hadrien / jean-baptiste . KERMARREC » figure comme athlète dans la vitrine du club |
| `/club` mobile (bas, « Résultats récents ») | `COPY-3` : `Source (breizhchrono)` **8 fois** sur un seul écran | Les athlètes **DNS** rendent une grille de splits complète à `00:00:00` (Natation/T1/Vélo/T2/Course), ~265 px CSS de carte par DNS — ce que le lot `PROF` avait écarté comme « hors périmètre » et que la capture rend voyant. Trois rendus d'ordinal cohabitent : « 443ᵉ », « 62e » et un « 1 » nu. Et cette `ResultCard` affiche les rangs Général/Genre/Catégorie que la page de détail dédiée omet (`RES-12`) |
| `/athletes/4` mobile | `PROF-6` : « Toutes les épreuves » ne montre que DATE + ÉPREUVE, barre de défilement horizontale visible ; FORMAT, TEMPS, PLACE et le ⚠ sont **hors écran**. `PROF-5` et `PROF-7` : le seul signal « c'est vous » est le libellé du bouton, qui est aussi le contrôle le plus voyant de la page | La grille de 5 tuiles KPI **ne se divise pas par 2** en mobile : la tuile 5 s'orpheline sur sa ligne et « TOP 10 0 » s'étire à la hauteur de la carte « MEILLEUR RATIO / Top 20 % », laissant ~180 px de vide |
| `AthletePicker`, « Herr » saisi | `NAV-8` : les 4 microcopies concurrentes, le pied vide « Pas de blocage d'accès — choisis librement ton profil » | **Le tri est par nombre de courses, pas par qualité de correspondance** : « yves herry » (5 courses) passe **au-dessus** de la correspondance exacte « Mathieu HERRMANN » (3 courses), suivie de CHERRUEAU / CHERRIER / CHERRUAULT (2 chacune). `NAV-8` avait vu le plafond à 100 participations, pas ce tri. Et la liste est coupée en milieu de ligne par le pied de modale, sans affordance de défilement |

---

## 4. Idées — passe transversale

### [ETAT-1] Les pages d'absence et de panne sont celles de Next.js, pas celles du club

*Fusionne `ACT-7`, `ACT-8`, `PROF-11`(a), `COPY-3`(4).*

- **Écran** : transversal (toutes les routes), plus les 3 routes dynamiques qui appellent
  `notFound()` : `courses/[id]:60`, `athletes/[id]:38`, `participations/[participationId]:36`.
- **Problème** : un lien mort affiche **« 404 — This page could not be found. »**, en
  anglais, dans un document déclaré `lang="fr"` — sans suggestion, sans retour. Il n'existe
  ni `not-found.tsx` ni `global-error.tsx` dans les 26 fichiers de route. Et une panne de
  rendu serveur ne produit **rien du tout** : `curl /courses/999999` rend **500 avec un
  corps HTML entièrement vide** (16 545 octets, 0 de texte visible), parce qu'`app/error.tsx`
  (12 lignes) est une frontière client jamais rendue au serveur. Cet écran-là, quand il
  s'affiche, rend `error.message` **verbatim** (`app/error.tsx:8`) : en production Next.js y
  substitue son paragraphe anglais sur le `digest`, et le seul geste offert est
  « Réessayer », qui refait la même chose — or la cause la plus fréquente ici est le
  réveil à froid du backend Render, documenté jusque dans `app/admin/layout.tsx`. Ce n'est
  pas un cas d'URL mal tapée : un lien partagé vers une épreuve fusionnée ou purgée y mène.
- **Proposition** : un `app/not-found.tsx` français qui nomme ce qui manque (« Cette épreuve
  n'existe pas ou plus ») et offre trois sorties (résultats, carte, ajouter) ; un
  `app/global-error.tsx` ; réécrire `app/error.tsx` en trois blocs — une phrase française
  décrivant la conséquence, « Réessayer » **plus** un lien de sortie et le `FeedbackButton`
  existant, et le `error.digest` en petit pour qu'un signalement soit exploitable. Ne jamais
  rendre `error.message` brut ; ajouter la capture PostHog au montage.
- **Référence** : Norman, *The Design of Everyday Things* (récupération d'erreur : dire où
  l'on est et quoi faire ensuite) — https://www.nngroup.com/books/design-everyday-things-revised/ ;
  WCAG 2.2 **3.1.1/3.1.2** (langue du contenu), formellement en défaut —
  https://www.w3.org/WAI/WCAG22/quickref/
- **Impact / effort** : **fort** / **S** — deux fichiers de ~30 lignes, plus le `.catch`
  d'une ligne du § 11.

### [ETAT-2] Un seul écran sur treize a un état de chargement, et le plus lourd n'en a pas

*Fusionne `RES-6`, `PROF-11`(b) et (c).*

- **Écran** : `/dashboard`, `/club`, `/club/athletes`, `/courses/[id]`, `/athletes/[id]`,
  `/ajouter`, détail de participation — 7 routes en rendu serveur sans repère.
- **Problème** : **1 `loading.tsx` pour 26 fichiers de route**. En navigation douce, ces 7
  pages laissent l'écran précédent figé sans aucun signe. Mesures sur la préproduction :
  `/resultats` TTFB 1,13 s / total 1,59 s ; `/dashboard` 0,73 s ; `/courses/340` 0,67 à
  1,24 s ; `/courses/214` 1,43 s ; `/club` **1 688 630 octets** de HTML pour 1,14 s
  (`page_size: 1000` sur `listParticipations`, `app/club/page.tsx:23`) — soit plusieurs
  secondes en 4G, exactement le contexte réel. Le seul squelette existant n'enveloppe pas
  `PageShell` (`app/resultats/loading.tsx:5` : `div.space-y-4` nu contre
  `px-4 pt-6 sm:px-8 sm:pt-9 md:px-10`), donc il s'affiche pleine largeur puis le contenu
  saute. `/carte` fait l'erreur inverse : son `Suspense` englobe **toute** la page, titre
  compris (`app/carte/page.tsx:66-71`), et le HTML servi ne contient qu'un mot.
  `/benevoles` sert 61 caractères, « Chargement… », dans un `div` centré à `margin: 80px auto`.
- **Proposition** : un `loading.tsx` par route lourde, calqué sur la géométrie réelle
  (`PageShell` + 5 tuiles `StatCard` + bloc de tableau), avec `components/ui/skeleton` déjà
  présent dans 16 fichiers `admin/` ; descendre la frontière `Suspense` de `/carte` autour
  du seul `<MapView>` ; borner la charge de `/club` (cf. `PROF-2`) plutôt que la masquer.
- **Référence** : Laws of UX, seuil de Doherty — https://lawsofux.com/doherty-threshold/ —
  5 des 7 routes dépassent 400 ms avec un écran inchangé.
- **Impact / effort** : **fort** / **M** — 6 à 7 squelettes plus le déplacement de la
  frontière `Suspense`.

### [ETAT-3] Les états vides des écrans publics sont des culs-de-sac, ceux du back-office non

- **Écran** : transversal — 9 états vides publics écrits à la main contre 3 exemplaires.
- **Problème** : sur le public, l'état vide est un `div` d'une phrase sans issue :
  « Aucune épreuve enregistrée. » (`dashboard/page.tsx:84`), « Aucune épreuve. » (`:119`),
  « Aucun résultat pour cet athlète. » (`athletes/[id]/page.tsx:107`), « Aucun résultat
  enregistré pour l'instant. » (`ajouter/page.tsx:41`), « Aucun participant à afficher. »
  (`RaceFinishers.tsx:244`), « Aucun athlète trouvé. » (`AthletePicker.tsx:177`),
  « Clubs non renseignés. » (`courses/[id]/page.tsx:112`), « Catégories non renseignées. »
  (`CategoryBars.tsx:23`), « Aucun résultat en attente de validation. »
  (`ValidationQueue.tsx:49`). Aucune ne dit quoi faire. À côté, `components/ui/empty-state`
  sert **20 fois dans `admin/`** et **2 fois** côté public, et trois modèles exemplaires
  existent déjà (`MapView.tsx:95-101`, `ClubDashboard.tsx:36-46`, `AthleteSeasonList.tsx:67/98`).
  Même asymétrie sur les refus : `lib/api/refus.ts` distingue proprement 401 / 403 / panne,
  et ne sert **que** dans `admin/` (6 appels).
- **Proposition** : passer les 9 états vides publics par `EmptyState` avec systématiquement
  une action ; distinguer « rien en base » de « rien pour ces filtres » sur `/resultats` et
  `RaceFinishers` ; étendre `messageDeRefus` aux écrans publics.
- **Référence** : Really Good UX — https://www.reallygoodux.io — un état vide est un moment
  d'orientation, pas un constat ; Norman sur le retour d'information.
- **Impact / effort** : **moyen** / **S** — remplacements localisés, composant et patrons
  existants.

### [A11Y-1] Aucun lien d'évitement : 11 contrôles à franchir sur chaque page

*Fusionne `NAV-1`(b).*

- **Écran** : transversal — le rail est monté dans `app/layout.tsx:54`.
- **Problème** : `grep -o 'href="#[^"]*"'` sur le HTML servi de `/resultats` rend **0
  résultat** : il n'existe aucun lien d'évitement dans l'application. Sur ce même HTML,
  **5 `<a>` et 6 `<button>` précèdent `<main>`** — 11 arrêts de tabulation à retraverser à
  chaque page, et le rail est `sticky`/`h-screen` (`AppNav.tsx:153`) donc toujours présent.
  `<main class="flex-1">` (`app/layout.tsx:56`) n'a ni `id` ni `tabIndex` pour servir de cible.
- **Proposition** : un lien « Aller au contenu » en tête de `<body>`, masqué hors focus
  (`sr-only focus:not-sr-only`), vers `<main id="contenu">` ; nommer aussi les deux repères
  secondaires (`role="search"` existe déjà sur `RaceFinishers.tsx:134`).
- **Référence** : WCAG 2.2 **2.4.1 Contourner des blocs**, niveau **A** — le seul
  manquement de niveau A de toute la passe —
  https://www.w3.org/WAI/WCAG22/quickref/#bypass-blocks
- **Impact / effort** : **fort** / **S** — 4 lignes dans `app/layout.tsx` et une classe.

### [A11Y-2] Les titres de page sont des `<div>` : quatre écrans publics ne rendent aucun titre

*Fusionne `NAV-1`(a), `PROF-5`(a).*

- **Écran** : `/dashboard`, `/ajouter`, `/carte`, `/courses/[id]`, `/athletes/[id]`.
- **Problème** : `<h1>` n'apparaît que **5 fois** dans 131 fichiers, `<h2>` **7 fois**,
  `<h3>` **0 fois**. Vérifié sur le HTML servi : `/dashboard` = **0 balise de titre**,
  `/ajouter` = **0**, `/carte` = **0**, `/athletes/27620` = **0**. La cause est un motif, pas
  un oubli : le titre est écrit en
  `<div style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(...)" }}>` —
  `dashboard/page.tsx:61`, `courses/[id]/page.tsx:79`, `athletes/[id]/page.tsx:71`,
  `ajouter/page.tsx:26` — et les titres de section suivent la même forme. Or le composant
  qui résout exactement ça existe, et son propre commentaire le dit (« Remplace les `h1`
  nus pour une hiérarchie cohérente sur tous les écrans », `PageHeader.tsx:6-7`, `h1` en
  `:43`) : il est adopté par 15 routes sur 26, presque toutes en `admin/`. `/dashboard` l'a
  recopié à la main.
- **Proposition** : `PageHeader` sur les 5 écrans publics restants — il accepte déjà
  `eyebrow`, `title`, `description`, `actions`, `children` et `backHref`. À minima,
  promouvoir les 4 titres en `<h1>` et les titres de carte en `<h2>` **sans changer une
  seule valeur de style** : la casse Anton et le `clamp()` se conservent tels quels sur une
  balise de titre.
- **Référence** : WCAG 2.2 **2.4.6** et **1.3.1** —
  https://www.w3.org/WAI/WCAG22/quickref/#headings-and-labels ; usability.gov, architecture
  de l'information — https://www.usability.gov/what-and-why/information-architecture.html
- **Impact / effort** : **fort** / **S** — changement de balise, styles inchangés.

### [A11Y-3] Six tableaux publics sont des grilles de `<div>`, et les lignes ne sont pas des liens

*Fusionne `RES-2`, `RES-3`(b), `PROF-6`(b).*

- **Écran** : `/resultats` (`EventList`), `/courses/[id]` (`RaceFinishers` + « Top clubs »),
  `/athletes/[id]`, `/ajouter`, `/dashboard` (« Épreuves préférées »).
- **Problème** : ces six listes de données sont des `display: grid` de `div` (15
  `gridTemplateColumns` dans le dépôt), avec une **ligne d'en-tête séparée reliée à rien** :
  `athletes/[id]/page.tsx:111-113`, `ajouter/page.tsx:37-38`, `dashboard/page.tsx:104-105`,
  `courses/[id]/page.tsx:108-109`, `EventList.tsx:118-122`, `RaceFinishers.tsx:177-186`. Un
  lecteur d'écran énonce « 13/06/2026 Triathlon et SwimRun Mesquer-Quimiac 2026 Triathlon S
  S 01:10:47 2 ⚠ » sans jamais dire quelle colonne est laquelle. Le back-office, lui, utilise
  de vrais tableaux (**65** `TableHead`). Seconde couche, plus coûteuse à l'usage : la ligne
  de classement est un `role="button"` + `tabIndex={0}` + `router.push`
  (`RaceFinishers.tsx:195-208`), donc **impossible d'ouvrir un résultat dans un nouvel
  onglet, de copier son lien ou de voir l'URL au survol** — confirmé, `curl /courses/340` ne
  contient **aucun** `href="/courses/340/participations/…"` — alors que `EventList.tsx:141-153`
  et `athletes/[id]/page.tsx:127` font la même chose avec un vrai `<Link>`, et que le
  commentaire de `CoursesAdminTable.tsx:218` documente précisément ce piège. Le clic
  n'émet en outre aucun retour visuel pendant les 0,67 à 1,43 s de réponse (`router.push`
  hors `startTransition`). Les en-têtes triables sont des boutons de 11 px sans padding
  (`:345-384`).
- **Proposition** : passer ces six grilles en `<table>` / `<th scope="col">` (la géométrie
  peut rester en grid via `display: grid` sur `<table>`/`<tr>`, ou par
  `role="table"`/`role="columnheader"` si elle doit être préservée à l'identique) ;
  remplacer le `role="button"` de la ligne de classement par un `<Link>` couvrant, comme sur
  la fiche athlète ; ajouter l'état `pending` de `useTransition` sur la ligne cliquée.
- **Référence** : WCAG 2.2 **1.3.1** —
  https://www.w3.org/WAI/WCAG22/quickref/#info-and-relationships — et **4.1.2** *Name, Role,
  Value* (annoncer « bouton » pour une navigation trompe l'aide technique) ; loi de Jakob —
  https://lawsofux.com/jakobs-law/ — un classement se comporte partout comme une liste de liens.
- **Impact / effort** : **fort** / **L** pour la sémantique des six grilles (~500 lignes de
  balisage, tests de rendu à reprendre) ; **S** pour le seul passage de la ligne en `<Link>`,
  qui est le gain immédiat (partager « le résultat de X » est le geste social central d'un club).

### [A11Y-4] L'orange de marque sert de couleur de texte : 3,32:1 sur 35 emplacements

- **Écran** : transversal — `Eyebrow` est présent sur presque tous les écrans (35 usages),
  plus `PlaceBadge`, `SegmentedControl`, `Badge`.
- **Problème** : contrastes **calculés** sur les valeurs réelles d'`app/globals.css` (formule
  WCAG, luminance relative) :
  - `--tcn-orange` #E9530E en texte = **3,32:1** sur `--tcn-paper`, **3,68:1** sur
    `--tcn-surface`. C'est la couleur par défaut d'`Eyebrow` (`Eyebrow.tsx:16`) et de
    `.eyebrow` (`globals.css:410`), **à 13 px gras** — donc soumise au seuil « texte
    normal » de 4,5:1. Aussi en texte sur `dashboard/page.tsx:113` (rang 1) et
    `courses/[id]/page.tsx:117-118` (nom et compte du club TCN dans « Top clubs »).
  - `PlaceBadge` podium : orange sur `--tcn-orange-12` (composite #fceae2) = **3,15:1** sur
    surface, **2,88:1** sur `paper` (`PlaceBadge.tsx:17`, rendu à `fontSize: 16` gras dans
    `RaceFinishers.tsx:214`, donc sous le seuil « grand texte »).
  - `SegmentedControl` option retenue : **3,25:1** à 13-14 px (`SegmentedControl.tsx:41`) —
    le composant des deux bascules publiques. `Badge` compteur : idem sur `--tcn-orange-12`.
  - `text-success` dans `ImportProgress.tsx:27` = **4,37:1**, sous le seuil.

  **L'identité n'est pas en cause : le token correctif existe déjà.** Les trois candidats ont
  été calculés sur les quatre fonds concernés — `--tcn-orange-deep` #d64000 ne passe que sur
  `surface` (4,57:1) et **échoue sur `paper` (4,12:1)** et sur les composites (3,92 à 4,13:1) ;
  seul **`--tcn-orange-deeper` #b83a00** franchit 4,5:1 partout (**4,51 à 5,21:1**). C'est
  exactement l'arbitrage déjà retenu pour `.tcn-btn--primary`.
- **Proposition** : `Eyebrow` (ton orange) et `.eyebrow` passent à `--tcn-orange-deeper` ;
  même bascule pour `PlaceBadge` podium, `SegmentedControl` retenu, `Badge` compteur,
  « Top clubs » TCN et le rang 1 du dashboard ; `text-success` remplacé par
  `--tcn-success-text` (7,58:1, déjà défini). L'orange de marque reste intact partout où il
  ne porte pas de texte.
- **Référence** : WCAG 2.2 **1.4.3 Contraste (minimum)**, AA, 4,5:1 sous 18,66 px gras —
  https://www.w3.org/WAI/WCAG22/quickref/#contrast-minimum
- **Impact / effort** : **fort** / **S** — un token par point d'usage, 6 fichiers, zéro
  géométrie touchée. L'eyebrow est l'élément d'identité le plus répété de l'app, et il est
  illisible au soleil sur un téléphone — situation d'usage littérale (arrivée de course).

### [A11Y-5] Rien n'est annoncé quand le contenu change : `role="status"` existe deux fois

- **Écran** : `/resultats` (5 filtres + tri + défilement infini), `/courses/[id]` (recherche,
  tri de 7 colonnes, pagination, bascule club), `/dashboard` et `/club` (3 bascules),
  `/ajouter` (import SSE).
- **Problème** : `grep "aria-live\|role=\"status\"\|aria-busy\|aria-atomic"` rend **12
  occurrences**, dont **10 sont des `role="alert"`** d'erreur de formulaire. Il ne reste que
  **2** annonceurs de changement : `AthleteSeasonList.tsx:92` (le bon patron) et
  `CourseSourcesPanel.tsx:105`. Conséquences : filtrer sur `/resultats` remplace la liste
  sans annoncer le nouveau décompte ; trier une colonne réordonne 1 080 px de tableau en
  silence ; le défilement infini (`EventList.tsx:58`) injecte des pages sans un mot ; et
  **l'import SSE n'a aucun annonceur** — `ImportProgress.tsx` affiche « Import en cours…
  340/1200 » et une `<Progress>` sans `aria-live`, `aria-busy` ni `aria-valuetext`, alors
  que c'est l'opération la plus longue de l'app. Le retour visuel existe
  (`data-pending:opacity-60/70`, 10 usages) mais il est *exclusivement* visuel.
- **Proposition** : un `role="status"` `sr-only` par zone de résultats annonçant le décompte
  après changement (« 48 épreuves, 312 résultats »), sur le modèle d'`AthleteSeasonList` ;
  `aria-live="polite"` + `aria-busy` sur `ImportProgress` avec une annonce jalonnée (pas à
  chaque message SSE) ; `aria-live` sur les états « en attente » des bascules.
- **Référence** : WCAG 2.2 **4.1.3 Messages d'état**, AA —
  https://www.w3.org/WAI/WCAG22/quickref/#status-messages
- **Impact / effort** : **moyen** / **S** — un composant `AnnonceStatut` sur 5 points
  d'insertion.

### [COPY-1] Trois mots pour le même objet, trois libellés pour le même bouton

- **Écran** : transversal — nav globale, `/ajouter`, `/resultats`, `/carte`, `/club`, `/dashboard`.
- **Problème** : « épreuve » est le mot retenu partout (**257 occurrences**), mais le même
  objet s'appelle aussi « course » et « triathlon » aux endroits les plus visibles : le
  bouton d'action principal, présent sur toutes les pages, dit **« Ajouter une course »**
  (`AppNav.tsx:258`, `:352`, `:375`) ; la page qu'il ouvre est titrée **« Ajouter un
  triathlon »** (`ajouter/page.tsx:26`) ; et les états vides invitent à **« Ajouter une
  épreuve »** (`MapView.tsx:99`, `ClubDashboard.tsx:44`). Trois libellés pour une seule
  destination. Même dérive dans un seul fichier : `ClubDashboard.tsx:57` affiche le KPI
  « Épreuves » et `:118` compte « {n} course(s) » douze lignes plus bas. Sur le panneau de
  filtres public, le champ s'appelle « Course » avec le placeholder « Rechercher une course »
  (`ResultsFilters.tsx:153/158`) dans une page titrée « Toutes les épreuves ».
- **Proposition** : figer « épreuve » comme terme unique visible utilisateur (majoritaire, et
  c'est le mot de la fédération), et laisser `course` comme seul identifiant technique
  (route `/courses/`, champ `course` — ce que le Principe I autorise explicitement) ; un
  libellé unique « Ajouter une épreuve » pour le bouton, le titre de page et les états
  vides ; une ligne de glossaire dans `frontend/AGENTS.md` contre la rechute.
- **Référence** : loi de Jakob — https://lawsofux.com/jakobs-law/ ; Vercel Web Design
  Guidelines (constance terminologique) —
  https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md
- **Impact / effort** : **moyen** / **S** — une vingtaine de remplacements textuels.

### [COPY-2] L'app tutoie et vouvoie le même utilisateur sur le même écran

- **Écran** : transversal — `FeedbackButton` est monté dans `app/layout.tsx:61`, donc partout.
- **Problème** : **7 tutoiements** et **8 vouvoiements**, qui se croisent. Tutoiement :
  « Clique sur une épreuve… » (`athletes/[id]/page.tsx:104`, `EventList.tsx:96`),
  « Clique pour voir la page de résultats → » (`ajouter/page.tsx:33`), « Sélectionne ton
  nom » / « choisis librement ton profil » / « Saisis au moins 2 lettres de ton nom »
  (`AthletePicker.tsx:126`, `:131`, `:181`), « Colle ici l'adresse des résultats de **ton**
  triathlon » (`TcnScrapeForm.tsx:122`). Vouvoiement, sur les mêmes écrans : « Décrivez le
  problème ou **votre** retour » (`FeedbackButton.tsx:137`, `:97`), « Importez une
  épreuve… » (`EventList.tsx:76`, `ClubDashboard.tsx:38`), « Essayez une autre saison »
  (`AthleteSeasonList.tsx:67`), « Sélectionnez un résultat dans la file »
  (`benevoles/page.tsx:128`). Le cas le plus net : sur `/resultats`, l'utilisateur lit
  « **Clique** sur une épreuve », « **Importez** une épreuve » et « **votre** retour » —
  trois adresses sur un seul écran.
- **Proposition** : trancher une fois (le vouvoiement domine légèrement et couvre les
  surfaces de formulaire et d'erreur, les plus sensibles), l'écrire dans `frontend/AGENTS.md`,
  aligner les 7 tutoiements. Au passage, supprimer les 3 phrases d'affordance (« Clique sur
  une épreuve… ») : sur un tableau dont chaque ligne est un lien, elles sont redondantes.
- **Référence** : Vercel Web Design Guidelines (la voix produit est une décision unique et
  documentée) ; Wroblewski, *Web Form Design*, sur la constance du registre.
- **Impact / effort** : **moyen** / **S** — une décision plus 7 remplacements.

### [COPY-3] Du vocabulaire technique fuit à l'écran : slugs de fournisseurs, énumérés bruts, « Heats »

- **Écran** : `/ajouter` (import), `/club` et `/resultats` (`ResultCard`).
- **Problème** : quatre fuites, toutes publiques. (1) `ResultCard.tsx:94` et `:97` affichent
  **« Source (njuko) »** — le slug brut — alors que `providerLabel()` existe dans
  `lib/constants` et est appelé **12 fois** ailleurs ; la capture `/club` montre
  `Source (breizhchrono)` **8 fois sur un écran**. (2) `ImportProgress.tsx:43` affiche
  `{c.event_type}` brut (`triathlon`, `bike-run`, `course-a-pied`) au lieu de
  `eventTypeLabel()`. (3) `ImportProgress.tsx:52-57` : **« Heats en erreur (3) »** suivi du
  `heat_slug` en `font-mono` — un mot anglais et un identifiant interne, sur l'écran le plus
  fréquenté par un non-technicien ; ligne 66, `{state.error}` relayé verbatim.
  (4) `app/error.tsx:8` rend `error.message` (traité en `ETAT-1`). Accessoirement
  `ResultCard.tsx:34` affiche `{a.gender}` brut (les chronométreurs publient « H »/« M »/« W »)
  alors que `genderShort()` existe, et `:114` compose l'ordinal à la main alors qu'`ordinalFr()`
  existe — d'où les **trois rendus d'ordinal** vus sur la même capture (« 443ᵉ », « 62e », « 1 »).
- **Proposition** : passer les cinq points par les formateurs déjà écrits (`providerLabel`,
  `eventTypeLabel`, `genderShort`, `ordinalFr`) ; reformuler le bloc d'échec d'import en
  français métier (« 3 séries n'ont pas pu être importées », détail replié).
- **Référence** : Principe I de la constitution (français pour le visible utilisateur) ;
  Really Good UX — https://www.reallygoodux.io — un message d'erreur nomme la conséquence,
  jamais l'implémentation.
- **Impact / effort** : **moyen** / **S** — toutes les fonctions de formatage existent.

### [RESP-1] Quatre tableaux à largeur plancher, jusqu'à 1 080 px, sur un public qui consulte au téléphone

*Fusionne `RES-3`(a), `PROF-6`(a).*

- **Écran** : `/courses/[id]`, `/athletes/[id]`, `/resultats`, `/ajouter`.
- **Problème** : les quatre tableaux sont enfermés dans un `overflowX: "auto"` autour d'un
  bloc à `minWidth` fixe : **1 080 px** pour le classement (`RaceFinishers.tsx:176`, 11
  colonnes), **988 px** pour la fiche athlète (`athletes/[id]/page.tsx:110`, `TRACKS =
  [120, {flexMin:200}, 150, 90, 120, 120, 28]` + 6 × 18 de gouttières + 52 de padding),
  **966 px** pour `/resultats` (`EventList.tsx:116`), **480 px** pour `/ajouter`. Sur un
  iPhone SE (375 px moins 32 de gouttière `PageShell`), lire un classement demande **3,1
  écrans de défilement horizontal**, sans en-tête figée — et dès qu'on atteint les inters,
  **la colonne « Athlète » a disparu à gauche** : on ne sait plus de qui on lit le temps.
  **La capture de `/athletes/4` le montre nu** : « Toutes les épreuves » n'affiche que DATE
  et ÉPREUVE, FORMAT / TEMPS / PLACE et le ⚠ sont hors écran — c'est-à-dire que la donnée
  pour laquelle on ouvre la page est invisible sans geste. Volume réel : 849 lignes sur 43
  pages pour la course 340. Aucune de ces grilles ne se replie : le dépôt compte **70
  utilitaires de point de rupture** (44 `sm:`, 14 `lg:`, 12 `md:`, 0 `xl:`) pour 131
  fichiers, contre **431 `style={{` en dur dans 53 fichiers**.
- **Proposition** : sous `sm:`, remplacer le tableau par une liste de cartes empilées portant
  les 3 à 4 champs qui comptent (place, nom, temps total, écart) et reléguer les splits dans
  un dépliant — le composant existe déjà, c'est `ResultCard` ; à défaut, en-tête collante,
  deux premières colonnes en `position: sticky; left: 0`, et colonnes de transition masquées
  sous `md:`.
- **Référence** : WCAG 2.2 **1.4.10 Redistribution** (pas de défilement bidirectionnel à
  320 px) — https://www.w3.org/WAI/WCAG22/quickref/#reflow
- **Impact / effort** : **fort** / **L** — 4 rendus alternatifs à concevoir et tester. C'est
  le contexte d'usage principal de l'application.

### [CIBLE-1] Les cibles tactiles sous le plancher de 24 px, inventaire transversal

*Rassemble les sous-constats de `ADM-9`, `RES-5`, `PROF-10`, `ACT-10`, `NAV-5`, `RESP-1`.*

- **Écran** : transversal — 7 emplacements mesurés.
- **Problème** : la coquille se donne 44 px pour plancher tactile et le dit
  (`AppNav.tsx:488`, `:644-647`, « 44 px, le plancher tactile de la grille »), mais le
  reste du produit descend bien en dessous du minimum normatif de 24 px : croix de retrait
  d'un rôle **16 × 16 px** (`UserRolesTable.tsx:107-116`, `size-4`, geste destructif sans
  confirmation) ; croix de retrait d'un chip de filtre **16 px** (`ResultsFilters.tsx:218-221`,
  `size-3` + `p-0.5` dans un badge `h-5`) ; case « Inclure les autres disciplines »
  **14 px** (`DisciplineToggle.tsx:44`, `size-3.5`) ; cercles cliquables de la carte
  **20 px de diamètre** (`MapView.tsx:116`, rayon 10) ; onglets de la file bénévole ~20 px
  de haut sans padding (`ValidationQueue.tsx:32,40`) ; en-têtes triables du classement 11 px
  sans padding (`RaceFinishers.tsx:345-384`) ; les trois contrôles de la barre d'outils du
  dashboard entre 26 et 34 px. À titre de comparaison, `ui/button` propose déjà `icon-xs` =
  24 px pile et `icon-sm` = 28 px.
- **Proposition** : porter les sept points à 24 px minimum, viser 28 px pour rester dans
  l'échelle du produit, et 44 px sur les contrôles publics fréquents. C'est une passe
  mécanique, mesurable, sans arbitrage de design.
- **Référence** : WCAG 2.2 **2.5.8 Taille de cible (minimum)**, AA, 24 × 24 px CSS —
  https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html ; loi de Fitts —
  https://lawsofux.com/fittss-law/
- **Impact / effort** : **moyen** / **S** — non-conformité AA avérée, correction sans risque.

### [RESP-2] Les graphiques ont une largeur fixe : leurs libellés tombent à ~3,5 px sur un téléphone

- **Écran** : `/courses/[id]` (histogramme), détail de participation (évolution du rang),
  `/club` (tendance mensuelle).
- **Problème** : les deux plus gros graphiques sont des SVG à `viewBox` fixe étirés à
  `width: 100%` — `Histogram.tsx:15-16` (`W = 900`) et `RankingEvolutionChart.tsx:13-14`
  (`WIDTH = 1000`). Leurs textes sont dimensionnés dans l'espace du `viewBox` :
  `fontSize="11"` pour les graduations (`Histogram.tsx:45`, `:58`), `fontSize={12}` pour
  l'axe et l'infobulle. Sur un iPhone SE, la largeur utile dans la carte vaut
  375 − 32 − 56 ≈ **287 px**, soit un facteur d'échelle de **0,32** : les graduations
  s'affichent à **3,5 px** et l'axe temporel à **3,8 px**. `MonthlyTrend` cumule deux
  défauts tactiles : les **valeurs des barres sont en `opacity-0` et ne réapparaissent qu'au
  `group-hover`** (`:39-41`) et le repli est un attribut `title` (`:36`) — deux mécanismes
  qui n'existent pas au doigt, donc sur téléphone les 12 barres n'affichent **jamais** de
  chiffre ; les mois y sont en `text-[8px]`. `Histogram` n'adapte pas son nombre de barres
  (`barGap = usableW / bars.length`, plancher 4 px). Et le `BarList` de `/club`, vu sur
  capture, s'étend de 1 à 279 sur une échelle **linéaire** : 8 lignes sur 14 rendent une
  barre invisible ou de 1 px.
- **Proposition** : dimensionner les textes SVG hors de l'échelle du `viewBox`, ou déclarer
  un `viewBox` plus étroit sous `sm:` avec moins de graduations ; sur `MonthlyTrend`,
  afficher la valeur en permanence et remonter les mois à 11 px en n'en affichant qu'un sur
  deux ; réduire le nombre de tranches de l'histogramme sous `sm:` ; donner au `BarList` une
  échelle qui reste lisible sur deux ordres de grandeur (racine, ou valeur en clair sur les
  petites lignes). Aucune de ces corrections ne demande d'interactivité : le rendu serveur
  sans JavaScript est préservé.
- **Référence** : WCAG 2.2 **1.4.10** — https://www.w3.org/WAI/WCAG22/quickref/#reflow — et
  **1.4.13** *Content on Hover or Focus* —
  https://www.w3.org/WAI/WCAG22/quickref/#content-on-hover-or-focus
- **Impact / effort** : **moyen** / **M** — 3 composants.

### [VIZ-1] Le codage couleur par discipline ne fonctionne pas : un token indéfini et six familles sur trois teintes

> Le premier point est un **bug**, pas une idée : il est repris en § 11 pour qu'il ne soit
> pas confondu avec une question d'identité visuelle. Un token qui ne résout pas est
> simplement cassé.

- **Écran** : `/club` et `/resultats` (`ResultCard`, `SportBadge`, `ui/medal`), `/dashboard`
  (barre empilée des disciplines).
- **Problème** : (1) **`--ink-mix` n'est déclaré nulle part.** `lib/sport-colors.ts:34` et
  `ResultCard.tsx:80` écrivent
  `color: color-mix(in oklch, <teinte>, var(--foreground) var(--ink-mix))` ; `grep -- "--ink-mix"`
  dans tout `frontend/` hors `node_modules` rend 3 occurrences dont un commentaire, **aucune
  déclaration**. Le HTML servi de `/club` le confirme mot pour mot. Une propriété
  personnalisée non résolue rend la déclaration invalide à la valeur calculée : `color`
  retombe sur l'héritage, et les badges de discipline, les médailles et les libellés de
  segment s'affichent tous dans la **même** couleur, sur un aplat teinté à 14 %. Le codage
  couleur voulu par le design est mort, silencieusement. Jumeau : la classe `.micro-label`,
  utilisée **5 fois**, **n'est définie dans aucun CSS** — d'où les `text-[8px]`/`text-[9px]`
  ajoutés à la main pour compenser. (2) **Deux échelles de disciplines divergentes.**
  `lib/sport-colors.ts:7-13` mappe cinq familles, avec `--run` **et** `--tri` tous deux
  égaux à `--tcn-orange` (un trail et un triathlon reçoivent la même couleur) ;
  `lib/utils/format.ts:30-38` définit *une autre* échelle à six familles pour la barre
  empilée du dashboard — sur ses 15 paires, **6 sont indistinguables** (Duathlon/Aquathlon
  1,10:1, Run&Bike/Autres 1,15:1, Aquathlon/Run&Bike 1,32:1, Triathlon/Duathlon 1,45:1,
  Duathlon/Run&Bike 1,45:1, Aquathlon/Autres 1,52:1) — ce que la capture `/dashboard`
  confirme à l'œil, Aquathlon à 0,3 % étant simplement invisible. La barre empilée
  (`dashboard/page.tsx:87-89`) n'a ni libellé, ni motif, ni infobulle : la couleur est le
  **seul** encodage, et la pastille de légende de 12 × 12 px est la seule clé. Enfin 4 des
  6 graphiques n'ont **aucune** alternative textuelle (`Histogram`, `CategoryBars`,
  `MonthlyTrend`, `BarList` : pas un `role`, `aria-*`, `<title>` ou `<desc>`).
- **Proposition** : déclarer `--ink-mix` dans `:root` (ou supprimer l'indirection et écrire
  le pourcentage), définir `.micro-label` dans `@layer utilities` puis retirer les
  compensations ; fusionner les deux échelles en une seule source en écartant les paires
  sous 1,6:1 (l'encre et les deux gris fournissent assez d'amplitude **sans quitter la
  palette**) ; ajouter un libellé ou un motif sur les segments de la barre empilée, et un
  `role="img"` + `aria-label` récapitulatif ou un tableau `sr-only` sur les 4 graphiques muets.
- **Référence** : WCAG 2.2 **1.4.1 Utilisation de la couleur** —
  https://www.w3.org/WAI/WCAG22/quickref/#use-of-color — et **1.1.1 Contenu non textuel**.
- **Impact / effort** : **moyen** / **S** pour les deux tokens et les alternatives
  textuelles, **M** si l'échelle est refondue et re-testée.

---

## 5. Idées — coquille, navigation, `/dashboard`

### [NAV-2] Rendre le rail replié lisible : marque, libellés, et une catégorie qui mène quelque part

- **Écran** : toutes les pages, rail replié — l'état par défaut de toute première visite et
  de tout rendu serveur.
- **Problème** : dans le format que voit tout nouveau visiteur sur desktop, l'écran ne porte
  **aucune marque et aucun mot**. Le logo n'est rendu que déplié
  (`AppNav.tsx:181-186`) : `logo-tcn.png` n'apparaît **qu'une fois** dans le HTML servi,
  celle de la barre mobile. Ni logo, ni lien « retour à l'accueil », ni libellé de
  destination — des pastilles d'icônes dont le seul intitulé est un attribut `title`
  (`:561`), c'est-à-dire une infobulle native à ~1 s de délai, absente au tactile et jamais
  lue par le clavier. **La capture desktop en montre huit empilées** (hamburger, « + »
  orange, loupe, avatar « MH », 5 pastilles de destination, « M » en pied). Pire, la pastille
  « Club » n'est pas un lien : c'est un bouton qui ne fait que déplier le rail (`:534`),
  alors que la section ne contient plus qu'**une** destination livrée (`nav.config.ts:86`) —
  deux gestes pour une page, sans `aria-expanded` pour signaler qu'il s'agit d'un dépliant.
- **Nuance apportée par la capture** : la pastille de la page courante **est** teintée
  orange. Le rail replié répond donc bien à « où suis-je » ; il ne répond ni à « quel site
  est-ce » ni à « où mène cette icône ».
- **Proposition** : poser le monogramme dans l'en-tête du rail replié aussi, en lien vers
  `/dashboard` ; remplacer les `title` par un micro-libellé sous l'icône (le rail fait 76 px,
  `--tcn-nav-rail`) ou une infobulle maison au survol **et** au focus ; faire d'une section
  réduite à une seule destination un lien direct.
- **Référence** : Krug, *Don't Make Me Think*, « trunk test » — https://sensible.com/dont-make-me-think/ ;
  loi de Jakob — https://lawsofux.com/jakobs-law/ — le logo en haut à gauche comme retour à
  l'accueil est l'une des conventions les mieux apprises du web, et elle est ici sacrifiée
  pour 26 px de haut.
- **Impact / effort** : **fort** / **M** — c'est l'état par défaut, donc la première
  impression de tous.

### [NAV-3] Supprimer le double saut de mise en page à l'hydratation

- **Écran** : toutes les pages, rail déplié et tiroir mobile — visiteurs de retour et connectés.
- **Problème** : la page bouge sous les doigts au chargement, **deux fois**. Le rendu serveur
  part toujours du rail replié (`AppNav.tsx:44-48`, `expanded: false`) et l'état réellement
  choisi n'est relu qu'au montage (`:50-65`) : qui avait laissé le rail déplié voit la
  colonne passer de 76 px (`--tcn-nav-rail`) à 288 px (`--tcn-nav-panel`) avec une animation
  de 220 ms, soit **212 px de décalage horizontal de tout le contenu**, après la première
  peinture. Second saut, indépendant : la session est lue côté client (`:39` via
  `useSession`, sans `initialData`), donc le rail se peint d'abord en version anonyme — le
  HTML servi ne contient que « Tableau de bord », « Résultats », « Club » et « Se connecter »
  — puis, pour un connecté porteur de pouvoirs, se voit ajouter jusqu'à deux sections et voit
  son bouton remplacé par un avatar. La tuile de l'athlète retenu (`:429`) arrive par le même
  chemin tardif.
- **Proposition** : décider la largeur du rail **avant** la peinture — un cookie plutôt que
  `localStorage` pour `tcn-nav-expanded`, lu par le layout serveur et posé en variable CSS
  sur `<html>` (le patron classique du thème sombre) ; neutraliser le saut résiduel de la
  session en réservant la place des sections conditionnelles ou en n'animant la largeur
  qu'après le premier montage.
- **Référence** : Vercel Web Design Guidelines (résoudre les états dépendants du client avant
  la peinture) ; effet d'esthétique-utilisabilité —
  https://lawsofux.com/aesthetic-usability-effect/ — un contenu qui saute deux fois en une
  seconde entame le crédit de fiabilité accordé au reste.
- **Impact / effort** : **fort** / **M** — le saut se produit à chaque chargement pour les
  utilisateurs réguliers, c'est-à-dire les membres du club.

### [NAV-4] Sortir la navigation mobile de derrière le hamburger, et dire où l'on est

- **Écran** : toutes les pages, barre du haut mobile et tiroir mobile.
- **Problème** : sous `md`, l'intégralité de l'arborescence est enfermée derrière un seul
  bouton (`AppNav.tsx:243-249`) alors que le site public ne compte que **trois destinations
  livrées** (`nav.config.ts:67-68`, `:86`). La barre ne dit **jamais** sur quelle page on se
  trouve : elle contient un logo et trois pastilles, et rien d'autre — le repère
  `aria-current` n'existe que dans le rail et le tiroir (là où le desktop, lui, teinte bien
  la pastille active). Les quatre cibles sont toutes en haut de l'écran, la zone la plus
  coûteuse au pouce, et la zone basse est entièrement vide. Dans le tiroir, le pied entier
  ferme le tiroir au clic (`:286-291`) : appuyer sur « Se déconnecter » fait disparaître le
  tiroir avant que l'état d'attente du bouton (`UserMenu.tsx:72`) n'ait pu se voir.
- **Proposition** : une barre basse fixe portant les trois destinations publiques avec leur
  libellé et le marqueur de page courante, le hamburger ne gardant que l'administration et le
  compte ; à défaut, afficher le nom de la page courante dans la barre du haut. Et restreindre
  la fermeture du tiroir aux liens de navigation plutôt qu'à tout le pied.
- **Référence** : loi de Fitts — https://lawsofux.com/fittss-law/ ; Krug, *Don't Make Me
  Think* (« where am I » se signale dans la navigation, pas seulement dans le contenu).
- **Impact / effort** : **fort** / **M** — un club de triathlon se consulte au téléphone, et
  deux gestes séparent aujourd'hui l'utilisateur de la liste des résultats.

### [NAV-5] Nommer la barre d'outils du tableau de bord, et en montrer la portée

- **Écran** : `/dashboard`, desktop et mobile.
- **Problème** : trois contrôles côte à côte, aucun ne dit ce qu'il commande ni sur quoi. Le
  premier n'affiche que quatre mots — « Général │ Catégorie │ Genre │ Tous », confirmé dans le
  HTML **et sur la capture** — et son seul intitulé est un `aria-label` invisible
  (`RankTypeToggle.tsx:55`) : un utilisateur voyant n'a rien pour comprendre qu'il choisit un
  type de classement, et « Tous » à côté de « Genre » ne veut rien dire hors contexte. Sa
  portée est plus opaque encore : il ne recalcule que **trois** des sept tuiles
  (`StatCardsRank.tsx:49-71`) — la carte héroïque « Dossards enregistrés », « Type
  d'épreuves » et « Épreuves préférées » ne bougent pas, le seul indice étant le mot en petit
  sous chaque compteur. À côté, une case à cocher (`DisciplineToggle.tsx:36-47`) et un
  déclencheur de saisons (`SeasonSelector.tsx:68`) agissent eux sur toute la page : **trois
  formes visuelles, deux portées, aucune étiquette**.
- **Proposition** : un libellé visible au-dessus ou à gauche de chaque contrôle (« Type de
  rang », « Disciplines », « Saisons ») ; regrouper le sélecteur de rang avec les trois cartes
  qu'il gouverne plutôt que dans l'en-tête de page ; remonter la hauteur des trois cibles à
  44 px sous `md` (cf. `CIBLE-1`).
- **Référence** : Norman, *The Design of Everyday Things* — un `aria-label` n'est pas un
  signifiant visuel ; Wroblewski, *Web Form Design* — les libellés persistants battent
  l'absence de libellé parce qu'ils survivent à l'interaction.
- **Impact / effort** : **fort** / **S** — ces trois contrôles sont le seul moyen d'interroger
  le tableau de bord, et l'un des trois est indéchiffrable.

### [NAV-6] Remplacer le mur de zéros par un état vide qui propose une sortie

- **Écran** : `/dashboard`, tous formats — saison sans données, ou base fraîchement installée.
- **Problème** : `/dashboard?seasons=2015` sur la préproduction rend, mot pour mot :
  « Dossards enregistrés 0 · 0 athlètes · 0 épreuves », « Victoires 0 », « Podiums 0 »,
  « Top 10 0 », « Aucune épreuve enregistrée. », « Aucune épreuve. ». Six compteurs à zéro
  dont un dans la grande carte orange censée porter la bonne nouvelle de l'écran, **deux
  formulations différentes pour la même absence** (`dashboard/page.tsx:84` et `:119`), et
  aucune indication de cause ni de sortie : rien ne dit « cette saison n'a pas de résultat »,
  rien ne renvoie vers la saison en cours, rien ne propose d'ajouter une course. Le sélecteur
  ne liste que les saisons pourvues, donc l'utilisateur arrivé là par un lien partagé n'a
  même pas de repère. Le cas n'est pas théorique : c'est aussi ce que voit une installation
  neuve.
- **Proposition** : un état vide unique qui remplace toute la grille quand `stats.total === 0`
  — une phrase qui nomme la cause (« Aucun résultat enregistré pour la saison 2015 — 2016 »),
  un bouton « Voir la saison en cours » et le bouton primaire « Ajouter une épreuve » déjà
  existant ; et une seule formulation d'absence dans les deux cartes.
- **Référence** : Really Good UX — https://www.reallygoodux.io — cause + issue + action ;
  Norman : un zéro sans explication ne distingue pas « pas de donnée » d'« erreur ».
- **Impact / effort** : **fort** / **S** — une condition et un bloc de rendu dans un fichier.

### [NAV-7] Faire répondre l'écran d'atterrissage à « qu'est-ce qui vient de se passer »

- **Écran** : `/dashboard`, tous formats (`/` y redirige, `app/page.tsx:4`).
- **Problème** : la page d'accueil du site ne contient **aucune date**. Elle répond à
  « quelles épreuves fréquentons-nous le plus », question annuelle et lente : la seule liste
  de l'écran est triée par volume de dossards (`dashboard/page.tsx:46`), et le HTML comme la
  capture le confirment — « Triathlon de Montreuil Juigné », « DUATHLON COUERON »… sans un
  seul repère temporel. Un membre qui ouvre le site le lundi cherche le week-end écoulé : les
  résultats qui viennent d'arriver, les podiums, les imports récents. Il ne les trouve nulle
  part et doit repartir vers `/resultats`. Le composant `RecentCourses` que l'architecture
  annonce dans `components/dashboard/` (`frontend/AGENTS.md:71`) **n'existe pas** : la place
  est décrite, pas occupée. La capture ajoute que les deux cartes basses laissent ~150 px de
  vide, sur desktop comme sur mobile — il y a de la place.
- **Proposition** : un bloc « Dernières épreuves » au-dessus ou à la place d'« Épreuves
  préférées », alimenté par le `listEvents` déjà appelé (`:38-41`, `page_size: 200`) trié par
  date décroissante — **à coût réseau nul** — avec date, format et nombre de participants du
  club ; en complément, la mise en avant des podiums récents.
- **Référence** : usability.gov, architecture de l'information (le schéma d'organisation doit
  refléter la tâche dominante ; ici l'organisation est « par volume » quand la tâche est
  « par récence ») ; effet de position sérielle —
  https://lawsofux.com/serial-position-effect/ — la première position est la plus mémorisée
  et elle est donnée à l'information la moins périssable.
- **Impact / effort** : **fort** / **S** — les données sont déjà chargées ; c'est un tri.

### [NAV-8] Faire de la recherche d'athlète une vraie palette : dire qu'elle cherche, se piloter aux flèches, classer par pertinence

- **Écran** : partout (`⌘K` / `Ctrl K`), palette `AthletePicker`.
- **Problème** : la palette la plus utilisée du site ne dit jamais qu'elle travaille, ne se
  pilote pas au clavier, perd le focus — et **ne classe pas par pertinence**.
  1. Pendant les 250 ms de silence plus le temps réseau (`AthletePicker.tsx:99-121`), la zone
     de résultats est **entièrement vide** : l'état `loading` est calculé mais ne sert qu'à
     masquer le message d'absence (`:176`), donc rien ne s'affiche et l'utilisateur ne peut
     pas distinguer « je cherche » de « je n'ai rien trouvé ».
  2. Les résultats sont des `div role="button" tabIndex={0}` (`:147-158`) : pas de
     `combobox`/`listbox`, donc aucune navigation aux flèches, aucun élément actif, aucune
     annonce du nombre de résultats — il faut tabuler jusqu'à douze fois.
  3. À la fermeture, le focus n'est rendu à rien : `Modal` gère `Escape` et le clic sur le
     fond mais ne piège ni ne restaure le focus (`Modal.tsx:28-35`).
  4. La liste peut mentir : elle agrège côté client les **100 premières participations**
     correspondant au nom (`:101`) et n'en garde que 12 athlètes — pour un patronyme
     fréquent, un athlète peu couru peut être absent alors que la modale affirme « Aucun
     athlète trouvé ».
  5. **Constat de capture, que le code seul ne montrait pas** : le tri est **par nombre de
     courses, pas par qualité de correspondance**. Saisir « Herr » place « yves herry »
     (5 courses) **au-dessus** de la correspondance exacte « Mathieu HERRMANN » (3 courses),
     suivie de CHERRUEAU / CHERRIER / CHERRUAULT. La liste est en outre coupée en milieu de
     ligne par le pied de modale, sans affordance de défilement.
- **Proposition** : un squelette de trois lignes tant que `loading` ; la liste en
  `role="listbox"` avec `aria-activedescendant`, flèches et `Entrée`, plus un compte annoncé ;
  mémoriser le déclencheur et lui rendre le focus, piéger le focus dans `Modal` ; distinguer
  « aucun résultat » de « trop de résultats, précisez » ; **classer par correspondance
  (préfixe exact, puis début de mot, puis sous-chaîne) avant le volume** ; borner la hauteur
  de la liste avec un défilement visible.
- **Référence** : seuil de Doherty — https://lawsofux.com/doherty-threshold/ ; loi de Jakob
  (une palette `⌘K` a des conventions que les utilisateurs apportent avec eux) ; WCAG 2.2
  **2.4.3** Ordre du focus.
- **Impact / effort** : **fort** / **M** — c'est le point d'entrée unique vers un athlète, et
  la porte du dispositif « athlète retenu » (§ 10). Le tri par pertinence peut demander une
  route dédiée côté backend.

---

## 6. Idées — `/resultats`, `/courses/[id]`, détail de participation

### [RES-1] Le détail d'un résultat peut afficher moins que la ligne sur laquelle on a cliqué

- **Écran** : `/courses/[id]/participations/[participationId]`.
- **Problème** : sur les chronométreurs qui ne publient pas les splits de tous les finishers,
  l'athlète clique sa ligne — qui affichait son rang, son temps total et ses cinq inters — et
  atterrit sur une page qui **n'affiche plus rien de tout cela** : un titre « Statistiques
  indisponibles » et deux liens de retour. La garde de
  `participations/[participationId]/page.tsx:41-48` sort avant tout rendu **alors que l'objet
  `participation` porte `total_time`, `splits`, `rank_overall`, `rank_category` et
  `rank_gender`** — vérifié sur `GET /api/v1/participations/58375` : `stats: null` mais
  `rank_overall: 2`, `rank_category: 1`, splits complets. Fréquence mesurée : **8
  participations sur 32** échantillonnées sur 8 courses, soit **100 % des courses Breizh
  Chrono** (214, 324).
- **Proposition** : ne jamais rendre `UnavailableState` seul. Rendre systématiquement
  `ResultRow` (rang, temps, segments, rangs catégorie/genre), puis remplacer **uniquement**
  les trois blocs calculés (comparaison, évolution, matrice) par l'explication actuelle, en
  carte de même largeur. Le message devient « Comparaison au classement indisponible » et non
  « Statistiques indisponibles ».
- **Référence** : Norman, *The Design of Everyday Things* — un geste ne doit jamais retirer de
  l'information à l'écran ; Really Good UX pour les états vides utiles.
- **Impact / effort** : **fort** / **S** — c'est le seul écran de valeur ajoutée du produit,
  un quart des clics y mènent à une impasse totale, et le composant existe avec toutes ses
  props disponibles : seule la garde bouge. **Meilleur rapport de tout l'audit.**

### [RES-4] Une même compétition occupe quinze lignes quasi identiques dans la liste des épreuves

- **Écran** : `/resultats`.
- **Problème** : la liste annonce « 273 épreuves » mais un seul week-end en consomme quinze,
  toutes préfixées des **49 mêmes caractères** — « MEDOC ATLANTIQUE FRENCHMAN Triathlon
  Carcans 2026 - Frenchkid Aquathlon - 2013/2014 - Fille », puis « … - 2013/2014 - Garçon »,
  puis « … - 2015 - Fille »… Le regard doit lire jusqu'au **60ᵉ caractère** pour distinguer
  deux lignes, et le défilement infini par paquets de 30 (`lib/queries/events.ts:6`) impose 10
  chargements pour atteindre les épreuves les plus anciennes. `EventList.tsx:140-177` rend une
  liste plate, sans aucun regroupement.
- **Proposition** : regrouper par compétition parente (préfixe commun avant le premier « - »)
  en ligne dépliable portant le total de résultats et le total TCN ; à défaut, replier le
  préfixe commun visuellement (préfixe en gris clair, suffixe distinctif en gras) et insérer
  des séparateurs de mois collants dans le défilement.
- **Référence** : usability.gov, *Organization Schemes* —
  https://www.usability.gov/how-to-and-tools/methods/organization-schemes.html — une liste
  plate n'est pas un schéma d'organisation quand la clé réelle est l'événement ; Krug pour la
  scannabilité (l'œil doit trancher au premier mot, pas au soixantième).
- **Impact / effort** : **fort** / **M** — c'est la porte d'entrée du produit et son écran le
  plus visité. Le regroupement peut se faire côté client sur les pages déjà chargées, mais des
  compteurs honnêtes demandent un appui backend.

### [RES-5] Les cinq filtres forment un mur, et leurs libellés n'existent pas pour un lecteur d'écran

- **Écran** : `/resultats`, mobile surtout.
- **Problème** : cinq champs (athlète, course, discipline, du, au) plus deux boutons occupent
  tout le premier écran d'un téléphone avant le moindre résultat, alors que l'usage dominant
  est « je cherche un nom ». Et les libellés « Du » / « Au » ne sont **associés à aucun
  champ** : `ResultsFilters.tsx:232-238` rend `<label>` et `<Input>` en frères, sans
  `htmlFor`/`id` — confirmé dans le HTML servi (`<label>Du</label>` face à
  `<input id="base-ui-_R_18pbsnmdb_" type="date">`, jamais référencé). Un lecteur d'écran
  annonce deux champs de date anonymes.
- **Proposition** : sous `sm`, garder le seul champ « Athlète » visible et replier les quatre
  autres dans un `ui/sheet` « Filtres (2) » portant le compte actif ; associer chaque libellé
  par `htmlFor`/`id` ; porter la croix des chips à 24 px (cf. `CIBLE-1`).
- **Référence** : loi de Hick — https://lawsofux.com/hicks-law/ ; Wroblewski, *Web Form
  Design* (un libellé doit être **lié** au champ, pas seulement posé dessus) ; WCAG 2.2
  **3.3.2** *Labels or Instructions*.
- **Impact / effort** : **fort** / **M** — cumul d'un blocage d'accessibilité certain et du
  coût d'entrée sur l'écran principal en mobile ; l'association des libellés seule est **S**.

### [RES-7] Des répartitions tronquées présentées comme complètes

- **Écran** : `/courses/[id]`.
- **Problème** : la carte « Répartition par catégorie » affiche huit barres dont les
  pourcentages totalisent **86,1 %** sur la course 214 — **67 athlètes (13,9 %) n'apparaissent
  nulle part**, et rien ne dit qu'il en manque. Idem pour « Top clubs » : neuf clubs, sans
  « et N autres ». `GET /courses/214/summary` renvoie exactement 8 catégories pour
  `categories_total: 498` ; `courses/[id]/page.tsx:103` passe bien `total` à
  `CategoryBars.tsx:31`, qui n'affiche aucun reste. Détail voisin : l'en-tête « Club /
  Athlètes » est rendu même quand la liste est vide, au-dessus de « Clubs non renseignés. »
  (`page.tsx:108-112`, cas réel de la course 340).
- **Proposition** : une dernière barre « Autres (N) » calculée par différence, un pied « et N
  autres clubs », l'en-tête masqué quand la liste est vide, et des titres qui disent ce qu'ils
  montrent (« Huit catégories les plus représentées »).
- **Référence** : Norman — un affichage doit rendre visible ce qu'il omet, sinon il induit un
  modèle mental faux ; Really Good UX pour les états partiels.
- **Impact / effort** : **moyen** / **S** — n'empêche aucune tâche, mais fait mentir un
  chiffre, ce qui coûte cher sur un produit de résultats.

### [RES-8] 43 pages, et pour seule commande « Précédent / Suivant »

- **Écran** : `/courses/[id]`.
- **Problème** : 849 participants paginés par 20 donnent **43 pages** ; pour voir le milieu de
  classement il faut 21 clics, et il n'existe ni saut de page, ni « dernière page », ni choix
  du nombre de lignes, ni « aller à ma position ». `RaceFinishers.tsx:264-314` ne rend que
  deux liens et un texte « Page 1 sur 43 » non interactif. L'API sait pourtant rendre tout le
  classement (`pageSize: null` est prévu, `:48-49`), mais aucun contrôle ne l'expose. Corollaire
  déjà signalé par le lot : le tri client ne porte que sur la tranche affichée, ce qui est
  trompeur sur 43 pages.
- **Proposition** : un champ « Page ⟨n⟩ / 43 » validable, des liens première/dernière, un
  sélecteur 20/50/200 lignes, et — plus utile que tout — un bouton « Aller à mon résultat »
  qui saute à la page contenant le rang connu.
- **Référence** : loi de Fitts — https://lawsofux.com/fittss-law/ (21 allers-retours pour un
  rang connu) ; UserInterface.wiki — https://www.userinterface.wiki/ pour les patrons de
  pagination.
- **Impact / effort** : **moyen** / **S** pour le saut de page et le nombre de lignes, **M**
  avec « aller à mon résultat ».

### [RES-9] Après une recherche dans le classement, rien ne dit qu'on est dans une vue filtrée

- **Écran** : `/courses/[id]`.
- **Problème** : on cherche « kermarrec » sur la course 214, deux lignes s'affichent — et tout
  le reste de l'écran continue d'affirmer le contraire : le segmenté annonce « Tous les
  participants (498) », le pied de carte « 498 participants · 447 finishers · 9 abandons… », la
  pagination a disparu sans un mot. Aucun « 2 résultats pour "kermarrec" », aucun bouton pour
  effacer. Les compteurs viennent de `summary`, indépendants de la sélection
  (`RaceFinishers.tsx:160-168`, `:253-255`). Pire pour le filtre club : sur une course sans
  athlète TCN, le message d'absence dit « Aucun athlète ne correspond à cette **recherche** »
  alors qu'aucune recherche n'a été faite (`:241-242`, vérifié sur `/courses/340?scope=club`,
  dont le segmenté annonce déjà « Triathlon Club Nantais (0) »).
- **Proposition** : une ligne d'état sous l'en-tête de carte — « 2 résultats sur 498 pour
  "kermarrec" · Effacer » — et deux messages d'absence distincts, celui du filtre club portant
  un lien « Voir tous les participants ». Griser l'onglet TCN quand `tcn_count === 0` plutôt
  que d'offrir un filtre garanti vide.
- **Référence** : Krug — « où suis-je, que vois-je » doit se lire sans reconstruction ; WCAG
  2.2 **4.1.3** *Status Messages* (cf. `A11Y-5`).
- **Impact / effort** : **moyen** / **S** — la donnée affichée est juste, mais son cadre est
  faux, ce qui fait douter du reste.

### [RES-10] Des temps manifestement faux sont affichés sans le moindre signal

- **Écran** : `/courses/[id]`.
- **Problème** : sur la course 214 (Triathlon S, 498 participants), le premier du classement
  affiche « Natation 00:00:31 · Vélo 00:00:34 · Course 00:19:18 » pour un total de 01:06:18 :
  les inters ne se rapprochent même pas du total, et rien ne l'indique. Sur la course 340, la
  colonne T1 affiche littéralement **« 0-2:-15:00 »** pour deux athlètes —
  `RaceFinishers.tsx:223-227` rend `splits[s.key]` tel quel. Et l'incohérence est interne au
  produit : l'API publie `is_reliable` et `quality_issues`, `frontend/lib/quality.ts` sait les
  mettre en phrases, `athletes/[id]/page.tsx:120-121` les affiche — mais **ni la page course,
  ni `EventList`, ni le détail de participation ne les lisent**.
- **Proposition** : afficher le signal de fiabilité là où la donnée est lue — un badge
  « données douteuses » dans l'en-tête de la page course avec l'infobulle de `lib/quality.ts`,
  et une marque dans `EventList`. Ajouter une garde d'affichage : un split négatif ou non
  parsable devient « n. d. » plutôt qu'une chaîne brute, et un écart total/somme des inters
  > 2 % pose un discret marqueur sur la ligne.
- **Référence** : Norman — un affichage qui présente une valeur impossible sur le même ton
  qu'une valeur juste détruit la confiance dans tout le tableau ; Really Good UX pour les
  patrons de signalement en tableau.
- **Impact / effort** : **fort** / **M** — sur un produit de résultats, un chiffre visiblement
  faux non signalé discrédite l'ensemble, et le mécanisme existe déjà à côté.

### [RES-11] Les trois cartes de synthèse sont des impasses, et parlent en codes de catégorie

- **Écran** : `/courses/[id]`.
- **Problème** : on voit « BLAIN TRIATHLON 33 » et « V2 12,0 % », on veut voir ces 33 athlètes
  ou ces V2 dans le classement — **rien n'est cliquable** (`courses/[id]/page.tsx:114-122`,
  lignes de club en `div` ; `CategoryBars.tsx:31-42`, aucun lien). La seule sélection possible
  est « tous » ou « TCN ». Et « S2, V1, V3, PoM, CA, JU » ne sont expliqués nulle part : un
  parent qui consulte le résultat de son enfant ne sait pas ce que « PoM » désigne.
- **Proposition** : rendre chaque ligne de club et chaque barre de catégorie cliquable vers
  `?club=…` / `?category=…` sur le classement, avec le chip retirable correspondant (cf.
  `RES-9`) ; ajouter le libellé complet de la catégorie en infobulle, depuis une table de
  correspondance FFTRI.
- **Référence** : loi de Fitts (le chemin le plus court vers « les V2 » est la barre V2
  elle-même) ; usability.gov, *Organization Schemes* — club et catégorie sont deux schémas
  déjà affichés mais non navigables.
- **Impact / effort** : **moyen** / **M** — ouvre l'exploration de données déjà calculées,
  mais demande un filtre `club`/`category` côté API.

### [RES-12] La page de détail dit « Ma performance » à qui n'est pas l'athlète, et perd deux classements en route

- **Écran** : détail de participation, mobile surtout.
- **Problème** : trois pertes cumulées. (1) L'en-tête annonce **« Ma performance »**
  (`participation-detail/ResultRow.tsx:41`) alors que la page est publique et qu'on y arrive
  le plus souvent en regardant le résultat de quelqu'un d'autre. (2) L'API porte
  `rank_category` et `rank_gender` (KERMARREC : 1ᵉʳ de catégorie, 2ᵉ hommes), et `ResultCard`
  les affiche bien ailleurs — **la capture de `/club` le montre** — mais `ResultRow.tsx:51-70`
  ne montre que le scratch : le fait le plus valorisant du résultat disparaît sur l'écran qui
  lui est consacré. Ni dossard, ni club, ni statut, ni lien vers la source. (3) La bande de
  segments est un `repeat(${columns.length}, minmax(0, 1fr))` sans point de rupture (`:84-90`) :
  cinq colonnes sur 360 px, soit ~60 px par tuile pour un libellé et un temps en `00:31:36`.
- **Proposition** : remplacer l'eyebrow par « Performance » (ou le nom de l'athlète) ; ajouter
  une rangée de trois `PlaceBadge` scratch / catégorie / genre avec l'effectif de référence
  (« 1ᵉʳ / 51 en S3 ») ; passer la bande de segments en
  `repeat(auto-fit, minmax(110px, 1fr))`.
- **Référence** : effet Von Restorff — https://lawsofux.com/von-restorff-effect/ — le rang de
  catégorie est l'élément à distinguer, il est aujourd'hui absent ; Vercel Web Design
  Guidelines pour la grille responsive.
- **Impact / effort** : **moyen** / **S** — améliore l'écran à plus forte valeur sans nouvelle
  donnée à produire.

---

## 7. Idées — `/club`, `/athletes/[id]`, `/benevoles`

### [PROF-1] `/club` est une page orpheline : aucun lien ne mène à l'Espace club

- **Écran** : `/club`, tous formats.
- **Problème** : la page la plus riche du périmètre (820 résultats, 350 athlètes, podiums,
  tendance mensuelle) **n'est atteignable qu'en tapant l'URL à la main**. Aucune entrée de
  navigation ne la porte : `nav.config.ts:82` déclare
  `{ id: "vueclub", label: "Espace club", soon: true }` **sans `href`**, et `AppNav.tsx:110`
  filtre `!i.soon` — l'entrée n'est donc jamais rendue. Un `grep '"/club'` sur `app/`,
  `components/`, `lib/` ne rend qu'**une** occurrence, celle de `/club/athletes`
  (`nav.config.ts:86`). Aucun écran ne renvoie vers `/club`, et `/club` ne renvoie pas vers
  `/club/athletes`.
- **Proposition** : poser le `href: "/club"` et retirer le `soon` — l'écran est livré et
  complet ; le commentaire de `nav.config.ts:80-82` (« une seule destination, pas deux entrées
  pour un même écran ») décrit un arbitrage qui a survécu à la livraison. Puis relier les deux
  écrans club dans les deux sens : depuis « Athlètes du club » (`ClubDashboard.tsx:101-105`) un
  lien « Voir saison par saison → », et depuis `/club/athletes` un `backHref="/club"` que
  `PageHeader.tsx:26` supporte déjà.
- **Référence** : usability.gov, *Information Architecture* —
  https://www.usability.gov/what-and-why/information-architecture.html — la *findability* est
  le critère premier : un contenu non atteignable par la navigation n'existe pas.
- **Impact / effort** : **fort** / **S** — deux lignes et deux liens pour rendre visible un
  écran déjà construit et déjà servi. **Mais à ne pas livrer seul : voir `PROF-2`.**

### [PROF-2] `/club` déverse 350 fiches d'athlètes sans recherche, sans tri, sans limite

- **Écran** : `/club`, mobile surtout.
- **Problème** : la section « Athlètes du club » rend **une fiche par membre, toutes en même
  temps** — 350 cartes, 362 liens `/athletes/…`, **1 686 889 octets** de document
  (405 397 hors scripts). Le tri est par nombre de courses décroissant
  (`club-aggregate.ts:141-144`) : qui cherche un nom traverse d'abord le peloton de tête, puis
  **164 fiches à « 1 course »** — 47 % du roster, 227 fiches (65 %) à deux courses ou moins.
  `ClubDashboard.tsx:106-124` fait un `roster.map` sans `slice`. Sur mobile, une colonne, 350
  écrans de défilement sans un point de repère. Et `app/club/page.tsx:23` demande
  `page_size: 1000` pour 820 participations : **à 82 % du plafond**, le roster et les quatre
  KPI se tronqueront en silence, sans aucun signal à l'écran.
- **Proposition** : traiter le roster comme un aperçu, pas comme un annuaire — les 12 à 18
  athlètes les plus actifs puis un « Voir les 350 athlètes → » vers `/club/athletes`, qui porte
  déjà la recherche insensible aux accents et le tri (`AthleteSeasonList.tsx:79-87`) ; à
  défaut, y porter la même barre de recherche. Et rendre le plafond visible : quand
  `participations.length === 1000`, l'annoncer sous les KPI au lieu de laisser croire à un
  total.
- **Référence** : loi de Hick — https://lawsofux.com/hicks-law/ — 350 cibles équiprobables et
  non filtrables coûtent plus qu'elles n'apportent, là où un top 12 plus une porte de sortie
  rend instantanées les deux intentions (« qui domine ? », « où est Untel ? »).
- **Impact / effort** : **fort** / **M** — le `slice`, le lien et la bannière de plafond sont
  **S** ; l'arbitrage produit sur ce qui reste côté `/club` est ce qui coûte.

### [PROF-3] Sur le même écran, « Podiums 12 » et 169 podiums dans la liste juste en dessous

- **Écran** : `/club`, tous formats.
- **Problème** : le KPI annonce **12 podiums** quand la section « Athlètes du club », deux blocs
  plus bas, badge **109 athlètes cumulant 169 podiums**. Les deux nombres sont justes et
  incomparables : `ClubPodiumKpi.tsx:19` compte selon `?rank=` (défaut `scratch`,
  `lib/rank.ts:11`), `buildRoster` compte sur `ALL_CANDIDATES` **sans condition**
  (`club-aggregate.ts:127-134`), donc scratch + genre + catégorie. Conséquence directe :
  basculer le `RankTypeToggle` sur « Catégorie » fait bouger le KPI et « Podiums &
  performances » et **laisse les 169 badges du roster inchangés** — un filtre qui n'agit que
  sur une moitié d'écran. Aggravant : `PodiumsList.tsx:23` tronque à 6 entrées sans « tout
  voir », alors que le KPI en annonce 12 : le lecteur qui veut vérifier ne peut pas.
- **Proposition** : un seul mot, une seule définition par écran. Soit le roster suit `?rank=`,
  soit chaque chiffre porte sa portée dans son libellé (« 4 podiums, toutes portées » face à
  « 12 podiums scratch ») — la portée est déjà nommée dans `PODIUM_SCOPE_META` et affichée par
  `PodiumsList.tsx:63`, elle manque là où le chiffre est agrégé. Et ouvrir la liste au-delà de
  6.
- **Référence** : Norman, *The Design of Everyday Things* — le gouffre d'évaluation : deux
  chiffres contradictoires sous le même mot cassent le modèle mental, et un filtre qui n'agit
  que sur une partie de l'écran détruit le retour d'information.
- **Impact / effort** : **fort** / **S** — perte de confiance dans les chiffres, sur l'écran
  dont les chiffres sont le seul objet ; le paramètre de portée existe déjà partout.

### [PROF-4] Les cinq tuiles du profil sont calibrées pour le champion et rendent des tirets pour l'athlète médian

- **Écran** : `/athletes/[id]`, tous formats.
- **Problème** : la grille de KPI est identique pour tous. Pour l'athlète à une seule course —
  **164 des 350 membres, 47 %** — elle rend : « Épreuves 1 », « Meilleure place 1 »,
  « Meilleur ratio — », « Top 10 1 », « Format favori — » : deux tuiles vides, deux
  tautologies, une seule information (relevé sur `/athletes/52278`). `bestRatio` exige
  `course_finishers` (`page.tsx:61`) et `formatToken` rend `"—"` quand `distance_km` est nul
  (`page.tsx:56-59`). L'utilisateur majoritaire arrive donc sur un profil qui affiche surtout
  des absences, au moment précis où la page devrait lui donner envie de revenir.
- **Nuance apportée par la capture** : sur `/athletes/4`, la grille se replie proprement en
  2 colonnes sur mobile — la mise en page tient ; c'est le contenu des tuiles qui ne tient pas.
- **Proposition** : rendre la grille adaptative au volume. Sous 3 épreuves, remplacer les
  tuiles indécidables par ce qui est certain et utile — date de la dernière épreuve, discipline
  pratiquée, temps réalisé — et un appel à l'action (« Ajouter une épreuve manquante →
  `/ajouter` »). Ne jamais afficher un « — » nu : `StatCard.tsx:101-105` porte déjà un `hint`
  qui peut dire *pourquoi* (« classement complet non publié par le chronométreur »).
- **Référence** : Really Good UX — https://www.reallygoodux.io — un profil peu rempli est un
  état vide déguisé ; le patron d'état vide montre ce qui est possible, pas ce qui manque.
- **Impact / effort** : **fort** / **M** — concerne la moitié des profils du club ; la logique
  de seuil est simple, l'arbitrage des tuiles de remplacement coûte.

### [PROF-5] Le profil ne dit pas de qui l'on parle : ni club, ni catégorie, ni genre

- **Écran** : `/athletes/[id]`, tous formats.
  *(Le volet « aucun titre sur la page » de cette idée est traité par `A11Y-2`.)*
- **Problème** : le seul contexte affiché est le nom et le sur-titre « Résultats enregistrés » —
  ni club, ni catégorie, ni genre, alors qu'`AthleteBrief` porte `gender` et `club`
  (`lib/types.ts:3-9`), que chaque participation porte `category` et `club`
  (`lib/types.ts:79-80`), et que la `ResultCard` de `/club` les affiche bel et bien
  (« TRIATHLON CLUB NANTAIS V2 M » — **visible sur la capture de `/club`**). Or les homonymes
  existent dans ce jeu de données : « Hadrien KERMARREC » et « FLEURY hadrien /
  jean-baptiste . KERMARREC » cohabitent dans le roster, et la palette de recherche renvoie
  cinq patronymes voisins pour « Herr » (§ 3). Arrivé sur le profil, **on ne peut plus vérifier
  qu'on est sur le bon**.
- **Proposition** : passer l'en-tête sur `PageHeader` — `eyebrow` = club, `title` = nom,
  `children` = pastilles catégorie/genre via `MetaPill`, `backHref` vers l'écran d'origine.
- **Référence** : Krug, *Don't Make Me Think* — https://sensible.com/dont-make-me-think/ — le
  *trunk test* exige qu'on sache en un coup d'œil où l'on est **et de qui l'on parle**.
- **Impact / effort** : **moyen** / **S** — dix lignes d'en-tête, composant cible existant ;
  ambiguïté d'identité réelle sur ce jeu de données.

### [PROF-6] Le tableau des épreuves du profil n'a ni filtre saison ni filtre discipline

- **Écran** : `/athletes/[id]`, tous formats.
  *(Le volet « 988 px de large » est traité par `RESP-1`, le volet sémantique par `A11Y-3`.)*
- **Problème** : un membre de dix ans lit **quarante lignes à plat**, sans aucun moyen de
  restreindre à une saison ou à une discipline — alors que `/club/athletes` porte exactement ces
  deux filtres, déjà écrits (`app/club/athletes/page.tsx:44-46`). Le libellé d'aide dit par
  ailleurs « Clique sur une épreuve » (`page.tsx:104`), un verbe de souris sur un écran
  majoritairement tactile (cf. `COPY-2`).
- **Proposition** : reprendre le couple saison + discipline de `/club/athletes` au-dessus du
  tableau, avec le compte de lignes filtrées.
- **Référence** : usability.gov, *Organization Schemes* — la chronologie seule cesse d'être un
  schéma d'organisation utilisable passé quelques dizaines d'entrées.
- **Impact / effort** : **moyen** / **S** — les deux contrôles existent, il s'agit de les
  réemployer.

### [PROF-9] Valider un résultat casse le flux du bénévole au lieu de l'enchaîner

- **Écran** : `/benevoles`, mobile en premier mais aussi desktop.
- **Problème** : le bénévole traite une file. À chaque validation,
  `app/benevoles/page.tsx:52-55` retire la ligne **et remet `selectedId` à `null`** : le
  panneau disparaît et laisse « Sélectionnez un résultat dans la file pour le relire »
  (`page.tsx:127-129`). Il faut donc, après **chaque** validation, retourner pointer l'entrée
  suivante à la main. Sur mobile c'est pire : la grille
  `md:grid-cols-[minmax(280px,360px)_1fr]` (`page.tsx:112`) s'empile, donc le panneau de détail
  est rendu **sous la totalité de la file** ; toucher une entrée ne déplace ni le défilement ni
  le focus (`ValidationQueue.tsx:62` appelle `onSelect` et rien d'autre), et l'utilisateur reste
  face à la même liste, son panneau plusieurs écrans plus bas. Aucune notion de progression :
  « File (n) » et « Non conformes (n) » (`ValidationQueue.tsx:34,42`) ne disent pas combien on
  en a traité, et une validation réussie n'émet aucune confirmation.
- **Proposition** : enchaîner. Après validation ou rejet, sélectionner automatiquement l'entrée
  suivante, avec une confirmation brève (« Résultat validé — 12 restants ») ; réserver l'état
  vide à la file réellement épuisée et en faire un état de réussite (« File vide, merci ! »).
  Sur mobile, faire du panneau une feuille (`ui/sheet`, déjà utilisée par `AppNav`) ou à défaut
  déplacer focus et défilement à la sélection. Ajouter un compteur de session et les raccourcis
  clavier qui vont avec l'usage réel (trente entrées d'affilée).
- **Référence** : gradient de but — https://lawsofux.com/goal-gradient-effect/ — une file qui
  affiche son reste et enchaîne d'elle-même se vide ; une file qui repart à zéro après chaque
  geste décourage au troisième.
- **Impact / effort** : **fort** / **M** — outil de production interne dont le débit est la
  seule métrique, et le geste le plus fréquent est celui qui coûte le plus. La sélection
  suivante seule est **S**.

### [PROF-10] Le panneau bénévole demande quatre enregistrements séparés et enterre l'action principale

- **Écran** : `/benevoles`, tous formats.
- **Problème** : `ParticipationPanel` empile **quatre gestes d'écriture indépendants**, chacun
  avec son bouton et sa zone d'erreur — « Enregistrer le nom » (`:223-229`), la réattribution
  par clic sur un résultat de recherche (`:264-274`), « Enregistrer les modifications » pour
  quatre champs (`:331-333`), puis « Valider ce résultat » (`:344-346`). Rien ne dit lesquels
  sont obligatoires ni dans quel ordre ; **rien ne signale qu'on a saisi un dossard sans avoir
  cliqué le bon bouton avant de valider** — la validation n'est pas bloquée et emporte
  l'ancienne valeur en silence. L'action principale est la dernière du DOM, après quatre
  sections séparées par des filets : sur mobile, elle est hors écran au chargement. Et le
  bénévole n'a pas le point de comparaison dont il a besoin : la page ne montre pas ce que la
  source annonçait, seulement « Lien vers les résultats ↗ » (`:186-188`), qui ouvre un onglet
  et fait perdre le contexte.
- **Proposition** : un seul état de formulaire, un seul enregistrement — nom d'épreuve, dossard,
  place, club, catégorie et réattribution dans un même bloc à sauvegarde unique, avec un
  indicateur « modifications non enregistrées » et une validation qui enregistre d'abord.
  Remonter « Valider ce résultat » dans une barre d'action collante en bas de panneau. Afficher
  les valeurs d'origine à côté des champs modifiés (le `Participation` complet est déjà en
  mémoire).
- **Référence** : Wroblewski, *Web Form Design* —
  https://www.lukew.com/resources/web_form_design.asp — un formulaire à actions multiples et
  non hiérarchisées produit des abandons et des enregistrements partiels ; l'action primaire
  doit être unique, visible, et sur le chemin de lecture.
- **Impact / effort** : **moyen** / **M** — public restreint, mais chaque perte de saisie
  silencieuse dégrade la donnée que tout le reste de l'app affiche. 389 lignes et quatre appels
  API à réorchestrer.

---

## 8. Idées — `/ajouter`, `/carte`, `/login`

### [ACT-1] La saisie manuelle est mise en quarantaine, et personne ne le dit

- **Écran** : `/ajouter`, saisie manuelle, tous formats.
- **Problème** : un membre qui saisit sa participation à la main reçoit « Résultat
  enregistré. », le formulaire disparaît — puis il ne trouve son résultat **ni** dans les
  résultats, **ni** dans les stats du club, **ni** sur sa fiche athlète, et rien ne lui dit
  pourquoi ni quand cela changera. Le backend force `is_pending_validation=True` sur toute
  création publique, ce qui rend le résultat « invisible de tout agrégat public jusqu'à la
  validation d'un bénévole » (`backend/app/api/v1/participations.py:55`, docstring `:77`) —
  quand le front promet l'inverse : « Ta participation sera bien enregistrée. »
  (`TcnScrapeForm.tsx:210`) et un toast fugace sans réserve (`:99`). `persist` referme la carte
  (`:100`) sans jamais exploiter la `Participation` retournée, qui porte pourtant son `id`.
- **Proposition** : remplacer le toast par une `Alert status="success"` persistante qui nomme
  l'état réel — « Merci ! Ta participation est en attente de validation par un bénévole du club.
  Elle apparaîtra dans les résultats et les statistiques dès qu'elle sera validée » — avec le
  `PendingBadge` (#270) qui porte déjà ce vocabulaire, un lien vers la participation créée, et
  un délai indicatif. Et réviser l'accroche `:210` pour qu'elle annonce la validation au lieu
  de la nier.
- **Référence** : Norman, *The Design of Everyday Things* —
  https://www.nngroup.com/books/design-everyday-things-revised/ — un accusé de réception qui
  décrit un autre état que l'état réel produit exactement le *gulf of evaluation*.
- **Impact / effort** : **fort** / **S** — c'est le seul chemin de secours de l'app, et il se
  termine par une promesse fausse, qui se lit comme un bug. Une alerte, deux phrases, un lien.

### [ACT-2] Tous les échecs d'import se ressemblent, et tous sont imputés au chronométreur

- **Écran** : `/ajouter`, tous formats.
- **Problème** : qu'il échoue sur un 429 (« Trop de demandes envoyées récemment »,
  `backend/app/api/deps.py:185-188`, plafond de 10/h), sur un 500, sur une coupure réseau ou sur
  une page vraiment illisible, l'import affiche le **même** écran : « Impossible d'importer
  automatiquement » + saisie manuelle (`TcnScrapeForm.tsx:191-204`). **Dans trois cas sur
  quatre ce n'est pas le bon geste** : il faut attendre, ou réessayer. Pire, le même effet
  signale l'URL comme fournisseur non supporté au back-office pour **n'importe quelle** cause
  (`:66-70`), ce qui pollue la file `pending-providers` avec des liens Klikego parfaitement
  supportés. Cause racine en amont : `importEventStream` lève une `Error` nue et jette le
  statut HTTP (`lib/api/sse.ts:46`), alors que le reste du front dispose d'`ApiError` et de
  `messageDeRefus` (`lib/api/refus.ts:21-39`).
- **Proposition** : faire lever une `ApiError` par `importEventStream`, puis trois issues
  distinctes — 429 → « Tu as lancé trop d'imports dans l'heure, réessaie dans N minutes » avec
  compte à rebours (le backend renvoie déjà `Retry-After`) ; 5xx/réseau → « Le service n'a pas
  répondu » + **Réessayer** ; échec de lecture réel → l'alerte actuelle et la saisie manuelle.
  Et ne déclencher `reportPendingProvider` que dans ce dernier cas.
- **Référence** : Really Good UX — https://www.reallygoodux.io — un message d'erreur utile nomme
  la cause **et** l'action suivante, qui diffère par cause.
- **Impact / effort** : **fort** / **M** — le plafond de débit est atteignable en usage normal
  (un membre qui importe une journée de courses), le remède proposé est alors le mauvais, et
  l'effet de bord pollue le back-office.

### [ACT-3] Un import à moitié réussi s'affiche comme un succès complet

- **Écran** : `/ajouter`, tous formats.
- **Problème** : sur un fan-out multi-épreuves (Klikego, Wiclax, RaceResult), une partie des
  heats peut échouer ; le flux SSE le dit explicitement (`heats_failed`, `failures[]` en phase
  `done`, `lib/types.ts:236`) et le hook les stocke (`useImportStream.ts:100-104`). L'écran ne
  les lit **jamais** : le composant ne destructure ni `failures`, ni `heatsFailed`, ni même
  `updated` (`TcnScrapeForm.tsx:38-41`) et affiche « Résultats enregistrés avec succès ! » avec
  deux chiffres sur cinq (`:176-178`). Un import où 3 heats sur 12 ont échoué se lit comme un
  plein succès. Corollaire mesurable : un import qui ne fait que **mettre à jour**
  (`imported = 0`, `updated = 50`) affiche « 0 résultat ajouté ». Le composant `ImportProgress`
  sait pourtant tout afficher, `failures` comprises (`ImportProgress.tsx:49-62`) : il n'est
  importé par aucun écran — **du code mort qui documente l'écran manquant**.
- **Proposition** : rendre les cinq chiffres du bilan (ajoutés / mis à jour / déjà présents /
  épreuves importées / épreuves en échec) et, si `failures.length > 0`, dégrader le statut en
  `warning` avec la liste des heats manquants et un « Relancer l'import » ciblé. Supprimer
  `ImportProgress` ou en récupérer le rendu.
- **Référence** : Vercel Web Design Guidelines — *handle every state the data can be in* : un
  état que l'API émet et que l'UI n'affiche pas est un état perdu pour l'utilisateur.
- **Impact / effort** : **fort** / **S** — silencieux par construction, donc découvert tard et
  vécu comme une perte de données ; les données sont déjà dans l'état du hook.

### [ACT-4] L'attente de l'import n'est ni tenue, ni annoncée, ni protégée

- **Écran** : `/ajouter`, tous formats.
- **Problème** : pendant la phase `scraping` d'un fournisseur mono-course, l'écran affiche une
  ligne de texte **immobile** — « Récupération des participants… » — sans barre, sans
  pourcentage, sans indicateur animé (`TcnScrapeForm.tsx:456`), et cela peut durer des minutes
  sur une grosse épreuve : impossible de distinguer « ça travaille » de « c'est figé ». Aucun
  moyen de renoncer non plus — le hook n'expose aucune annulation, `importStream.reset` n'est
  jamais appelé, aucun `AbortController` (`useImportStream.ts:62-115`) : le seul recours est de
  fermer l'onglet, ce qui **coupe la connexion SSE et arrête l'import à mi-course**, sans
  qu'aucun écran ne l'ait prévenu (aucun `beforeunload` dans tout le front).
- **Proposition** : (a) indicateur animé indéterminé + minuterie écoulée en phase `scraping` ;
  (b) « Annuler l'import » branché sur un `AbortController` ; (c) un message sous la barre —
  « Reste sur cette page : quitter interrompt l'import » — doublé d'un garde `beforeunload` tant
  que `running`. *(Le volet `role="status"` est traité par `A11Y-5`.)*
- **Référence** : seuil de Doherty — https://lawsofux.com/doherty-threshold/ — au-delà de
  400 ms, il faut occuper l'attente par un retour continu.
- **Impact / effort** : **fort** / **M** — c'est le cœur du parcours, et la fenêtre où
  l'utilisateur peut tout perdre par un geste que rien ne décourage. L'annulation demande de
  faire passer un signal jusqu'au `fetch` de `sse.ts`.

### [ACT-5] Coller et vérifier une URL longue au doigt

- **Écran** : `/ajouter`, mobile.
- **Problème** : le geste fondateur de l'app se fait sur un champ dont la police fait **15 px**
  (`components/tcn/Input.tsx:48`), donc **sous** le seuil de 16 px à partir duquel iOS Safari
  cesse de zoomer automatiquement à la mise au point : l'écran fait un bond dès qu'on touche le
  champ et la page déborde. Une fois l'URL collée (les liens Klikego/Wiclax font facilement 120
  caractères), seule sa **fin** est visible ; aucun bouton pour effacer d'un geste
  (`Input.tsx:39-52` ne rend qu'un `<input>` nu), aucune aide au collage, et le champ n'est
  déclaré ni non capitalisant ni non corrigé (`TcnScrapeForm.tsx:129-139` pose `type="url"` et
  `inputMode="url"`, mais ni `autoCapitalize`, ni `spellCheck={false}`, ni `enterKeyHint`).
  Vérifier qu'on a collé le bon lien demande de faire défiler le texte au doigt à l'intérieur du
  champ.
- **Proposition** : porter la police à 16 px sur mobile (`ui/input` le fait déjà avec
  `text-base md:text-sm`) ; ajouter un « × » d'effacement (cible 44 px) et un bouton « Coller »
  via `navigator.clipboard.readText()` ; poser `autoCapitalize="none"`, `spellCheck={false}`,
  `enterKeyHint="go"` ; afficher sous le champ le domaine reconnu en clair (« klikego.com »)
  pour confirmer le bon lien sans faire défiler.
- **Référence** : Wroblewski, *Web Form Design* —
  https://rosenfeldmedia.com/books/web-form-design/ — formulaires mobiles : réduire la saisie,
  adapter le clavier, rendre visible ce qui a été saisi.
- **Impact / effort** : **fort sur mobile** / **S** — c'est le seul champ obligatoire de l'app,
  et le zoom iOS au focus se rencontre à chaque usage.

### [ACT-6] Une adresse non reconnue se dit trois fois, et rien ne prévient avant d'essayer

- **Écran** : `/ajouter`, tous formats.
- **Problème** : depuis la suppression de la sentinelle attrape-tout, une URL non reconnue ne
  matche **aucun** fournisseur — et l'écran l'annonce **trois fois en même temps** : un badge
  rouge « Non supporté — saisie manuelle » (`ProviderDetector.tsx:63`), une alerte jaune
  « Impossible d'importer automatiquement / Aucun chronométreur ne reconnaît cette adresse. »
  (`TcnScrapeForm.tsx:191-200`), et un bouton principal « Enregistrer les résultats » qui reste
  **actif** et promet le contraire (`:153`, dont le `disabled` ne teste que
  `running || !urlIsValid`, jamais `providerUnsupported`). Symétriquement, rien n'indique
  **avant** de coller quels chronométreurs sont pris en charge : le seul repère est un domaine
  inventé dans le placeholder (`résultats-chrono.fr`, `:134`), que personne ne reconnaîtra.
  L'utilisateur découvre donc le support après l'échec. Le badge apparaît et disparaît sans état
  intermédiaire (`ProviderDetector.tsx:54`), ce qui décale le bouton pendant la frappe.
- **Proposition** : un seul verdict, à un seul endroit — une ligne d'état sous le champ
  (fournisseur reconnu, ou non reconnu + « Saisir à la main ») à la place du badge et de
  l'alerte ; désactiver le bouton principal quand `providerUnsupported` ; réserver la hauteur de
  la ligne ; et afficher au repos les chronométreurs reconnus en puces, depuis
  `apiClient.listProviders()` qui existe déjà (`lib/api/client.ts:133`) — donc sans liste tenue
  à la main dans le front.
- **Référence** : Krug, *Don't Make Me Think* — trois formulations du même verdict font douter
  qu'il s'agisse du même, et un bouton actif est une promesse qu'on ne tient pas.
- **Impact / effort** : **fort** / **M** — c'est le point de rupture le plus fréquent du
  parcours, et il se présente aujourd'hui comme contradictoire.

### [ACT-9] La connexion ne gère ni la panne, ni le retour

- **Écran** : `/login`, tous formats.
- **Problème** : deux impasses. (a) `useAuthMethods` peut échouer (backend endormi, 500) ; la
  page ne lit que `data` et `isPending` (`app/login/page.tsx:23`) et **ne teste jamais
  `isError`** — le visiteur obtient alors une carte « Connexion » avec son paragraphe
  d'explication et **aucun bouton, aucun message, aucun Réessayer** : un écran qui a l'air fini
  et ne permet rien. La branche « aucun moyen de connexion » existe pourtant juste à côté
  (`:55-59`). (b) Le parcours ne se souvient pas d'où l'on vient : `UserMenu` pousse `/login`
  sans paramètre de retour (`UserMenu.tsx:45`), et le backend redirige **toujours** vers
  `/admin` après succès (`backend/app/api/v1/auth.py:228`), d'où pour un contributeur sans
  pouvoir d'administration un rebond silencieux vers `/dashboard`. Un bénévole qui se connecte
  depuis `/carte` se retrouve sur un tableau de bord, sans confirmation que sa connexion a
  réussi, et sans sa page de départ.
- **Proposition** : (a) ajouter la branche d'erreur — `Alert status="error"` « Les moyens de
  connexion n'ont pas pu être chargés » + **Réessayer** (`refetch`), en réutilisant
  `messageDeRefus` qui sait déjà distinguer panne et refus ; (b) faire porter au lien de
  connexion un `?next=`, le relayer au backend et rediriger là, `/admin` en seul repli ; et un
  toast « Connecté en tant que … » au retour, pour que le succès soit dit.
- **Référence** : Really Good UX — un écran qui ne peut rien faire doit le dire et offrir un
  geste, jamais se présenter comme complet.
- **Impact / effort** : **fort** pour (a) / **S** — la panne est probable sur un backend Render
  qui s'endort ; (b) est **moyen** / **M**, le `next=` traversant le backend.

### [ACT-10] La carte piège le défilement, et ce qu'on y touche ne mène nulle part

- **Écran** : `/carte`, mobile en premier.
  *(Le volet « cercles de 20 px » est traité par `CIBLE-1`.)*
- **Problème** : (1) le conteneur Leaflet occupe toute la largeur sur 320 px de haut
  (`MapView.tsx:109`) et ne désactive que la molette (`scrollWheelZoom={false}`) : `dragging` et
  `touchZoom` restent aux valeurs par défaut, donc **un doigt posé sur la carte pour faire
  défiler la page déplace la carte** — piège de défilement classique, qui rend la légende et la
  liste textuelle qui suivent difficiles à atteindre. (2) Quand on parvient à ouvrir un popup,
  c'est un cul-de-sac : nom, discipline, mois, nombre de participants et membres TCN
  (`MapView.tsx:131-145`) mais **aucun lien vers l'épreuve**, parce que `GeoEvent` ne transporte
  pas d'identifiant (`lib/types.ts:122-130`). On voit qu'il y a 34 participants à Vertou et on
  ne peut pas y aller ; la liste textuelle de repli n'a pas de lien non plus
  (`ListeEpreuves.tsx:37-55`).
- **Proposition** : (1) sur pointeur grossier, exiger un geste délibéré — `dragging: false` avec
  un voile « Toucher pour activer la carte », ou une contrainte à deux doigts façon *cooperative
  gestures* ; (2) ajouter `course_id` à `GET /stats/events-geo` et faire du nom de l'épreuve un
  lien vers `/courses/{id}`, dans le popup **et** dans la liste — c'est ce qui transforme la
  carte d'illustration en point d'entrée.
- **Référence** : WCAG 2.2 **2.5.7** *Dragging Movements* ; loi de Fitts —
  https://lawsofux.com/fittss-law/.
- **Impact / effort** : **fort sur mobile** pour le piège (il gêne la lecture de toute la page),
  **S** ; le lien est **moyen** / **M** car il touche le contrat de l'API et son type — mais
  c'est lui qui donne une raison de revenir sur cet écran.

### [ACT-11] Le formulaire manuel : seize champs, quatre obligatoires, et rien ne les distingue

- **Écran** : `/ajouter`, saisie manuelle, mobile en priorité.
- **Problème** : une quinzaine de champs de poids visuel identique
  (`ManualResultForm.tsx:138-256`) dont **quatre seulement sont requis** (prénom, nom, date, nom
  de l'épreuve — `:26-30`) : rien à l'écran ne le dit, ni astérisque, ni « optionnel », ni
  `aria-required`, le composant `Field` ne rendant qu'un libellé et un enfant (`:279-288`).
  L'utilisateur croit devoir tout remplir — y compris cinq champs de temps intermédiaires qu'il
  n'a pas — ou découvre les manques **après** avoir touché « Enregistrer le résultat » au bas de
  la page : `useForm` reste en validation à la soumission (`:87-94`, aucun `mode`), donc les
  erreurs arrivent toutes d'un coup, après coup. Microcopie : « Lien vers les résultats » est
  prérempli avec l'URL qui vient d'échouer, sans dire à quoi il sert ni qu'il est facultatif.
  *(Le volet `aria-invalid`/`aria-describedby` est traité par `A11Y-3`.)*
- **Proposition** : marquer les quatre champs requis et suffixer « (optionnel) » ailleurs ;
  passer en validation au `blur` (`mode: "onTouched"`) pour que chaque champ se corrige où il se
  remplit ; regrouper visuellement « Qui / Quelle épreuve / Quel résultat / Temps » (le bloc
  `Temps` montre déjà le patron) et replier les temps intermédiaires derrière un « Ajouter mes
  temps par discipline » ; reformuler en « Lien vers la page de résultats, si tu en as un
  (optionnel) ».
- **Référence** : Wroblewski, *Web Form Design* — marquage requis/optionnel, validation en
  ligne, regroupement : les trois chapitres qui portent exactement ces défauts.
- **Impact / effort** : **moyen à fort** / **M** — c'est le chemin de secours, emprunté
  précisément par ceux que l'automatisme a déjà laissés tomber, donc le pire moment pour
  abandonner.

---

## 9. Idées — back-office `/admin/*`

Le public de ces écrans est un bénévole occasionnel, non formé, qui revient après plusieurs
mois. Toutes les idées de cette section se lisent avec ce public en tête.

### [ADM-1] Trois écrans offrent des gestes que le serveur refusera

- **Écran** : `/admin/utilisateurs`, `/admin/acces`, `/admin/fournisseurs`.
- **Problème** : un administrateur clique un contrôle qui a toute l'apparence d'un contrôle
  actif, et récolte un message de refus brut ; il ne peut pas distinguer « je m'y prends mal »
  de « je n'ai pas le droit », et l'écran ne le lui dira jamais. Trois cas du même moule :
  `UserRolesTable` appelle `useRolesAttribuables()` mais **n'en destructure pas
  `peutAttribuer`** (`UserRolesTable.tsx:30`), donc le `<select>` « Attribuer un rôle » (`:125`)
  et la croix de retrait (`:107`) sont rendus sans condition alors que `lib/roles.ts:38` expose
  exactement le test attendu ; `RevokeSessionsCard` rend « Fermer toutes les sessions » sans
  aucune vérification (`:72`) quand la route exige `sessions:revoke`
  (`backend/app/api/v1/admin_sessions.py:36`) — et que le bouton **frère, sur le même écran**,
  teste bien ce pouvoir (`AllowedEmailsTable.tsx:46`) ; `PendingProvidersTable` rend « Traité »
  sans condition (`:73`) quand la route exige `pending_providers:handle`, distinct du
  `pending_providers:read` qui a ouvert la liste (`backend/app/api/v1/admin.py:54`, `:72`).
- **Proposition** : appliquer le patron déjà écrit trois fois dans le même dossier
  (`CoursesAdminTable`, `GroupsTable`, `CourseDuplicatesTable`) — un booléen dérivé de
  `session.permissions`, et le contrôle non rendu. Pour `UserRolesTable`, il suffit de consommer
  `peutAttribuer`. Corollaire à trancher une fois : quand un écran est atteint en lecture seule,
  y afficher la phrase que `RolePermissionsEditor:424` sait déjà dire (« Cet écran est en
  consultation ») plutôt que de laisser une page muette dont on ne sait pas si elle est cassée.
- **Référence** : Norman, *The Design of Everyday Things* —
  https://jnd.org/books/design-of-everyday-things-revised.html — un signifiant qui promet une
  action indisponible est la définition du faux affordance ; la prévention passe par ne pas
  offrir le geste.
- **Impact / effort** : **fort** / **S** — `frontend/AGENTS.md` identifie ce risque nommément
  pour `roles:read`/`roles:write`, mais la garde n'a été posée que sur cet écran-là ; trois
  autres portent le même défaut, dont un sur un geste d'incident. Trois booléens, trois
  conditions.

### [ADM-2] `/admin/batches` est annoncé à qui ne peut pas le lire

- **Écran** : `/admin/batches`.
- **Problème** : la personne à qui la navigation propose cet écran y arrive et trouve un bloc
  d'erreur là où devrait être l'état courant. L'entrée est conditionnée à `batch:run`
  (`nav.config.ts:127`), mais deux des trois sections exigent `batch:read` : `BatchRunList`
  appelle `useBatchRuns()` sans garde (`:113`) et rend un `EmptyState` « Lancements
  indisponibles » portant le message serveur brut (`:120-123`) ; et le garde-fou « un batch
  tourne déjà » de `BatchLauncher` se calcule sur cette même liste (`:42`, `:51`), donc pour ce
  porteur `enCours` vaut **toujours `false`** — le bouton reste actif, l'avertissement de `:140`
  ne s'affiche jamais, et le double lancement se solde par un conflit serveur. Le commentaire de
  `lib/queries/batches.ts:12` décrit exactement cette composition (« un porteur de `batch:run`
  seul n'a pas `batch:read` ») : elle est prévue, pas gérée.
- **Proposition** : trancher le public de l'écran. Soit `batch:read` devient le pouvoir qui
  l'annonce et `BatchLauncher` se masque sans `batch:run` ; soit les deux sections de lecture se
  remplacent, sans `batch:read`, par une phrase qui dit ce qui manque et pourquoi le lancement
  reste possible à l'aveugle. Dans les deux cas, ne pas laisser le garde-fou anti-double-lancement
  dépendre silencieusement d'une lecture facultative.
- **Référence** : Vercel Web Design Guidelines — un état d'erreur ne doit jamais être le rendu
  par défaut d'un utilisateur légitime ; un écran doit être cohérent avec la porte par laquelle
  on y entre.
- **Impact / effort** : **fort** / **S** — c'est l'écran des tâches lourdes, et son seul
  garde-fou contre un double lancement disparaît précisément pour le profil auquel on l'annonce.

### [ADM-3] On ne peut pas savoir quand un batch a démarré, ni s'il a réussi

- **Écran** : `/admin/batches`.
- **Problème** : l'administrateur lance une reprise et le tableau lui répond « En cours »,
  « 20/08/2026 », « — ». La colonne « Démarré » passe par `formatDate`
  (`BatchRunList.tsx:171`), qui **découpe l'horodatage sur les dix premiers caractères et jette
  l'heure** (`lib/utils/date.ts:3-4`) : deux lancements du même jour sont indiscernables, et
  rien ne dit si celui-ci a deux minutes ou six heures. La durée reste « — » tant que
  `duration_s` est nul, c'est-à-dire **pendant toute l'exécution** (`:172`, `:65-69`). Le seul
  retour temporel arrive au bout de deux heures (`:147-168`), bien après le moment où l'on se
  demande si quelque chose est coincé. Et l'état se lit dans un `<Badge>` sans variante (`:155`) :
  « Réussi », « Échec » et « Annulé » sortent tous en aplat orange primaire, **identiques à
  l'œil** — alors que le composant offre `destructive` et `secondary`
  (`components/ui/badge.tsx:12-19`) et que `FeedbackTable:122` sait déjà s'en servir. Enfin,
  rien à l'écran ne dit que le batch tourne sur un runner et non dans l'onglet : l'information
  n'existe que dans un commentaire de code (`app/admin/batches/page.tsx:14`).
- **Proposition** : un horodatage complet et un « démarré il y a X » qui se rafraîchit (le hook
  `useMaintenant` de `:31` le permet déjà, sans une requête de plus), une durée écoulée pour les
  états `pending`/`running`, une variante de badge par issue, et le lien vers l'exécution en
  permanence. Plus une phrase sous le titre : « Le traitement continue même si vous fermez cet
  onglet ; revenez ici pour lire le bilan. »
- **Référence** : seuil de Doherty — https://lawsofux.com/doherty-threshold/ — ici la
  progression est *régressive* : on en sait moins en regardant qu'en lançant. Complément : effet
  Von Restorff — https://lawsofux.com/von-restorff-effect/ — un échec qui porte la même couleur
  qu'un succès ne sera pas vu.
- **Impact / effort** : **fort** / **S** — c'est le seul endroit du produit où l'on constate
  qu'un traitement de masse s'est mal passé, et il ne le montre pas.

### [ADM-4] Un import lancé depuis un fichier n'apparaît pas dans « Lancements récents »

- **Écran** : `/admin/batches`.
- **Problème** : l'administrateur téléverse son fichier, lit « Import lancé (abc123) — 42
  épreuves », fait défiler jusqu'à « Lancements récents » où son import **ne figure pas** — et
  conclut que le lancement a échoué, donc recommence. `SheetUpload` utilise un `useMutation`
  brut dont le `onSuccess` ne fait que poser un état local (`SheetUpload.tsx:44-49`), là où
  `useLaunchBatch` invalide explicitement le cache des lancements
  (`lib/queries/batches.ts:55`) — et le commentaire de `:52` dit exactement pourquoi c'est
  nécessaire (« la plateforme ne rend aucun identifiant au dispatch : c'est cette invalidation
  qui fait apparaître l'exécution dans la liste »). Le `correlation_id` affiché ne vit que dans
  l'état du composant : un rechargement l'efface, et il n'est raccrochable à rien.
- **Proposition** : faire passer le lancement par fichier par la même invalidation que le
  lancement par formulaire, et remplacer le bloc de confirmation local par un renvoi vers la
  ligne créée dans « Lancements récents » — le compte-rendu appartient à la liste, pas au
  formulaire qui l'a déclenché.
- **Référence** : Norman — le retour d'information doit fermer la boucle à l'endroit où
  l'utilisateur ira vérifier ; un accusé non corroboré par l'état du système produit une seconde
  tentative.
- **Impact / effort** : **fort** / **S** — le double lancement d'un import de masse est le
  scénario coûteux, et il est ici encouragé par l'interface. **Une ligne d'invalidation** (cf.
  § 11 : c'est un bug, pas un manque de design).

### [ADM-5] Après un geste irréversible, il ne reste rien : ni reçu, ni journal

- **Écran** : `/admin/courses`, `/admin/doublons`.
- **Problème** : l'écran promet une trace que personne ne peut lire, et ne rend aucun compte de
  ce qu'il vient de détruire. `DeleteCourseDialog` affirme « Elle restera tracée dans le journal
  d'administration » (`:57-58`) et l'en-tête répète « Ces actions sont irréversibles et
  **tracées** » (`app/admin/courses/page.tsx:32`) — or le journal existe côté serveur
  (`backend/app/models/admin_action_log.py`,
  `backend/app/repositories/admin_action_log_repository.py:36`) **sans aucune route pour le
  lire** ni écran pour l'afficher : la promesse est invérifiable. Symétriquement, la purge totale
  chiffre l'avant (`WipeCoursesCard.tsx:103-119`) puis n'annonce qu'un « Toutes les épreuves ont
  été supprimées. » sans quantité (`:56`), l'appel rendant un 204 vide
  (`lib/api/client.ts:202`). Un bénévole qui vient de purger ne peut ni prouver ce qu'il a fait,
  ni dire combien, ni constater le lendemain qui avait fait quoi.
- **Proposition** : exposer le journal en lecture (une entrée de navigation, ou un panneau
  « Dernières actions d'administration » en pied des écrans concernés — les gestes destructifs y
  sont déjà tous écrits), et faire rendre par les routes de purge et de fusion le décompte réel,
  à réafficher dans le message de succès. À défaut d'exposer le journal, **retirer la promesse
  du texte** : une phrase qui rassure sur un filet inexistant est pire que le silence.
- **Référence** : Norman — la récupération d'erreur exige au minimum de savoir *ce qui a été
  fait* ; sans annulation possible, la traçabilité lisible est le seul substitut, et elle doit
  être atteignable par celui qui a agi.
- **Impact / effort** : **fort** / **L** — public bénévole, gestes sans retour, plusieurs
  administrateurs sur la même base : c'est le seul mécanisme de responsabilité du back-office, et
  il est écrit sans être lisible. Une route de lecture, un écran, et un changement de contrat sur
  deux routes de suppression.

### [ADM-6] `/admin` ne dit pas à quoi servent ses neuf écrans

- **Écran** : `/admin`.
- **Problème** : un bénévole qui revient après trois mois arrive sur une carte vide — « Tableau
  de bord à venir. Choisissez un écran d'administration dans la navigation. »
  (`app/admin/page.tsx:18-21`) — et doit reconstituer seul la carte des lieux depuis une liste
  de libellés. Or quatre de ces libellés sont quasi synonymes pour un non-initié : « Accès au
  back-office », « Rôles des utilisateurs », « Droits des rôles », « Groupes d'appartenance »
  (`nav.config.ts:162-195`). Chaque page porte bien la phrase qui la désambiguïse
  (`app/admin/groupes/page.tsx:20` : « Un groupe n'accorde aucun droit ») — mais elle n'est
  lisible qu'**après** avoir choisi, c'est-à-dire après l'hésitation qu'elle devait éviter.
  Incohérence de gabarit au passage : le rail annonce « Gestion des courses » quand l'écran
  s'intitule « Épreuves », et cette entrée est la seule de la section à ne porter **aucun**
  `permission` (`nav.config.ts:109`), donc la seule proposée à qui n'y peut rien faire.
- **Proposition** : faire de `/admin` un vrai sommaire — une tuile par écran, avec le titre exact
  de l'écran et sa phrase de description (elles existent déjà toutes, dans les `PageHeader`),
  filtrée par les mêmes pouvoirs que la navigation. Coût quasi nul puisque le contenu est écrit,
  et l'écran cesse d'être une impasse. Aligner le libellé de navigation sur le titre de la page.
- **Référence** : usability.gov, *Organization Schemes* —
  https://www.usability.gov/how-to-and-tools/methods/organization-schemes.html — un ensemble de
  destinations aux noms proches se désambiguïse par une page d'orientation qui expose le critère
  de découpage, pas par les libellés seuls. Complément : Krug — le coût d'une hésitation est payé
  à chaque visite, et un utilisateur occasionnel les paie toutes.
- **Impact / effort** : **fort** / **M** — c'est le point d'entrée du public exact décrit par la
  demande : rare, oublieux, non formé.

### [ADM-7] La purge totale campe au pied de l'écran le plus fréquenté

- **Écran** : `/admin/courses`.
- **Problème** : l'écran où l'on vient corriger la date d'une épreuve est celui qui héberge, en
  pied de page, « Purger tous les résultats » et « Supprimer toutes les épreuves »
  (`app/admin/courses/page.tsx:43-44`). Un administrateur qui feuillette le catalogue, atteint
  la dernière page et fait défiler se retrouve **à un clic de la destruction de toute la base**.
  Les deux cartes sont pourtant bien faites individuellement — chiffrage préalable, mot à taper,
  aucune ambiguïté de texte (`WipeCoursesCard.tsx:101-131`) : le problème n'est pas la
  confirmation, c'est le **voisinage**. Et rien ne sépare visuellement la zone de travail
  quotidien de la zone sans retour : trois `Card` empilées dans le même `space-y-6`.
- **Proposition** : isoler les deux purges dans une section explicitement nommée et visuellement
  distincte (« Zone de dangers — gestes sans retour »), repliée par défaut, ou mieux sur un écran
  de maintenance à part avec sa propre entrée gardée par
  `courses:wipe_all`/`participations:wipe_all`. Le geste rare doit coûter une navigation ; c'est
  ce coût qui le protège.
- **Référence** : loi de Fitts — https://lawsofux.com/fittss-law/ — la distance et la taille
  d'une cible doivent être proportionnelles à l'intention, ce qui implique d'éloigner
  délibérément les cibles dangereuses des trajectoires fréquentes. Complément : Really Good UX —
  le patron « danger zone » séparée est le standard des back-offices sur ce cas précis.
- **Impact / effort** : **moyen à fort** / **S** — la confirmation tient, mais la proximité crée
  l'occasion, et une purge n'a pas de seconde chance.

### [ADM-8] L'affordance destructive change d'un écran à l'autre

- **Écran** : `/admin/acces`, `/admin/groupes`, `/admin/courses`.
- **Problème** : rien de constant ne dit à l'administrateur « ce bouton-là détruit ». Sur
  `/admin/courses`, la corbeille est bordée et colorée en `destructive` au repos, avec un
  commentaire qui explique justement que « sans couleur rien ne dit lequel détruit »
  (`CoursesAdminTable.tsx:253-264`). Sur `/admin/acces`, « Retirer » — qui **ferme un accès et
  coupe les sessions vivantes** — et « Fermer les sessions » — réparable par une reconnexion —
  sont deux `variant="outline"` neutres, adjacents et de taille identique
  (`AllowedEmailsTable.tsx:212-234`) : **le plus grave des deux est le moins signalé**. Sur
  `/admin/groupes`, « Supprimer » est aussi un `outline` neutre (`GroupsTable.tsx:168-178`).
  Trois écrans, trois grammaires. Le mécanisme de confirmation est aussi hétérogène :
  `window.confirm` natif ici (`AllowedEmailsTable.tsx:85`, `RolePermissionsEditor.tsx:203,215`),
  `Dialog` maison là (`WipeCoursesCard`, `DeleteCourseDialog`), rien ailleurs
  (`GroupsTable:67-79`, justifié par le refus serveur d'un groupe peuplé — mais l'utilisateur ne
  le sait qu'après avoir cliqué).
- **Proposition** : une règle de deux lignes, appliquée aux cinq écrans — couleur `destructive`
  obligatoire dès qu'un geste ferme un accès ou détruit une donnée, neutre pour tout ce qui se
  refait ; et un seul mécanisme de confirmation, le `Dialog` du produit et non le `confirm` du
  navigateur, qui n'est ni traduisible, ni stylable, ni testable au même titre. Pour
  `GroupsTable`, dire *avant* le clic que la suppression sera refusée si le groupe est peuplé.
- **Référence** : Norman — les signifiants ne fonctionnent que s'ils sont cohérents : un code
  couleur appliqué sur un écran et pas sur le suivant n'enseigne rien et cesse d'être lu.
  Complément : UserInterface.wiki — https://www.userinterface.wiki/.
- **Impact / effort** : **moyen** / **S** — aucun geste n'est mal cadré isolément, mais le public
  occasionnel n'acquiert aucun réflexe, ce qui est exactement ce dont il aurait besoin.

### [ADM-9] Retirer un rôle à quelqu'un ne demande aucune confirmation

- **Écran** : `/admin/utilisateurs`.
  *(Le volet « cible de 16 px » est traité par `CIBLE-1`.)*
- **Problème** : le retrait d'un rôle — geste qui ôte des pouvoirs à quelqu'un, dont possiblement
  soi-même — s'exécute au premier clic, **sans confirmation ni annulation**
  (`UserRolesTable.tsx:107-116`). La comparaison interne est parlante : le retrait d'une
  **adresse** autorisée, de gravité comparable, est protégé par une confirmation nominative
  (`AllowedEmailsTable.tsx:85`) ; le retrait d'un rôle, non. Cas particulier jamais annoncé : le
  retrait de son propre dernier rôle, que le serveur refuse par un conflit — on l'apprend après.
- **Proposition** : une confirmation nommant la personne et le rôle, sur le modèle exact
  d'`AllowedEmailsTable`, et le cas « votre dernier rôle » dit **avant** le clic.
- **Référence** : Norman — un geste destructif sans confirmation ni annulation ne laisse aucune
  voie de récupération.
- **Impact / effort** : **moyen à fort** / **S** — c'est le seul geste destructif du périmètre à
  n'avoir aucun garde-fou ; un `Dialog` recopié de l'écran voisin.

### [ADM-10] Les retours utilisateurs ne forment pas une file de traitement

- **Écran** : `/admin/retours-utilisateurs`.
- **Problème** : l'administrateur ouvre l'écran pour répondre à « qu'est-ce qui reste à
  traiter ? » et n'obtient qu'une liste de tout, triée par date. **Aucun filtre par statut**
  (`FeedbackTable.tsx:61-85` : seuls `sort` et `order` sont pilotables), aucune pagination, et le
  statut s'affiche en texte nu (`:135`) là où le type est en badge coloré (`:122`) — de sorte que
  « Nouveau » et « Ignoré » ont exactement le même poids visuel. Le changement de statut est
  enfoui dans la modale de détail (`FeedbackDetailDialog.tsx:120-137`) : instruire dix
  signalements demande dix ouvertures-fermetures.
  *(Le volet `aria-sort` est traité par `A11Y-3`.)*
- **Proposition** : un filtre par statut au-dessus du tableau — « Nouveau » seul devrait être la
  vue par défaut —, un badge coloré par statut, un compteur « N nouveaux », et le changement de
  statut directement en ligne.
- **Référence** : Really Good UX — le patron de file de traitement (filtre par statut, action en
  ligne, compteur) est le standard de ce type d'écran.
- **Impact / effort** : **moyen** / **M** — l'écran fonctionne, mais son coût par élément traité
  est élevé, et un bénévole qui vient dix minutes n'en traitera qu'un ou deux.

### [ADM-11] Mobile : lisible, oui ; optimisé, non — et une seule barrière est vraiment gênante

- **Écran** : tous les `/admin/*`, `/admin/acces` en particulier.
- **Problème** : le lot tranche, arguments à l'appui — **ces écrans doivent être lisibles sur
  téléphone mais pas optimisés pour lui** : composer un rôle sur dix-huit cases, purger la base
  en tapant un mot, choisir entre deux doublons quasi identiques sont des gestes de bureau, et le
  seul geste réellement urgent, la révocation d'urgence, a une jumelle en CLI. L'état actuel
  tient d'ailleurs mieux que prévu : les tableaux sont enveloppés dans un `overflow-x-auto`
  (`components/ui/table.tsx:9-12`), ce qui est la réponse admise pour un tableau de données ; les
  filtres du catalogue passent en pleine largeur sous `sm` (`CoursesAdminTable.tsx:378,441`) ; et
  l'accordéon des rôles a été choisi précisément « pour que cela tienne sur un téléphone »
  (`RolePermissionsEditor.tsx:388`). **Une seule barrière est concrète** : le formulaire d'ajout
  d'adresse de `/admin/acces` est un `flex items-end gap-2` sans `flex-wrap` ni point de rupture
  (`AllowedEmailsTable.tsx:114`), avec dedans un champ e-mail extensible, un `<select>` en `w-48`
  fixe (`:134`) et un bouton — sur 375 px, le champ e-mail est écrasé à quelques dizaines de
  pixels. Or autoriser une adresse est justement le geste qu'un responsable fait en réunion,
  téléphone en main.
- **Proposition** : corriger ce seul formulaire (`flex-col gap-3 sm:flex-row sm:items-end`, comme
  `BenevoleAccessConfig.tsx:145` le fait déjà dans le même écran) **et écrire la position
  quelque part** : le back-office cible le bureau, la seule exigence mobile étant qu'aucun écran
  ne soit *cassé*. Cela ferme le sujet plutôt que de le rouvrir à chaque revue.
- **Référence** : Wroblewski, *Web Form Design* — un formulaire en ligne unique ne survit pas à la
  contrainte de largeur ; l'empilement est le défaut attendu, la mise en ligne l'exception.
  Complément : WCAG 2.2 **1.4.10** *Reflow*, qui admet explicitement le défilement horizontal
  pour les tableaux de données — ce qui valide le choix déjà fait sur les tableaux.
- **Impact / effort** : **faible à moyen** / **S** — un seul écran réellement pénalisé, mais
  c'est celui du geste le plus probablement fait en mobilité. Une classe, plus une décision à
  consigner.

---

## 10. Instruction de #323 — « à quoi sert un athlète retenu ? »

#323 a été fermée le 15/08/2026 (PR #361) en versant explicitement la question à cette passe :

> Hors périmètre — renvoyé vers #325 · « À quoi sert un athlète retenu ? » (filtre par défaut
> des listes, mise en avant dans les classements, comparaison, alertes…) n'est pas tranché et
> ne se tranche pas dans cette issue. Le besoin est versé au backlog d'idées produit de #325 ;
> chaque usage retenu deviendra sa propre issue.

**Le constat de terrain, d'abord.** Le stock `tcn-athlete` n'a que **deux** consommateurs dans
tout le front — vérifié par `grep readAthlete` sur `app/`, `components/`, `lib/` :
`AppNav.tsx:62,85` (la tuile du rail) et `app/athletes/[id]/SelectAthleteButton.tsx:20`. **Aucun
écran ne filtre, ne trie, ni ne se personnalise dessus.** Le geste est donc sans récompense — et
la promesse n'est nulle part énoncée : le même objet porte **quatre noms différents** selon
l'endroit (« Accès athlète » / « Sélectionne ton nom » dans la palette,
`AthletePicker.tsx:125-126` ; « Pas de blocage d'accès — choisis librement ton profil » en pied
de modale, `:131` ; « Mon profil » dans la tuile, `AppNav.tsx:450` ; « Choisir cet athlète » sur
le profil, `SelectAthleteButton.tsx:36`). La boucle se referme sur elle-même : rien ne motive le
geste, donc personne ne le fait, donc personne ne réclame la personnalisation.

**La réponse proposée** tient en quatre usages, classés du plus rentable au plus spéculatif. Les
quatre partagent un même arbitrage technique, à trancher **une fois pour toutes avant de coder** :
l'athlète retenu vit en `localStorage`, donc il n'atteint aucun rendu serveur. Deux voies —
cookie miroir lisible par le serveur, ou bloc rendu côté client sous un en-tête serveur. C'est le
vrai coût de ce cluster, et il est mutualisable.

### [PROF-7] Un état affiché, pas un libellé de commande

- **Écran** : `/athletes/[id]`, tous formats.
- **Problème** : sur le profil, le seul signal que « c'est vous » est le libellé du bouton, qui
  bascule de « Choisir cet athlète » à « Ne plus choisir cet athlète »
  (`SelectAthleteButton.tsx:31-38`) : **un libellé de commande, pas un état affiché**. Et rien ne
  répond à la question que l'utilisateur se pose au moment de cliquer : *pour quoi faire ?*
- **Proposition** : (a) quand le profil **est** l'athlète retenu, l'en-tête porte un signifiant
  permanent — pastille « C'est vous » via `MetaPill`, anneau orange sur l'`Avatar` — et le bouton
  devient secondaire ; (b) sous le bouton non retenu, un bénéfice nommé : « Choisir cet athlète
  pour retrouver ses résultats en un geste et se comparer au club ».
- **Référence** : effet de dotation — https://lawsofux.com/endowment-effect/ — tant que le profil
  ne reflète pas l'appropriation, le geste ne produit aucun sentiment de propriété et reste sans
  motif. Complément : Norman — un état système doit être signifié, pas déduit du libellé de son
  propre interrupteur.
- **Impact / effort** : **fort** / **S** — c'est le nœud : sans bénéfice visible, la notion
  entière reste morte, et avec elle les trois autres usages.

### [NAV-9] Une bande personnelle « Ma saison » en tête du tableau de bord

- **Écran** : `/dashboard`, tous formats.
- **Problème** : l'écran d'atterrissage ne parle que du club en agrégat ; le membre qui a désigné
  son nom n'y trouve rien de lui.
- **Proposition** : quand un athlète est retenu, insérer **au-dessus** des compteurs club une
  bande « Ma saison » reprenant les cinq indicateurs déjà calculés par la page profil
  (`app/athletes/[id]/page.tsx:78-101`) **mis en regard du club sur la même saison** : « 4
  épreuves · 1 podium — le club en a fait 32 ». C'est la réponse la moins spéculative à la
  question de #323 : elle transforme une vitrine de club en tableau de bord et réutilise un
  calcul existant. Corollaire de microcopie : nommer la chose **une** fois (« Mon athlète ») et
  énoncer la promesse au moment du choix — « Ton tableau de bord affichera tes résultats en
  premier » — au lieu du rassurant mais vide « Pas de blocage d'accès ».
- **Référence** : gradient de but — https://lawsofux.com/goal-gradient-effect/ — un dispositif ne
  se maintient que si le progrès qu'il apporte est visible.
- **Impact / effort** : **fort** / **M** — change la nature de l'écran d'accueil pour les
  membres ; porte l'arbitrage de transport décrit ci-dessus.

### [NAV-10] Propager le choix : filtre proposé et ligne retrouvée

- **Écran** : `/resultats`, `/courses/[id]`, tuile du rail.
- **Problème** : une fois son nom désigné, l'utilisateur doit quand même le **retaper partout**.
  `/resultats` expose un filtre par nom (`app/resultats/page.tsx:19`, servi par
  `ParticipationFilters.name`, `lib/types.ts:497`) que rien ne pré-remplit ; et dans un
  classement de 498 lignes, un athlète cherche sa propre ligne à l'œil.
- **Proposition** : trois gestes, tous à coût backend nul. (1) Sur `/resultats`, une pastille
  « Mes résultats » qui pose `?name=<nom complet>` — un filtre **proposé et révocable**, jamais
  appliqué en silence, pour ne pas faire croire que la base est vide. (2) Sur `/courses/[id]`,
  mettre visuellement en avant la ligne de l'athlète retenu et offrir un « aller à ma ligne » —
  c'est la demande la plus fréquente sur une page de classement, et elle rejoint `RES-8`. (3) Un
  raccourci « Mes résultats » dans la tuile du rail, à côté du lien vers le profil.
- **Référence** : effet Von Restorff — https://lawsofux.com/von-restorff-effect/ — dans une liste
  homogène, l'élément distinct est retrouvé sans être cherché. Complément : loi de Hick — un
  filtre pré-proposé retire un choix à faire à chaque visite sans en retirer la liberté.
- **Impact / effort** : **moyen à fort** / **M** — fort en usage quotidien, moyen en portée
  puisque cela ne concerne que les visiteurs ayant fait le choix. La pastille seule est **S**.

### [PROF-8] Ma ligne, retrouvable dans les listes du club

- **Écran** : `/club`, `/club/athletes`, tous formats.
- **Problème** : sur `/club`, ma carte est l'une de 350 triées par volume : si je cours deux fois
  par an, je suis quelque part dans les 227 fiches du bas. Sur `/club/athletes`, 207 lignes pour
  la saison en cours, même problème (`AthleteSeasonList.tsx:103-125`). Aucun des deux écrans ne
  lit l'athlète retenu. Pour se trouver, il faut soit connaître son propre volume, soit taper son
  nom dans la recherche de `/club/athletes` — geste que `/club` n'offre même pas (cf. `PROF-2`).
- **Proposition** : mettre ma ligne en évidence **sans casser le tri** — liseré orange et pastille
  « Vous », plus un rappel épinglé en tête de section quand ma ligne est hors du premier écran :
  « Vous : 3 épreuves — 41ᵉ du club », avec une ancre vers ma position réelle. C'est aussi la
  seule façon de rendre lisible la statistique que ces listes contiennent déjà implicitement : mon
  rang de volume dans le club.
- **Référence** : effet Von Restorff, complété par l'effet de position sérielle —
  https://lawsofux.com/serial-position-effect/ — l'épinglage en tête exploite la primauté quand la
  ligne réelle tombe au milieu, la zone la moins mémorisée.
- **Impact / effort** : **moyen** / **M** — forte valeur perçue, mais suspendu à `PROF-7` : sans
  raison de choisir un athlète, la mise en avant ne se déclenche pour personne. Les deux listes
  doivent devenir sensibles à une valeur client, ce qui touche l'hydratation de `ClubDashboard`,
  aujourd'hui purement serveur.

**Écarté sur ce cluster** : les **alertes et notifications** (piste nommée par #323) — elles
supposent un canal de notification et un compte lié à l'athlète, deux briques absentes. À rouvrir
seulement si `PROF-7`/`NAV-9` s'avèrent utilisés. Et la **personnalisation de `/benevoles`** :
l'écran ne connaît aucune identité individuelle par construction — mot de passe partagé, choix
RGPD/CNIL documenté (`app/benevoles/page.tsx:13-19`) — il n'y a rien à personnaliser.

**Réponse courte à la question de #323**, pour la porter telle quelle dans les issues filles :
*un athlète retenu sert à faire du tableau de bord le sien (« Ma saison » en regard du club), à
retrouver sa ligne sans la chercher (classements et listes du club), et à se comparer.* Il ne
sert **pas** à filtrer en silence, ni à recevoir des alertes.

---

## 11. Bugs, pas des idées

Cinq constats de cet audit ne sont pas des propositions de design : ce sont des défauts qui se
corrigent **sans aucun arbitrage produit**. Ils sont listés à part pour que personne ne les
confonde avec une question d'identité visuelle ou de parcours.

| # | Défaut | Preuve | Conséquence |
| --- | --- | --- | --- |
| 1 | `getCourseSources` n'a pas le `.catch(rendreNullSi404)` de ses voisins | `app/courses/[id]/page.tsx:58` contre `:56-57` | `/courses/999999` rend un **500 au corps HTML entièrement vide** au lieu du `notFound()` de `:60` |
| 2 | La variable CSS `--ink-mix` n'est déclarée nulle part | consommée par `lib/sport-colors.ts:34` et `ResultCard.tsx:80` | la couleur calculée retombe sur une valeur indéfinie |
| 3 | La classe `.micro-label` n'est définie dans aucun CSS | 5 usages dans les composants | cinq libellés rendus sans leur style |
| 4 | `SheetUpload` n'invalide pas le cache des lancements | `SheetUpload.tsx:44-49` contre `lib/queries/batches.ts:55` et son commentaire `:52` | l'import lancé n'apparaît pas dans la liste ⇒ double lancement (`ADM-4`) |
| 5 | Un split non parsable est rendu brut | `RaceFinishers.tsx:223-227` ; observé : `0-2:-15:00` sur la course 340 | l'utilisateur lit une chaîne impossible comme s'il s'agissait d'un temps (`RES-10`) |

Les points **2** et **3** méritent d'être dits explicitement : ce sont des **jetons morts**, pas
une remise en cause de la palette ni de la typographie. Les corriger revient à faire fonctionner
l'identité arbitrée telle qu'elle est écrite — c'est l'inverse de la rouvrir.

---

## 12. Fusions : de 69 constats bruts à 63 entrées

Les six lots ont produit **69 idées**. Sept ont disparu comme entrées autonomes parce qu'elles
décrivaient, écran par écran, un défaut qui se corrige **une fois** dans la coquille ; une entrée
nouvelle est née de l'agrégation d'un défaut que cinq lots avaient chacun rencontré sur leur
propre écran. Reste **63 entrées** — 69 − 7 + 1.

| Entrée conservée | Absorbe | Pourquoi la fusion |
| --- | --- | --- |
| `ETAT-1` | `ACT-7`, `ACT-8`, `PROF-11` (a) | un `not-found.tsx` et un `error.tsx`, pas trois diagnostics |
| `ETAT-2` | `RES-6`, `PROF-11` (b) et (c) | l'absence de `loading.tsx` est un manque de coquille, pas d'écran |
| `A11Y-1` | `NAV-1` (b) | un seul lien d'évitement pour tout le site |
| `A11Y-2` | `NAV-1` (a), `PROF-5` (a) | même défaut de balise sur quatre écrans, une seule correction |
| `A11Y-3` | `RES-2`, `RES-3` (b), `PROF-6` (b), `ACT-11` (a11y), `ADM-10` (`aria-sort`) | six grilles de `<div>`, une seule règle sémantique |
| `A11Y-5` | `ACT-4` (d) | un composant d'annonce, cinq points d'usage |
| `RESP-1` | `RES-3` (a), `PROF-6` (a) | quatre tableaux à largeur plancher, un même patron mobile |
| `CIBLE-1` *(nouvelle)* | sous-constats de `ADM-9`, `RES-5`, `PROF-10`, `ACT-10`, `NAV-5` | l'inventaire des cibles < 24 px se corrige en une passe, pas en cinq |

Les entrées qui gardent un **volet** dans une idée transversale le disent en italique sous leur
titre (`PROF-5`, `PROF-6`, `ACT-4`, `ACT-10`, `ACT-11`, `ADM-9`, `ADM-10`) : leur reste est
spécifique à l'écran et ne se traite pas dans la coquille.

**Couverture par écran** — les huit écrans publics annoncés par l'issue et les routes `/admin/*`
ont tous au moins une entrée, sauf `/club/athletes`, dont les deux constats
(`PROF-1` lien manquant, `PROF-8` ma ligne) sont portés par les écrans voisins, et
`/admin/doublons`, couvert par `ADM-5` et `ADM-8`.

---

## 13. Priorisation impact × effort

Impact = nombre d'utilisateurs touchés × fréquence du geste × gravité. Effort = **S** un fichier
ou quelques lignes, **M** un composant ou un aller-retour avec l'API, **L** plusieurs rendus à
concevoir et tester.

| | **S** | **M** | **L** |
| --- | --- | --- | --- |
| **Fort** | `ETAT-1` `A11Y-1` `A11Y-2` `A11Y-4` `NAV-5` `NAV-6` `NAV-7` `RES-1` `PROF-1` `PROF-3` `PROF-7` `ACT-1` `ACT-3` `ACT-5`¹ `ACT-9`² `ACT-10`³ `ADM-1` `ADM-2` `ADM-3` `ADM-4` | `ETAT-2` `NAV-2` `NAV-3` `NAV-4` `NAV-8` `NAV-9` `RES-4` `RES-5` `RES-10` `PROF-2` `PROF-4` `PROF-9` `ACT-2` `ACT-4` `ACT-6` `ADM-6` | `A11Y-3` `RESP-1` `ADM-5` |
| **Moyen** | `ETAT-3` `A11Y-5` `COPY-1` `COPY-2` `COPY-3` `CIBLE-1` `VIZ-1` `RES-7` `RES-8` `RES-9` `RES-12` `PROF-5` `PROF-6` `ADM-7` `ADM-8` `ADM-9` | `RESP-2` `RES-11` `PROF-8` `PROF-10` `NAV-10` `ACT-11` `ADM-10` | — |
| **Faible** | `ADM-11` | — | — |

¹ fort sur mobile · ² pour son volet (a), la branche d'erreur · ³ pour son volet piège de
défilement ; le lien vers l'épreuve est moyen / M.

**Vingt entrées en fort × S** : c'est le fait saillant de cet audit. Le produit ne souffre pas
d'un déficit de conception mais d'un **arriéré de finition** — des composants écrits et non
branchés (`ImportProgress`, `peutAttribuer`, `lib/quality.ts`, `PageHeader`, `RecentCourses`
annoncé et absent), des états non nominaux jamais rendus, des gardes posées sur un écran et pas
sur ses voisins.

---

## 14. Top 5 assumé

Le critère : impact réel mesuré sur la préproduction, effort tenable en une branche, et aucune
dépendance à un arbitrage produit ouvert. Trois des cinq sont en **fort × S**.

| # | Idée | Écran | Pourquoi celle-là |
| --- | --- | --- | --- |
| 1 | `RESP-1` — le temps d'arrivée hors écran sur mobile | `/resultats`, `/courses/[id]`, `/athletes/[id]`, `/benevoles` | Le club se consulte au téléphone, et l'information qu'on vient chercher — le temps, la place — est celle qui tombe hors du cadre : quatre tableaux à largeur plancher jusqu'à 1 080 px sur 288 px disponibles. C'est le seul **L** du top 5, et il est là parce qu'aucune retouche ne le remplace. |
| 2 | `RES-1` — le détail affiche moins que la ligne cliquée | détail de participation | Meilleur rapport de tout l'audit : **une garde à déplacer**, et un clic sur quatre cesse d'être une impasse (8 participations sur 32 échantillonnées, 100 % des courses Breizh Chrono). L'écran de plus forte valeur du produit. |
| 3 | `RES-4` — le mur de quinze lignes quasi identiques | `/resultats` | Porte d'entrée du produit, écran le plus visité : 49 caractères communs avant de pouvoir distinguer deux lignes, et 10 chargements pour atteindre le fond de liste. |
| 4 | `ETAT-1` — les pages d'absence et de panne | tout le site | Deux fichiers de trente lignes. Aujourd'hui : un 404 anglais en police système sur tout lien partagé périmé, et un **500 au corps vide** sur une course inconnue (le `.catch` manquant du § 11). C'est ce que voit un visiteur avant tout le reste. |
| 5 | `A11Y-4` — l'orange en texte à 3,32:1 | 35 emplacements | Non-conformité AA nette, sur la couleur la plus utilisée du site. **L'identité n'est pas touchée** : on remplace `--tcn-orange` par `--tcn-orange-deeper`, un token existant de la même palette, uniquement là où l'orange porte du texte. |

**Suppléants, si l'arbitrage produit préfère intervertir** — chacun est défendable à la place du
cinquième :

- **`PROF-1` + `PROF-2`, couplés** — le gain le moins cher de tout l'audit (deux lignes dans
  `nav.config.ts` rendent visible un écran complet déjà servi), mais **à ne pas livrer seul** :
  publier `/club` sans le rendre tenable expose une page de 1,69 Mo et 350 fiches non
  cherchables. Les deux ensemble, ou aucun des deux.
- **`A11Y-2`** — quatre écrans publics sans un seul titre ; changement de balise, styles
  inchangés.
- **`ACT-1`** — le seul chemin de secours de l'app se termine par une promesse fausse.
- **`NAV-6`** — le mur de zéros de l'écran d'atterrissage, qui se lit comme une panne.
- **`PROF-7`** — le nœud du cluster #323 (§ 10), à retenir si l'on veut ouvrir ce sujet
  maintenant plutôt que plus tard.

**Non retenu dans le top 5 malgré un impact fort** : `A11Y-3` (sémantique des six grilles) et
`ADM-5` (journal d'administration lisible) sont des **L** qui demandent respectivement ~500 lignes
de rendu à reprendre et une nouvelle route backend — ils appellent leur propre branche, pas un
premier train.

---

## 15. Écarté délibérément

Consolidé depuis les six lots, avec la raison. Ces lignes existent pour que le sujet ne se
rouvre pas à la prochaine revue.

**Hors périmètre par arbitrage déjà rendu**

- **La frontière `components/tcn/` vs `components/ui/`** — dette explicitement assumée dans
  `frontend/AGENTS.md` (« 485 lignes de rendu à re-vérifier pour zéro gain fonctionnel »). Sept
  écrans publics restent sur `ui/{card,button,badge,input}` : ce n'est pas rejugé ici.
- **Harmoniser `pushState` et `router.push`** entre les sélecteurs d'URL — asymétrie voulue et
  documentée paramètre par paramètre : `?sort=` n'est lu par aucun rendu serveur, `?seasons=`
  l'est.
- **Remplacer les `<select>` natifs** du formulaire manuel et du `CourseNavigator` par
  `ui/select` — choix explicite documenté.
- **Fusionner `/club` et `/club/athletes`** — #274 a tranché la séparation (synthèse contre liste
  nominative par saison) ; le problème est le lien manquant (`PROF-1`), pas la scission.
- **Paginer `/club/athletes` côté serveur** (207 lignes, 155 Ko) — tri et filtre en mémoire sur
  liste complète sont un arbitrage mesuré (#274, #382), et 207 lignes avec recherche restent
  tenables. Le volume problématique est celui de `/club` (`PROF-2`).
- **Un écran dédié à la révocation d'urgence** — décision d'architecture tranchée (#169) ; seule
  son ergonomie est challengée (`ADM-1`).
- **Repenser le regroupement des pouvoirs de `PermissionGrid`** — il vient du serveur par décision
  explicite (#240), et le composant est le plus soigné du périmètre (`<fieldset>`/`<legend>`,
  `aria-describedby`, cases figées visibles).
- **Rendre l'onglet « Carte » dans la navigation** — `MapView` existe et l'entrée est `soon`
  (`nav.config.ts:71`) : décision produit en attente, pas problème d'UX.
- **Squelette réservant la hauteur de la carte** pendant `Suspense`/`dynamic()` — le libellé
  d'attente unique est un arbitrage récent et volontaire (#299).
- **Renommer l'URL `/benevoles`** — le nom désigne un public quand l'écran est une tâche, et il
  entrera en collision avec la future entrée « Bénévolat » ; mais l'URL est communiquée telle
  quelle aux bénévoles (#271). À retrancher le jour où l'écran de créneaux arrive.

**Écarté sur le fond**

- **Découper `/ajouter` en assistant multi-étapes** — le champ unique « colle une URL » est la
  force de l'écran ; le fractionner ajouterait des étapes à un parcours qui n'en a qu'une.
- **Historique / autocomplétion des URL collées** — « Derniers résultats enregistrés » couvre déjà
  le besoin réel (« l'ai-je déjà importée ? »).
- **Grouper les cercles de la carte** (*marker clustering*) — une dépendance de plus pour un
  volume d'épreuves modeste ; à rouvrir si la densité mesurée le justifie.
- **Garder le bouton « Enregistrer les résultats » toujours actif** (recommandation Wroblewski) —
  l'erreur en ligne sous le champ dit déjà pourquoi, et `ACT-6` propose l'inverse pour le cas
  « non supporté » : deux règles opposées sur le même bouton seraient pires.
- **Fil d'Ariane** — trois niveaux de profondeur au maximum et le `backHref` de `PageHeader` déjà
  disponible : de la chrome sans désorientation constatée à résoudre.
- **`aria-expanded` sur la pastille de catégorie du rail replié** — vrai défaut, qui disparaît si
  `NAV-2` transforme la pastille en lien direct.
- **`aria-live` sur le KPI « Podiums » au changement de `?rank=`** — annoncer un chiffre incohérent
  aggrave `PROF-3` au lieu de le corriger.
- **Personnaliser `/benevoles` sur l'athlète retenu** — l'écran ne connaît aucune identité
  individuelle par construction (mot de passe partagé, choix RGPD/CNIL documenté).
- **Alertes et notifications sur l'athlète retenu** — supposent un canal de notification et un
  compte lié à l'athlète, deux briques absentes (§ 10).
- **Le plafond silencieux à 50 résultats de `CourseParticipationsDialog`** — réel, mais la
  recherche débouclée le compense et le cas d'usage est ciblé, pas exhaustif.
- **La perte de saisie à la fermeture d'`EditCourseDialog`/`EditAthleteDialog`** — trois à quatre
  champs, et le refus serveur préserve déjà la saisie, qui est le cas coûteux.
- **Le bouton flottant de retour utilisateur** — l'action la plus rare occupe la cible la plus
  facile à atteindre, et son glyphe est un emoji `💬` là où tout le reste utilise lucide. D'un cran
  sous les retenues, et il chevauche la question de l'iconographie.
- **Le rendu du RSC de `/admin/courses` avant la redirection vers `/login`** — relève de la
  sécurité, pas de l'UX ; le volet UX (un lien profond dépose sur `/login` sans explication ni
  retour) est couvert par `ADM-6` et `ACT-9`.
- **Corriger les splits `00:00:00` affichés pour les DNS** dans les « Résultats récents » de
  `/club` — vrai défaut de lecture, mais il vit dans `components/results/ResultCard`, et il est
  couvert par le principe de `RES-10`.

---

## 16. Manques de visualisation

**Routage — corrigé en cours d'audit.** L'issue #329 et ses filles #369 / #370 sont **fermées**,
et la PR #391 a migré les graphiques SVG vers **`d3-scale@4` et `d3-shape@3`** : le front **n'est
pas** sans bibliothèque graphique, et #329 a posé la règle par avance — « si l'audit UX recommande
de nouveaux graphiques, ils se posent sur la bibliothèque retenue ici, pas avant ». Ces manques
alimentent donc une **issue nouvelle**, dont la prémisse est la bibliothèque déjà en place ; ils ne
se versent pas dans des issues closes.

**Inventaire de l'existant** : histogramme des temps + donut genre (`conic-gradient` CSS) + barres
catégories sur `courses/[id]`, `RankingEvolutionChart` (258 l., client), `BarList` (42 l.),
`MonthlyTrend` (52 l.), `Histogram` (64 l.), `CategoryBars` (45 l.), `histogram-ticks.ts` (70 l.)
— quatre des six en rendu serveur.

Les 28 constats des lots se ramènent à **13 questions** que l'utilisateur se pose et que l'app ne
sait pas montrer. Formulées comme des questions, pour que le choix du graphique reste ouvert.

| # | Question | Où | Ce qui existe déjà |
| --- | --- | --- | --- |
| 1 | « Est-ce que je progresse ? » | `/athletes/[id]` | `bestRatio`/`rankRatio` sont calculés **puis réduits à un scalaire** (`page.tsx:61`) ; aucune série temporelle nulle part |
| 2 | « Mon temps, il vaut quoi ? » | `/courses/[id]`, détail de participation | l'histogramme des temps existe (`courses/[id]/page.tsx:126-137`) mais **ne marque pas où est l'athlète**, et n'est pas repris sur l'écran de la personne concernée |
| 3 | « Où je me situe dans **ma** catégorie ? » | `/courses/[id]`, détail | `CategoryBars` montre l'effectif par catégorie, jamais la place ; `rank_category` n'est affiché qu'en nombre nu, sans dénominateur |
| 4 | « Où je perds du temps, et est-ce que ça change ? » | détail, `/athletes/[id]` | `ComparisonTable.tsx:46-60` donne des pourcentages à lire ligne par ligne, pour **une** course ; `participation.splits` est chargé sur chaque ligne du profil et jamais affiché |
| 5 | « Ai-je accéléré, ou les autres ont-ils ralenti ? » | détail | `RankingEvolutionChart` ne trace que des **positions**, jamais des temps cumulés |
| 6 | « Comment je me compare à un coéquipier ? » | `/athletes/[id]` | aucune vue athlète contre athlète ; la donnée est déjà en mémoire (`listParticipations` en ramène 1 000) — c'est aussi le bénéfice manquant de `PROF-7` |
| 7 | « Sur quoi je cours vraiment, et combien par saison ? » | `/athletes/[id]` | `formatToken` calcule la distribution complète dans une `Map` (`page.tsx:54-58`) puis n'en garde que le mode ; `listAthleteSeasonActivity` sait compter par saison mais n'alimente que `/club/athletes` |
| 8 | « Le club progresse-t-il ? » | `/dashboard`, `/club` | `MonthlyTrend` compte du **volume**, jamais de la performance ; `SeasonSelector` accepte plusieurs saisons mais le tableau de bord n'en fait qu'un agrégat unique, alors que `rank_counters` et `by_month` sont servis |
| 9 | « À quoi ressemble le club ? » | `/club` | `buildRoster` agrège `gender` et `category` (`club-aggregate.ts:115-116`) sans jamais les afficher ; le fait le plus structurant du jeu de données (164 athlètes sur 350 à une seule course) n'est énoncé nulle part |
| 10 | « Où le club performe-t-il ? » | `/club`, `/dashboard` | `BarList` donne des épreuves par discipline, jamais discipline × performance ; `podiumsByScope` est calculé par athlète et jamais agrégé au club — c'est ce que `PROF-3` rate |
| 11 | « Quelles saisons sont couvertes, où sont les trous ? » | `/resultats` | 273 épreuves, aucune vue d'ensemble par mois ou année, alors que `MonthlyTrend` existe dans `components/charts/` |
| 12 | « Quelles épreuves près de chez moi, et lesquelles à venir ? » | `/carte` | les cercles sont dimensionnés au nombre de participants, sans filtre temporel, sans distinction des épreuves futures, sans distance : la carte répond « où le club est allé », pas « où je pourrais aller » |
| 13 | « La file de validation tient-elle le rythme ? » | `/benevoles` | `ValidationQueue.tsx:34,42` ne donne que deux cardinalités instantanées : ni arriéré dans le temps, ni délai moyen |

Deux constats des lots ne relèvent pas de la visualisation et sont traités ailleurs : le contrôle
de cohérence « somme des inters vs temps total » (`RES-10` et § 11) et la barre « Autres » des
catégories tronquées (`RES-7`).

---

## 17. Suite — comment #325 se ferme

L'issue se ferme sur **ce rapport fusionné et les issues filles créées**, sans aucune modification
de `frontend/` dans cette branche : c'est la contrainte posée par la demande, et elle est tenue.

**Décision d'arbitrage (20/08/2026).** Le top 5 du § 14 est retenu **tel quel**, avec deux
précisions du demandeur : les 63 entrées sont portées par une **issue parente (epic)** — l'intention
est de **tout traiter à terme**, pas de garder 58 entrées en réserve dormante — et les cinq bugs du
§ 11 partent en **cinq issues séparées**, indépendantes du backlog d'idées.

**Épic parente : #460** — porte les 63 entrées de ce rapport, groupées par la matrice du § 13,
chaque entrée cochable. Elle est le point de vérité de l'avancement ; ce fichier reste le point de
vérité des preuves. Une entrée ne se traite jamais depuis l'epic : elle devient une issue fille au
moment où quelqu'un s'y met.

**Issues filles créées d'emblée** — les cinq du top 5, plus deux, toutes rattachées à #460 :

1. **#461** — `RESP-1`, les quatre tableaux à largeur plancher sur mobile
2. **#462** — `RES-1`, le détail qui affiche moins que la ligne cliquée
3. **#463** — `RES-4`, le regroupement de la liste des épreuves
4. **#464** — `ETAT-1`, `not-found.tsx` et `error.tsx` en français
5. **#465** — `A11Y-4`, l'orange en texte, via `--tcn-orange-deeper`
6. **#466** — manques de visualisation (§ 16), prémisse `d3-scale`/`d3-shape` déjà en place,
   puisque #329/#369/#370 sont closes
7. **#467** — usages de l'athlète retenu (§ 10), la réponse à la question versée par #323 ; #323
   étant fermée, elle ne peut pas se trancher dans son fil. Un usage retenu = une issue, comme son
   corps le prescrivait — d'où `PROF-7` seul, dont `NAV-9`, `NAV-10` et `PROF-8` dépendent

**Les cinq bugs du § 11**, hors de l'arriéré d'idées : **#468** le `.catch` manquant, **#469**
`--ink-mix`, **#470** `.micro-label`, **#471** l'invalidation de cache de `SheetUpload`, **#472** le
split rendu brut. Chacune est minuscule, revuable seule, et livrable sans attendre l'arbitrage d'une
idée. Aucune ne rouvre l'identité visuelle : les deux jetons morts la font fonctionner telle qu'elle
est écrite.

**Ce que ce rapport n'autorise pas.** C'est un backlog, pas un plan : chaque issue fille reprend le
cycle normal (`docs/WORKFLOW-IA.md`), et une idée d'ici ne dispense ni de spec, ni de TDD, ni de la
revue `ui-ux-review` en fin de branche — laquelle juge du rendu contre l'identité arbitrée, sans
jamais la rouvrir (§ 1).

