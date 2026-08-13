# Feature Specification: Page de résultats détaillée d'une participation

**Feature Branch**: `20260813-163525-resultats-detail-participation`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "Page de résultats détaillée pour une participation athlète à un triathlon (issue #272)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Se comparer aux autres coureurs sur sa performance (Priority: P1)

Un membre du club consulte le tableau des finishers d'une course (page course
ou page athlète) où sa ligne est surlignée. Il clique dessus et accède à une
page dédiée qui rassemble son résultat (rang, temps par segment) et le compare
au classement complet de l'épreuve : où se situe-t-il par rapport au 1er, au
10e, au 25e, au 50e, au 100e, segment par segment ?

**Why this priority** : c'est la valeur centrale demandée par l'issue — une
« feuille de route personnelle » de comparaison, et le produit a explicitement
priorisé ce bloc en premier devant les deux autres.

**Independent Test** : peut être testé seul en affichant, pour une
participation éligible, le bloc ligne de résultat + le tableau de comparaison
par position de référence — sans le graphique ni la simulation de gains, la
page délivre déjà une valeur autonome (« comment je me situe »).

**Acceptance Scenarios**:

1. **Given** une course éligible aux statistiques détaillées et une
   participation sur cette course, **When** l'utilisateur clique sur la ligne
   de cette participation dans le tableau des finishers, **Then** il accède à
   la page de détail affichant le rang scratch, le nom, la catégorie, le sexe,
   le temps total et les splits publiés par l'épreuve.
2. **Given** la page de détail affichée, **When** l'utilisateur consulte le
   bloc de comparaison, **Then** il voit, pour chacune des positions 1er, 10e,
   25e, 50e et 100e, le temps de l'athlète exprimé en pourcentage du temps de
   la référence, pour chaque segment et pour le total.
3. **Given** un split absent pour l'athlète consulté (segment non publié par
   le chronométreur), **When** la ligne de résultat s'affiche, **Then** la
   cellule correspondante montre une valeur explicitement vide (tiret), jamais
   un zéro.

---

### User Story 2 - Comprendre l'évolution de son classement au fil de la course (Priority: P2)

Depuis la page de détail, l'utilisateur veut voir comment son classement a
évolué au fil des étapes (natation, T1, vélo, T2, course) : a-t-il remonté ou
perdu des places, et sur quel segment a-t-il été le plus fort ou le plus
faible pris isolément ?

**Why this priority** : complète la comparaison du P1 par une lecture
temporelle, mais reste secondaire dans l'ordre de valeur fixé par le produit.

**Independent Test** : peut être testé en affichant uniquement le graphique
d'évolution (position scratch cumulée + position sur le segment) sur une
participation déjà dotée du bloc P1 ; se vérifie indépendamment via les
positions affichées à chaque étape et le comportement des infobulles au
survol.

**Acceptance Scenarios**:

1. **Given** la page de détail d'une participation éligible, **When**
   l'utilisateur consulte le graphique d'évolution du classement, **Then** il
   voit une position scratch cumulée par étape (ligne) et une position sur le
   segment isolé (barre), sur les cinq étapes de la course, avec la meilleure
   position en haut du graphique.
