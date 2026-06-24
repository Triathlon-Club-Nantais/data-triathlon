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

## Objectif

Transformer la liste de la page Résultats : remplacer l'accordéon dépliable par
une **liste de lignes/cartes cliquables** qui naviguent vers `/courses/[id]`.
Supprimer le chargement inline des participations sur cette page.

## Design

### `EventList.tsx` — de l'accordéon à la liste de liens

- **Supprimer** le bloc `Accordion / AccordionItem / AccordionTrigger /
  AccordionContent` et le montage de `<EventParticipations />`.
- **Remplacer** chaque épreuve par un élément `<Link href={\`/courses/${ev.id}\`}>`
  (composant `next/link`) rendant **exactement les mêmes métadonnées** qu'aujourd'hui
  dans le trigger, pour ne rien perdre visuellement :
  - `ev.event_name` (titre)
  - `<SportBadge type={ev.event_type} />`
  - date `formatDate(ev.event_date)`
  - badge « Relais » si `ev.is_relay`
  - badge « N résultats » (`ev.total`)
  - badge « N TCN » si `ev.tcn_count > 0`
- Conserver l'affordance de clic : `hover`, `focus-visible`, curseur pointeur,
  bordure arrondie (réutiliser le style de carte `rounded-md border px-4 py-3`).
- **Conserver** le tri (`Select` `SORT_OPTIONS`), le scroll infini
  (`IntersectionObserver` + sentinelle), l'`EmptyState` et l'état de chargement.

### Suppression du delete inline (à valider avec Vincent)

Aujourd'hui `EventList` câble `onDelete` → `useDeleteParticipation`, utilisé par
les `ResultCard` dépliées. En passant en liste de liens, **plus aucune
participation n'est rendue sur `/resultats`** : le bouton supprimer disparaît de
cette page.

- **Proposition** : retirer de `EventList` la logique `onDelete` / `del` /
  invalidations associées (elle n'a plus de point d'usage ici).
- La suppression d'un résultat reste possible depuis la fiche course
  `/courses/[id]` **si** elle y est exposée — **à confirmer** : faut-il porter
  l'action « supprimer un résultat » sur `RaceFinishers` ? (hors périmètre
  immédiat de l'issue, mais c'est la conséquence directe).

### Composants devenus inutilisés

- `components/results/EventParticipations.tsx` n'est plus monté par `EventList`.
  Vérifier qu'aucun autre appelant ne l'utilise ; si non → **suppression** (et de
  son éventuel test).
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
- L'éventuel portage de la suppression de résultat vers la fiche course est
  listé comme question ouverte, pas livré par défaut.

## Points à valider par Vincent

1. **OK pour supprimer purement l'accordéon** au profit d'une simple liste
   cliquable (pas de demi-mesure type « voir un aperçu » au survol) ?
2. **Suppression d'un résultat** : on l'enlève de la page Résultats — faut-il la
   réexposer sur la fiche course `/courses/[id]`, ou est-ce inutile ?
3. **Forme de l'item** : ligne pleine largeur cliquable (style actuel) convient,
   ou souhaite-t-il un autre rendu (grille de cartes, etc.) ?
