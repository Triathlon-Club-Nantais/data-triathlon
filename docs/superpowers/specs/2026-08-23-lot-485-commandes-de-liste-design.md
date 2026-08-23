# Lot #485 — Commandes de liste sur `/resultats` et le classement

Design validé le 2026-08-23. Couvre `RES-5`, `RES-8` et `RES-9` du § 6 de
`docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`. Lot de l'epic #460,
refs #325.

## Le problème

Les trois entrées sont les **commandes de liste** — filtrer, paginer, savoir ce
qu'on regarde — sur `components/results/ResultsFilters.tsx` et
`components/results/RaceFinishers.tsx`.

- **`RES-5`** — cinq champs plus deux boutons occupent tout le premier écran
  d'un téléphone avant le moindre résultat, alors que l'usage dominant est « je
  cherche un nom ». Et aucun des libellés n'est **associé** à son champ :
  `Field` rend `<label>` et `<Input>` en frères, sans `htmlFor`/`id`. Un lecteur
  d'écran annonce des champs anonymes — WCAG 2.2 **3.3.2**.
- **`RES-8`** — 849 participants paginés par 20 donnent 43 pages ; atteindre le
  milieu du classement demande 21 clics. La pagination ne rend que deux liens et
  un « Page 1 sur 43 » non interactif. L'API sait pourtant rendre tout le
  classement (`page_size=all`, contractuel), aucun contrôle ne l'expose.
- **`RES-9`** — on cherche « kermarrec », deux lignes s'affichent, et tout le
  reste de l'écran affirme le contraire : le segmenté annonce « Tous les
  participants (498) », le pied de carte « 498 participants · 447 finishers… »,
  la pagination a disparu sans un mot. Sur le filtre club, le message d'absence
  parle d'une « recherche » qui n'a jamais eu lieu.

`RES-9` est la conséquence directe des deux autres : une vue filtrée dont le
cadre mentirait après un saut de page ne serait pas moins fausse.

## Décisions d'arbitrage

Quatre points tranchés en amont du design, avec leur raison :

1. **Le tri client reste local à la tranche, et le dit.** Le rendre global
   demanderait un paramètre d'API, un passage repository et des tests backend —
   hors d'un lot frontend. À la place, le périmètre du tri devient explicite
   dans l'annonce et dans l'`aria-label` des en-têtes. Le sélecteur de lignes
   rend d'ailleurs le problème largement caduc : à 200 lignes ou à `all`, le tri
   porte sur tout ou presque tout le classement.
2. **Le sélecteur de lignes expose `20 / 50 / 200 / Tout`.** `all` est
   l'échappatoire contractuelle de l'API (`backend/app/api/AGENTS.md`) ; c'est
   elle qui rend le tri client exact et le `Ctrl+F` du navigateur utilisable sur
   une grosse épreuve.