2. **Given** le graphique affiché, **When** l'utilisateur survole un point ou
   une barre, **Then** une infobulle affiche le nom de l'étape et la position
   correspondante (scratch ou segment selon l'élément survolé), et une seule
   infobulle est visible à la fois.

---

### User Story 3 - Estimer le gain de classement d'une amélioration ciblée (Priority: P3)

Depuis la page de détail, l'utilisateur veut savoir combien de places il
aurait gagnées au classement scratch s'il avait amélioré un segment donné
d'un certain pourcentage, pour prioriser ses axes d'entraînement.

**Why this priority** : lecture la plus prospective et la plus « gadget »
des trois, explicitement placée en dernier par le produit.

**Independent Test** : peut être testé en affichant uniquement le tableau de
simulation (5 segments × 6 pourcentages d'amélioration) sur une participation
déjà dotée des blocs P1 et P2 ; se vérifie en comparant le nombre de places
gagnées affiché au recalcul manuel à partir du classement complet.

**Acceptance Scenarios**:

1. **Given** la page de détail d'une participation éligible, **When**
   l'utilisateur consulte le tableau des places gagnées par amélioration,
   **Then** il voit, pour chacun des cinq segments et chacun des six
   pourcentages (0,5 %, 1 %, 2 %, 5 %, 10 %, 25 %), le nombre de places
   scratch qui auraient été gagnées si ce segment avait été amélioré de ce
   pourcentage, toutes choses égales par ailleurs.

---

### Edge Cases

- Une course n'est pas éligible aux statistiques détaillées (résultats saisis
  manuellement, ou données scrapées jugées incomplètes) : la page affiche un
  état « statistiques indisponibles » avec message explicatif et un lien de
  retour, sans aucun tableau ni graphique — jamais une page partiellement
  remplie ou une erreur technique.
- Une participation est un relais (`is_relay = true`) : elle est exclue du
  dispositif, la répartition des segments entre plusieurs athlètes rendant une
  lecture individuelle non pertinente (cf. #295, un duo est traité comme une
  épreuve d'équipe, pas comme un individuel).
- Une épreuve n'a pas de transitions chronométrées (duathlon, swimrun) : les
  blocs n'affichent que les segments effectivement publiés pour cette épreuve,
  sans colonnes de transition vides forcées.
- Le classement de la course compte moins de finishers qu'une position de
  référence (ex. moins de 100 finishers) : la ligne correspondante du tableau
  de comparaison est masquée plutôt qu'affichée avec une valeur vide ou
  trompeuse.
- L'identifiant de participation demandé n'existe pas, ou n'appartient pas à
  la course indiquée dans l'URL : la page se comporte comme une ressource
  introuvable (même traitement que les autres pages de détail existantes).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre d'accéder à une page de détail dédiée
  à une participation depuis une ligne éligible du tableau des finishers d'une
  course.
- **FR-002**: Le système DOIT permettre d'accéder à cette même page de détail
  depuis la liste des courses affichée sur la page d'un athlète.
- **FR-003**: Le système DOIT déterminer l'éligibilité d'une course à
  l'affichage détaillé à partir d'une liste explicite de fournisseurs
  **exclus**, connus pour ne publier des splits complets que pour une partie
  des finishers (ex. T2Area et Breizh Chrono, qui ne récupèrent les splits fins
  que sur la fiche individuelle des membres TCN). Tout autre fournisseur est
  éligible par défaut : une liste d'exclusion échoue de façon **visible** (trop
  permissive) là où une liste blanche se périmerait **silencieusement** à
  chaque nouveau fournisseur enregistré. Cette liste est maintenue dans
  le code, au même titre que la liste blanche des clubs (`app/core/club.py`) —
  **pas** via un panel d'administration : la fiabilité d'un fournisseur pour
  cet usage est une propriété du scraper qui l'implémente, pas un réglage
  métier arbitrable ; sa mise à jour accompagne toujours une évolution du
  scraper concerné, dans la même PR. Une participation saisie manuellement
  (fournisseur « manuel ») n'ouvre jamais cet état, quel que soit son contenu.
- **FR-004**: Le système NE DOIT PAS restreindre l'affichage détaillé aux
  seules participations club : dès qu'une course est éligible (FR-003), la
  page de détail est accessible pour tout finisher de cette course. Les splits
  affichés dans le tableau des finishers existant étant déjà publics pour
  toute participation, club ou non, une restriction au niveau de cette page
  n'apporterait pas de confidentialité supplémentaire ; l'app ne distingue de
  toute façon pas les visiteurs connectés des autres sur ces pages de
  résultats.
- **FR-005**: Quand une course n'est pas éligible (fournisseur hors liste
  fiable, ou résultats saisis manuellement), le système DOIT afficher un état
  « statistiques indisponibles » qui explique la raison à l'athlète — que les
  statistiques détaillées ne s'affichent que lorsque l'intégralité des
  résultats du chronométreur a pu être récupérée pour cette course — avec un
  lien de retour vers les résultats de l'athlète, sans rendre aucun tableau,
  graphique ni bouton d'action supplémentaire. Le message reste générique
  (la raison de fond, pas le nom du fournisseur ni un jugement de fiabilité
  affiché à l'utilisateur).
- **FR-006**: Le système DOIT afficher, pour la participation consultée, un
  rang scratch, le nom complet de l'athlète, la catégorie, le sexe, le temps
  total, et les splits publiés par l'épreuve (natation, T1, vélo, T2, course —
  jusqu'à cinq, cf. FR-013), avec une mise en avant visuelle distincte pour les
  disciplines chronométrées par rapport aux transitions.
- **FR-007**: Le système DOIT afficher un split absent comme une valeur
  explicitement vide, jamais comme un zéro ou une case ambiguë.
- **FR-008**: Le système DOIT afficher un tableau de comparaison croisant cinq
  positions de référence du classement scratch (1er, 10e, 25e, 50e, 100e) avec
  chaque segment et le temps total, exprimant le temps de l'athlète consulté
  en pourcentage du temps du coureur occupant cette position sur ce segment.
- **FR-009**: Le système DOIT afficher un graphique d'évolution du classement
  sur les cinq étapes de la course (natation, T1, vélo, T2, course), montrant
  à la fois la position scratch cumulée de l'athlète à la sortie de chaque
  étape et sa position isolée sur cette étape, la meilleure position étant
  représentée en haut.
- **FR-010**: Le système DOIT afficher, au survol d'un élément du graphique
  d'évolution, une infobulle indiquant le nom de l'étape et la position
  correspondante (scratch cumulée ou segment isolé selon l'élément survolé),
  une seule infobulle étant visible à la fois.
- **FR-011**: Le système DOIT afficher un tableau de simulation croisant chaque
  segment publié par l'épreuve (jusqu'à cinq, cf. FR-013) avec six pourcentages
  d'amélioration (0,5 %, 1 %, 2 %, 5 %,
  10 %, 25 %), indiquant pour chaque cellule le nombre de places gagnées au
  classement scratch si ce segment avait été amélioré de ce pourcentage,
  toutes choses égales par ailleurs.
