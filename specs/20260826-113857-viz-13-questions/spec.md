# Feature Specification: Les 13 questions que l'app ne sait pas montrer

**Feature Branch**: `20260826-113857-viz-13-questions`

**Created**: 2026-08-26

**Status**: Draft

**Input**: User description: "Issue #466 — les 13 questions que l'app ne sait pas montrer (docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md §16). Périmètre : livrer les 13 questions dans une seule PR parapluie, traitées séquentiellement. Contraintes de l'issue : tout nouveau graphique se pose sur d3-scale/d3-shape déjà en dépendance, pas de nouvelle bibliothèque ; identité visuelle non rouverte (palette, typographie, dégradés) ; réponse au responsive requise pour tout graphique ajouté (RESP-2 déjà traité en #480)."

## User Scenarios & Testing *(mandatory)*

Chaque histoire correspond à une des 13 questions du § 16 de l'audit UX
(`docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`). Elles sont
indépendamment testables et déployables ; l'ordre de priorité suit l'ordre du
rapport, qui va du plus personnel (un athlète sur sa propre page) au plus
collectif (le club), puis aux écrans transverses (couverture, carte,
bénévoles).

### User Story 1 - Est-ce que je progresse ? (Priority: P1)

Un·e athlète consultant sa propre page veut voir si son niveau (classement
relatif, ratio par rapport au meilleur temps) évolue dans le temps, pas
seulement sa valeur actuelle.

**Why this priority**: C'est la question la plus fréquente et la plus
personnelle ; `bestRatio`/`rankRatio` sont déjà calculés côté serveur mais
réduits à un scalaire unique — la donnée existe, seule la vue manque.

**Independent Test**: Se rendre sur `/athletes/[id]` d'un athlète ayant
participé à plusieurs épreuves et vérifier qu'un graphique de série temporelle
montre l'évolution du ratio/classement au fil des épreuves.

**Acceptance Scenarios**:

1. **Given** un athlète avec au moins 3 participations, **When** il consulte
   sa page profil, **Then** un graphique affiche l'évolution de son ratio de
   performance dans l'ordre chronologique des épreuves.
2. **Given** un athlète avec une seule participation, **When** il consulte sa
   page profil, **Then** la zone du graphique affiche un état explicite
   indiquant qu'il faut plus de données, sans graphique vide ni erreur.

---

### User Story 2 - Mon temps, il vaut quoi ? (Priority: P2)

Un·e athlète regardant le détail de sa participation à une épreuve veut situer
son propre temps dans la distribution de tous les temps de l'épreuve.

**Why this priority**: L'histogramme des temps existe déjà sur `/courses/[id]`
mais ne marque pas la position de l'athlète, et n'est pas repris sur l'écran
de détail de participation — un rapprochement de deux vues existantes plutôt
qu'un nouveau calcul.

**Independent Test**: Ouvrir le détail d'une participation et vérifier que
l'histogramme des temps de l'épreuve y est repris avec un repère visuel sur le
temps de l'athlète concerné.

**Acceptance Scenarios**:

1. **Given** une participation avec un temps final connu, **When** l'athlète
   ouvre le détail de cette participation, **Then** l'histogramme des temps de
   l'épreuve s'affiche avec un repère distinct sur sa propre barre/position.
2. **Given** un temps de course manifestement incohérent (déjà signalé par
   ailleurs), **When** l'histogramme est affiché, **Then** le repère de
   l'athlète ne casse pas l'échelle du graphique pour les autres valeurs.

---

### User Story 3 - Où je me situe dans ma catégorie ? (Priority: P3)

Un·e athlète veut voir sa place dans sa catégorie (ex. M40) avec un
dénominateur clair (« 12ᵉ sur 47 »), pas un nombre nu.

**Why this priority**: `CategoryBars` montre déjà l'effectif par catégorie ;
`rank_category` est déjà servi par l'API mais affiché en nombre brut sans
contexte — complète la même zone d'écran que l'US précédente.

**Independent Test**: Ouvrir le détail d'une participation et vérifier que le
classement en catégorie est présenté avec sa position visuelle dans
l'effectif total de la catégorie.

**Acceptance Scenarios**:

1. **Given** une participation avec un `rank_category` et un effectif de
   catégorie connus, **When** le détail est affiché, **Then** la position est
   montrée à la fois en texte (« 12ᵉ / 47 ») et par une représentation visuelle
   de la place dans l'effectif.

