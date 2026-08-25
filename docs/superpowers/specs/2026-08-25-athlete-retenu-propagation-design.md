# Propager l'athlète retenu — `NAV-10` (#503)

Design validé le 2026-08-25. Lot de l'epic #460, cluster « à quoi sert un
athlète retenu ? ». Preuves : `docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`, § 10.

## Le problème

Une fois son nom désigné, l'utilisateur doit le **retaper partout**.
`/resultats` expose un filtre par nom que rien ne pré-remplit, et dans un
classement de 498 lignes un athlète cherche sa propre ligne à l'œil.

Trois gestes, tous à **coût backend nul** : aucune route, aucun paramètre
d'API n'est ajouté ni modifié.

## Ce que ce lot ne fait pas

**Filtrer en silence.** Aucun filtre n'est appliqué au chargement d'un écran.
Chaque geste est proposé, déclenché par un clic, et révocable par une commande
déjà présente à l'écran. Pas d'alertes non plus.

## Dépendances levées

- **#467** — l'arbitrage `localStorage` → rendu serveur est tranché : **pas de
  cookie miroir**. Le stock `tcn-athlete` se lit côté client, jamais en rendu
  serveur (`frontend/AGENTS.md`, § « L'athlète retenu ne franchit pas la
  frontière serveur »). Ce lot ne le rouvre pas : aucun de ses trois gestes
  n'est un besoin serveur, tous sont de la mise en avant ou de la pré-saisie.
- **#485** — les commandes de liste du classement (saut de page, taille de
  tranche, état de vue filtrée) sont livrées. Le bandeau « X résultats sur 498
  pour « Nom » · Effacer » de `RaceFinishers` en vient : c'est lui qui rend le
  volet 2 lisible et révocable sans rien ajouter.

## 1. Socle partagé — `useSelectedAthlete()`

`components/layout/AthletePicker.tsx` porte déjà le stock, `readAthlete()` et
`useIsSelectedAthlete(id)`. Les volets 1 et 3 ont besoin de l'**athlète**, pas
d'un booléen : d'où un second hook, à côté du premier.

```
useSelectedAthlete(): PickedAthlete | null
```

Même `subscribeAthlete`, même repli `null` au rendu serveur.
`useSyncExternalStore` exige un `getSnapshot` qui rende une **référence stable**
d'un appel à l'autre — or `readAthlete()` reconstruit un objet à chaque lecture,
ce qui bouclerait indéfiniment. Le hook mémorise donc le dernier couple
(chaîne brute lue dans `localStorage`, objet analysé) au niveau du module, et
ne ré-analyse que si la chaîne a changé. C'est exactement la raison pour
laquelle `useIsSelectedAthlete` rendait un booléen, documentée dans son
commentaire.

Prix assumé, hérité de #467 : la valeur n'est **jamais dans le HTML initial**
et apparaît à l'hydratation. Les trois surfaces le supportent — deux d'entre
elles rendent une commande en plus, pas un déplacement de contenu.

## 2. Volet 1 — la pastille de `/resultats`

Dans `components/results/ResultsFilters.tsx` (déjà `"use client"`), sous le
champ « Athlète » : un bouton `Mes résultats` précédé de l'avatar de l'athlète.

**Condition d'affichage** : un athlète est retenu **et**
`sp.get("name") !== nomComplet(athlete)`. Le filtre posé, la pastille
disparaît — le chip actif `Athlète : <Nom> ✕` déjà rendu tient la révocation,
et deux commandes pour le même état se contrediraient à l'écran.

**Au clic** : `push({ name: nomComplet(athlete), … })`, les autres filtres de
l'URL conservés, avec le `captureEvent("results_filter_applied")` que porte
déjà `apply()`.