3. **Le volet mobile applique à la validation, pas à la frappe.** C'est
   l'arbitrage #387 — discipline et dates ne s'appliquent que sur « Filtrer » —
   qu'un volet à application immédiate contredirait. Le champ « Athlète », hors
   volet, garde sa recherche live (#383).
4. **Le repli mobile ne monte pas sur desktop.** Replier quatre champs derrière
   un bouton coûterait deux clics là où l'espace ne manque pas.

## A — `/resultats` : `ResultsFilters.tsx` (`RES-5`)

### Association des libellés

`Field` prend un `id` et rend `<label htmlFor={id}>`. Les quatre `Input`
reçoivent cet `id`.

Le `SelectTrigger` de Base UI est un `<button>`, qu'un `<label for>` **n'associe
pas** : `for` ne désigne que les contrôles de formulaire étiquetables. Il reçoit
donc `aria-labelledby={labelId}`, `Field` exposant les deux identifiants.

La correction porte sur les **cinq** champs, pas seulement « Du » et « Au » : les
trois autres n'étaient pas plus liés, ils étaient seulement moins visibles dans
le constat.

### Repli sous `sm`

Sous `sm`, seul le champ « Athlète » reste inline, accompagné d'un bouton
`Filtres (n)` où `n` compte les filtres actifs **hors athlète** (0 → pas de
compte, juste « Filtres »). Il ouvre un `ui/sheet` `side="right"` portant
Épreuve, Discipline, Du, Au, puis en pied « Appliquer » (applique et ferme) et
« Réinitialiser ».

Au-dessus de `sm`, la disposition actuelle ne bouge pas.

Les quatre champs repliables sont rendus **deux fois** — inline sous
`hidden sm:contents`, et dans le volet — avec des `id` suffixés `-inline` et
`-volet`. C'est ce qui évite un `useMediaQuery` : un hook média rendrait la
disposition dépendante de l'hydratation, avec le flash que cela implique sur un
écran dont les filtres sont la première chose vue. Le contenu du volet n'existe
dans le DOM qu'à l'ouverture (portail `Dialog`), et l'état React est partagé
entre les deux rendus — les deux jeux de champs affichent donc toujours la même
saisie.

Les chips de filtres actifs restent **hors** du volet, toujours visibles : ils
disent ce qui est appliqué, exactement la fonction que la ligne d'état remplit
côté classement.

## B — Classement : `RaceFinishers.tsx` (`RES-8` + `RES-9`)

### Le paramètre d'URL `page_size`

Nouveau paramètre, valeurs `20 | 50 | 200 | all`, défaut `20`.
`app/(public_restricted)/courses/[id]/page.tsx` le lit via une **liste blanche**
et le passe à `apiServer.getCourse` ; toute autre valeur retombe à `20`. Sans
cette liste, une URL bricolée (`page_size=500`, dans les bornes du backend)
afficherait une taille que le sélecteur ne sait pas représenter.

`CourseQuery.page_size` existe déjà côté types, et le backend accepte déjà
`1..500` plus `all`. **Aucun changement backend.**

Quand `page_size=all`, le backend renvoie `page_size: null` et `nbPages` vaut 1 :
la navigation de pages disparaît, le sélecteur reste.

### `ClassementPagination.tsx`

Extraction dans un fichier voisin de `components/results/`, avec ses propres
tests. C'est le seul morceau du lot à porter une logique réelle — parsing et
bornes du champ de page — et `RaceFinishers.tsx` dépasse déjà 400 lignes.

Le composant rend une barre de commandes **toujours visible** portant le
sélecteur de lignes (20 / 50 / 200 / Tout). La navigation de pages ne s'y ajoute
que si `nbPages > 1` :

```
‹‹ Première · ‹ Précédent · [ Page (n) / 43 ] · Suivant › · Dernière ››
```

- Le champ de page est un `<form method="get">` dont l'`action` est le `pathname`
  et qui porte les autres paramètres en champs cachés, intercepté par
  `router.push`. Le saut fonctionne donc **avant hydratation** comme après, sans
  perdre la recherche ni le filtre en cours.
- Saisie hors bornes : ramenée dans `[1, nbPages]` plutôt que refusée — un « 99 »
  sur 43 pages veut dire « la fin ».
- Le champ porte un libellé associé, `min`/`max` et `inputMode="numeric"`.
- Première/dernière et précédent/suivant restent des `<Link>`, comme aujourd'hui :
  ouvrables en nouvel onglet et fonctionnels sans JavaScript.
- Changer la taille de page renvoie à la **page 1** : la position courante n'a
  pas d'équivalent d'une taille à l'autre, et « à peu près la même zone » serait
  une promesse fausse.
- Le comportement hors bornes existant est conservé : depuis une page inexistante,
  « Précédent » ramène à la dernière page réelle.

### La vue filtrée se nomme (`RES-9`)

**Ligne d'état** sous l'en-tête de carte, rendue uniquement en vue filtrée
(recherche, filtre club, ou les deux) :

- recherche seule — « **2 résultats sur 498** pour « kermarrec » · Effacer »
- filtre club seul — « **12 résultats sur 498** du Triathlon Club Nantais · Effacer »
- les deux — « **1 résultat sur 498** pour « kermarrec », du Triathlon Club Nantais · Effacer »

`total` est le total de la sélection, `summary.total` celui de l'épreuve entière :
c'est cette opposition qui manquait. « Effacer » retire recherche **et** filtre.

**Deux messages d'absence distincts** :

- recherche (avec ou sans filtre club) → « Aucun athlète ne correspond à cette
  recherche », action « Effacer la recherche » — l'actuel ;
- filtre club **sans** recherche → « Aucun athlète du Triathlon Club Nantais sur
  cette épreuve », action « Voir tous les participants ».

**Onglet TCN grisé** quand `summary.tcn_count === 0` : offrir un filtre garanti
vide est une impasse. `components/tcn/SegmentedControl` gagne un `disabled?:
boolean` par option (`aria-disabled`, `onChange` non appelé, curseur
`not-allowed`). C'est une extension du composant, pas un déplacement de la
frontière `components/tcn/` ↔ `components/ui/` que #460 laisse hors débat.

Cas limite : une URL portant déjà `scope=club` sur une épreuve à zéro athlète TCN
rend l'onglet actif **et** désactivé ; l'onglet « Tous les participants » reste
cliquable, la sortie est donc toujours ouverte, et le message d'absence porte de
son côté « Voir tous les participants ».

**Pied de carte** préfixé « Sur l'ensemble de l'épreuve : … ». Le décompte est
juste, c'est son cadre qui manquait.

### Le tri dit son périmètre

`AnnonceStatut` et l'`aria-label` des en-têtes triables précisent la portée :
« trié par temps total, croissant, sur les 50 lignes affichées ». La mention
disparaît quand `page_size=all`, le tri étant alors global.

L'annonce enrichie reste celle qui vit **déjà** dans `RaceFinishers` ; le lot ne
prend pas d'avance sur `A11Y-5`, qui porte l'annonce des décomptes à l'échelle du
produit.

## Hors périmètre

- **« Aller à mon résultat »** — volet **M** de `RES-8`, rejoint `NAV-10` et
  attend #467.
- **Tri serveur global** — voir la décision 1.
- **`A11Y-5`** — l'annonce généralisée des décomptes.
- **Identité visuelle** (`--tcn-*`, Anton/Barlow) et frontière `components/tcn/`
  ↔ `components/ui/` : arbitrées, non rejugées (#325, #460).

## Tests

Vitest + RTL, TDD. Ce que la suite doit tenir :

**`ResultsFilters`**
- les cinq champs sont atteignables par `getByLabelText` — c'est la régression
  WCAG 3.3.2 elle-même ;
- le bouton du volet porte le compte des filtres actifs hors athlète, et rien
  quand il vaut 0 ;
- « Appliquer » pousse l'URL attendue **et** ferme le volet ; un changement de
  discipline non validé ne modifie pas l'URL ;
- le champ « Athlète » garde sa recherche live (non-régression #383/#387).

**`ClassementPagination`**
- le saut de page pousse l'URL en conservant `q`, `scope` et `page_size` ;
- une saisie hors bornes est ramenée dans `[1, nbPages]` ;
- le sélecteur de lignes pousse `page_size` et retire `page` ;
- `page_size=all` masque la navigation de pages et garde le sélecteur.

**`RaceFinishers`**
- la ligne d'état apparaît en vue filtrée, avec les deux décomptes, et pas en vue
  complète ; « Effacer » retire les deux paramètres ;
- les deux messages d'absence sont bien distincts, celui du filtre club portant
  « Voir tous les participants » ;
- l'onglet TCN est désactivé et n'appelle pas `onChange` quand `tcn_count === 0` ;
- l'annonce de tri nomme le périmètre, et ne le nomme plus sous `page_size=all`.

**`courses/[id]/page.tsx`**
- la liste blanche de `page_size` : une valeur hors liste retombe à 20.
