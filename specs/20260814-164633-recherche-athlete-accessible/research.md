# Research — Recherche d'athlète toujours accessible et sélection explicite

## État des lieux (constaté dans le code, pas supposé)

- Un seul composant, `frontend/components/layout/AppNav.tsx`, rend les trois
  formats de navigation (rail md+, barre mobile, tiroir mobile) depuis
  `NavContent` (`AppNav.tsx:301-508`).
- Le bloc "actions primaires" (`AppNav.tsx:368-462`) alterne aujourd'hui entre
  **deux rendus mutuellement exclusifs** : tuile athlète (`athlete ? ... :`)
  ou bouton "Rechercher un athlète". C'est cette exclusivité qui casse
  l'invariant documenté en tête de fichier (`AppNav.tsx:21-24` : "les deux
  actions primaires gardent le même ancrage").
- En rail replié (`expanded === false`) avec un athlète retenu, le chevron
  "Changer d'athlète" (seul déclencheur du picker dans cette branche) est
  lui-même conditionné à `{expanded && (...)}` (`AppNav.tsx:390-413`) : aucune
  icône n'est donc rendue du tout — seul `⌘K`/`Ctrl+K` fonctionne.
- La barre mobile (`AppNav.tsx:224-251`) garde déjà un bouton loupe
  indépendant de l'état athlète — non concernée par ce problème.
- La sélection persistée (`PickedAthlete`) vit dans `AthletePicker.tsx` sous
  forme de deux fonctions pures (`readAthlete`/`writeAthlete`, l.32-52) lisant
  et écrivant `localStorage["tcn-athlete"]`. Pas de store/contexte React :
  `AppNav` lit la valeur une fois au montage (l.62) et la garde en état local.
- La page profil (`app/athletes/[id]/page.tsx`) est un Server Component
  (fetch direct `apiServer.getAthlete`) sans aucun état de sélection.

## Décisions

### D1 — Afficher recherche et tuile simultanément, jamais en alternative

**Decision** : remplacer le rendu `athlete ? tuile : boutonRecherche` par un
rendu qui affiche toujours l'entrée "Rechercher un athlète" (icône seule en
rail replié, icône + libellé + raccourci en rail déplié), et qui affiche *en
plus*, quand un athlète est retenu, la tuile comme élément complémentaire
distinct — dans les deux largeurs de rail.

**Rationale** : c'est la plus petite modification qui répare l'invariant déjà
documenté en commentaire (`AppNav.tsx:21-24`) sans réagencer la navigation ;
elle répond directement aux constats #1 et #2 de l'issue.

**Alternatives rejetées** :
- Fusionner recherche et tuile en un seul contrôle (menu déroulant) — casse
  l'ouverture directe par `⌘K`/`Ctrl+K` et le contrat visuel "actions
  primaires à ancrage fixe" existant.
- N'ajouter qu'une icône secondaire de recherche en haut de la nav, à part du
  bloc actions primaires — dupliquerait un pattern déjà résolu côté mobile
  pour un problème qui n'existe que sur le rail desktop replié ; ajoute de la
  surface UI sans nécessité.

### D2 — Synchroniser la sélection via un `CustomEvent` DOM natif

**Decision** : `writeAthlete` et la nouvelle `clearAthlete` déclenchent un
`CustomEvent` sur `window` (ex. `tcn-athlete-changed`) après écriture ;
`AppNav` s'y abonne en plus de sa lecture au montage, pour refléter
immédiatement un changement fait depuis la page profil.

**Rationale** : un seul lecteur concurrent (`AppNav`) et un seul nouveau
point d'écriture (le bouton profil) — la solution la plus petite qui fait
converger les deux sans re-render global (Principe VI, YAGNI).

**Alternatives rejetées** :
- Contexte React englobant l'app — sur-dimensionné pour deux consommateurs,
  impose de remonter un provider au-dessus du layout pour un besoin ponctuel.
- Événement `storage` natif — ne se déclenche **pas** dans l'onglet qui
  écrit (seulement dans les autres onglets), alors que FR-008 exige une mise
  à jour immédiate dans le même onglet, sans rechargement.
- Poll périodique du localStorage — latence perçue et cycles gaspillés pour
  un événement qui ne se produit qu'au clic utilisateur.

### D3 — `clearAthlete()` rejoint `readAthlete`/`writeAthlete` dans `AthletePicker.tsx`

**Decision** : ajouter l'export `clearAthlete()` dans le même fichier plutôt
que créer un nouveau module de stockage dédié.

**Rationale** : `AthletePicker.tsx` n'a pas de directive `"use client"`
(commentaire l.1-3) précisément pour rester importable depuis n'importe quel
composant client — trois fonctions ne justifient pas un module séparé
(Principe VI).

### D4 — Le bouton de sélection de la page profil est un sous-composant client minimal

**Decision** : nouveau composant `"use client"` (`SelectAthleteButton`),
monté depuis `app/athletes/[id]/page.tsx` (qui reste un Server Component).

**Rationale** : `readAthlete`/`writeAthlete`/`clearAthlete` touchent
`window.localStorage`, donc doivent tourner côté client ; isoler ce besoin
dans le plus petit composant client possible évite de convertir toute la page
en Client Component et de perdre le fetch serveur direct
(`apiServer.getAthlete`).

## Non-résolu → aucun (spec sans marqueur `[NEEDS CLARIFICATION]`)
