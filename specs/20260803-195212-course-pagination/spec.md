# Feature Specification: Pagination et recherche du classement d'une épreuve

**Feature Branch**: `fix-course-mettre-en-place-une-pagination-pour-v`

**Created**: 2026-08-03

**Status**: Draft

**Input**: issue #163 — « mettre en place une pagination pour éviter de récupérer l'ensemble des résultats ». Exemple cité : `/courses/25`, plus de 2500 résultats transportés d'un coup. Demande : afficher les 20 premiers, avec pagination et champ de recherche.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Consulter une grosse épreuve sans en télécharger tout le classement (Priority: P1)

Un visiteur ouvre la page d'une épreuve à 2500 participants. La page s'affiche
avec ses statistiques d'ensemble (répartition genre, catégories, top clubs,
histogramme des temps, décompte partants / finishers / abandons, nombre
d'athlètes du club) et les 20 premiers du classement. Il n'a reçu qu'une
synthèse et vingt lignes, pas le classement entier.

**Why this priority**: c'est la demande de l'issue et la seule qui change la
charge transportée. Sans elle, les deux autres histoires n'ont pas de raison
d'être.

**Independent Test**: ouvrir `/courses/25`, comparer le contenu affiché
au-dessus du tableau avec la version actuelle (identique) et vérifier que la
réponse reçue par le navigateur ne contient que la synthèse et 20
participations.

**Acceptance Scenarios**:

1. **Given** une épreuve de 2500 participations, **When** un visiteur ouvre sa
   page, **Then** les six blocs de statistiques affichent les mêmes valeurs
   qu'avant la feature, et le tableau affiche 20 lignes.
2. **Given** cette même épreuve, **When** on observe ce que le navigateur
   reçoit, **Then** la charge ne contient plus l'intégralité des
   participations.
3. **Given** une épreuve de 12 participations, **When** un visiteur ouvre sa
   page, **Then** les 12 lignes s'affichent et aucun contrôle de pagination
   n'est présenté.

---

### User Story 2 — Parcourir le classement page par page (Priority: P1)

Le visiteur navigue dans le classement au moyen de contrôles « Précédent /
page N sur M / Suivant ». La page consultée figure dans l'adresse, si bien que
le lien est partageable et que le bouton « retour » du navigateur fonctionne.

**Why this priority**: sans navigation, l'histoire 1 rend le classement
inaccessible au-delà du rang 20 — une régression, pas une amélioration.

**Independent Test**: ouvrir la page 3 d'une épreuve directement par son
adresse et vérifier que les lignes affichées sont bien les rangs 41 à 60 de
l'ordre d'affichage.

**Acceptance Scenarios**:

1. **Given** une épreuve de 2500 participations, **When** le visiteur atteint
   la page 3, **Then** l'adresse porte le numéro de page et les lignes
   affichées poursuivent exactement celles de la page 2, sans doublon ni trou.
2. **Given** la page 1, **When** le visiteur l'affiche, **Then** le contrôle
   « Précédent » est inactif ; **Given** la dernière page, **Then** c'est
   « Suivant » qui l'est.
3. **Given** un numéro de page au-delà du dernier, **When** le visiteur ouvre
   cette adresse, **Then** la page s'affiche avec un classement vide et un
   message, jamais une erreur technique.
4. **Given** l'ordre d'affichage actuel (finishers classés d'abord, puis les
   non classés, puis les abandons), **When** on parcourt toutes les pages
   d'affilée, **Then** la suite obtenue est identique, ligne pour ligne, au
   classement affiché avant la feature.

---

### User Story 3 — Retrouver un athlète par son nom (Priority: P2)

Le visiteur saisit un nom dans un champ de recherche au-dessus du classement.
Le tableau ne montre plus que les participations dont le nom ou le prénom
correspond, quelle que soit la page où elles se trouvaient. Les statistiques
d'ensemble, elles, ne bougent pas.

