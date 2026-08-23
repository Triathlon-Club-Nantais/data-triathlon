# Graphiques : lisibilité au téléphone et couleurs distinguables — design

**Issue** : [#480](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/480)
(`RESP-2` + `VIZ-1` du § 4 de `2026-08-20-ui-ux-challenge-audit.md`) · Lot de l'epic #460 · Refs #325
**Bloquants levés** : #469 (`--ink-mix: 42%` déclaré), #470 (`.micro-label` définie)
**Date** : 2026-08-23

## 1. Le problème, et la contrainte qu'il faut d'abord admettre

Six graphiques existent. Aucun n'est lisible au téléphone, et le codage couleur
des disciplines ne distingue pas les disciplines.

- **`RESP-2`** — `Histogram` (`W = 900`) et `RankingEvolutionChart` (`WIDTH = 1000`)
  sont des SVG à `viewBox` fixe étirés à `width: 100%`. Leurs `<text>` sont
  dimensionnés dans l'espace du `viewBox`, donc mis à l'échelle avec lui : sur
  iPhone SE (287 px utiles dans la carte), facteur **0,32**, graduations à
  **3,5 px**. `MonthlyTrend` met ses valeurs en `opacity-0` révélées au
  `group-hover` et son repli dans un attribut `title` — deux mécanismes qui
  n'existent pas au doigt, donc les 12 barres n'affichent **jamais** de chiffre
  sur téléphone. Le `BarList` de `/club` s'étend de 1 à 279 sur une échelle
  linéaire : 8 lignes sur 14 rendent une barre invisible.
- **`VIZ-1`** — deux échelles de disciplines divergentes (`lib/sport-colors.ts`
  et `lib/utils/format.ts`), 6 paires indistinguables sur 15, la barre empilée du
  tableau de bord où la couleur est le **seul** encodage, et 4 graphiques sans
  aucune alternative textuelle.

### 1.1 La contrainte mesurée : la palette TCN ne porte que 4 couleurs séparables

Avant toute proposition, le calcul des 36 ratios de contraste entre les neuf
tons de la palette (`--tcn-orange`, `-deeper`, `-300`, `-200`, `--tcn-ink`,
`-2`, `-3`, `--tcn-grey-400`, `-300`) donne :

> **Le plus grand sous-ensemble de la palette dont *toutes* les paires tiennent
> ≥ 1,6:1 compte 4 couleurs** (8 solutions ; la meilleure, `orange + ink +
> ink-3 + grey-300`, plafonne à 1,77:1).

L'attendu littéral de l'issue — « une seule échelle de disciplines, paires sous
1,6:1 écartées **sans quitter la palette** » — est donc **infaisable à six
familles**. #325 interdit d'élargir la palette et #460 ne rejuge pas l'identité.

**Arbitrage retenu** : on garde les 6 familles et les 6 couleurs, et on déplace
l'exigence là où elle est atteignable et où elle compte réellement.

1. Dans une barre empilée, seules les paires **adjacentes** se touchent : 5
   paires, pas 15. Un ordre alterné clair/foncé les sépare largement.
2. La couleur cesse d'être le **seul** encodage (WCAG 1.4.1) : filet de
   séparation, libellé dans le segment quand la largeur le permet, légende
   nommée, alternative textuelle. Les paires non adjacentes n'ont dès lors plus
   à se distinguer entre elles.

Les deux autres sorties ont été écartées : réduire à 4 familles colorées ferait
disparaître Aquathlon et Run & Bike du codage ; élargir la palette rouvrirait
#325.

## 2. Échelle unique des disciplines

### 2.1 Source unique

`lib/sport-colors.ts` — le module *nommé* pour l'échelle catégorielle des
disciplines — devient la source unique. Il accueille `disciplineFamily()`
(nom + token) et `FAMILY_ORDER`, aujourd'hui dans `lib/utils/format.ts`.
`eventTypeColor()` n'est plus qu'un `disciplineFamily(type).color`, et
`aggregateDisciplines()` reste dans `format.ts` mais importe la famille.

Le jeu de familles retenu est **celui du tableau de bord** (statu quo) :
Triathlon, Swim & Run, Duathlon, Aquathlon, Run & Bike, Autres. L'ordre
d'empilement et de légende ne bouge pas.

### 2.2 Réaffectation des tokens

Triathlon garde l'orange de marque (`--tri` est documenté comme découplé du
primaire) ; « Autres » reste un neutre. Sous ces deux bornes, l'affectation qui
maximise l'adjacence est :

