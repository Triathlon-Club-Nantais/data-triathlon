# Sondage — choisir une bibliothèque de dataviz (#369, sous-tâche de #329)

**Date** : 2026-08-15

**Contexte** : #329 demande de choisir une bibliothèque de dataviz avant de
refondre les six graphiques SVG écrits à la main (~450 lignes). Le risque
identifié par l'issue : une bibliothèque orientée composants React ferait
basculer en `"use client"` quatre graphiques aujourd'hui rendus côté serveur
(RSC, zéro JS), à l'encontre du budget de perf mesuré par #328
(`docs/superpowers/specs/2026-08-14-perf-frontend-sondage.md`, ~930 ko bruts
de JS partagé par page).

Ce fichier est un **sondage** au sens d'AGENTS.md : il consigne ce qui a été
mesuré sur le terrain à la date ci-dessus, et **prime** sur toute spec/plan/
design en cas de divergence — toute correction se fait en re-sondant.

**Conclusion** : retenir **d3 en modules seuls** (`d3-scale` + `d3-shape`),
pas une bibliothèque de composants React ni visx. Détail et réserves
ci-dessous.

## Méthode

Quatre candidats prototypés dans une worktree isolée (`/tmp/dataviz-sondage`,
jamais mergée), sur le même graphique réel — l'histogramme "Distribution des
temps des finishers" de `app/courses/[id]/page.tsx` (fonction `Histogram`,
~ligne 198), reproduit à l'identique (mêmes tokens `--tcn-*`, même logique de
graduations via `lib/utils/histogram-ticks.ts`) dans chaque piste :

1. **d3 (modules seuls)** — `d3-scale@4.0.2` + `d3-shape@3.2.0`.
2. **visx** — `@visx/scale@4.0.0` + `@visx/shape@4.0.0` + `@visx/group@4.0.0`.
3. **Observable Plot** — `@observablehq/plot@0.6.17`.
4. **Recharts** (option composants React) — `recharts@3.10.1`, retenue plutôt
   que Tremor/shadcn-charts parce qu'elle accepte des couleurs arbitraires en
   prop (`fill="var(--tcn-orange)"`) — Tremor restreint sa prop `color` à une
   énumération de teintes nommées, ce qui aurait demandé une surcouche pour
   nos tokens.

Chaque prototype vit dans une route `app/proto-<candidat>/page.tsx`, construit
en production (`npm run build`), servi en mode `standalone`
(`node .next/standalone/server.js`, le seul mode compatible avec
`next.config.ts:7`). Poids JS mesuré par la méthode de #328 : lister les
`<script src="/_next/static/...">` du HTML rendu de chaque route et sommer
leur `Content-Length` réel (octets bruts, sans `--compressed`). Tout le code
de prototype a été supprimé après mesure (spike jetable) — seul ce document
est livré.

## Mesures

### Compatibilité RSC et rendu sans JS

| Candidat | Rend en RSC (sans `"use client"`) | HTML initial (avant hydratation) |
| --- | --- | --- |
| d3 (modules) | ✅ Oui | SVG complet, tout de suite |
| visx | ✅ Oui | SVG complet, tout de suite |
| Observable Plot | ❌ Non | Zone vide |
| Recharts | ❌ Non | Zone vide |

**d3 et visx** rendent sans erreur en composant serveur : leurs modules ne
touchent jamais le DOM, ils produisent des nombres/coordonnées consommés par
du JSX ordinaire (`<rect>`, `<line>`…). Testé en supprimant toute directive
client et en lançant `npm run build` — succès dans les deux cas.

**Observable Plot** échoue en RSC, mesuré directement :

```
TypeError: Cannot read properties of undefined (reading 'documentElement')
    at Plot.plot({ ... })
```