Le nom complet vient de `nomComplet()`, jamais d'un recollage local :
`prenom` et `nom` restent séparés dans le stock pour la raison mesurée en #264.
Le filtre `name` du backend cherche mot à mot, `nom` **ou** `prénom`, sans
casse ni accents (`name_filter`, #357) — un nom complet y correspond donc.

## 3. Volet 2 — `/courses/[id]`

Tout dans `components/results/RaceFinishers.tsx`.

### La ligne mise en avant

Le liseré orange gauche **est déjà pris** par `is_tcn` : il ne peut pas porter
un second sens sans rendre les deux illisibles. La ligne de l'athlète retenu
prend donc :

- un fond `var(--tcn-orange-08)` — celui de la tuile du rail, même sens ;
- un chip « Vous » après le nom.

Le chip n'est pas décoratif : la couleur seule échouerait WCAG 1.4.1. Le fond
prime sur le gris des non-finishers — un athlète qui a abandonné reste
l'athlète retenu, et l'information « c'est vous » est celle qu'il cherche.

Reconnaissance côté client par `useIsSelectedAthlete(p.athlete.id)`, sur les
seules lignes de la tranche affichée : c'est tout ce que le client tient.

### « Aller à ma ligne »

Un bouton à côté du formulaire de recherche du classement, rendu **dès qu'un
athlète est retenu** — sans condition sur sa présence dans l'épreuve, que le
front ne peut pas connaître.

Au clic : `naviguer({ q: nomComplet(athlete) })`. La recherche existante du
classement (`q`, insensible aux accents, #163) est la seule façon d'atteindre
la ligne **quelle que soit sa page** à coût backend nul : l'ordre d'affichage
est une propriété de la requête SQL (`_ordre_affichage` — finishers par rang,
puis DNF/DSQ/DNS par temps), et `orderParticipations` a été **supprimée** côté
front précisément parce qu'elle ne sait pas le reproduire. Calculer « ma page »
demanderait soit une route neuve, soit de télécharger tout le classement
(1,15 Mo mesuré sur l'épreuve de #163) pour ne faire que compter.

Le geste est un filtrage, et il est **explicite** : le bandeau
« X résultats sur 498 pour « Nom » · Effacer » de #485 le nomme et l'annule.
Pas d'ancre `#`, pas de défilement : la sélection tient sur une ligne, déjà en
haut du tableau.

### L'impasse

Quand la recherche courante vaut exactement `nomComplet(athlete)` et ne rend
rien, l'état vide ne dit plus « Aucun athlète ne correspond à cette recherche »
mais « <Nom> ne figure pas sur cette épreuve », avec « Voir tous les
participants ». Une branche de plus dans l'`EmptyState` en place, aucun appel.

## 4. Volet 3 — le raccourci de la tuile du rail

`components/layout/AppNav.tsx`. La tuile de l'athlète retenu passe en colonne :

```
┌─ rail déplié ──────────────┐
│ (TJ)  Thomas          ✕    │
│  Mes résultats             │
└────────────────────────────┘
```

La rangée actuelle — avatar, prénom, croix de désélection — ne bouge pas. En
dessous, un lien texte discret « Mes résultats » vers
`/resultats?name=<nom complet>`, `prefetch={false}` pour la même raison que le
lien de profil voisin (#425) : un athlète épinglé n'est pas une destination
probable.

**Rail déplié et tiroir mobile seulement**, comme la croix de désélection :
replié, la tuile fait 44 px et l'avatar l'occupe entière.

## Tests

Vitest + RTL, TDD, dans les fichiers de test existants.

| Fichier | Ce qui est établi |
| --- | --- |
| `AthletePicker.test.tsx` | `useSelectedAthlete` rend `null` sans stock, l'athlète avec, se resynchronise sur `ATHLETE_CHANGED_EVENT`, et son snapshot est **stable** entre deux rendus (sans quoi `useSyncExternalStore` boucle) |
| `ResultsFilters.test.tsx` | pastille absente sans athlète retenu, absente quand `name` vaut déjà le nom complet, présente sinon ; clic → URL portant `name`, les autres filtres conservés |
| `RaceFinishers.test.tsx` | chip « Vous » sur la seule ligne de l'athlète retenu ; bouton « Aller à ma ligne » → navigation avec `q=<nom complet>` ; état vide nommé quand `q` vaut ce nom et que rien ne remonte |
| `AppNav.test.tsx` | seconde ligne rendue avec le bon `href` quand un athlète est retenu, absente sinon et hors du rail déplié |

## Hors périmètre

- `/dashboard` (#502) et les listes du club (#504) — les deux autres lots du
  cluster, chacun sur sa branche.
- L'identité visuelle (`--tcn-*`, Anton/Barlow) et la frontière
  `components/tcn/` vs `components/ui/` : arbitrées en #325, non rejugées ici.
- Toute alerte, notification ou personnalisation qui dépasserait la mise en
  avant et la pré-saisie.