**Why this priority**: sur 2500 lignes, la recherche du navigateur (Ctrl+F) ne
trouve plus que ce qui est chargé. Elle devient indispensable dès que la
pagination existe — mais la page reste utilisable sans elle.

**Independent Test**: chercher un nom connu d'une épreuve à plus de 100
participants et vérifier qu'il ressort même s'il figurait en page 40.

**Acceptance Scenarios**:

1. **Given** une épreuve où figure « Le Guen », **When** le visiteur saisit
   « guen », **Then** la ligne ressort, quelle que soit la page où elle se
   trouvait.
2. **Given** une épreuve où figure « LEMÉE », **When** le visiteur saisit
   « lemee » sans accent, **Then** la ligne ressort.
3. **Given** une recherche en cours, **When** on regarde les six blocs de
   statistiques, **Then** ils affichent toujours les valeurs de l'épreuve
   entière, inchangées.
4. **Given** une recherche sans résultat, **When** elle s'applique, **Then** le
   tableau est vide avec un message, et les statistiques restent affichées.
5. **Given** le visiteur en page 7, **When** il lance une recherche ou bascule
   le filtre club, **Then** l'affichage revient à la première page.

---

### Edge Cases

- **Épreuve sans aucune participation** : la synthèse est vide, aucun
  pourcentage n'est calculé sur un dénominateur nul, aucun histogramme n'est
  affiché.
- **Épreuve dont personne n'a de temps publié** : l'histogramme est absent, le
  classement s'affiche quand même.
- **Recherche portant sur les lignes non appariées à un coureur** : certaines
  sources publient des libellés du type `?DOSSARD #43637`, importés tels quels
  en nom (cf. runnerbreizh). Ils restent cherchables comme les autres.
- **Filtre club actif sur une épreuve dont la source ne publie aucun club** :
  plusieurs fournisseurs (runnerbreizh, chronoweb, Competitor) laissent le club
  vide, donc le filtre y rend zéro ligne. Comportement déjà en vigueur, non
  modifié.
- **Numéro de page au-delà du dernier** : tranche vide et total exact, jamais
  d'erreur technique.
- **Taille de tranche invalide** (négative, nulle, non numérique et différente
  de `all`) : erreur d'usage explicite, jamais une interprétation silencieuse.
- **Taille de tranche `all` sur une épreuve à 2500 lignes** : le classement
  entier est rendu en une page. C'est l'échappatoire d'intégration, pas le
  chemin du site.
- **Recherche ne contenant que des espaces** : traitée comme une recherche
  vide.

## Requirements *(mandatory)*

### Functional Requirements

**Classement paginé**

- **FR-001**: Le classement d'une épreuve DOIT être servi par tranches, avec
  une taille de tranche de 20 par défaut.
- **FR-002**: La taille de tranche demandée DOIT être plafonnée, à la manière
  des autres points de lecture du projet.
- **FR-003**: La réponse DOIT indiquer le nombre total de participations
  correspondant à la sélection courante, afin que le nombre de pages soit
  calculable sans les parcourir.
- **FR-004**: Un numéro de page au-delà du dernier DOIT rendre une tranche vide
  et un total exact, jamais une erreur.
- **FR-005**: Le classement DOIT être paginé **par défaut**, c'est-à-dire en
  l'absence de tout paramètre. C'est un changement de comportement de la route
  existante, assumé : laisser le défaut sur « tout rendre » n'aurait résolu
  l'issue que pour l'appelant qui pense à demander autre chose.
- **FR-006**: Un appelant DOIT pouvoir redemander le classement entier en une
  fois, en donnant explicitement la valeur `all` à la taille de tranche. La
  réponse est alors une page unique, et le total reste exact.
- **FR-007**: Une taille de tranche invalide (négative, nulle, non numérique et
  différente de `all`) DOIT être rejetée comme une erreur d'usage, jamais
  interprétée silencieusement.

**Ordre d'affichage**

- **FR-008**: L'ordre du classement DOIT avoir une seule définition, appliquée
  à la sélection avant son découpage en pages — faute de quoi la page N servie
  ne serait pas la page N affichée.
