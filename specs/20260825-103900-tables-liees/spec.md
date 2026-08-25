# Feature Specification: Des tableaux qui se lisent, des lignes qui se partagent

**Feature Branch**: `worktree-issue-481-tables-liees`

**Created**: 2026-08-25

**Status**: Draft

**Input**: Issue #481 — `refactor(a11y): turn the six public div grids into tables with linked rows`. Entrée `A11Y-3` du § 4 de `docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`. Lot de l'epic #460, refs #325. Périmètre retenu par le mainteneur : le **L complet**, pas le découpage S.

## Contexte

Six listes de données des écrans publics sont dessinées en `display: grid` de
`<div>`, avec une ligne d'en-tête **séparée, reliée à rien**. Un lecteur
d'écran énonce donc « 13/06/2026 Triathlon et SwimRun Mesquer-Quimiac 2026
Triathlon S S 01:10:47 2 ⚠ » sans jamais dire quelle colonne est laquelle. Le
back-office, lui, utilise de vrais tableaux (65 `TableHead`) : l'asymétrie
n'est pas un choix, c'est une dette.

Seconde couche, sur le seul classement d'épreuve : sa ligne est un
`role="button"` piloté au clavier et par navigation programmatique. On ne peut
donc **ni ouvrir un résultat dans un nouvel onglet, ni copier son lien, ni voir
l'URL au survol** — alors que partager « le résultat de X » est le geste social
central d'un club. La page rendue ne contient aucun lien vers les
participations : ce qui n'est pas un `href` n'existe pas pour qui partage, ni
pour un moteur.

### Inventaire vérifié le 2026-08-25 (les repères de l'issue ont bougé)

L'issue et le rapport citent des chemins et des numéros de ligne antérieurs à
#509 (déplacement sous `app/(public_restricted)/`), à #489 (extraction
d'`EventsTable`) et à la refonte de `/dashboard`. Inventaire réel, six listes :

| # | Liste | Fichier | En-tête | Ligne |
| --- | --- | --- | --- | --- |
| 1 | Classement d'une épreuve | `components/results/RaceFinishers.tsx` | `:273` | `:304` — **`role="button"`** |
| 2 | Liste des épreuves | `components/results/EventList.tsx` | `:167` | `:227` (`EventRow`) + `:281` (ligne de groupe dépliable) |
| 3 | Épreuves d'un athlète | `app/(public_restricted)/athletes/[id]/EventsTable.tsx` | `:241` | `:267` (+ sous-ligne de preuve/actions) |
| 4 | Derniers résultats enregistrés | `app/(public_restricted)/ajouter/page.tsx` | `:38` | `:46` |
| 5 | Dernières épreuves | `components/dashboard/RecentCourses.tsx` | `:52` | `:80` |
| 6 | Top clubs | `app/(public_restricted)/courses/[id]/page.tsx` | `:113` | `:121` — lignes **non interactives** |

Deux points que cet inventaire corrige, et qui réduisent le périmètre réel :

