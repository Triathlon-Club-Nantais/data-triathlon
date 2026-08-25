# Phase 1 — Structures

**Feature** : `specs/20260825-103900-tables-liees/` (issue #481)

Cette feature ne touche **aucun modèle de données** : rien en base, rien dans
les DTO, aucune migration. Ce qu'elle définit est une **structure de rendu**, et
c'est elle que ce document fixe — l'inventaire des six tableaux, et la forme
commune de leurs lignes.

## 1. Inventaire des six tableaux

Relevé dans le code le 2026-08-25. La colonne « Ligne » dit ce qui rend la
ligne activable **aujourd'hui**.

| # | Tableau | Fichier | Colonnes | Ligne aujourd'hui |
| --- | --- | --- | --- | --- |
| 1 | Classement d'une épreuve | `components/results/RaceFinishers.tsx` | Rang, Athlète, Catég., Sexe, **Temps total*(triable)*, *n* inters *(triables, variables)*, Club | `role="button"` + `router.push` |
| 2 | Liste des épreuves | `components/results/EventList.tsx` | Date, Épreuve, Type, Format, Résultats, *(club, libellé court)*, *(colonne « → » sans libellé)* | `<Link>` (`EventRow`) **et** `<button aria-expanded>` (ligne de groupe) |
| 3 | Épreuves d'un athlète | `app/(public_restricted)/athletes/[id]/EventsTable.tsx` | Date, Épreuve, Type, Format, Temps final, Place, *(colonne sans libellé)* | `<Link>` + **sous-ligne** |
| 4 | Derniers résultats enregistrés | `app/(public_restricted)/ajouter/page.tsx` | Date, Épreuve, Format, Athlètes club | `<Link>` |
| 5 | Dernières épreuves | `components/dashboard/RecentCourses.tsx` | Date, Épreuve, Format, Dossards | `<Link>` (`prefetch={false}`, #425) |
| 6 | Top clubs | `app/(public_restricted)/courses/[id]/page.tsx` | Club, Athlètes | **aucune** — lignes non interactives |

**Trois natures de ligne**, et elles ne se traitent pas pareil :

- **Ligne-lien** (1, 2-`EventRow`, 3, 4, 5) — navigue. Cible : un `<a>`.
- **Ligne-dépliante** (2-groupe) — ne navigue pas, révèle ses épreuves. Cible :
  un `<button aria-expanded>`. **Reste un bouton** (cf. `research.md` D5).
- **Ligne inerte** (6) — aucune cible, aucun `.tcn-rowlink`, aucun survol.

**Trois colonnes sans libellé** (2, 3, et la colonne « → » de 2) : leur `<th>`
existe pour tenir la piste de grille, et son libellé est vide. Il ne doit pas
produire un en-tête annoncé vide à chaque ligne (cf. Edge Cases de la spec).

## 2. Forme commune d'un tableau

La géométrie actuelle est **conservée à l'identique** — mêmes valeurs de
`gridTemplateColumns`, mêmes gouttières, mêmes paddings, même `minWidth` dans
le conteneur défilable.

```
<div style={{ overflowX: "auto" }}>          ← inchangé (le repli mobile est #461)
  <div style={{ minWidth: … }}>              ← inchangé : la largeur plancher
    <table role="table" class="tcn-table">            display: block
      <thead role="rowgroup">                         display: block
        <tr role="row">                               display: grid, COLS
          <th role="columnheader" scope="col" [aria-sort]>…</th>   × n
      <tbody role="rowgroup">                         display: block
        <tr role="row" class="tcn-rowlink">           display: grid, COLS
          <td role="cell">…</td>                      × n
```

**La largeur plancher reste sur le `<div>` intérieur**, là où elle est
aujourd'hui — la porter sur le `<table>` serait un déplacement gratuit, et #461
doit partir d'une base inchangée. `.tcn-table` (`app/globals.css`) porte la
surcharge de `display` et les remises à zéro de `th`/`td` (padding, alignement,
graisse), qui reproduisent le `<div>` remplacé.

**Pourquoi les rôles ARIA en plus des balises** : la géométrie impose de
surcharger `display`, ce qui peut retirer la sémantique de tableau à l'aide
technique. Les rôles la redéclarent. Raisonnement complet et alternatives
rejetées : `research.md` D1.

**Groupement par `<tbody>`** — un `<tbody>` par entrée dès qu'une entrée porte
plus d'une ligne :

- tableau 3 : `<tbody>` = ligne + sous-ligne éventuelle, et **c'est le `<tbody>`
  qui porte le trait de séparation** (aujourd'hui un `<div>` enveloppant, que
  la structure de tableau n'autorise plus). L'absence de trait pour une ligne
  en attente sans sous-ligne (#270) se conserve telle quelle. **La sous-ligne
  d'administration porte sa `<tr>` elle-même** (prop `colonnes` de
  `ParticipationAdminActions`) — *découvert à l'implémentation* : la poser côté
  appelant rendrait une ligne **vide** à tout visiteur sans pouvoir, puisque le
  composant décide sa visibilité dans le navigateur (#439). C'est le corollaire
  de l'invariant que sa docstring pose déjà — le conteneur de la sous-ligne
  appartient au composant.
- tableau 2 : `<tbody>` = ligne de groupe + épreuves révélées.
- tableaux 1, 4, 5, 6 : un seul `<tbody>` pour toutes les lignes.

## 3. La ligne activable : `.tcn-rowlink` étendue

La classe existe (`app/globals.css:432-449`) et porte déjà `cursor`, fond
transparent, transition, `:hover` et l'anneau `:focus-visible`. Elle passe du
**lien lui-même** à la **ligne**, et gagne le mécanisme de couverture.

| Élément | Rôle dans le mécanisme |
| --- | --- |
| `<tr class="tcn-rowlink">` | `position: relative` — l'origine du voile. Porte `:hover`. |
| `<a class="tcn-rowlink__cible">` dans la cellule de nom | La vraie cible : `href`, un seul arrêt clavier. Son `::after` en `position: absolute; inset: 0` couvre la ligne. |
| `.tcn-rowlink:has(a:focus-visible)` | L'anneau de focus se pose sur la ligne, pas sur le mot cliqué. `:has()` est déjà employé dans `globals.css:496`. |

**Invariants à ne pas casser** :

- **Aucun `overflow` sur la cellule qui porte la cible** *(découvert à
  l'implémentation)*. Le voile du lien et celui de l'attente sont absolus et
  calés sur le `<tr>` ; une cellule intermédiaire en `overflow: hidden` les
  **rogne**, et la ligne cesse d'être cliquable hors du mot. La cellule prend
  `minWidth: 0` — même effet qu'`overflow` sur la taille minimale automatique
  d'un élément de grille, donc la piste `1fr` ne bouge pas — et l'ellipsis
  descend sur un `<span>` intérieur. Seule la colonne « Athlète » du classement
  était concernée ; la colonne « Club », qui garde son `overflow`, ne porte
  aucune cible.
- **Un seul arrêt clavier par ligne** (FR-011) — une seule cible par `<tr>`.
- **La cellule qui porte la cible est celle du nom** : nom de l'athlète
  (tableau 1), nom de l'épreuve (2, 3, 4, 5). C'est ce qui donne au lien son
  nom accessible.
- **Le liseré orange des lignes du club** (tableau 1, `borderLeft` selon
  `is_tcn`) et le fond grisé des non-finishers restent sur le `<tr>`.
- **`.tcn-rowlink` porte aussi la ligne-dépliante** (tableau 2) : la classe ne
  suppose pas un lien, elle décrit une ligne activable — le commentaire de
  `globals.css:437-441` le dit déjà pour les `<button>` de #439.

## 4. États de la ligne du classement (tableau 1)

Quatre états, tous portés par le `<tr>` :

| État | Déclencheur | Rendu |
| --- | --- | --- |
| repos | — | fond transparent |
| survol | `:hover` | `--tcn-surface-sunk` |
| focus clavier | `:has(a:focus-visible)` | anneau `--tcn-orange`, `outline-offset: -2px` |
| **attente** *(nouveau)* | `useLinkStatus().pending` d'un enfant de l'ancre | **filet de 3 px en pied de ligne** (`--tcn-orange`), **sans mouvement** — jamais une nappe par-dessus, qui ferait tomber le texte sous 4,5:1 (revue UI/UX) |

L'attente ne s'allume que sur une navigation **cliente** : ⌘/Ctrl+clic et clic
milieu ouvrent un onglet sans la déclencher (FR-005, scénario 2 — satisfait par
construction). Elle exige `prefetch={false}` sur la ligne, sans quoi la phase
d'attente est sautée en production. Détail et sources : `research.md` D3.

## 5. Ce que la feature ne touche pas

- Aucun appel API, aucun champ, aucun contrat `/api/v1`.
- Aucune requête ni tri déplacé : l'ordre d'affichage du classement reste une
  propriété de la requête (#163), le tri par inters reste côté client comme
  aujourd'hui.
- Aucune largeur plancher, aucun `overflowX` (lot #461).
- Aucun token `--tcn-*`, aucune police, aucune frontière `tcn/` vs `ui/`
  (contraintes de #325).