- **FR-009**: Cet ordre DOIT reproduire exactement l'ordre affiché aujourd'hui :
  finishers d'abord par rang croissant, puis les finishers sans rang, puis les
  non-finishers groupés DNF, puis DSQ, puis DNS ; au sein d'un groupe, par temps
  croissant, les temps absents en fin, puis par nom.
- **FR-010**: Un temps vide ou égal à `00:00:00` DOIT être traité comme un temps
  absent, sémantique déjà en vigueur.
- **FR-011**: L'ordre DOIT être total et déterministe : deux consultations
  successives de la même page, sans import intermédiaire, rendent les mêmes
  lignes dans le même ordre.

**Recherche**

- **FR-012**: Un visiteur DOIT pouvoir restreindre le classement à un nom
  d'athlète, la correspondance portant sur le nom ou le prénom, en sous-chaîne.
- **FR-013**: Cette recherche DOIT être insensible à la casse **et aux
  accents**, en développement comme en production — les deux moteurs de base ne
  se comportent pas de la même façon sur ce point.
- **FR-014**: La recherche NE DOIT PAS porter sur le club, le dossard ni la
  catégorie. Ce périmètre est arbitré, pas oublié.
- **FR-015**: Une recherche vide ou composée d'espaces DOIT équivaloir à
  l'absence de recherche.
- **FR-016**: La recherche et le filtre club DOIVENT se composer : les deux
  actifs ensemble restreignent la sélection aux lignes qui satisfont les deux.

**Synthèse d'épreuve**

- **FR-017**: Une synthèse d'épreuve DOIT être exposée, portant : le décompte
  ventilé (total, finishers, non-finishers, indéterminés), le nombre d'athlètes
  du club, la répartition par genre, la répartition par catégorie, les
  principaux clubs représentés avec leur appartenance au club, les tranches de
  l'histogramme des temps, et la liste des segments de temps intermédiaires
  renseignés sur l'épreuve.
- **FR-018**: La synthèse DOIT toujours porter sur l'épreuve **entière**,
  indépendamment de la recherche et du filtre club en cours.
- **FR-019**: La synthèse DOIT rendre les mêmes valeurs que celles calculées
  aujourd'hui dans le navigateur, y compris les mêmes limites d'affichage
  (8 catégories, 9 clubs) et le même découpage de l'histogramme.
- **FR-020**: L'appartenance au club DOIT venir de la définition unique du
  projet et n'être réimplémentée nulle part.
- **FR-021**: La synthèse d'une épreuve sans participation DOIT être servie sans
  erreur, avec des valeurs vides.
- **FR-022**: Le calcul de la synthèse NE DOIT PAS charger plus de données que
  les champs dont il a besoin.

**Interface**

- **FR-023**: La page d'épreuve DOIT afficher les mêmes six blocs de
  statistiques qu'aujourd'hui, alimentés par la synthèse.
- **FR-024**: La page consultée, la recherche en cours et le filtre club DOIVENT
  figurer dans l'adresse, pour qu'un lien soit partageable et que l'historique
  du navigateur fonctionne.
- **FR-025**: Tout changement de recherche ou de filtre club DOIT ramener à la
  première page.
- **FR-026**: Les contrôles de pagination DOIVENT être navigables au clavier et
  ouvrables dans un nouvel onglet.
- **FR-027**: Aucun contrôle de pagination NE DOIT être affiché quand la
  sélection tient en une page.
- **FR-028**: Les colonnes de temps intermédiaires DOIVENT venir de la synthèse
  et rester identiques d'une page à l'autre.
- **FR-029**: Le filtre « Tous les coureurs / Triathlon Club Nantais » existant
  DOIT être conservé, en portée d'épreuve entière et non de page courante.
- **FR-030**: Le pied de tableau DOIT continuer d'annoncer le décompte ventilé
  de l'épreuve entière, distinct du nombre de lignes affichées.

### Key Entities

