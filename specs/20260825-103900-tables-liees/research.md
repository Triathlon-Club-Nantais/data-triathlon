# Phase 0 — Recherche

**Feature** : `specs/20260825-103900-tables-liees/` (issue #481)
**Date** : 2026-08-25

Cinq inconnues portées par la spec (§ Assumptions) et par la consigne de plan.
Chacune est tranchée ci-dessous, avec ce qui a été **vérifié dans le dépôt ou
dans les types installés** distingué de ce qui relève du choix.

---

## D1 — La forme de la conversion : balises réelles, rôles ARIA, ou les deux

**Décision** : **les deux**. Balises `<table>`/`<thead>`/`<tbody>`/`<tr>`/`<th
scope="col">`/`<td>` réelles, la géométrie actuelle en `display: grid`
**conservée telle quelle**, et les rôles ARIA correspondants (`table`,
`rowgroup`, `row`, `columnheader`, `cell`) **posés explicitement** sur ces
mêmes balises.

**Rationale** — trois faits qui se composent :

1. **La géométrie ne se réexprime pas en disposition de tableau sans dérive.**
   Les six listes reposent sur `grid-template-columns` mêlant des pistes fixes
   en px et une piste souple, plus un `column-gap`. Relevé :
   `EventsTable` déclare `TRACKS = [120, {flexMin:200}, 150, 90, 120, 120, 28]`,
   `RaceFinishers` calcule ses colonnes selon le nombre d'inters de l'épreuve.
   La disposition de tableau native n'a ni `1fr`, ni `minmax()`, ni
   `column-gap` (son `border-spacing` s'applique aussi verticalement et pousse
   les bordures). Reproduire l'apparence au pixel demanderait de retraduire
   chaque piste en pourcentage et chaque gouttière en padding de cellule —
   c'est-à-dire de rouvrir le dessin de six listes, quand **FR-007 exige
   l'inverse**. Conserver `display: grid` sur chaque `<tr>` garde les mêmes
   valeurs, littéralement copiées.
2. **Surcharger `display` sur des éléments de tableau peut retirer leur
   sémantique de tableau à l'aide technique.** C'est un piège connu et
   documenté de longue date (Adrian Roselli, *Tables, CSS Display Properties,
   and ARIA*) : le rôle implicite d'un `<table>` découle en pratique de sa
   disposition, et le passer en `block`/`grid` le fait tomber dans plusieurs
   navigateurs et lecteurs d'écran. Le remède documenté est de **redéclarer les
   rôles ARIA** sur les mêmes balises. Nous n'avons pas de banc de test lecteur
   d'écran dans ce dépôt : poser les rôles est une assurance à coût nul, pas
   une affirmation que tel navigateur est cassé aujourd'hui.
3. **Les balises réelles restent utiles même une fois les rôles posés** : la
   source cesse de mentir (c'est le grief même de l'audit — 65 `TableHead` au
   back-office contre zéro au public), `scope="col"` et `aria-sort` sont des
   attributs natifs de `<th>`, et le rendu sans CSS redevient un tableau.

**Alternatives rejetées** :

| Alternative | Rejetée parce que |
| --- | --- |
| `<table>` natif, géométrie retraduite en `table-layout: fixed` + `<colgroup>` | Rouvre le dessin des six listes ; risque direct contre FR-007 et SC-005, pour un gain de sémantique que les rôles ARIA donnent déjà. |
| `<div>` conservés + rôles ARIA seuls | Le travail ARIA est **identique** (les rôles doivent être posés dans les deux cas, cf. fait 2), donc l'économie se réduit au nom des balises — et on garde une source qui ment, sans repli si l'ARIA saute. « Décider l'architecture pour le long terme » tranche contre. |
| Réemployer `components/ui/table.tsx` | Ses classes portent la densité du back-office (`h-10`, `p-2`, `text-sm`, `border-b` Tailwind) ; les plaquer sur un écran public rouvrirait l'identité visuelle que #325 interdit de rejuger. La frontière autorise `ui/` depuis un écran public, elle n'oblige à rien. |

---

## D2 — Une ligne entièrement cliquable qui reste un lien, et un seul arrêt clavier

**Contrainte dure, et elle est dirimante** : le rôle ARIA d'un élément
**remplace** son rôle implicite. Un `<a href>` auquel on donne `role="row"`
n'est plus annoncé comme un lien — ce qui contredit frontalement **FR-002**.
La ligne ne peut donc pas *être* l'ancre, ni en balises réelles (un `<tr>` ne
porte pas de `href`) ni en ARIA.

