# Design — migration des graphiques SVG vers d3 (#370)

**Date** : 2026-08-15

**Contexte** : #370 est la sous-tâche 2/2 de #329, débloquée par la conclusion
du sondage #369 (`docs/superpowers/specs/2026-08-15-dataviz-librairie-sondage.md`),
qui prime sur ce design en cas de divergence. Le sondage retient **d3 en
modules seuls** (`d3-scale` + `d3-shape`) plutôt qu'une bibliothèque de
composants React, pour préserver le rendu serveur (RSC, zéro JS) des quatre
graphiques qui le sont aujourd'hui, et tranche déjà, graphique par graphique,
qui migre et vers quoi. Ce document couvre ce que le sondage a explicitement
laissé à traiter ici : détail d'implémentation, séquencement par lot,
structure de fichiers, stratégie de tests.

## 1. Portée et structure de fichiers

Quatre graphiques migrent vers d3, extraits en composants isolés sous
`components/charts/` :

- `components/charts/Histogram.tsx` — extrait de la fonction `Histogram`
  interne à `app/courses/[id]/page.tsx` (actuellement ligne ~198, non
  exportée).
- `components/charts/GenderDonut.tsx` et `components/charts/CategoryBars.tsx`
  — extraits du bloc actuellement inline dans `app/courses/[id]/page.tsx`
  (lignes ~110-141), qui mêle aujourd'hui donut et barres catégorie dans le
  même rendu de page. Séparés en deux composants car ce sont deux graphiques
  distincts, cohérent avec le reste de `components/charts/` (un fichier par
  graphique).
- `components/charts/MonthlyTrend.tsx` — déjà isolé ; migration interne
  seulement, pas de déplacement de fichier.
- `components/tcn/participation-detail/RankingEvolutionChart.tsx` — déjà
  isolé ; migration interne seulement.

Inchangés : `lib/utils/histogram-ticks.ts` (savoir métier sur le pas des
graduations temporelles, pas remplacé par d3, réutilisé tel quel par la
version d3 de l'histogramme) et `components/charts/BarList.tsx` (confirmé
hors périmètre par le sondage — 42 lignes de barres proportionnelles
simples, aucune valeur mesurable à migrer).

**Note sur une incohérence relevée dans le sondage** : les barres catégorie
(`app/courses/[id]/page.tsx:124-141`) sont structurellement identiques à
`BarList.tsx` (des `<div>` en largeur `%`, pas de SVG) — la même justification
qui exclut `BarList.tsx` s'appliquerait à elles. Décision actée pour #370 :
elles migrent quand même, à la lettre du tableau de conclusion du sondage.

## 2. Détail par graphique

### Histogramme (`app/courses/[id]/page.tsx:198` → `Histogram.tsx`)

`d3.scaleLinear()` remplace le calcul manuel des positions Y et des
graduations Y (actuellement lignes 226-237 et 239-242). L'axe X garde
`histogram-ticks.ts` tel quel — `buildTicks`/`formatTickLabel` ne sont pas du
calcul de position, mais du choix de pas "humain" par bande de durée, un
savoir métier que d3 ne remplace pas. Rendu serveur (RSC) préservé : d3-scale
ne touche jamais le DOM.

### Donut genre (`GenderDonut.tsx`)

`d3-shape.arc()` avec `innerRadius`/`outerRadius` remplace le
`conic-gradient` CSS actuel. Un `<path>` par tranche (homme/femme), chacun
avec son `role="img"`/`aria-label` (ou `title`) propre — l'alternative
textuelle par tranche que le sondage identifie comme gain par rapport au
dégradé CSS actuel, qui n'a que la légende externe comme texte. Le cercle
central (pourcentage affiché) reste un overlay HTML positionné en absolu,
comme aujourd'hui — seul l'anneau devient SVG.

**Point de vigilance** : le sondage n'a prototypé que l'histogramme : la
conclusion `d3-shape.arc()` pour le donut est une extrapolation non mesurée.
Migré en 2e lot (après l'histogramme, qui valide le patron d3 de bout en
bout) pour lever ce risque tôt plutôt qu'en fin de séquence.

### Barres catégorie (`CategoryBars.tsx`)

Même schéma que l'histogramme : `d3.scaleLinear()` pour la largeur en `%`
(remplace le calcul manuel `c.pct` déjà présent, qui devient
`scale(c.count)` plutôt qu'une division manuelle). Reste en CSS
(`<div>` de largeur `%`), pas de passage en SVG — seul le calcul change.

### Évolution du rang (`RankingEvolutionChart.tsx`, 247 lignes, déjà client)

`d3.scaleLinear()` pour l'échelle Y (`yOf`, remplace le calcul manuel lignes
~62-83 du fichier actuel) ; `d3.line()` avec `.curve(d3.curveMonotoneX)` pour
le tracé de la courbe scratch (remplace la construction manuelle de la
chaîne `path`, lignes ~75-77). Déjà `"use client"` : zéro régression RSC
possible ici, seul le poids de code interne change.