`Plot.plot()` appelle `document.createElementNS` en interne — aucun `document`
n'existe côté serveur Node. Passer en `"use client"` fait disparaître
l'erreur, mais alors le graphique ne rend **rien** tant que le JS n'a pas
exécuté (testé : `curl` sur le HTML initial ne contient aucune trace du SVG
généré, seulement un `<div>` vide en attente d'un `useEffect`).

**Recharts** échoue en RSC pour une autre raison :

```
TypeError: (0 , q.createContext) is not a function
```

`ResponsiveContainer`/`BarChart` s'appuient sur le contexte React, indisponible
dans le graphe de modules serveur sans `"use client"`. Même symptôme que Plot
une fois la directive ajoutée : le HTML initial ne contient aucune trace du
graphique, seulement le conteneur vide.

### Poids ajouté au bundle (après tree-shaking, mesuré sur ce graphique)

| Route | Scripts référencés | Poids total (octets bruts) | Delta vs référence |
| --- | --- | --- | --- |
| Référence (SVG manuel actuel) | 17 | 929 552 | — |
| d3 (modules) | 17 | 929 552 | **+0** |
| visx | 17 | 929 552 | **+0** |
| Observable Plot (`"use client"`) | 19 | 1 182 838 | **+253 286** (+27 %) |
| Recharts (`"use client"`) | 19 | 1 250 181 | **+320 629** (+34 %) |

d3 et visx ajoutent **zéro octet** de JS client — logique, puisqu'ils ne
produisent que du SVG calculé côté serveur, comme le fait déjà le code manuel
actuel. Plot et Recharts ajoutent chacun le tiers d'un socle JS déjà mesuré à
~930 ko par #328 — pour un seul graphique, à multiplier par les quatre
graphiques aujourd'hui serveur si la bibliothèque devait tous les couvrir.

### Accessibilité

Aucun des quatre candidats n'ajoute d'accessibilité *automatiquement* sur le
rendu que nous avons testé (aucun de nos quatre prototypes n'avait de rôle,
alt ou navigation clavier — ni la version actuelle en SVG manuel, d'ailleurs).
Ce qui diffère, c'est l'**outillage disponible** si on l'active :

- **d3, visx** : rien d'intégré — un `role="img"`/`aria-label` sur le `<svg>`
  et une alternative textuelle restent entièrement à la charge du code
  applicatif, exactement comme aujourd'hui.
- **Observable Plot** : `ariaLabel`/`aria-description` et un `role` par défaut
  sur le SVG racine sont **intégrés au générateur** (`src/style.js`,
  `src/plot.js` du paquet installé) — un vrai atout si le rendu n'échouait pas
  en RSC.
- **Recharts** : `accessibilityLayer` (prop opt-in depuis la v2.1, confirmée
  présente dans `3.10.1` — `PolarChart.js`, `rootPropsSlice.js`) ajoute
  navigation clavier et focus par point de données. Le seul candidat des
  quatre à offrir une navigation clavier **construite**, pas à écrire à la
  main.

Aucun des deux critères d'accessibilité intégrée (Plot, Recharts) ne compense
leur échec RSC pour les quatre graphiques aujourd'hui serveur : l'un
n'empêche pas l'autre d'être un correctif à faire à la main dans tous les cas
si on choisit d3/visx.

### Thématisation (tokens `--tcn-*`, Anton/Barlow)

Les quatre acceptent `var(--tcn-*)` nativement dans leurs props de couleur/
police (`fill`, `tick.fill`, styles CSS) — aucune surcouche nécessaire.
Nuance pour une bibliothèque de composants **non retenue** dans ce sondage :
Tremor restreint sa prop `color` à une énumération de teintes nommées et
aurait demandé une transformation, contrairement à Recharts.

### Responsive sans `ResizeObserver` imposé

| Candidat | `ResizeObserver` |
| --- | --- |
| d3 (modules) | Aucun usage (grep sur les sources du paquet) |
| visx (`scale`/`shape`/`curve`/`group`) | Aucun usage |
| Observable Plot | Aucun usage par défaut (largeur fixe sauf câblage manuel) |
| Recharts | **4 fichiers** du paquet l'utilisent — `ResponsiveContainer` en dépend structurellement |

d3 et visx héritent du même mécanisme que le rendu actuel : un `viewBox` SVG
et `width: 100%` en CSS, sans mesure JS. Recharts impose son
`ResponsiveContainer` pour tout redimensionnement fluide — encore un point qui
n'aurait pu s'éviter qu'en gérant soi-même les dimensions, perdant l'intérêt
du composant.

### Maintenance et écosystème

| Paquet | Dernière publication (npm) | Remarque |
| --- | --- | --- |
| `d3-scale` / `d3-shape` | 2023-04-12 | API stable depuis des années — c'est la fondation sur laquelle **visx et Observable Plot eux-mêmes s'appuient en interne**. L'absence de republish récent traduit la maturité de l'API, pas l'abandon : c'est le module le plus universellement dépendu de tout l'écosystème dataviz JS. |
| `@visx/scale` (et `@visx/shape`, `@visx/group`) | 2026-06-11 | Actif. `@visx/scale` ne dépend plus directement de `d3-scale` mais de `@visx/vendor`, qui vendorise les mêmes primitives avec un cycle de publication propre. |
| `@observablehq/plot` | 2026-04-06 | Actif, maintenu par Observable. |
| `recharts` | 2026-07-25 | Le plus actif des quatre, très large communauté React. |

## Conclusion

**Bibliothèque retenue : d3 (modules `d3-scale` + `d3-shape`, éventuellement
`d3-array` selon les besoins de la refonte).**

Raisons, par ordre de poids dans la décision :

1. **RSC intact, zéro octet ajouté** — seul candidat (avec visx, à égalité
   stricte sur ces deux critères) qui ne fait basculer aucun graphique
   aujourd'hui serveur vers `"use client"`. Plot et Recharts sont écartés sur
   ce seul critère : ils contredisent la contrainte posée par #329 elle-même.
2. **d3 plutôt que visx, à mesures égales** — visx est une couche d'ergonomie
   React posée sur les mêmes primitives (`@visx/shape` dépend de
   `@visx/scale`, qui vendorise les modules d3). Sur des graphiques déjà écrits
   en SVG à la main (`<rect>`, `<line>`, `<text>`), cette ergonomie
   (`<Bar>`, `<Group>` à la place de `<rect>`) réduit le code de façon
   marginale — pas assez pour justifier une indirection supplémentaire, au
   regard du principe du projet « pas d'abstraction spéculative »
   (`AGENTS.md`, Principes de conception). Si la refonte découvre un vrai
   besoin de composition (motifs répétés entre plusieurs graphiques), visx
   reste l'option de repli la plus proche — même verdict RSC et bundle, à
   réévaluer **alors**, pas maintenant.
3. **La staleness apparente de d3-scale/d3-shape n'est pas un signal
   d'abandon** — mesurée honnêtement ci-dessus, elle reflète une API figée et
   universellement dépendue (visx et Plot la portent tous deux en interne),
   pas un risque de maintenance.

### Graphiques concernés (sur les 6 de l'inventaire #329)

| Graphique | Fichier | Décision |
| --- | --- | --- |
| Histogramme des temps d'arrivée | `app/courses/[id]/page.tsx` (`Histogram`) | **Migre vers d3-scale** (positionnement des barres/graduations Y) ; `lib/utils/histogram-ticks.ts` (logique de pas "humain" par bande de durée de course) est un savoir métier que d3 ne remplace pas — **conservé tel quel**. |
| Donut genre + barres catégories | `app/courses/[id]/page.tsx` (`conic-gradient` CSS) | **Migre vers d3-shape** (`arc()`) pour le donut — un vrai `<path>` par tranche, plus manipulable pour une alternative textuelle par tranche que le dégradé CSS actuel. Les barres de catégories suivent le même patron que l'histogramme. |
| Évolution du rang par segment | `components/tcn/participation-detail/RankingEvolutionChart.tsx` (247 lignes, déjà client) | **Migre vers d3-scale + d3-shape** (`line()`, `curveMonotoneX`) — déjà `"use client"`, donc zéro régression RSC ; gain attendu sur les 247 lignes actuelles, à chiffrer dans #370. |
| Activité mensuelle | `components/charts/MonthlyTrend.tsx` (44 lignes) | **Migre vers d3-scale**, par cohérence avec l'histogramme — gain modeste vu la taille actuelle, mais le motif est déjà en place une fois l'histogramme fait. |
| Barres horizontales (top clubs…) | `components/charts/BarList.tsx` (42 lignes) | **Reste en SVG/CSS manuel** — confirmé par ce sondage : sur 42 lignes de barres proportionnelles simples, aucun des quatre candidats n'aurait réduit le code ni ajouté de valeur mesurable. |
| Calcul des graduations | `lib/utils/histogram-ticks.ts` | **Conservé**, réutilisé tel quel par la version d3 de l'histogramme (cf. ligne 1 du tableau). |

Détail d'implémentation, séquencement par lot et chiffrage précis du gain de
lignes : à traiter dans #370 (bloquée par ce sondage, désormais débloquable).

## Ce qui n'a pas été mesuré

- **Le donut réel** n'a pas été prototypé (seul l'histogramme, le graphique de
  référence désigné par #369) — la conclusion `d3-shape.arc()` pour le donut
  est une extrapolation à vérifier lors de la refonte, pas une mesure.
- **Poids compressé (gzip/brotli)** : mesuré en octets bruts comme le sondage
  #328, pour rester comparable au même socle de référence (~930 ko). Le
  transfert réseau réel est plus petit des deux côtés.
- **`d3-array`** et d'autres modules d3 potentiellement utiles à la refonte
  (agrégation de bins, etc.) n'ont pas été mesurés séparément — le principe
  (modules purs, zéro JS client) est identique à `d3-scale`/`d3-shape`.
- **Preview Vercel/Render** : écarté, comme #328, mesure locale uniquement.
