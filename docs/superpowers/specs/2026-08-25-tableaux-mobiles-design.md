# Design — replier les tableaux à largeur plancher sur mobile (#461)

*Issue : #461. Origine : `RESP-1` de `2026-08-20-ui-ux-challenge-audit.md`, top 5 de #325.*
*Voie : Superpowers. Ce document est le design validé ; le plan d'implémentation le suit.*

## Le problème

Quatre écrans enferment une **liste d'enregistrements** dans une grille CSS à
`minWidth` fixe, sous un `overflowX: "auto"` :

| Écran | Composant | Plancher | Colonnes |
| --- | --- | --- | --- |
| Classement d'une course | `components/results/RaceFinishers.tsx` | 1 080 px | 11 |
| Fiche athlète | `app/(public_restricted)/athletes/[id]/EventsTable.tsx` | 988 px | 7 |
| `/resultats` | `components/results/EventList.tsx` | 948 px | 7 |
| `/ajouter` | `app/(public_restricted)/ajouter/page.tsx` | 480 px | 4 |

Sur un iPhone SE (375 px moins 32 px de gouttière `PageShell`), lire un
classement demande 3,1 écrans de défilement horizontal, sans en-tête figée : dès
qu'on atteint les inters, la colonne « Athlète » a disparu à gauche. Sur
`/athletes/4`, « Toutes les épreuves » n'affiche que DATE et ÉPREUVE — FORMAT,
TEMPS, PLACE et le ⚠ sont hors écran. La donnée pour laquelle on ouvre la page
est invisible sans geste, sur le contexte d'usage principal de l'application.

**Référence** : WCAG 2.2 **1.4.10 Redistribution** — pas de défilement
bidirectionnel à 320 px de large.

## Ce qui est décidé

### Technique : deux rendus, bascule CSS

Chaque écran rend **deux arbres** : la grille existante et une liste de cartes.
La bascule est une paire de classes Tailwind (`hidden min-[Npx]:block` /
`min-[Npx]:hidden`), donc pure CSS : le rendu serveur reste complet, il n'y a ni
`matchMedia`, ni état client, ni saut de mise en page à l'hydratation.

Deux techniques ont été écartées :