- **FR-012**: Le système DOIT exclure du dispositif toute participation de
  relais (`is_relay = true`).
- **FR-013**: Le système DOIT n'afficher, pour une épreuve donnée, que les
  segments effectivement publiés par cette épreuve (ex. pas de colonnes de
  transition pour un duathlon ou un swimrun sans T1/T2 chronométrés).
- **FR-014**: Le système DOIT masquer, dans le tableau de comparaison, la
  ligne d'une position de référence qui n'existe pas dans le classement de la
  course consultée (effectif insuffisant), plutôt que d'afficher une valeur
  vide ou trompeuse.
- **FR-015**: Le système DOIT proposer, depuis la page de détail, un retour
  vers la page de résultats de l'athlète courant et un accès au bouton
  d'ajout d'un triathlon, cohérents avec la navigation existante des autres
  pages de l'application.

### Key Entities *(include if feature involves data)*

- **Ligne de résultat de la participation** : synthèse d'une participation
  existante (rang scratch, identité, temps total, splits par segment) déjà
  présente en base, réutilisée telle quelle pour l'en-tête de la page.
- **Comparaison par position de référence** : agrégat calculé à la demande à
  partir du classement complet de la course, croisant une position de
  référence et un segment (ou le total) en un pourcentage de temps ; n'est pas
  une donnée stockée.