| Famille | Avant | Après | Contraste avec la précédente |
| --- | --- | --- | --- |
| Triathlon | `--tcn-orange` | `--tcn-orange` | — |
| Swim & Run | `--tcn-ink` | `--tcn-ink-2` | **2,96:1** |
| Duathlon | `--tcn-orange-300` | `--tcn-orange-300` | **4,29:1** |
| Aquathlon | `--tcn-grey-400` | `--tcn-ink` | **6,58:1** |
| Run & Bike | `--tcn-orange-200` | `--tcn-orange-deeper` | **2,90:1** |
| Autres | `--tcn-grey-300` | `--tcn-grey-300` | **3,79:1** |

**Minimum entre voisins : 2,90:1**, contre 1,10:1 aujourd'hui. Rien ne quitte la
palette.

### 2.3 Deux conséquences assumées

- **`--violet` est mort.** `DISCIPLINE_COLORS.violet` n'est renvoyé par aucune
  branche d'`eventTypeColor`, et le token n'a aucun autre consommateur. Il est
  supprimé de `lib/sport-colors.ts`, de `:root` et du bloc `@theme` — pas de
  couche de compatibilité, conformément aux principes de conception. `--tri`
  suit, pour la raison expliquée en § 2.4.
- **Les badges de `/resultats` perdent la distinction trail / cyclisme** : les
  deux tombent dans « Autres ». Sans coût d'accessibilité — le libellé de la
  discipline est écrit *dans* le badge, la couleur n'y a jamais été le seul
  encodage. C'est le prix du jeu de familles du tableau de bord, retenu pour ne
  pas redécouper la légende que les utilisateurs lisent déjà.

### 2.4 Effet de bord dans le même périmètre : l'échelle des splits

`lib/utils/splits.ts` réutilise `--swim` / `--bike` / `--run` pour les segments
d'une course (natation, vélo, course à pied, transitions), qui s'affichent
**côte à côte** dans `ResultCard`. Deux d'entre eux valent aujourd'hui
**1,45:1** (`bike` = `--tcn-orange-300` contre `run` = `--tcn-orange`) : c'est le
même défaut, sur un axe sémantique différent.

Le quadruplet est repris sous la même règle :

| Rôle | Avant | Après |
| --- | --- | --- |
| `--swim` | `--tcn-ink` | `--tcn-ink` |
| `--bike` | `--tcn-orange-300` | `--tcn-ink-3` |
| `--run` | `--tcn-orange` | `--tcn-orange` |
| transitions (T1/T2) | `--muted-foreground` | `--tcn-grey-300` |

**Minimum sur les 6 paires : 1,77:1** — le maximum atteignable dans la palette,
puisque c'est exactement la clique de 4 de la § 1.1.

Note : la collision `--run` = `--tri` que l'issue relève dans `eventTypeColor`
disparaît **par la fusion elle-même**, la fonction ne lisant plus ces alias.

Des cinq alias sémantiques, il n'en survit donc que **trois**, et pour les seuls
splits : `--swim`, `--bike`, `--run`. `--violet` n'a jamais eu de consommateur
(§ 2.3) et `--tri` perd le sien avec la fusion, la table des familles écrivant
directement ses tokens `--tcn-*` comme `disciplineFamily` le fait déjà. Les deux
sont supprimés de `:root` **et** du bloc `@theme` (`--color-tri`,
`--color-violet`).

## 3. Sortir les textes de l'échelle du `viewBox`

Avec `viewBox` fixe et `width: 100%`, **aucune unité CSS ne fige la taille d'un
`<text>` en px** : tout est mis à l'échelle avec le `viewBox`. Le rapport entre
desktop (~900 px) et iPhone SE (~287 px) valant 3:1, aucune valeur de `fontSize`
ne sert les deux.

`Histogram` et `RankingEvolutionChart` passent donc en **grille CSS** :

- le `<svg>` ne porte plus que la **géométrie** — barres, courbe, points, lignes
  de grille, axes ;
- les **graduations Y** deviennent une colonne de `<span>` à gauche du tracé ;
- les **libellés X** deviennent une rangée de `<span>` sous le tracé ;
- tous sont dimensionnés en **px réels** (11 px, quelle que soit la largeur).

Un seul rendu, aucune duplication de géométrie, aucun JavaScript : le rendu
serveur sans JS est préservé. Bénéfice de bord : ces textes deviennent
sélectionnables et lisibles par un lecteur d'écran, ce qu'un `<text>` SVG sans
`role` n'était pas.

Sur `RankingEvolutionChart`, la position de chaque segment s'écrit **en clair**
sous son libellé : l'infobulle au survol cesse d'être le seul accès au chiffre
(WCAG 1.4.13). L'infobulle elle-même reste inchangée.

## 4. `MonthlyTrend`, `BarList`, et les reliquats de #470

