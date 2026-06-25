# Page « Résultats » : liste d'épreuves cliquable vers la fiche course

Date : 2026-06-24
Cible : `frontend/`
Issue : [#8 — revue de la page résultats](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/8)

## Contexte (retour de Vincent)

Sur la page **Résultats** (`/resultats`), chaque épreuve est rendue dans un
accordéon (`components/results/EventList.tsx`). Au clic sur le titre d'un
triathlon, le panneau se déplie et affiche **tous les résultats en ligne** via
`EventParticipations` (cartes `ResultCard` chargées à la demande).

Vincent remonte deux points :

1. **L'affichage des résultats en ligne dans l'accordéon ne sert pas à
   grand-chose → à supprimer.**
2. **Au clic sur une épreuve, il veut être redirigé vers la page « résultats
   complets » de la course**, c.-à-d. la fiche existante `/courses/[id]`
   (exemple cité : `/courses/14`).

Cette fiche course existe déjà (`app/courses/[id]/page.tsx`) et offre une vue
bien plus riche que l'accordéon : entête, répartitions genre / catégories /
clubs, classement complet (`RaceFinishers`). C'est la bonne destination.

## Décisions de Vincent (revue PR #12, 2026-06-25)

Les trois questions ouvertes (cf. bas de spec) sont tranchées :

1. **Accordéon supprimé** au profit d'une liste cliquable — confirmé, pas de
   demi-mesure (« oui, on supprime l'accordéon »).
2. **Forme de l'item** : « on fait un menu qui ressemble à la page athlète ».
   → on n'aligne **pas** sur l'ancien rendu shadcn (badges dans un trigger) mais
   sur le **TCN Design System** déjà en place sur `/athletes/[id]` : une `Card`
   contenant une **table de lignes-liens** (`tcn-rowlink`). Voir Design ci-dessous.
3. **Suppression d'un résultat** : « à supprimer de cette page ». On la retire
   purement et simplement de `/resultats`, et on **ne la porte pas** sur la fiche
   course. Vincent prévoit une **page d'administration / validation des résultats
   dédiée**, réservée (derrière un mot de passe) — c'est elle qui hébergera la
   suppression. Hors périmètre de cette issue (voir Hors périmètre).

## Objectif

Transformer la liste de la page Résultats : remplacer l'accordéon dépliable par
une **liste de lignes-liens au style « page athlète » (TCN Design System)** qui
naviguent vers `/courses/[id]`. Supprimer le chargement inline des participations
**et** la suppression de résultat sur cette page.

## Design

### `EventList.tsx` — de l'accordéon à la table de lignes-liens (style page athlète)

Modèle de référence : `app/athletes/[id]/page.tsx` — une `Card` (composant
`@/components/tcn`) enveloppant une grille de lignes, chaque ligne étant un
`<Link className="tcn-rowlink">` vers `/courses/[id]`, avec un entête de colonnes
et une flèche `→` en fin de ligne. On reprend ce vocabulaire visuel (tokens
`--tcn-*`, `Card`, `tcn-rowlink`, `FormatChip`, `eventTypeLabel`) plutôt que les
`Badge` / `Accordion` shadcn actuels.

- **Supprimer** le bloc `Accordion / AccordionItem / AccordionTrigger /
  AccordionContent` et le montage de `<EventParticipations />`.
- **Envelopper** la liste dans une `Card` (`padding={0}`, `overflow: hidden`)
  avec un titre type « Toutes les épreuves » + sous-titre « Clique sur une épreuve
  pour voir le détail → », comme la fiche athlète. Le `Select` de tri se place
  dans cet entête de carte (à droite).
- **Rendre un entête de colonnes** puis une ligne `<Link href={\`/courses/${ev.id}\`}
  className="tcn-rowlink">` par épreuve. Colonnes proposées à partir des champs
  `EventOut` disponibles (`id, event_name, event_date, event_type, is_relay,
  distance_km, total, tcn_count`) :
  - **Date** — `formatDate(ev.event_date)`
  - **Épreuve** — `ev.event_name` (colonne large `1fr`)
  - **Type** — `eventTypeLabel(ev.event_type)`
  - **Format** — `<FormatChip>{formatToken(ev.event_type, ev.distance_km)}</FormatChip>`
  - **Résultats** — `ev.total`
  - **TCN** — `ev.tcn_count` (ou « — » si 0)
  - colonne finale **→** (`--tcn-text-disabled`)

  Le badge « Relais » (`ev.is_relay`) est conservé, accolé au nom de l'épreuve
  (petit chip), pour ne pas perdre l'information.
- Reprendre l'affordance `tcn-rowlink` (hover/focus déjà gérés par cette classe)
  et la trame de colonnes via une constante `COLS` (cf. page athlète).
- **Conserver** le tri (`SORT_OPTIONS`), le scroll infini (`IntersectionObserver`
  + sentinelle), l'`EmptyState` et l'état de chargement. Le `Select` peut rester
  le composant shadcn existant ; seul le conteneur des épreuves change.

> Note : `EventList` reste un Client Component (`useInfiniteEvents`, scroll
> infini, tri via l'URL). On reproduit donc le **rendu visuel** de la page
> athlète, pas son implémentation Server Component.

### Suppression du delete inline — retirée de cette page

Décision Vincent : la suppression d'un résultat **quitte** `/resultats` et n'est
**pas** portée sur la fiche course. Elle vivra sur une future page
d'administration/validation dédiée (protégée par mot de passe), hors périmètre.

- Retirer de `EventList` toute la logique `onDelete` / `del`
  (`useDeleteParticipation`) / invalidations / `toast` associés : sans
  participation rendue ici, elle n'a plus de point d'usage.
- Ne **rien** ajouter sur `/courses/[id]` ni `RaceFinishers` dans le cadre de
  cette issue.

### Composants devenus inutilisés

- `components/results/EventParticipations.tsx` n'est plus monté par `EventList`.
  Vérifier qu'aucun autre appelant ne l'utilise ; si non → **suppression** (et de
  son éventuel test).
- `components/results/SportBadge.tsx` n'est plus utilisé par `EventList` (remplacé
  par `eventTypeLabel` + `FormatChip`) mais **reste utilisé** par `ResultCard` et
  `ClubDashboard` → **ne pas** le supprimer.
- Vérifier les usages restants de `ResultCard` (probablement la fiche athlète
  `/athletes/[id]`) avant toute suppression : **ne pas** toucher `ResultCard`.

### Tests

- Mettre à jour `components/results/EventList.test.tsx` :
  - une épreuve rend un lien pointant vers `/courses/${id}` ;
  - plus d'expansion / plus de `ResultCard` rendue dans la liste ;
  - tri, scroll infini et `EmptyState` toujours couverts.
- Supprimer/adapter `EventParticipations`-related si le composant disparaît.
- `npm test` + `npm run build` (TS strict) verts.

## Hors périmètre

- Aucune modification backend ni API.
- Pas de refonte de la fiche `/courses/[id]` elle-même (destination déjà en
  place).
- **Suppression d'un résultat** : retirée de cette page, **pas** portée sur la
  fiche course. Sera traitée par la future **page d'administration / validation
  des résultats** (réservée, protégée par mot de passe) — non couverte ici.

## Questions tranchées (revue PR #12, voir « Décisions de Vincent »)

1. **Accordéon → liste cliquable** : oui, suppression franche. ✅
2. **Suppression d'un résultat** : retirée de `/resultats`, non réexposée sur
   `/courses/[id]` ; reportée à une page d'admin dédiée. ✅
3. **Forme de l'item** : table de lignes-liens au style de la page athlète
   (TCN Design System), pas l'ancien rendu shadcn. ✅