- **DOM unique piloté par CSS** (cellules `data-label`, bascule dans
  `globals.css`, patron de `.result-segments-grid` #462) : plus économe, mais la
  carte reste forcément la grille repliée. Les quatre écrans veulent des
  compositions différentes — un dépliant d'inters ici, un groupe repliable là,
  une sous-ligne d'actions ailleurs.
- **En-tête et colonnes collantes** (le repli de secours de l'audit) : ne
  supprime pas le défilement bidirectionnel, donc ne satisfait pas 1.4.10.

### Seuils : un par tableau, à son plancher

| Écran | Plancher grille | Seuil de bascule | Classe grille | Classe cartes |
| --- | --- | --- | --- | --- |
| Classement | 1 080 px | 1 237 px | `hidden min-[1237px]:block` | `min-[1237px]:hidden` |
| Fiche athlète | 988 px | 1 145 px | `hidden min-[1145px]:block` | `min-[1145px]:hidden` |
| `/resultats` | 948 px | 1 105 px | `hidden min-[1105px]:block` | `min-[1105px]:hidden` |
| `/ajouter` | 480 px | 640 px (`sm:`) | `hidden sm:block` | `sm:hidden` |

Un seuil unique à `sm:` aurait laissé la tablette et le petit portable sur un
tableau qui défile ; un seuil unique à `lg:` aurait renoncé à un tableau qui
tient encore sur `/ajouter` et `/resultats`. Chaque tableau bascule au point où
il cesse de tenir, et aucun écran ne défile jamais à l'horizontale.

**Correction (revue UI/UX #461, après la première implémentation) :** les crans
Tailwind par défaut (`lg:` 1024, `md:` 768) ignoraient le rail de navigation
(76 px replié) et les gouttières de `PageShell` (80 px à partir de `md:`) : sur
la bande de largeur entre le cran et `plancher + chrome`, la grille s'affichait
sans tenir, et redéfilait à l'horizontale — le défaut même que #461 corrige.
Les seuils ci-dessus sont désormais `plancher + CHROME_RAIL_REPLIE` (157 px,
`lib/utils/table.ts`), sauf `/ajouter` dont le plancher tient déjà sous `sm:`
une fois ce chrome ajouté (637 px). Le rail **déplié** (288 px, cookie #482)
n'est pas couvert par ce chrome — le résiduel documenté dans
`lib/utils/table.ts`.

### Le composant partagé : `components/tcn/LigneCarte.tsx`

Une coquille **sans état** — donc **sans `"use client"`**, ce qui laisse
`/ajouter` en Server Component.

```
LigneCarte
├─ zone cliquable   <Link href> ou <button> selon l'écran
│   ├─ marqueur     PlaceBadge / StatusBadge / date
│   ├─ titre        nom d'athlète ou d'épreuve (+ badges inline)
│   ├─ valeur       temps total / place / compteur   → justify-self: end
│   └─ meta         bande secondaire, qui passe à la ligne
├─ dépliant?        <details><summary>…</summary>   ← FRÈRE, jamais enfant
└─ actions?         liens et actions                 ← FRÈRE, jamais enfant
```

Props d'état visuel : `accent` (liseré orange TCN, repris du `borderLeft: 3px`
de `RaceFinishers`), `attenue` (fond grisé des non-finishers).

**Le dépliant et les actions sont frères de la zone cliquable, jamais enfants** :
un `<a>` ou un `<button>` imbriqué dans un `<Link>` est invalide en HTML. C'est
déjà la raison pour laquelle `EventsTable` sort « Voir la preuve » de sa ligne
(`EventsTable.tsx:314-341`), et le design ne fait que généraliser cette
contrainte.

**Plancher tactile de 44 px** sur la zone cliquable et sur le `<summary>`
(WCAG 2.2 2.5.8). `CIBLE-1` inventorie déjà sept manques de ce type dans le
produit ; il n'est pas question d'en créer un huitième.

Le composant ne sait rien des colonnes : pas de `Track[]`, pas de
`renderLigne`/`renderCarte`. Ce que les quatre tableaux partagent est un
**dessin**, pas une structure — `EventList` interpose des groupes de compétition,
`EventsTable` glisse deux sous-lignes après chaque ligne, `RaceFinishers` a
quatre états vides et un tri. Un composant générique aurait abstrait ce qu'ils
ont de moins commun.

### Écran 1 — le classement (`RaceFinishers`)

```
┌────────────────────────────────┐
│ Trier par : Temps total ▾   ↑↓ │  ← lg:hidden, écrit dans le même état `tri`
├────────────────────────────────┤
│▌①  Jean DUPONT         1:04:12 │  ← ▌ liseré orange si is_tcn
│    TCN · SEM · H               │
│    ▸ Inters                    │
├────────────────────────────────┤
│ DNF Marie MARTIN           —   │  ← fond atténué, StatusBadge en marqueur
└────────────────────────────────┘
```

- **Marqueur** : `PlaceBadge` si classé, `StatusBadge` si non-finisher, `—` sinon
  — la même logique que la cellule « Rang », déplacée.
- **Valeur** : `total_time`.
- **Méta** : club (en orange et gras si `is_tcn`) · catégorie · sexe.
- **Dépliant « Inters »** : la grille des segments, qui **réutilise
  `CelluleInter` tel quel**. Le ⚠ des temps illisibles (#472), son `title`, son
  `aria-label` et son `role="img"` survivent sans être réécrits.
- **Tri** : un `Select` « Trier par » alimenté par les mêmes clés que les
  en-têtes (`__temps_total__` plus une par segment) et un bouton d'inversion. Il
  écrit dans le **même état `tri`** : tourner le téléphone ne perd pas le tri, et
  le périmètre annoncé (« sur les N lignes affichées ») reste vrai des deux
  côtés.
- `AnnonceStatut` (WCAG 4.1.3, #477) est **au-dessus** des deux arbres : une
  seule région live, pas deux.

**Hors des deux arbres, donc inchangés** : la recherche, le filtre club, les
quatre états vides, `ClassementPagination`, le pied de synthèse. Seul le bloc
`overflowX` est dupliqué.

### Écran 2 — la fiche athlète (`EventsTable`)

```
┌────────────────────────────────┐
│ 12 mai 2025                    │
│ Triathlon de Nantes    1:04:12 │
│ Triathlon · [M] · ② /148  ⚠    │
│ [👁 Voir la preuve]            │  ← frère, comme aujourd'hui
│ [actions admin]                │  ← frère, se rend nul sans pouvoir
└────────────────────────────────┘
```

`PendingBadge` reste collé au nom d'épreuve. Le ⚠ de fiabilité garde son
`title`, son `aria-label`, son `role="img"` et son `data-testid`. Les deux
`Select` de filtre et le décompte `role="status"` sont au-dessus des deux
arbres, en un seul exemplaire.

`ParticipationAdminActions` est rendu dans les **deux** arbres, donc monté deux
fois par ligne — et c'est accepté, faute de pouvoir le placer une seule fois
sous deux blocs distincts du DOM. Le surcoût est nul en réseau : les vingt
lignes d'une page partagent déjà un seul appel de session (`useSession` a une
clé de cache unique, cf. le docstring du composant), et l'arbre masqué par CSS
n'est ni cliquable ni atteignable au clavier. Ce qui doit être vérifié en test
n'est donc pas l'unicité du montage, mais que la sous-ligne d'actions **existe
aussi dans l'arbre carte** : l'oublier retirerait aux administrateurs, sur
téléphone, des gestes qu'ils ont sur écran large.

### Écran 3 — `/resultats` (`EventList`)

```
┌────────────────────────────────┐
│ 12 mai 2025                    │
│ Triathlon de Nantes        [3] │  ← [3] Badge count TCN
│ Triathlon · [M] · 148 résultats│
├────────────────────────────────┤
│ 12 mai 2025                    │
│ Coupe de Bretagne          ▸   │  ← groupe #463, <button aria-expanded>
│ 4 épreuves · 512 résultats [7] │
│   ┌──────────────────────────┐ │
│   │ … Sprint H         [2]   │ │  ← cartes filles en retrait quand ouvert
└───┴──────────────────────────┴─┘
```

Le repli par compétition (#463) est **plus** utile en carte qu'en tableau :
c'est là que quinze lignes coûtent quinze écrans. L'état `ouverts` est partagé
par les deux arbres — replier sur téléphone puis élargir garde le repli.

Le défilement infini (`IntersectionObserver` sur une sentinelle) est en dehors
des deux arbres : une seule sentinelle, inchangée.

### Écran 4 — `/ajouter`

La carte la plus simple : date en marqueur, nom d'épreuve en titre, `FormatChip`
en méta, `Badge count` en valeur. Aucun dépliant, aucune action. **La page reste
un Server Component** — c'est la raison pour laquelle `LigneCarte` est sans
état.

### Écrans 5 et 6 — les deux matrices du détail de participation

`ComparisonTable` et `ImprovementMatrix` sont hors de `RESP-1` et hors de #461,
mais portent le même `overflowX`. Ils reçoivent un traitement **différent**, et
volontairement :

**Ils ne violent pas 1.4.10.** Ce sont de vrais `<table>`, et de vraies matrices
croisées (position × segment, segment × pourcentage). Le critère exempte
explicitement « les parties du contenu qui nécessitent une disposition
bidimensionnelle pour leur usage ou leur sens » ; les tableaux de données en
sont l'exemple canonique. Les quatre écrans ci-dessus, eux, sont des listes
d'enregistrements déguisées en grille — c'est ce qui les fait tomber sous le
critère.

**Une carte par ligne y détruirait l'information** : l'intérêt d'une matrice est
la comparaison colonne à colonne, et l'empiler la supprime.

Ce qu'ils reçoivent est une **réduction de colonnes sous `sm:`**, en CSS pure
(une classe par cellule masquée), sans double arbre :

- `ComparisonTable` — masquer les colonnes des segments `small` (T1, T2), déjà
  rendues en gris atténué et déjà signalées comme bruitées par la note du bas.
  7 colonnes → 5, soit ~370 px au lieu de ~500. La note existante gagne une
  phrase disant que ces colonnes se lisent sur écran large.
- `ImprovementMatrix` — passer de six paliers (0,5 / 1 / 2 / 5 / 10 / 25 %) à
  trois sous `sm:` (1 / 5 / 25 %). 7 colonnes → 4, ~300 px. Les paliers retirés
  s'interpolent à l'œil entre ceux qui restent.

Les deux restent des Server Components. Aucun impact sur les tests existants.

## Le piège des tests, et sa parade

**jsdom ne charge aucune feuille de style.** `hidden lg:block` est une classe
Tailwind ; dans la suite Vitest, les deux arbres sont donc présents et
interrogeables. Chaque nom d'athlète, chaque temps, chaque badge existe en
double, et tout `getByText` singulier lève « found multiple elements ».

Mesure faite avant décision : **159 requêtes singulières** dans les quatre
fichiers de test concernés (`RaceFinishers` 106, `EventsTable` 28, `EventList`
22, `ajouter` 3). Celles qui visent l'en-tête, la recherche ou la pagination
survivent ; celles qui visent le contenu d'une ligne, non — soit 60 à 90
assertions.

**Parade retenue**, dans `test/setup.ts` :

```ts
configure({
  defaultIgnore: 'script, style, [data-affichage="cartes"], [data-affichage="cartes"] *',
});
```

Le sélecteur de descendance n'est pas décoratif. `defaultIgnore` est appliqué
par `node.matches(ignore)`
(`@testing-library/dom@10.4.1`, `dist/queries/text.js:31`) : il n'écarte que les
nœuds qui matchent **eux-mêmes**. `'script, style'` fonctionne parce que le
texte y est porté *par* la balise ; le texte d'une carte, lui, est porté par un
descendant du conteneur marqué. Sans `[data-affichage="cartes"] *`, la parade ne
filtre rien du tout. Vérifié à l'exécution avant d'être retenu.

Deux conséquences, l'une bénigne, l'autre à connaître :

- **`getByRole` n'utilise pas `ignore`.** Une requête de rôle visant l'intérieur
  d'une ligne reste à scoper à la main, avec `within`.
- **`within` ne lève pas l'exclusion.** La configuration étant globale,
  `within(cartes()).getByText(…)` ne trouve rien : l'arbre carte devient
  invisible aux requêtes texte, y compris à celles qui le visent. Un test qui
  porte sur les cartes doit passer `{ ignore: false }` par requête. L'oubli ne
  se lit pas dans le message d'erreur — la requête dit simplement « unable to
  find an element », comme si la carte n'existait pas. C'est pourquoi un
  petit module `test/cartes.ts` expose `dansLesCartes(testId)`, dont la méthode
  `texte()` porte le `{ ignore: false }` une fois pour toutes.

Contrepartie assumée : c'est une **règle globale de test**, donc invisible à la
lecture d'un fichier de test. Elle est verrouillée par un test dédié dans
`test/`, qui rougit si la configuration disparaît — sans elle, une future carte
dupliquerait silencieusement toute assertion texte.

## Ce que les tests doivent prouver

TDD (Principe III de la constitution) : chaque point ci-dessous s'écrit en test
avant le code.

1. **Les champs annoncés sont dans la carte.** Un test par écran : rendre le
   composant, entrer dans `[data-affichage="cartes"]`, vérifier la présence de
   ce que le design lui donne (place, nom, temps, méta).
2. **Les seuils.** Le bloc grille porte bien `hidden lg:block` /
   `hidden md:block` / `hidden sm:block` selon l'écran. C'est la seule preuve
   automatisable de 1.4.10, et une erreur qui se réintroduit à la première
   retouche.
3. **Le ⚠ des inters illisibles (#472)** est rendu dans le dépliant, avec son
   nom accessible.
4. **Le tri mobile écrit dans le même état** que les en-têtes : trier depuis le
   `Select` réordonne aussi les lignes de l'arbre grille.
5. **Le repli de compétition (#463) est partagé** entre les deux arbres.
6. **La sous-ligne d'actions admin existe aussi dans l'arbre carte**, et « Voir
   la preuve » avec elle — deux gestes qu'un oubli retirerait au téléphone.
7. **La configuration `defaultIgnore` est présente** (test dans `test/`).
8. **Les matrices réduisent leurs colonnes** sous `sm:` sans perdre la note
   explicative.

## Hors périmètre

- `RESP-2` (graphiques à largeur fixe) — issue distincte.
- `CIBLE-1` (cibles tactiles sous 24 px) — issue distincte ; ce design n'en
  crée aucune nouvelle, il ne corrige pas les sept existantes.
- L'identité visuelle : couleurs, familles typographiques et tokens `--tcn-*`
  ne bougent pas.
- Le backend : aucun changement d'API, aucune migration.