**Note** : `xOf` n'a, in fine, pas migré vers `scaleLinear` malgré ce que
laisse entendre le titre de section — c'est une décision, pas un oubli.
`xOf` mappe un index d'étape vers le centre d'une bande
(`PAD.left + (PLOT_W / steps.length) * (index + 0.5)`), ce qui est le
territoire de `d3-scale`'s `scaleBand`, pas de `scaleLinear` (le domaine
n'est pas continu, c'est un ensemble discret d'index). Introduire
`scaleBand` pour une seule ligne de calcul aurait dépassé le périmètre du
plan, qui exclut explicitement de laisser d3 choisir des valeurs de
position au-delà d'une projection linéaire simple.

**Contrat de non-régression** : les attributs `data-role`, `data-step`,
`data-y` et le comportement de survol/tooltip restent strictement identiques
— `RankingEvolutionChart.test.tsx` (déjà écrit, 12 cas) doit rester vert
**sans modification** ; ces tests sont le garde-fou de non-régression
comportementale pour ce lot, pas seulement une case à cocher.

### Activité mensuelle (`MonthlyTrend.tsx`, 44 lignes)

Reste en CSS flex — pas de passage en SVG, la migration ne change que le
calcul. **Corrigé pendant l'implémentation** : ce paragraphe annonçait à
l'origine `d3.scaleLinear().domain([0, max]).range([4, 100])(value)` comme
équivalent à `Math.max(4, (value / max) * 100)` — c'est faux
(`range([4,100])` donne 52 pour `value = max/2`, pas 50 : le plancher de 4
décale toute l'échelle, pas seulement le bas) et ce n'est pas ce qui a été
livré. Le code réellement livré (`MonthlyTrend.tsx`) garde le domaine
linéaire pur dans le scale — `d3.scaleLinear().domain([0, max]).range([0,
100])` — et applique le plancher `Math.max(4, ...)` **en dehors** du scale,
au point d'usage (`Math.max(4, heightScale(value))`). Gain de lignes quasi
nul ; migré pour la cohérence actée par le sondage (le motif est déjà en
place une fois les lots précédents faits), pas pour un gain de code sur ce
composant précis.

## 3. Stratégie de tests

TDD par composant, non-négociable (Principe III de la constitution) :
écrire ou adapter le test de rendu **avant** de toucher l'implémentation.

- **Histogramme, donut, barres catégorie** : aucun test de rendu n'existe
  aujourd'hui (`app/courses/[id]/page.test.tsx` ne teste que le calcul des
  pourcentages de catégorie, pas la structure SVG/DOM rendue) → un nouveau
  fichier de test par composant nouvellement extrait, sur le patron de
  `RankingEvolutionChart.test.tsx` : assertions sur la structure et les
  attributs rendus (nombre de barres/tranches, ordre, graduations, libellés),
  jamais de comparaison pixel ou de snapshot brut.
- **Évolution du rang** : le test existant (`RankingEvolutionChart.test.tsx`)
  est conservé tel quel et sert de garde-fou (cf. § précédent).
- **Activité mensuelle** : aucun test aujourd'hui → un test est ajouté,
  couvrant le comportement CSS-flex inchangé (hauteur relative, tri
  chronologique, troncature à 12 mois, état vide) au-delà du seul calcul du
  `%` qui change.

## 4. Séquencement

Quatre PRs, dans cet ordre :

1. **Histogramme** — le plus sûr : déjà prototypé dans le sondage (patron
   connu), rendu serveur, pas de comportement de survol à préserver.
2. **Donut + barres catégorie** — regroupés (même fichier source aujourd'hui,
   même PR). Le donut lève le risque non mesuré du sondage tôt dans la
   séquence plutôt qu'en dernier.
3. **Évolution du rang** — le plus gros gain de lignes attendu (247 lignes
   actuelles) ; bénéficie des patrons déjà validés par les deux lots
   précédents.
4. **Activité mensuelle** — ferme la marche, gain modeste, change surtout par
   cohérence.

**Étape de clôture** (pas nécessairement une 5e PR) : une fois les quatre
lots livrés, revue de duplication entre les usages de `d3.scaleLinear()`
introduits dans chacun. Un helper partagé (p. ex.
`lib/charts/scales.ts`) n'est extrait **que si** un vrai doublon apparaît à
ce stade — décision explicitement reportée à après implémentation complète,
pas prise par anticipation (« pas d'abstraction spéculative », `AGENTS.md`).
Chaque composant importe `d3-scale`/`d3-shape` directement dans les quatre
premiers lots.

## 5. Hors périmètre (rappel de l'issue #370)

- `components/charts/BarList.tsx` — inchangé, confirmé par le sondage.
- Aucune issue backend en regard : le contrat `/api/v1` reste gelé pour cette
  branche (Principe IV de la constitution).
- Le partage incohérent des agrégats front/backend (podiums recalculés vs
  catégories/clubs/histogramme venant du backend) — hors sujet, déjà dans le
  lot 2 de #328.
- `lib/utils/histogram-ticks.ts` — conservé tel quel, pas remplacé par d3.