- **Cinq listes sur six ont déjà une ligne cliquable correcte** (`<Link>` ou,
  pour la ligne de groupe d'`EventList`, un `<button aria-expanded>` qui est le
  bon élément puisqu'elle déplie au lieu de naviguer). Seule la liste 1 est
  encore un `role="button"`.
- **Les cibles tactiles des en-têtes triables sont déjà au plancher** : #479 a
  posé `padding: 4px 0` et `minHeight: 24` sur `EnteteTriable`, avec le
  commentaire qui l'atteste. Le lot `CIBLE-1` est passé ; il n'y a rien à
  reprendre ici.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lire un tableau au lecteur d'écran (Priority: P1)

Un membre du club qui utilise un lecteur d'écran ouvre le classement d'une
épreuve, la liste des épreuves ou sa propre fiche d'athlète. Il veut savoir, à
chaque valeur énoncée, de quelle colonne elle vient — « Temps total, 01:10:47 »
plutôt que « 01:10:47 » au milieu de six autres nombres.

**Why this priority**: C'est le défaut d'origine, il est transversal aux six
listes, et il rend la donnée inintelligible pour l'aide technique. Les cinq
autres écrans du back-office n'ont pas ce problème : l'écart est entièrement
subi par le public.

**Independent Test**: Livrable seul. Se vérifie liste par liste, sans toucher à
la navigation : chaque cellule doit être rattachée à son en-tête de colonne, et
l'ensemble doit s'annoncer comme un tableau de N colonnes et M lignes.

**Acceptance Scenarios**:

1. **Given** le classement d'une épreuve affiché, **When** l'utilisateur
   parcourt une ligne à l'aide technique, **Then** chaque valeur est annoncée
   avec le nom de sa colonne.
2. **Given** n'importe laquelle des six listes, **When** l'aide technique
   annonce la structure, **Then** elle la présente comme un tableau et en donne
   le nombre de colonnes et de lignes.
3. **Given** une liste dont l'en-tête porte un contrôle de tri actif,
   **When** l'utilisateur atteint cet en-tête, **Then** la direction du tri en
   cours est annoncée (croissant / décroissant), et non seulement le libellé.
4. **Given** une liste vide ou filtrée à zéro résultat, **When** elle s'affiche,
   **Then** l'état vide existant reste rendu **à l'identique de ce qu'il est
   aujourd'hui**, en-tête comprise : les listes qui rendent leur en-tête sur une
   liste vide continuent de la rendre, celles qui la masquent continuent de la
   masquer. FR-007 prime ici sur toute harmonisation — la répartition liste par
   liste est dans `contracts/structure-accessible.md` C1.

---

### User Story 2 - Partager le résultat d'un athlète (Priority: P1)

Un membre trouve la ligne d'un coéquipier dans le classement d'une épreuve. Il
veut en envoyer le lien sur la boucle du club : clic droit → copier l'adresse,
ou clic milieu pour l'ouvrir à côté sans perdre le classement, ou simplement
survoler pour voir où mène la ligne.

**Why this priority**: Même priorité que P1 parce que c'est l'usage social
principal de l'application et qu'il est aujourd'hui **impossible**, pas
seulement dégradé. Livrable indépendamment de P1 (l'issue prévoit ce
découpage), mais le mainteneur a tranché pour le lot complet.

**Independent Test**: Livrable seul, sur la seule liste 1. Se vérifie sur la
page rendue par le serveur : elle doit contenir une adresse de détail par
ligne, sans exécution de script.

**Acceptance Scenarios**:

1. **Given** le classement d'une épreuve, **When** l'utilisateur survole une
   ligne, **Then** l'adresse de la page de détail du résultat est visible dans
   la barre d'état du navigateur.
2. **Given** la même ligne, **When** l'utilisateur l'ouvre en nouvel onglet
   (clic milieu, ⌘/Ctrl+clic, menu contextuel), **Then** le détail du résultat
   s'ouvre dans un nouvel onglet et le classement reste en place.
3. **Given** la page du classement récupérée sans exécuter de script,
   **When** on en cherche les adresses de détail, **Then** il y en a une par
   ligne affichée.
4. **Given** un utilisateur au clavier, **When** il atteint une ligne,
   **Then** l'aide technique l'annonce comme un lien — pas comme un bouton — et
   `Entrée` l'ouvre.

---

### User Story 3 - Savoir que le clic a été pris en compte (Priority: P2)

Un membre clique sur une ligne du classement. La réponse met entre 0,67 s et
1,43 s. Aujourd'hui, rien ne bouge pendant ce temps : il ne sait pas si son
clic a porté, et il reclique.

**Why this priority**: C'est un défaut de confort, pas d'accès : le geste
finit par aboutir. Il arrive après P1 et P2, mais il tient dans la même
branche parce qu'il porte sur la même ligne que P2 et qu'un mécanisme d'attente
existe déjà sur cet écran pour la recherche et la pagination.

**Independent Test**: Livrable seul, une fois P2 posé. Se vérifie en observant
la ligne cliquée entre le clic et l'arrivée de la page suivante.

**Acceptance Scenarios**:

1. **Given** le classement affiché, **When** l'utilisateur active une ligne,
   **Then** un état d'attente est visible **sur cette ligne** tant que la page
   de détail n'est pas rendue.
2. **Given** cet état d'attente, **When** l'utilisateur ouvre volontairement la
   ligne dans un nouvel onglet, **Then** aucun état d'attente ne s'affiche —
   la page courante ne change pas.
3. **Given** un visiteur ayant demandé la réduction des animations,
   **When** il active une ligne, **Then** l'attente reste perceptible sans
   mouvement.

---

### Edge Cases

- **La ligne de groupe d'`EventList` n'est pas un lien** : elle déplie une
  compétition qui en porte plusieurs. Elle doit rester un contrôle qui annonce
  son état déplié/replié, et les épreuves qu'elle révèle doivent rester
  rattachées à la même structure de colonnes que les lignes de premier niveau.
- **La sous-ligne d'`EventsTable`** (lien de preuve, gestes d'administration
  posés dans le navigateur, #439) vit sous sa ligne et n'existe pas au rendu
  serveur. Elle doit rester attachée à sa ligne sans casser le rattachement des
  cellules à leurs en-têtes, et le trait de séparation doit continuer de porter
  sur le couple, pas sur chaque moitié.
- **Le défilement horizontal reste** : les largeurs plancher (1 080 px, 988 px,
  966 px, 480 px) sont le lot #461 (`RESP-1`) et ne sont pas touchées ici. La
  structure doit rester défilable horizontalement à l'intérieur de son cadre,
  sans faire défiler la page entière.
- **Les colonnes du classement varient** : le nombre d'inters dépend de
  l'épreuve, et une colonne d'en-tête vide existe sur trois listes (la colonne
  de la flèche « → »). Une colonne sans libellé ne doit pas produire un en-tête
  annoncé comme vide à chaque ligne.
- **Une ligne en attente de validation** porte un marqueur et, parfois, aucune
  sous-ligne : le dessin actuel (absence de trait dans ce cas précis) est un
  acquis de #270, à préserver.
- **Le survol et le focus** de la ligne sont aujourd'hui portés par une classe
  partagée dont l'anneau de focus est un trait opaque en `--tcn-orange`
  (3,32:1) : ils doivent survivre au changement de structure, y compris le
  décalage négatif de l'anneau qui le garde à l'intérieur de la ligne.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Les six listes inventoriées ci-dessus MUST exposer une structure
  de tableau à l'aide technique : chaque cellule rattachée à l'en-tête de sa
  colonne, et l'ensemble annoncé avec son nombre de colonnes et de lignes
  (WCAG 2.2 **1.3.1 Info and Relationships**).
- **FR-002**: La ligne du classement d'une épreuve MUST devenir un lien
  véritable vers le détail du résultat, annoncé comme lien par l'aide technique
  (WCAG 2.2 **4.1.2 Name, Role, Value**), et non plus un élément portant un
  rôle de bouton.
- **FR-003**: La page du classement rendue par le serveur MUST contenir une
  adresse de détail par ligne affichée, exploitable sans exécution de script.
- **FR-004**: Les gestes natifs de navigation MUST fonctionner sur cette ligne :
  ouverture en nouvel onglet, copie de l'adresse, aperçu de la cible au survol.
- **FR-005**: L'activation d'une ligne du classement MUST afficher un état
  d'attente **sur la ligne activée** jusqu'au rendu de la page de détail, et
  cet état MUST rester perceptible sans mouvement pour qui a demandé la
  réduction des animations.
- **FR-006**: Les en-têtes triables du classement MUST annoncer la direction du
  tri en cours à l'aide technique, en plus du libellé et de l'action à venir
  déjà annoncés.
- **FR-007**: L'apparence rendue des six listes MUST rester celle d'aujourd'hui
  — mêmes colonnes, mêmes largeurs, mêmes gouttières, mêmes traits de
  séparation, même retour au survol, même anneau de focus, même liseré des
  lignes du club.
- **FR-008**: Les comportements déjà acquis sur ces listes MUST être préservés :
  dépliage d'une compétition à plusieurs épreuves, sous-ligne de preuve et de
  gestes d'administration, marqueurs d'épreuve non fiable et de résultat en
  attente, badges de place et de statut, états vides et leurs sorties,
  chargement à la volée de la liste des épreuves.
- **FR-009**: Chaque liste convertie MUST être couverte par un test qui
  échouerait si la structure repassait à une grille sans rattachement — le test
  porte sur ce que l'aide technique perçoit, pas sur le nom des balises.
- **FR-010**: La ligne du classement MUST être couverte par un test qui
  échouerait si elle redevenait un élément non navigable — vérification de la
  présence d'une adresse de destination, pas seulement d'un gestionnaire de
  clic.
- **FR-011**: La conversion MUST NOT introduire de tabulation supplémentaire par
  ligne : une ligne cliquable reste **un** arrêt au clavier, comme aujourd'hui.

### Hors périmètre

- Le repli des tableaux en cartes empilées sur mobile et les largeurs plancher —
  lot #461 (`RESP-1`).
- Les cibles tactiles des en-têtes triables — déjà livrées par #479.
- L'identité visuelle arbitrée (`--tcn-*`, Anton/Barlow) et la frontière
  `components/tcn/` vs `components/ui/`, que les contraintes de #325 (cf. #460)
  interdisent de rejuger.
- Les tableaux du back-office, qui sont déjà de vrais tableaux.
- Tout changement d'API : la feature est entièrement côté rendu.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur chacune des six listes, un lecteur d'écran annonce la colonne
  de chaque valeur qu'il énonce — 6/6, contre 0/6 aujourd'hui.
- **SC-002**: La page d'un classement contient autant d'adresses de détail que
  de lignes affichées — 20 sur une page par défaut, contre 0 aujourd'hui.
- **SC-003**: Les quatre gestes natifs sur une ligne de classement (nouvel
  onglet, copie du lien, aperçu au survol, ouverture au clavier) fonctionnent —
  4/4, contre 1/4 aujourd'hui (seul le clavier répond).
- **SC-004**: Sur une réponse qui prend jusqu'à 1,43 s, la ligne activée porte
  un état d'attente **visible dès le relâchement du clic** et jusqu'au rendu de
  la page de détail — observable à l'œil nu, sans instrument. Aucun autre
  élément de la page ne bouge dans l'intervalle. *(Ce critère remplace un seuil
  de 100 ms qu'aucune tâche ne mesurait : un nombre invérifiable ne fait pas un
  critère de succès.)*