- **`MonthlyTrend`** — la valeur de chaque barre est affichée **en permanence**
  (`opacity-0` / `group-hover` supprimés), l'attribut `title` est retiré, les
  mois remontent à 11 px et ne s'affichent **qu'un sur deux** sous `sm:` pour
  tenir la largeur. La compensation `text-[8px]` disparaît.
- **`PodiumsList`** — la compensation `text-[9px]` disparaît de la même façon.
  Ces deux `text-[Npx]` sont les derniers reliquats du temps où `.micro-label`
  n'existait pas (#470).
- **`BarList`** — l'échelle reste **linéaire** : une barre deux fois plus longue
  doit continuer de valoir deux fois plus. Une échelle racine rendrait 279 contre
  1 comme un rapport de 17, que le chiffre affiché à côté démentirait. Seul un
  **plancher de largeur à 2 %** est ajouté, comme `MonthlyTrend` le fait déjà à
  4 % : la comparaison fine des petites valeurs se lit sur le chiffre, déjà
  présent à droite de chaque barre.

## 5. Alternatives textuelles et barre empilée

### 5.1 Les quatre graphiques muets

`Histogram`, `CategoryBars`, `MonthlyTrend` et `BarList` reçoivent
`role="img"` + un `aria-label` **récapitulatif** : une phrase de synthèse
nommant la nature de la répartition, son étendue et son extremum (par exemple
« Répartition par mois, 12 mois, de 3 à 47 dossards, maximum en juin »).

Le tableau `sr-only` a été écarté : dans trois de ces quatre graphiques la
valeur est déjà écrite en clair à côté de sa barre, et le quatrième
(`Histogram`) porte des tranches de temps dont le détail chiffré n'apporte rien
qu'un récapitulatif ne dise mieux.

### 5.2 La barre empilée de `/dashboard`

Trois ajouts, dont deux retirent à la couleur son statut d'encodage unique :

1. `role="img"` + `aria-label` récapitulatif sur la barre.
2. Un **filet blanc de 1 px** entre segments : la frontière devient visible même
   entre deux tons proches.
3. Le **nom de la famille dans le segment** quand sa largeur le permet. En
   dessous, la légende sous la barre porte déjà nom + pourcentage — un segment à
   0,3 % ne peut porter aucun libellé, et c'est la légende qui le nomme.

## 6. Ce qui est testé

TDD sur les cinq suites de graphiques existantes, plus un test neuf :

- **Un test de contraste**, sur le modèle d'`app/globals.test.ts`, qui verrouille
  les **5 paires adjacentes** de l'échelle des disciplines et les **6 paires**
  du quadruplet des splits au seuil de 1,6:1. C'est la seule régression que rien
  n'attrape à la lecture d'un diff : réordonner une famille ou retoucher un token
  casse silencieusement la séparation.
- `lib/sport-colors.test.ts` — la fusion des deux échelles, famille par famille,
  et la disparition de `--violet`.
- Les suites de `Histogram`, `MonthlyTrend`, `GenderDonut`, `CategoryBars` et
  `RankingEvolutionChart` — les libellés sortent du SVG, leurs sélecteurs
  changent.
- Le rendu serveur sans JavaScript reste vérifié : aucun des correctifs
  n'introduit d'interactivité.

## 7. Fichiers touchés

| Fichier | Nature |
| --- | --- |
| `lib/sport-colors.ts` | source unique de l'échelle ; `--violet` supprimé |
| `lib/utils/format.ts` | `disciplineFamily` / `FAMILY_ORDER` déplacés ; `aggregateDisciplines` importe |
| `lib/utils/splits.ts` | quadruplet des splits repris |
| `app/globals.css` | tokens de discipline réaffectés, `--violet` supprimé (`:root` + `@theme`) |
| `components/charts/Histogram.tsx` | grille CSS, libellés HTML, `role="img"` |
| `components/charts/MonthlyTrend.tsx` | valeurs permanentes, mois 1/2, `title` retiré, `role="img"` |
| `components/charts/BarList.tsx` | plancher de largeur, `role="img"` |
| `components/charts/CategoryBars.tsx` | `role="img"` |
| `components/tcn/participation-detail/RankingEvolutionChart.tsx` | grille CSS, libellés HTML, positions en clair |
| `components/club/PodiumsList.tsx` | `text-[9px]` retiré |
| `app/(public_restricted)/dashboard/page.tsx` | barre empilée : filet, libellés, `role="img"` |

## 8. Hors périmètre

- L'identité visuelle (`--tcn-*`, Anton/Barlow) et la frontière
  `components/tcn/` vs `components/ui/` : arbitrées, non rejugées (#325, #460).
- Les 13 questions du § 16 de l'audit (#466), qui se posent **sur** ce lot.
- Toute nouvelle visualisation : ce lot est l'hygiène des six graphiques
  existants, à faire avant d'en ajouter.