- **Évolution du classement par étape** : agrégat calculé à la demande,
  associant à chaque étape de la course la position scratch cumulée et la
  position sur le segment isolé de l'athlète consulté ; n'est pas une donnée
  stockée.
- **Simulation de gains par amélioration** : agrégat calculé à la demande,
  croisant un segment et un pourcentage d'amélioration en un nombre de places
  gagnées au classement scratch ; n'est pas une donnée stockée.
- **Éligibilité aux statistiques détaillées** : propriété de la course (pas de
  la participation), déterminant si les trois agrégats ci-dessus peuvent être
  calculés et affichés pour l'ensemble de ses participations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un membre du club éligible atteint sa page de détail de
  participation en un seul clic depuis n'importe quel tableau de résultats où
  sa ligne apparaît (page course ou page athlète).
- **SC-002**: 100 % des splits absents affichés sur la page se distinguent
  sans ambiguïté d'un temps réel de zéro, sur l'ensemble des courses
  consultées.
- **SC-003**: La page affiche l'intégralité de ses blocs (ligne de résultat,
  comparaison, évolution, simulation) en moins de 2 secondes pour une course
  de taille courante (quelques centaines de finishers).
- **SC-004**: Sur une course non éligible, 100 % des accès à la page affichent
  l'état « statistiques indisponibles » de façon prévisible, sans page
  partiellement remplie ni erreur technique visible par l'utilisateur.
- **SC-005**: Le rang scratch et les positions par segment affichés sur cette
  page restent cohérents à tout instant avec le classement affiché par
  ailleurs dans l'application pour la même course (aucune divergence de rang
  observable entre les deux écrans).

## Assumptions

- Une participation de relais (`is_relay = true`) est exclue du dispositif —
  cf. Edge Cases et #295.
- Le pays de l'athlète n'est pas affiché : la donnée n'existe ni en base
  (`athletes` porte `nom`, `prenom`, `gender`, `birth_date`, `club`) ni dans
  les charges scrapées. L'afficher supposerait une migration et une évolution
  des douze scrapers éligibles, sans rapport avec la valeur de comparaison
  visée — écarté du périmètre le 2026-08-13.
- Les épreuves sans transitions chronométrées affichent uniquement les
  segments effectivement publiés, sans forcer de colonnes T1/T2 vides ;
  cohérent avec l'adaptation déjà en place sur le tableau des finishers
  existant.
- Les bornes de l'axe des ordonnées du graphique d'évolution du classement
  sont calculées dynamiquement à partir du minimum et du maximum des positions
  de l'athlète sur la course consultée, avec une marge, plutôt que fixées
  comme sur la maquette de référence.
- L'affichage s'adapte aux petits écrans par un empilement vertical des blocs
  de la colonne de droite, sans exigence de parité pixel-perfect avec la
  maquette desktop.
- L'accès en lecture à cette page reste public, sans nouvelle exigence
  d'authentification, cohérent avec le reste des pages de résultats déjà
  publiques de l'application.
- Le contenu visuel détaillé (couleurs, typographie, dimensions, comportement
  exact des infobulles) suit la spécification fonctionnelle et la maquette
  jointes à l'issue #272 ; ce document produit ne les reproduit pas
  intégralement, elles font foi pour le plan de conception à venir.
- La liste des fournisseurs exclus pour incomplétude des splits
  (FR-003) vit dans le code, pas dans un panel d'administration : c'est une
  propriété du scraper qui alimente chaque fournisseur, pas un réglage métier
  arbitrable par un opérateur — décision actée en clarification (2026-08-13),
  après avoir écarté un panel admin pour ce cas précis.
- Aucune restriction club sur l'accès à la page elle-même (FR-004) : décision
  actée en clarification (2026-08-13), la restriction n'ajoutant pas de
  confidentialité réelle vu que les splits bruts sont déjà publics par
  ailleurs et que l'app n'authentifie pas ses lecteurs sur les pages de
  résultats.