- **SC-005**: Aucune régression visuelle sur les six listes : colonnes,
  largeurs, traits et états de survol/focus identiques avant et après, vérifiés
  écran par écran.
- **SC-006**: La suite de tests du front reste verte et le build de production
  passe, avec au moins un test par liste convertie qui échoue si la structure
  régresse.

## Assumptions

- **La décision de mise en œuvre est laissée au plan.** L'issue et le rapport
  ouvrent deux voies — vraies balises de tableau avec géométrie en grille, ou
  rôles ARIA posés sur la structure actuelle — et la première n'est pas
  gratuite : une ligne entièrement cliquable est aujourd'hui **un seul lien**
  couvrant la ligne, ce qu'une ligne de tableau ne peut pas être directement.
  La spec n'impose donc que le résultat perçu (FR-001, FR-002, FR-007,
  FR-011) ; l'arbitrage se tranche en `/speckit-plan`, liste par liste si
  nécessaire.
- **« Six listes » est un inventaire, pas un compte à préserver.** Il a été
  revérifié le 2026-08-25 et deux entrées ont changé de fichier depuis le
  rapport. Une septième découverte en cours de route entre dans le périmètre ;
  la vérité est le code, pas le tableau ci-dessus.
- **Aucun changement de contrat API n'est nécessaire** : toutes les données
  affichées sont déjà servies, y compris l'identifiant de participation dont
  l'adresse de détail est construite.
- **Le test se fait sans réseau** (Principe III) : les six listes se rendent à
  partir de données fournies, et l'aide technique se vérifie sur le rendu.
- **Le volet `aria-sort` appartient à ce lot** : #500 (`ADM-10`) le renvoie
  explicitement ici, et il n'a de sens qu'une fois les en-têtes rattachés à
  leurs colonnes.
- **La géométrie mobile reste en l'état** : ce lot ne doit pas améliorer ni
  dégrader le défilement horizontal, pour que #461 parte d'une base connue.