---

### User Story 4 - Où je perds du temps, et est-ce que ça change ? (Priority: P4)

Un·e athlète veut voir sur quels segments (splits) il perd ou gagne du temps
par rapport aux autres, et si ce point faible se répète d'une course à
l'autre.

**Why this priority**: `ComparisonTable` existe déjà pour une course unique
mais oblige à lire ligne par ligne ; `participation.splits` est chargé sur
chaque ligne du profil athlète et jamais affiché — la donnée est déjà en
mémoire côté client.

**Independent Test**: Ouvrir le détail d'une participation ayant des splits
enregistrés et vérifier qu'une représentation visuelle (pas seulement un
tableau) montre l'écart par segment ; sur la page profil, vérifier qu'une vue
agrégée indique si un segment est récurrent.

**Acceptance Scenarios**:

1. **Given** une participation avec des splits enregistrés, **When** le détail
   est affiché, **Then** une représentation visuelle montre l'écart par
   segment en plus du tableau existant.
2. **Given** un athlète ayant plusieurs participations avec splits, **When**
   il consulte sa page profil, **Then** une vue agrégée signale si un même
   segment est systématiquement son point faible.

---

### User Story 5 - Ai-je accéléré, ou les autres ont-ils ralenti ? (Priority: P5)

Un·e athlète regardant l'évolution de son classement pendant une course veut
savoir si un changement de position vient de son propre rythme ou de celui des
autres.

**Why this priority**: `RankingEvolutionChart` existe déjà mais ne trace que
des positions relatives, jamais des temps cumulés — ajoute une dimension au
graphique existant plutôt que d'en créer un nouveau.

**Independent Test**: Ouvrir le détail d'une participation avec des positions
intermédiaires connues et vérifier qu'une vue complémentaire au graphique de
classement permet de distinguer un ralentissement propre d'un dépassement par
d'autres.

**Acceptance Scenarios**:

1. **Given** une participation avec des temps de passage intermédiaires,
   **When** le détail est affiché, **Then** un graphique de temps cumulés
   (allure) est disponible en complément du graphique de classement existant.

---

### User Story 6 - Comment je me compare à un coéquipier ? (Priority: P6)

Un·e athlète veut comparer son évolution ou sa performance sur une épreuve à
celle d'un autre membre du club.

