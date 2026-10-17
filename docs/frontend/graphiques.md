# Graphiques et couleurs de discipline

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## La géométrie dans le SVG, les textes en HTML (#480)

**« La géométrie dans le SVG, les textes en HTML »** (#480, RESP-2) — pour
tout `viewBox` fixe étiré à `width: 100%` (`Histogram`, `RankingEvolutionChart`) :
aucune unité CSS ne fige la taille d'un `<text>` SVG dans ce cas, il est mis à
l'échelle avec le `viewBox` et tombe à ~3,5 px sur un iPhone SE. D'où
`preserveAspectRatio="none"` + une hauteur en px, et les libellés posés en
HTML autour. Corollaire qui a coûté une ronde de correction : une abscisse
HTML s'exprime en **pourcentage d'une rangée absolue dont la largeur épouse
celle du SVG**, jamais du conteneur — celui-ci porte la gouttière des
graduations, contre laquelle un `%` se résoudrait, gouttière comprise.

## `lib/sport-colors.ts` (#480)

**`lib/sport-colors.ts` est la source unique de l'échelle des disciplines**
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