**Décision** : la ligne est un `<tr>`, l'ancre vit **dans une cellule** — celle
qui porte le nom de la ligne (nom de l'athlète pour le classement, nom de
l'épreuve ailleurs) — et **couvre la ligne par un pseudo-élément**
`::after { position: absolute; inset: 0 }`, le `<tr>` étant `position: relative`.

Conséquences vérifiées :

- **Un seul arrêt clavier par ligne** (FR-011) : il n'y a qu'une ancre.
- **Les quatre gestes natifs** (FR-004) marchent parce que la cible est une
  vraie ancre : le survol montre l'URL, le clic milieu ouvre un onglet, le menu
  contextuel offre « copier l'adresse ».
- **Le survol et le focus se posent sur la ligne** : `.tcn-rowlink:hover` comme
  aujourd'hui, et l'anneau de focus par `.tcn-rowlink:has(a:focus-visible)`.
  `:has()` est **déjà employé dans ce dépôt** — `app/globals.css:496`
  (`.tcn-radio-toggle:has(input:focus-visible)`), verrouillé par
  `components/club/AthleteSortToggle.test.tsx:34`. Aucune nouveauté à valider.
- **La sélection de texte reste impossible sur la ligne**, le voile la captant.
  *Corrigé après revue de code* : c'était déjà le cas sur **cinq** listes, dont
  la ligne entière est une ancre — mais **pas** sur le classement d'épreuve, où
  la ligne était un `div[role="button"]` dont le texte se sélectionnait. Copier
  un nom ou un temps depuis le classement démarre désormais un glisser-déposer
  de lien. C'est une régression réelle, mineure et assumée : `pointer-events:
  none` sur le voile rendrait la ligne incliquable hors du nom, ce qui coûterait
  bien plus que ce que la sélection rapporte. Le nom reste sélectionnable depuis
  la page de détail, qui est à un clic.
- **Ce que le voile capte aussi, et qu'il faut lui reprendre** : tout élément en
  flux d'une cellule voisine perd le survol — mesuré sur les deux marqueurs ⚠
  (inter illisible de `CelluleInter`, épreuve non fiable d'`EventsTable`), dont
  l'infobulle ne s'ouvrait plus. Les deux `<span>` prennent
  `position: relative`, ce qui les repose au-dessus du voile dans l'ordre de
  peinture. Toute cellule qui gagnera un contrôle survolable devra faire de
  même.

**Où porte le changement** : cinq listes sur six ont déjà une ancre couvrant la
ligne, il s'agit donc de la **déplacer** dans une cellule, pas de la créer. La
sixième (`RaceFinishers`) n'en a aucune : c'est là que l'ancre naît (FR-002).

**Le mécanisme est mutualisé dans `.tcn-rowlink`**, la classe qui porte déjà le
survol, le fond transparent et l'anneau de focus (`app/globals.css:432-449`) —
on l'étend, on ne crée pas de composant. Principe VI : six emplois du **même**
mécanisme CSS ne sont pas une abstraction spéculative, et la classe existe.

---

## D3 — L'état d'attente sur la ligne activée (FR-005)

**Décision** : `useLinkStatus()` de `next/link`, lu par un composant enfant de
l'ancre, qui rend un voile d'attente couvrant la ligne. `prefetch={false}` sur
les lignes du classement.

**Vérifié dans les paquets installés** (Next **16.3.1**) :

- `node_modules/next/dist/client/link.d.ts:117` —
  `export declare const useLinkStatus: () => { pending: boolean }`.
- `node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-link-status.md` —
  trois contraintes qui décident de la forme :
  - « must be used within a descendant component of a `Link` » → l'ancre ne
    peut pas lire son propre état ; c'est un **enfant** qui le lit.
  - « If the linked route has been prefetched, the pending state will be
    skipped » et « most useful when `prefetch={false}` » → sans
    `prefetch={false}`, l'indicateur ne s'afficherait **jamais** en production.
  - « Inline indicators can easily introduce layout shifts. Prefer a
    fixed-size, always-rendered hint element and toggle its opacity » → le
    voile est rendu en permanence et ne change que d'opacité.

**Trois conséquences qui tombent juste** :

- `prefetch={false}` sur 20 lignes de classement est **aussi** le bon choix de
  charge, et le dépôt a déjà tranché ainsi pour la même raison :
  `components/dashboard/RecentCourses.tsx:74` le pose sur ses six liens (#425),
  commentaire à l'appui. Ce que la doc de Next exige ici, le projet le fait
  déjà ailleurs.
- **Ouvrir en nouvel onglet n'allume aucune attente** (FR-005, scénario 2)
  **par construction** : ⌘/Ctrl+clic et clic milieu ne déclenchent pas de
  navigation cliente, donc `pending` reste faux. Rien à coder pour ce scénario.
- **Sans mouvement** (FR-005, scénario 3) : une variation d'opacité satisfait
  `prefers-reduced-motion` sans cas particulier, et c'est déjà le motif de
  l'écran — `RaceFinishers.tsx:270` porte
  `className="transition-opacity data-pending:opacity-60"` pour l'attente de
  recherche et de pagination.

**Alternative rejetée** : envelopper `router.push` dans le `useTransition`
existant (`RaceFinishers.tsx:109`). Il faudrait garder un gestionnaire de clic
et une navigation programmatique — c'est-à-dire **reconstruire ce que FR-002
vient de retirer**. Le `useTransition` de l'écran reste en place pour ce qu'il
sert déjà (recherche, tri, pagination) ; il ne sert pas les lignes.

---

## D4 — La sous-ligne d'`EventsTable` et le trait porté par le couple

**Situation** (`app/(public_restricted)/athletes/[id]/EventsTable.tsx:255-267`) :
chaque entrée est un `<div>` enveloppant qui porte le `border-bottom`, et qui
contient la ligne-lien puis, le cas échéant, une sous-ligne (lien de preuve,
gestes d'administration montés **dans le navigateur** seulement, #439). Le trait
est absent pour une ligne en attente sans sous-ligne (acquis de #270).

**Décision** : **un `<tbody>` par entrée**. Le trait passe du `<div>`
enveloppant au `<tbody>`, la ligne et sa sous-ligne devenant deux `<tr>` frères
à l'intérieur.

**Rationale** : un tableau accepte **plusieurs `<tbody>`** — c'est la manière
prévue de grouper des lignes. Aucun élément intermédiaire n'est permis entre
`<tbody>` et `<tr>`, donc le `<div>` enveloppant ne peut pas survivre tel quel ;
et le déplacer sur chaque `<tr>` casserait justement l'invariant « le trait
porte sur le couple ». Le groupe garde en outre sa propriété utile : le rendu
serveur ne sait pas quelle sous-ligne existera, et il n'a pas à le savoir.

La sous-ligne devient un `<tr>` dont la cellule unique porte `colSpan` sur
toute la largeur.

---

## D5 — Les deux natures de ligne d'`EventList`

**Situation** : `EventRow` est une ligne-lien ; `CompetitionRows` rend une
ligne de groupe qui **déplie** (`<button aria-expanded>`,
`EventList.tsx:281`) puis, une fois ouverte, ses épreuves indentées.

**Décision** : même traitement que D2, avec un contrôle différent. La ligne de
groupe reste un `<tr class="tcn-rowlink">` dont la cellule de nom contient le
`<button aria-expanded>`, couvrant la ligne par le même pseudo-élément. Le
groupe et les épreuves qu'il révèle forment **un `<tbody>`** — même mécanisme
qu'en D4, et l'indentation reste un padding de la cellule de date.

**Ce qu'on ne change pas** : la ligne de groupe **doit rester un bouton**. Elle
ne navigue pas, elle déplie ; en faire un lien serait une régression de
`4.1.2`, exactement le défaut qu'on corrige ailleurs. `aria-expanded` reste sur
le bouton, pas sur le `<tr>`.

---

## D6 — `aria-sort` sur les en-têtes triables (FR-006)

**Décision** : `aria-sort` sur le `<th>`, pas sur le bouton — `ascending` /
`descending` sur la colonne triée, `none` sur les autres colonnes triables,
attribut absent sur les colonnes non triables. Le `<button>` d'`EnteteTriable`
reste **à l'intérieur** du `<th>` et garde son `aria-label` actuel, qui annonce
l'action **à venir** (« Trier par temps total, décroissant »).

**Rationale** : `aria-sort` qualifie la colonne, et son seul porteur valide est
l'en-tête. Les deux informations sont complémentaires et ne font pas doublon —
`aria-sort` dit l'état courant, l'`aria-label` du bouton dit ce que
l'activation produira. C'est le manque du premier que l'audit relève.

**Périmètre** : seul `RaceFinishers` a des en-têtes triables. Les cinq autres
listes n'en ont pas ; `EventList` trie par un `<Select>` hors du tableau, qui
n'est pas concerné.

**Rien à faire sur les cibles tactiles** : #479 a déjà posé `padding: 4px 0` et
`minHeight: 24` sur `EnteteTriable` (`RaceFinishers.tsx:466-470`, commentaire à
l'appui). Le lot `CIBLE-1` est passé.

---

## D7 — Comment le tester sans lecteur d'écran (Principe III)

**Décision** : les tests portent sur **l'arbre d'accessibilité tel que Testing
Library le voit**, jamais sur le nom des balises — c'est ce que FR-009 demande
(« porte sur ce que l'aide technique perçoit, pas sur le nom des balises »).

Concrètement, les rôles ARIA que D1 impose sont exactement ce qui rend le test
possible : `getByRole("table")`, `getAllByRole("row")`,
`getByRole("columnheader", { name: /temps total/i })`, et le rattachement
cellule↔colonne se vérifie par `getByRole("cell")` dans la ligne visée.
`@testing-library/dom` est déjà présent via RTL, et les six listes ont déjà
leur fichier de test (`*.test.tsx`, donc **projet jsdom** sans toucher à
`vitest.config.ts`, dont `GLOBS_JSDOM` prend `**/*.test.tsx`).

**Ce que le test ne peut pas prouver, et qu'on assume** : qu'un lecteur d'écran
réel énonce bien « Temps total, 01:10:47 ». jsdom n'implémente pas le calcul du
nom accessible d'une cellule à partir de son en-tête. Le test verrouille la
**structure** qui rend cette énonciation possible ; la vérification finale est
manuelle, et elle est portée par `quickstart.md` puis par le sous-agent
`ui-ux-review` en fin de branche.

**Test de non-régression du lien** (FR-010) : assertion sur la présence d'un
`href` de destination, pas sur un gestionnaire de clic — c'est précisément la
différence qui a laissé passer le défaut d'origine.
