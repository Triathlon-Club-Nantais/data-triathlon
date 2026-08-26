# Feature Specification: Portée des compteurs configurable depuis le panel admin

**Feature Branch**: `tjarrier/chore-admin-rendre-configurables-en-bdd-les-disc`

**Created**: 2026-08-26

**Status**: Draft

**Issue**: [#95](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/95) — dépend du panel admin (#81), principes posés en #76, remontée en review de #94.

**Input**: Rendre configurables en base les deux listes qui définissent la portée des compteurs, aujourd'hui en dur dans le code : les disciplines non fédérales et les libellés de club du TCN. Périmètre complet : stockage en base, chargement en cache invalidé à chaque modification, alignement du filtre affiché et du filtre calculé, endpoints d'administration et écran d'édition dans le panel admin.

## Contexte

Deux listes décident, aujourd'hui, de ce que l'application compte :

- **Les disciplines hors fédération triathlon** (trail, course à pied, cyclisme…) — celles que le toggle « Inclure les autres disciplines » retire des compteurs.
- **Les libellés du club** — les orthographes sous lesquelles les chronométreurs écrivent « Triathlon Club Nantais », et qui font qu'un résultat est compté comme un résultat du club.

Les deux vivent en dur dans le code. Ajouter une variante d'orthographe repérée sur une nouvelle épreuve, ou sortir une discipline des compteurs, demande aujourd'hui un développeur, un commit et un déploiement — alors que ce sont des décisions d'exploitation qu'un administrateur du club sait prendre seul.

Ce n'est pas une correction : l'état actuel est juste, versionné et testé. C'est un confort d'exploitation qui retire un développeur du chemin critique.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Déclarer une nouvelle orthographe du club (Priority: P1)

Un administrateur constate, après l'import d'une épreuve, que des membres du club n'apparaissent pas dans les compteurs du club : le chronométreur a écrit « TRIATHLON CLUB NANTAIS 44 », une orthographe encore inconnue. Il ouvre l'écran de configuration du panel admin, ajoute ce libellé à la liste des libellés du club, et le vérifie immédiatement : les résultats concernés sont désormais comptés comme résultats du club, dans les compteurs comme sur les badges affichés.

**Why this priority**: C'est le geste le plus fréquent et le seul qui corrige une donnée visiblement fausse — un membre du club absent des classements du club. Livré seul, il retire déjà le développeur du chemin critique.

**Independent Test**: Ajouter un libellé depuis l'écran d'administration, puis recharger une page de résultats contenant ce libellé et constater que la ligne porte le badge du club et entre dans les compteurs du club.

**Acceptance Scenarios**:

1. **Given** un résultat portant un libellé de club absent de la configuration, **When** l'administrateur ajoute ce libellé à la liste, **Then** le résultat est compté comme résultat du club sans redéploiement et sans redémarrage.
2. **Given** un libellé présent dans la configuration, **When** l'administrateur le retire, **Then** les résultats qui le portent sortent des compteurs du club dès la requête suivante.
3. **Given** un libellé saisi avec des majuscules, des espaces surnuméraires ou des espaces insécables, **When** l'administrateur l'enregistre, **Then** il est retenu sous une forme comparable et vaut pour toutes les variantes de casse et d'espacement du même libellé.
4. **Given** un libellé déjà présent dans la liste (à la casse ou aux espaces près), **When** l'administrateur tente de l'ajouter à nouveau, **Then** l'application le refuse avec un message explicite plutôt que de créer un doublon.
5. **Given** un libellé qui contient un libellé du club sans lui être égal (« TRIATHLON CLUB NANTAIS SUD »), **When** il apparaît dans un résultat, **Then** il n'est **pas** compté comme résultat du club.

---

### User Story 2 - Sortir ou rentrer une discipline des compteurs (Priority: P2)

Un administrateur décide que le duathlon indoor n'a pas sa place dans les compteurs de triathlon, ou au contraire qu'une discipline aujourd'hui exclue doit y revenir. Il ouvre le même écran, agit sur la liste des disciplines exclues, et le toggle « Inclure les autres disciplines » reflète immédiatement sa décision.

**Why this priority**: Moins fréquent que le libellé de club, et sans conséquence sur l'exactitude des données affichées — seulement sur le périmètre des compteurs. Utile, mais pas urgent.

**Independent Test**: Exclure une discipline depuis l'écran d'administration, puis constater sur une page de compteurs que les résultats de cette discipline disparaissent quand le toggle « Inclure les autres disciplines » est fermé, et réapparaissent quand il est ouvert.

**Acceptance Scenarios**:

1. **Given** une discipline absente de la liste d'exclusion, **When** un résultat de cette discipline existe, **Then** il entre dans les compteurs même toggle fermé — l'inconnu reste fédéral par défaut.
2. **Given** une discipline ajoutée à la liste d'exclusion, **When** le toggle « Inclure les autres disciplines » est fermé, **Then** les résultats de cette discipline sortent des compteurs dès la requête suivante.
3. **Given** une discipline retirée de la liste d'exclusion, **When** le toggle est fermé, **Then** ses résultats rentrent dans les compteurs.
4. **Given** l'administrateur saisit une discipline qui ne correspond à aucune discipline connue de l'application, **When** il l'enregistre, **Then** l'application l'avertit que cette entrée ne correspond à aucune discipline existante.

---

### User Story 3 - Comprendre et auditer la configuration (Priority: P3)

Un administrateur ouvre l'écran de configuration pour comprendre pourquoi un résultat n'est pas compté. Il voit les deux listes en clair, avec pour chaque entrée qui l'a ajoutée et quand, et l'écran lui explique en une phrase la règle de chacune : liste d'exclusion pour les disciplines, liste des libellés reconnus pour le club. Chaque modification apparaît ensuite dans le journal d'administration.

**Why this priority**: Confort de compréhension et traçabilité. La feature fonctionne sans, mais deux listes qui décident silencieusement de ce qui est compté méritent d'être lisibles et traçables.

**Independent Test**: Ouvrir l'écran, lire les deux listes et leur explication, modifier une entrée, puis retrouver la modification dans le journal d'administration.

**Acceptance Scenarios**:

1. **Given** un administrateur sur l'écran de configuration, **When** il consulte une liste, **Then** il lit chaque entrée, son auteur et sa date d'ajout.
2. **Given** une modification de l'une des deux listes, **When** l'administrateur consulte le journal d'administration, **Then** il y trouve qui a modifié quoi et quand.
3. **Given** un utilisateur sans le pouvoir de gérer cette configuration, **When** il tente d'ouvrir l'écran ou d'appeler l'API correspondante, **Then** l'accès est refusé.

---

### Edge Cases

- **Configuration vide au démarrage** : une base neuve, ou une liste vidée par erreur, ne doit pas faire basculer l'application dans un état absurde. Liste de disciplines exclues vide = tout est fédéral (comportement dégradé mais cohérent) ; liste de libellés de club vide = plus aucun résultat n'est du club, ce qui vide tous les compteurs du club. Ce second cas est le dangereux : l'application doit refuser de vider entièrement la liste des libellés du club.
- **Retrait du libellé canonique** : retirer « triathlon club nantais » alors que le nom affiché du club reste celui-là est incohérent — plus rien portant le nom du club ne serait compté. Le retrait reste possible (il n'est pas nécessairement faux), mais la confirmation le dit explicitement.
- **Libellé vide ou fait uniquement de blancs** : refusé à la saisie.
- **Modification pendant un import ou un batch en cours** : l'import en cours peut avoir déjà classé des lignes avec l'ancienne configuration. Les compteurs étant recalculés à la lecture, le résultat final reste cohérent, mais les décisions prises pendant l'import (les scrapers qui ne détaillent que les lignes du club) peuvent rater des lignes de l'épreuve en cours de traitement.
- **Deux administrateurs modifient la même liste en même temps** : la dernière écriture l'emporte, sans perte silencieuse de l'entrée ajoutée par l'autre.
- **Discipline saisie sous une forme non canonique** : normalisée (minuscules, bords rognés) puis **acceptée**, jamais refusée — exclure une discipline pas encore importée est un geste légitime. C'est l'avertissement de FR-011 qui porte l'information, pas un refus.

## Requirements *(mandatory)*

### Functional Requirements

**Stockage et lecture**

- **FR-001**: L'application MUST conserver en base la liste des disciplines exclues des compteurs et la liste des libellés reconnus comme libellés du club.
- **FR-002**: L'application MUST livrer ces deux listes préremplies avec exactement les valeurs aujourd'hui en dur, de sorte qu'une base existante ou neuve se comporte à l'identique avant toute modification.
- **FR-003**: La règle d'appartenance au club MUST rester un match à **l'égalité** sur une forme normalisée (casse, espaces de bord, espaces internes, blancs non-ASCII aplatis), jamais un match en sous-chaîne.
- **FR-004**: La règle de discipline MUST rester une **liste d'exclusion** : une discipline absente de la liste est fédérale, y compris une discipline apparue après la configuration.
- **FR-005**: Le verdict rendu sur un résultat individuel (le badge affiché) et le verdict rendu sur un ensemble de résultats (les compteurs et les listes filtrées) MUST toujours coïncider, pour toute configuration.
- **FR-006**: Les deux listes MUST être lues sans coût d'accès à la base par résultat traité — le classement d'une épreuve de plusieurs milliers de lignes ne doit pas dégrader.

**Modification**

- **FR-007**: Un administrateur habilité MUST pouvoir consulter, ajouter et retirer une entrée dans chacune des deux listes.
- **FR-008**: Toute modification MUST prendre effet immédiatement, sans redéploiement ni redémarrage de l'application.
- **FR-009**: L'application MUST refuser un libellé de club vide, fait uniquement de blancs, ou déjà présent une fois normalisé.
- **FR-010**: L'application MUST refuser de laisser la liste des libellés du club entièrement vide.
- **FR-011**: L'application MUST avertir quand une discipline saisie ne correspond à aucune discipline connue de l'application, sans pour autant la refuser d'office.
- **FR-012**: L'accès en consultation et en modification MUST être réservé aux utilisateurs détenant le pouvoir dédié ; un utilisateur sans ce pouvoir se voit refuser l'écran comme l'API.
- **FR-013**: Chaque modification MUST être tracée dans le journal d'administration, avec l'auteur, la liste concernée, l'entrée et le sens du geste.

**Écran d'administration**

- **FR-014**: Le panel admin MUST offrir un écran présentant les deux listes, chacune éditable entrée par entrée.
- **FR-015**: L'écran MUST expliquer en une phrase la règle de chaque liste — exclusion pour les disciplines, libellés reconnus pour le club — et l'effet d'une modification sur les compteurs.
- **FR-016**: L'écran MUST afficher, pour chaque entrée, qui l'a ajoutée et quand.
- **FR-017**: Le retrait d'une entrée MUST demander une confirmation, en rappelant l'effet sur les compteurs. La confirmation MUST signaler spécifiquement le retrait du libellé correspondant au nom d'affichage du club.

**Non-régression**

- **FR-018**: Le contrat qui vérifie l'accord entre le verdict individuel et le verdict d'ensemble MUST être conservé et MUST s'évaluer sur la configuration en vigueur, pas sur des valeurs figées dans le test.
- **FR-019**: Le corpus de libellés réels issu des données de production MUST être conservé comme cas de référence.
- **FR-020**: L'outil de repérage des libellés de club manquants MUST continuer de fonctionner et MUST se prononcer selon la configuration en vigueur.

### Key Entities

- **Discipline exclue** : une discipline que l'application ne compte pas comme discipline de la fédération triathlon. Porte l'identifiant de la discipline, l'auteur et la date d'ajout.
- **Libellé du club** : une orthographe sous laquelle un chronométreur désigne le club. Porte le libellé sous sa forme comparable, l'auteur et la date d'ajout. La forme saisie n'est **pas** conservée : la retenir obligerait à normaliser à la lecture des deux côtés du miroir SQL, deux occasions de plus de diverger pour un affichage à peine plus fidèle (`data-model.md`, § Forme stockée).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ajouter une orthographe de club ou exclure une discipline se fait en moins de deux minutes, par un administrateur seul, sans intervention d'un développeur et sans déploiement.
- **SC-002**: Une modification est visible sur les compteurs dès le rechargement de page suivant.
- **SC-003**: Avant toute modification, l'application rend exactement les mêmes compteurs, les mêmes badges et les mêmes listes filtrées qu'aujourd'hui — aucun écart sur les données existantes.
- **SC-004**: Le temps d'affichage du classement d'une épreuve de 3 000 résultats ne se dégrade pas de plus de 5 % par rapport à aujourd'hui.
- **SC-005**: Le verdict individuel et le verdict d'ensemble coïncident sur 100 % du corpus de libellés réels, pour la configuration livrée comme pour une configuration modifiée.
- **SC-006**: 100 % des modifications des deux listes sont retrouvables dans le journal d'administration.

## Assumptions

- **Un seul club.** L'application sert le TCN ; la liste des libellés désigne ce club et un seul. Une configuration multi-clubs est hors périmètre.
- **Le nom d'affichage du club reste une constante du code**, des deux côtés (serveur et interface) : c'est un texte statique, pas une règle de comptage. Seule la liste des libellés *reconnus* devient configurable.
- **La normalisation des libellés ne change pas.** Seul l'ensemble des libellés reconnus devient configurable ; la façon de les comparer reste celle d'aujourd'hui. Une évolution de la normalisation est hors périmètre.
- **La nomenclature des disciplines reste dans le code.** La configuration choisit lesquelles sont exclues des compteurs ; elle ne crée pas de nouvelles disciplines.
- **Un nouveau pouvoir dédié** est ajouté à l'inventaire des pouvoirs plutôt que de réutiliser un pouvoir existant : la portée des compteurs n'est ni un geste sur les rôles, ni un geste sur les épreuves.
- **L'application tourne en un seul processus serveur** : une modification prend effet pour toutes les requêtes suivantes sans mécanisme de propagation entre processus.
- **Le panel admin (#81) existe déjà** et accueille cet écran comme il accueille les écrans de configuration existants.
- **Les modifications ne déclenchent aucun recalcul de masse** : les compteurs se calculent à la lecture, une modification suffit donc à les changer sans reprise des données.