**Why this priority**: Aucune vue athlète-contre-athlète n'existe ; la donnée
est déjà en mémoire (`listParticipations` en ramène jusqu'à 5000) mais
nécessite une interaction de sélection nouvelle — plus gros effort que les US
précédentes qui ne font qu'exposer des données déjà calculées.

**Independent Test**: Sur la page profil d'un athlète, choisir un second
athlète du club et vérifier qu'une vue comparative affiche les deux
performances sur une même épreuve ou une même période.

**Acceptance Scenarios**:

1. **Given** deux athlètes ayant participé à la même épreuve, **When**
   l'utilisateur sélectionne l'un comme point de comparaison depuis la page de
   l'autre, **Then** un graphique affiche les deux séries côte à côte ou
   superposées.
2. **Given** deux athlètes sans épreuve commune, **When** l'utilisateur tente
   la comparaison, **Then** un message explicite indique l'absence de données
   comparables, sans graphique vide.

---

### User Story 7 - Sur quoi je cours vraiment, et combien par saison ? (Priority: P7)

Un·e athlète veut voir la répartition de ses disciplines/distances pratiquées
et leur évolution par saison, pas seulement la discipline dominante.

**Why this priority**: `formatToken` calcule déjà la distribution complète
dans une `Map` avant de n'en garder que le mode (la valeur la plus fréquente) ;
`data.participations`, déjà chargé en entier sur `/athletes/[id]`, porte
`event_type`/`distance_km`/`event_date` par ligne — la répartition par
discipline et par saison est calculable côté client sans appel API
supplémentaire (`listAthleteSeasonActivity` ne porte pas de discipline et
n'alimente que `/club/athletes` : piste écartée après vérification).

**Independent Test**: Consulter la page profil d'un athlète actif sur
plusieurs saisons et disciplines, et vérifier qu'une vue montre la répartition
complète (pas seulement le mode) et son évolution par saison.

**Acceptance Scenarios**:

1. **Given** un athlète ayant couru plusieurs disciplines sur plusieurs
   saisons, **When** il consulte sa page profil, **Then** une vue affiche la
   répartition par discipline et par saison, au-delà de la seule discipline
   dominante actuellement montrée.

---

### User Story 8 - Le club progresse-t-il ? (Priority: P8)

Un membre du bureau ou un·e athlète veut voir si la performance collective du
club évolue, pas seulement le volume d'activité.

**Why this priority**: `MonthlyTrend` compte déjà du volume mais jamais de la
performance ; `rank_counters` et `by_month` sont déjà servis par l'API mais le
tableau de bord n'en fait qu'un agrégat toutes saisons confondues malgré un
sélecteur de saison déjà présent.

**Independent Test**: Sur `/dashboard` ou `/club`, changer la sélection de
saison et vérifier qu'un graphique de performance (pas seulement de volume)
se met à jour en conséquence.

**Acceptance Scenarios**:

1. **Given** des données de classement disponibles sur plusieurs saisons,
   **When** l'utilisateur change la saison sélectionnée, **Then** un
   graphique de performance collective (ex. évolution des `rank_counters`) se
   met à jour pour la saison choisie.

---

### User Story 9 - À quoi ressemble le club ? (Priority: P9)

Un membre veut voir la composition du club (genre, catégories d'âge), un fait
déjà calculé mais jamais montré.

**Why this priority**: `buildRoster` agrège déjà `gender` et `category` mais
ne les affiche jamais ; c'est le fait le plus structurant du jeu de données
selon l'audit (164 athlètes sur 350 concentrés sur une seule course) et n'est
énoncé nulle part dans l'app actuellement.

**Independent Test**: Consulter `/club` et vérifier qu'une vue affiche la
répartition par genre et par catégorie d'âge de l'effectif du club.

**Acceptance Scenarios**:

1. **Given** un roster du club avec des athlètes de genres et catégories
   variés, **When** l'utilisateur consulte `/club`, **Then** une
   représentation visuelle montre la répartition par genre et par catégorie
   d'âge.

---

### User Story 10 - Où le club performe-t-il ? (Priority: P10)

Un membre veut savoir sur quelles disciplines le club obtient ses meilleurs
résultats, pas seulement où il est le plus actif.

**Why this priority**: `BarList` donne déjà les épreuves par discipline mais
jamais croisées avec la performance ; `podiumsByScope` est déjà calculé par
athlète mais jamais agrégé au niveau du club.

**Independent Test**: Consulter `/club` ou `/dashboard` et vérifier qu'une vue
croise discipline et performance (ex. taux de podium par discipline), distincte
du simple décompte d'épreuves par discipline déjà existant.

**Acceptance Scenarios**:

1. **Given** des podiums enregistrés sur plusieurs disciplines, **When**
   l'utilisateur consulte la vue club, **Then** un graphique montre la
   performance du club par discipline (ex. podiums agrégés), pas seulement le
   volume d'épreuves.

---

### User Story 11 - Quelles saisons sont couvertes, où sont les trous ? (Priority: P11)

Un utilisateur cherchant des résultats veut une vue d'ensemble des épreuves
couvertes par mois/année avant de plonger dans la liste de 273 épreuves.

**Why this priority**: `MonthlyTrend` existe déjà dans `components/charts/`
mais n'est utilisé nulle part sur `/resultats` — réutilisation d'un composant
existant sur un nouvel écran.

**Independent Test**: Consulter `/resultats` et vérifier qu'une vue de
couverture temporelle (mois/année) précède ou complète la liste d'épreuves, et
signale visuellement les périodes sans épreuve enregistrée.

**Acceptance Scenarios**:

1. **Given** des épreuves réparties de façon inégale sur plusieurs années,
   **When** l'utilisateur consulte `/resultats`, **Then** une vue par mois/année
   montre la densité d'épreuves et les périodes vides.

---

### User Story 12 - Quelles épreuves près de chez moi, et lesquelles à venir ? (Priority: P12)

Un utilisateur consultant la carte veut trouver les épreuves à venir et celles
proches de lui, pas seulement où le club est allé par le passé.

**Why this priority**: La carte actuelle dimensionne les cercles au nombre de
participants passés, sans filtre temporel ni distance — répond à « où
pourrais-je aller » plutôt qu'à « où le club est allé », un changement
d'intention qui touche filtre et légende plus qu'un nouveau graphique.

**Independent Test**: Sur `/carte`, vérifier qu'un filtre permet de ne montrer
que les épreuves à venir, et que la distance à une position de référence est
visible ou triable.

**Acceptance Scenarios**:

1. **Given** des épreuves passées et futures dans les données, **When**
   l'utilisateur active le filtre « épreuves à venir », **Then** seules les
   épreuves dont la date est future sont affichées sur la carte.
2. **Given** une position de référence disponible, **When** l'utilisateur
   consulte la carte, **Then** les épreuves peuvent être triées ou filtrées
   par distance à cette position.

---

### User Story 13 - La file de validation tient-elle le rythme ? (Priority: P13)

Un·e bénévole ou administrateur·rice veut savoir si l'arriéré de validation
s'accumule dans le temps et quel est le délai moyen de traitement, pas
seulement le nombre en attente à l'instant présent.

**Why this priority**: `ValidationQueue` ne donne aujourd'hui que deux
cardinalités instantanées ; c'est un écran opérationnel à public restreint,
donc la priorité la plus basse des 13 malgré son utilité pour le pilotage
bénévole.

**Independent Test**: Consulter `/benevoles` et vérifier qu'un graphique
montre l'évolution de l'arriéré dans le temps et un délai moyen de traitement,
en plus des cardinalités instantanées déjà affichées.

**Acceptance Scenarios**:

1. **Given** un historique de validations avec des dates de création et de
   traitement, **When** un·e bénévole consulte `/benevoles`, **Then** un
   graphique montre l'évolution de l'arriéré dans le temps et un délai moyen
   de traitement est affiché en chiffre.

---

### Edge Cases

- Un athlète, une épreuve ou une catégorie sans historique suffisant (une
  seule participation, un seul athlète dans la catégorie) : chaque graphique
  affiche un état vide explicite, jamais un graphique cassé, une division par
  zéro ou un graphique techniquement vide sans explication.
- Des temps ou splits déjà signalés comme incohérents ailleurs (cf. `RES-10`,
  hors périmètre de cette feature) ne doivent pas déformer l'échelle des
  graphiques qui les incluent.
- Toutes les vues restent utilisables sans JavaScript côté rendu initial
  (rendu serveur), conformément à l'existant sur les graphiques SVG actuels.
- Sur un écran de largeur téléphone, chaque graphique ajouté reste lisible
  (texte non compressé sous le seuil déjà fixé par RESP-2/#480) : responsive
  hérité, pas re-testé à chaque US.
- Un athlète comparé (US6) qui retire ou masque ses données (si un tel
  mécanisme existe) : la comparaison ne doit pas exposer plus que ce que
  chaque page individuelle expose déjà séparément.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT afficher, sur la page profil d'un athlète, une
  série temporelle de son ratio de performance à travers ses participations
  (US1).
- **FR-002**: Le système DOIT afficher, sur le détail d'une participation, la
  position du temps de l'athlète dans la distribution des temps de l'épreuve
  (US2).
- **FR-003**: Le système DOIT afficher, sur le détail d'une participation, la
  position en catégorie avec son dénominateur (effectif de la catégorie),
  visuellement et en texte (US3).
- **FR-004**: Le système DOIT afficher, sur le détail d'une participation, une
  représentation visuelle des écarts de temps par segment (US4).
- **FR-005**: Le système DOIT afficher, sur la page profil, si un même segment
  est un point faible récurrent à travers les participations de l'athlète
  (US4).
- **FR-006**: Le système DOIT afficher, sur le détail d'une participation, un
  graphique de temps cumulés (allure) en complément du graphique d'évolution
  du classement existant (US5).
- **FR-007**: Le système DOIT permettre à un utilisateur de sélectionner un
  second athlète du club et d'afficher une vue comparative des deux
  performances (US6).
- **FR-008**: Le système DOIT afficher, sur la page profil, la répartition
  complète des disciplines/distances pratiquées et son évolution par saison
  (US7).
- **FR-009**: Le système DOIT afficher, sur le tableau de bord ou la vue club,
  un graphique de performance collective qui répond au filtre de saison déjà
  existant (US8).
- **FR-010**: Le système DOIT afficher, sur `/club`, la répartition du club
  par genre et par catégorie d'âge (US9).
- **FR-011**: Le système DOIT afficher, sur `/club` ou `/dashboard`, la
  performance du club par discipline (au-delà du simple volume d'épreuves)
  (US10).
- **FR-012**: Le système DOIT afficher, sur `/resultats`, une vue de la
  couverture temporelle (mois/année) des épreuves, y compris les périodes sans
  épreuve (US11).
- **FR-013**: Le système DOIT permettre de filtrer la carte pour n'afficher
  que les épreuves à venir (US12).
- **FR-014**: Le système DOIT permettre de trier ou filtrer les épreuves de la
  carte par distance à une position de référence (US12).
- **FR-015**: Le système DOIT afficher, sur `/benevoles`, l'évolution de
  l'arriéré de validation dans le temps et un délai moyen de traitement
  (US13).
- **FR-016**: Chaque graphique ajouté DOIT utiliser exclusivement
  `d3-scale`/`d3-shape`, déjà en dépendance, sans introduire de nouvelle
  bibliothèque de visualisation.
- **FR-017**: Chaque graphique ajouté DOIT respecter l'identité visuelle
  existante (palette `--tcn-*`, typographie Anton/Barlow, dégradés) sans la
  rouvrir.
- **FR-018**: Chaque graphique ajouté DOIT rester lisible sur un écran de
  largeur téléphone, selon le standard déjà posé par RESP-2/#480.
- **FR-019**: Chaque graphique ajouté DOIT afficher un état vide explicite
  quand les données sous-jacentes sont insuffisantes, plutôt qu'un graphique
  vide ou une erreur.

### Key Entities *(include if feature involves data)*

- **Participation** : une performance d'un athlète à une épreuve donnée —
  temps final, splits, classement scratch et en catégorie ; entité déjà
  existante, ces vues en réutilisent des champs déjà calculés ou déjà chargés.
- **Athlète** : un membre du club avec un historique de participations, un
  genre et une catégorie d'âge ; déjà existant.
- **Épreuve (course)** : une compétition avec date, discipline(s), distance(s)
  et localisation géographique ; déjà existante.
- **File de validation bénévole** : les entrées en attente ou traitées de
  validation de résultats, avec dates de création et de traitement ; déjà
  existante côté modèle, seule la vue agrégée dans le temps est nouvelle.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Les 13 vues des questions du § 16 sont accessibles depuis les
  écrans existants correspondants, sans navigation supplémentaire non prévue
  par l'audit.
- **SC-002**: Un athlète ayant un historique suffisant peut répondre, sans
  quitter sa propre page profil, à « est-ce que je progresse ? » et « sur quoi
  je cours vraiment ? » en moins de 10 secondes de lecture.
- **SC-003**: Aucun des 13 graphiques ajoutés ne produit d'état visuellement
  cassé (graphique vide sans message, texte illisible) sur un jeu de données
  réel du club, y compris les cas à faible historique testés en Edge Cases.
- **SC-004**: Sur un écran de largeur téléphone (375 px), chaque graphique
  ajouté conserve un texte lisible, au même standard que les graphiques
  existants remis en conformité par #480.
- **SC-005**: Aucune nouvelle bibliothèque de visualisation n'apparaît dans
  les dépendances du frontend à l'issue de la PR.

## Assumptions

- Les 13 questions sont livrées dans une seule branche et une seule PR
  parapluie, traitées séquentiellement (US1 → US13), par décision explicite de
  l'utilisateur — dérogation au découpage par question suggéré dans le corps
  de l'issue #466 ("chaque question retenue se découpe, avec sa spec et son
  TDD" y est repris ici comme découpage en user stories d'une même spec, pas
  en issues séparées).
- La comparaison athlète-contre-athlète (US6) ne nécessite pas de mécanisme de
  confidentialité nouveau : toute donnée déjà visible individuellement sur les
  pages profil publiques reste au même niveau de visibilité une fois combinée.
- La notion de « position de référence » pour le filtre de distance sur la
  carte (US12) s'appuie sur une localisation déjà disponible dans le modèle
  (ex. commune du club ou de l'athlète), sans nouvelle collecte de données
  utilisateur (pas de géolocalisation navigateur pour cette itération).
- Les contrôles de cohérence des temps/splits (`RES-10`) et la troncature des
  répartitions de catégories (`RES-7`) sont hors périmètre, déjà traités
  ailleurs selon l'issue #466.
- Le rendu serveur sans JavaScript des graphiques existants est préservé pour
  les nouveaux graphiques, cohérent avec la contrainte posée par #480.