- **Participation** : la ligne de classement d'un athlète sur une épreuve —
  rang, temps, statut, catégorie, club, temps intermédiaires. Entité existante,
  non modifiée.
- **Page de classement** : une tranche ordonnée de participations, accompagnée
  du total de la sélection et de la position de la tranche.
- **Synthèse d'épreuve** : les agrégats d'une épreuve entière, indépendants de
  toute sélection — décomptes, répartitions, histogramme, segments présents.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur l'épreuve citée par l'issue, le nombre de participations
  transportées au navigateur au premier affichage passe de plus de 2500 à 20.
- **SC-002**: Le contenu affiché au-dessus du tableau est identique, valeur
  pour valeur, à celui d'avant la feature.
- **SC-003**: La concaténation de toutes les pages du classement, dans l'ordre,
  est identique ligne pour ligne au classement affiché avant la feature.
- **SC-004**: Un visiteur atteint la ligne d'un athlète donné en au plus deux
  actions (saisir son nom, lire le résultat), sans dérouler le classement.
- **SC-005**: Une épreuve à zéro participation, une épreuve à moins de 20
  participations et un numéro de page hors bornes s'affichent tous sans erreur.
- **SC-006**: La suite de tests hors réseau passe intégralement.
- **SC-007**: Une demande explicite du classement entier rend le même nombre de
  participations qu'avant la feature, dans le même ordre — l'échappatoire est
  vérifiable, pas déclarative.

## Assumptions

- Le seul consommateur connu du point de lecture d'une épreuve est le site
  lui-même ; aucune intégration tierce n'est recensée. C'est ce qui rend le
  changement de défaut de FR-005 tenable sans ouvrir une `/api/v2` : le
  Principe IV n'est pas contourné mais soldé par l'échappatoire explicite de
  FR-006, qui laisse le comportement d'aujourd'hui accessible à qui le
  demande.
- Les temps sont stockés sous forme de chaînes `HH:MM:SS` à deux chiffres
  d'heures, ce que garantit la normalisation à l'import ; leur comparaison
  alphabétique vaut donc comparaison chronologique en deçà de 100 heures.
- **L'« exactement » de FR-009 souffre une exception, sur le seul départage
  final.** L'ordre passe d'une comparaison de chaînes du navigateur à la
  collation de la base, et les deux ne placent pas les caractères accentués au
  même endroit. L'écart n'est observable qu'entre deux lignes partageant le
  groupe **et** le rang (ou le temps) — soit des ex æquo, dont l'ordre relatif
  n'a de toute façon aucun sens métier. On l'assume plutôt que d'ajouter une
  couche de collation pour départager ce que la source elle-même ne départage
  pas.
- Le découpage de l'histogramme (tranches de 5 minutes, 60 tranches au plus) et
  les limites d'affichage (8 catégories, 9 clubs) sont repris tels quels : la
  feature déplace ces calculs, elle ne les rejuge pas.
- **Une exception à la règle précédente, assumée** : l'histogramme **exclut**
  désormais les temps à `00:00:00`, là où le calcul du navigateur les comptait
  comme zéro seconde et créait une barre parasite à l'origine. C'est FR-010 qui
  l'impose — un `00:00:00` vaut temps absent —, et l'ancien comportement était
  un défaut, pas une référence à préserver. Un écart à SC-002 donc, mais dans le
  bon sens, et visible seulement sur les épreuves qui publient de telles valeurs.
- La sémantique du filtre club reste celle en vigueur : une participation dont
  la source ne publie pas de club n'en fait pas partie.
- Aucune donnée n'est ajoutée ni modifiée en base : la feature ne porte que sur
  la lecture.

## Out of Scope

- Cache serveur de la synthèse d'épreuve. À envisager sur mesure, pas avant.
- Tri du classement par colonne à la demande du visiteur.
- Recherche par club, par dossard ou par catégorie.
- Nouvel index en base : aucun avant d'avoir mesuré.
- Pagination des autres pages du site (page athlète, page club), non visées par
  l'issue.
