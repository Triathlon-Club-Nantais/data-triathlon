# Tableaux publics : grille, lignes liées, cartes

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## Les six listes publiques (#481)

**Les six listes publiques sont des tableaux dont la géométrie reste une
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

## Tableaux repliés en cartes sous leur seuil (#461)

**Tableaux repliés en cartes sous leur seuil** (#461, `RESP-1`) — quatre
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
  même que #461 corrige. Le rail **déplié** (288 px, cookie #482, `navigation.md`) n'est pas
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
