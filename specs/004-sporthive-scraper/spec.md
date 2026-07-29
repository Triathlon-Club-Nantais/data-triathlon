# Feature Specification: Support de MYLAPS Sporthive comme fournisseur de résultats

**Feature Branch**: `feat-scrapers-supporter-results.sporthive.com-my`

**Created**: 2026-07-29

**Status**: Draft

**Input**: Issue [#53](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/53)
(sous-issue de #33, section B « nouveaux moteurs »).

**Source de vérité technique**: `docs/superpowers/specs/2026-07-29-sporthive-sondage.md`
— sondage de l'API réelle effectué le 29/07/2026 (7 événements, 32 courses,
10 360 participations, 1 063 requêtes). Il **prime** sur l'énoncé de l'issue,
dont l'endpoint, la route et le mode de pagination sont tous les trois périmés,
et sur cette spec en cas de divergence factuelle.

## Contexte métier

Les membres du club déposent dans un formulaire l'URL des résultats des épreuves
qu'ils ont couru. **Un** de ces liens pointe `results.sporthive.com` — le
Triathlon Sud Vendée 2024, où le dossard désigné appartient à un
« TRI CLUB NANTAIS », donc à un membre du club au sens de la définition unique
d'appartenance.

Le volume immédiat est donc faible, et l'issue le dit : la valeur est surtout
**prospective**. Sporthive est la plateforme de résultats de MYLAPS, acteur
international du chronométrage : l'épreuve du Sheet est française, mais le même
moteur sert des épreuves britanniques, portugaises et algériennes, toutes
importables par le même travail. Un membre qui court une épreuve chronométrée
MYLAPS n'importe où sera couvert sans développement supplémentaire.

Aujourd'hui ce lien échoue : aucun fournisseur ne le reconnaît, il part au
fallback Playwright qui n'en tire rien — la page publique n'est qu'une coquille
JavaScript de 2 Ko.

## Clarifications

### Session 2026-07-29

- Q: Une URL Sporthive désigne une course précise au sein d'un événement qui en
  compte souvent plusieurs — qu'importe-t-on ? → A: **Tout l'événement**, comme
  ok-time et Chronoplace. Motif : le Sheet ne porte qu'un lien par épreuve, et un
  membre du club inscrit sur un autre format du même événement resterait sinon
  invisible. Sur l'épreuve du Sheet, cela fait 955 participations réparties en
  6 courses au lieu de 366 en une seule.
- Q: Certains événements publient des sous-classements dont tous les
  participants figurent déjà dans une autre course (mesuré : 90 dossards sur 90
  du « Senior Men 9 to count » sont dans le « Senior Men ») — les écarte-t-on ?
  → A: **Non, tout est importé.** La source ne publie aucun critère distinguant
  une course dérivée, et deviner sur son intitulé écarterait un jour une vraie
  course, silencieusement. Les participations en double vivent dans des épreuves
  distinctes, sans collision de dossard.
- Q: Les courses de relais publient une ligne par équipe, dont le nom est un nom
  d'équipe (« LA COUSINADE ») et non celui d'une personne — les importe-t-on ?
  → A: **Oui, marquées comme relais**, le nom d'équipe tenant lieu de nom. Le
  classement reste complet ; la contrepartie assumée est que des fiches
  d'athlète portent un nom d'équipe.
- Q: La source publie deux niveaux de temps intermédiaires (les segments, et des
  points de passage à l'intérieur de chaque segment) — que stocke-t-on ? → A:
  **Les segments seuls**, libellés depuis le champ de discipline normalisé.
  Retenir les deux mêlerait deux granularités dans un même ensemble, sans
  équivalent chez les autres fournisseurs.
- Q: Quelle langue pour le code du nouveau fournisseur, la constitution
  (principe I : anglais technique) et `AGENTS.md` (français) divergeant ? → A:
  **Anglais**, comme la constitution : docstrings et commentaires techniques en
  anglais ; vocabulaire métier, messages d'erreur destinés à l'opérateur et
  textes utilisateur en français.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Importer une épreuve Sporthive depuis un lien collé (Priority: P1)

Un membre du club colle dans le formulaire « Ajouter » l'URL d'une page de
résultats Sporthive — celle d'un dossard, celle d'une course, ou celle de
l'événement. L'application reconnaît le fournisseur et importe **toutes les
courses de l'événement** avec l'intégralité de leurs participants, puis les rend
consultables sur les fiches d'épreuve et d'athlète.

**Why this priority**: C'est le cœur de l'issue et la seule chose qui débloque
le lien du Sheet. Sans elle, rien d'autre n'a de valeur.

**Independent Test**: Coller l'URL du Sheet, constater que les six courses de
l'événement sont créées, que le nombre de participants de chacune égale le
nombre de classés annoncé par la source, et que les temps, rangs et segments
d'un participant vérifié à la main correspondent.

**Acceptance Scenarios**:

1. **Given** l'URL d'un dossard d'un événement Sporthive comptant 6 courses et
   955 classés, **When** l'utilisateur soumet cette URL, **Then** les 6 épreuves
   sont enregistrées et leurs 955 participants importés en une seule opération.
2. **Given** une course dont la source annonce 366 classés, **When** l'import
   s'exécute, **Then** exactement 366 participations sont enregistrées pour
   cette épreuve.
3. **Given** un événement dont le nom est « Triathlon Sud Vendee Dimanche » et
   dont une course s'appelle « Triathlon S », **When** l'import s'exécute,
   **Then** l'épreuve correspondante porte un nom qui distingue cette course des
   autres du même événement, sa date réelle, sa discipline, sa taille et son
   kilométrage.
4. **Given** un participant de triathlon dont la source publie cinq segments,
   **When** l'utilisateur consulte sa participation, **Then** les cinq segments
   sont affichés dans l'ordre de la course, sous des libellés lisibles, y
   compris quand les deux transitions portent le même libellé.
5. **Given** une course d'enfants publiée avec quatre segments seulement (une
   seule transition), **When** l'import s'exécute, **Then** la course à pied
   finale est bien enregistrée comme telle et non comme une transition.
6. **Given** une épreuve déjà importée et un second import lancé avant
   expiration du délai de fraîcheur, **When** l'utilisateur resoumet l'URL,
   **Then** aucune requête n'est adressée à la source et l'épreuve est servie
   depuis la base.

---

### User Story 2 - Voir les membres du club apparaître dans le périmètre club (Priority: P2)

Les participations importées portent le club déclaré par la source, ce qui fait
entrer automatiquement les membres du TCN dans le tableau de bord, la page club
et les statistiques restreintes au club.

**Why this priority**: C'est ce qui transforme l'import en valeur visible pour le
club. Distinct de P1 parce que l'import a déjà de la valeur sans lui (les
résultats sont consultables), mais la reconnaissance du club est ce qui les fait
remonter dans les vues du club.

**Independent Test**: Importer l'épreuve du Sheet, filtrer sur le périmètre club,
et constater que les participations « TRI CLUB NANTAIS » y figurent.

**Acceptance Scenarios**:

1. **Given** une participation dont la source déclare le club « TRI CLUB
   NANTAIS », **When** l'utilisateur consulte les vues restreintes au club,
   **Then** cette participation y figure.
2. **Given** une participation dont la source ne déclare aucun club (56 % des
   lignes mesurées), **When** l'import s'exécute, **Then** la participation est
   enregistrée sans club et n'apparaît pas dans le périmètre club.
3. **Given** un libellé de club voisin mais distinct (« ASPTT NANTES TRI »),
   **When** l'utilisateur consulte les vues restreintes au club, **Then** cette
   participation n'y figure pas.

---

### User Story 3 - Comprendre pourquoi un lien Sporthive n'est pas importable (Priority: P3)

Quand un lien Sporthive ne peut pas être importé, l'opérateur lit une cause
explicite dans le bilan de la commande de masse ou dans le message d'erreur du
formulaire, plutôt qu'un échec muet ou, pire, l'import silencieux d'une épreuve
étrangère.

**Why this priority**: Sans elle l'import fonctionne, mais un lien fautif coûte
une investigation manuelle. Le risque spécifique à ce fournisseur est qu'une
mauvaise lecture d'URL réussisse en important les résultats d'une autre épreuve.

**Independent Test**: Soumettre une URL dont l'identifiant d'événement n'existe
pas, une URL Sporthive sans identifiant d'événement lisible, et constater que
chacune rend un message nommant la cause.

**Acceptance Scenarios**:

1. **Given** une URL Sporthive dont l'identifiant d'événement est inconnu de la
   source, **When** l'import s'exécute, **Then** il échoue avec un message
   indiquant que l'événement est introuvable, et rien n'est enregistré.
2. **Given** une URL Sporthive dont le chemin ne contient aucun identifiant
   d'événement exploitable, **When** l'import s'exécute, **Then** il échoue avec
   un message nommant la forme d'URL attendue.
3. **Given** un lot d'URLs contenant un lien Sporthive fautif, **When**
   l'opérateur lance l'import de masse, **Then** l'URL et sa cause figurent au
   détail des épreuves en erreur du bilan, et les autres épreuves du lot sont
   importées normalement.

---

### Edge Cases

- **Une course dont le numéro figure dans l'URL n'appartient pas à
  l'événement** : l'identifiant de course visible dans l'URL est un numéro
  d'ordre local à l'événement, et il existe des courses portant ce même numéro
  dans d'autres événements. Le système ne doit jamais importer une course qui
  n'appartient pas à l'événement désigné — c'est le risque d'import silencieux
  d'une épreuve étrangère.
- **Le classement est servi par tranches de dix au plus** : la source refuse
  toute tranche plus large et ignore silencieusement les paramètres de
  pagination annoncés par l'issue. Que se passe-t-il si une tranche intermédiaire
  revient vide alors que le classement n'est pas terminé ?
- **Une course annonce un nombre de classés différent du nombre lu** : l'import
  doit-il valider ce total et refuser un classement tronqué plutôt que
  d'enregistrer une épreuve incomplète marquée fiable ?
- **Un participant n'a ni temps réel ni temps officiel** (73 lignes mesurées) :
  quel statut lui est attribué ?
- **Un participant est non-partant, abandonné ou disqualifié** : la source le
  signale par un champ dédié, et publie pour lui un segment fantôme de durée
  nulle qui ne doit produire ni temps ni segment.
- **La source publie deux champs booléens de statut qui sont toujours faux**,
  y compris pour les non-partants : s'y fier raterait la totalité des statuts.
- **Un rang de classement vaut zéro** : la valeur signifie « non classé », pas
  « premier ».
- **Le genre est inconnu sur 41 % des lignes.**
- **Un événement ne publie qu'une seule course** (cas mesuré à 2 685
  participants) : l'import de « tout l'événement » se réduit alors à cette
  course.
- **Deux courses du même événement réutilisent les mêmes dossards** : chaque
  course doit rester une épreuve distincte, sinon les dossards entrent en
  collision.

## Requirements *(mandatory)*

### Functional Requirements

**Reconnaissance et lecture de l'URL**

- **FR-001**: Le système MUST reconnaître comme Sporthive les URLs servies par
  les hôtes publics de la plateforme, sur le seul critère de l'hôte — jamais sur
  la présence d'un jeton dans l'URL entière.
- **FR-002**: Le système MUST accepter les trois profondeurs d'URL publiées par
  la plateforme : événement, course, et dossard ; les trois désignent le même
  événement à importer.
- **FR-003**: Le système MUST rejeter, avec un message nommant la forme
  attendue, toute URL Sporthive dont il ne peut extraire un identifiant
  d'événement.
- **FR-004**: Le système MUST traiter le numéro de course présent dans l'URL
  comme un numéro d'ordre local à l'événement, et MUST NOT l'utiliser tel quel
  comme identifiant de course auprès de la source.

**Périmètre et complétude de l'import**

- **FR-005**: Le système MUST importer toutes les courses de l'événement
  désigné, indépendamment de la course pointée par l'URL.
- **FR-006**: Le système MUST enregistrer chaque course comme une épreuve
  distincte, qualifiée par son intitulé, de sorte que deux courses du même
  événement ne fusionnent pas et que leurs dossards n'entrent pas en collision.
- **FR-007**: Le système MUST parcourir l'intégralité du classement de chaque
  course, en respectant la taille de tranche maximale imposée par la source.
- **FR-008**: Le système MUST vérifier, après lecture, que le nombre de
  participants lus pour une course correspond au nombre de classés annoncé par
  la source, et MUST refuser l'import de cette course plutôt que d'enregistrer un
  classement tronqué.
- **FR-009**: Le système MUST refuser l'import plutôt que de poursuivre
  indéfiniment si le critère d'arrêt de la pagination ne se vérifie pas.

**Données de participation**

- **FR-010**: Le système MUST enregistrer, pour chaque participant, son nom, son
  dossard, sa catégorie, son genre, son club, son temps et ses rangs quand la
  source les publie.
- **FR-011**: Le système MUST retenir le temps réel du participant en priorité,
  et se rabattre sur le temps officiel quand le premier est absent.
- **FR-012**: Le système MUST normaliser les durées vers le format unique du
  projet, en écartant les fractions de seconde publiées par la source.
- **FR-013**: Le système MUST traiter une durée nulle comme une absence de
  temps, et non comme un temps de zéro.
- **FR-014**: Le système MUST déduire le statut sportif du seul champ de statut
  effectivement renseigné par la source, en couvrant les trois valeurs observées
  (abandon, non-partant, disqualification), et MUST NOT se fier aux champs
  booléens de statut, mesurés toujours faux.
- **FR-015**: Le système MUST traiter un rang nul comme une absence de rang.
- **FR-016**: Le système MUST enregistrer les segments de chaque participant
  dans l'ordre publié, libellés depuis la discipline normalisée de chaque
  segment — le libellé libre saisi par le chronométreur étant absent d'un quart
  des segments mesurés — et MUST distinguer deux segments de même libellé.
- **FR-017**: Le système MUST NOT produire de segment ni de temps à partir du
  segment fantôme publié pour les participants non classés.
- **FR-018**: Le système MUST marquer comme relais les participations issues des
  courses où la source publie une ligne par équipe, le nom d'équipe tenant lieu
  de nom.
- **FR-019**: Le système MUST reporter le club déclaré par la source sur la
  participation, en s'appuyant sur la définition unique d'appartenance au club du
  projet, sans la réimplémenter.

**Métadonnées d'épreuve**

- **FR-020**: Le système MUST enregistrer la date réelle de l'événement telle
  que publiée par la source.
- **FR-021**: Le système MUST classer la discipline et la taille de chaque
  épreuve à partir de l'intitulé de la course, en n'utilisant le nom de
  l'événement que comme appoint quand l'intitulé ne nomme aucun sport.
- **FR-022**: Le système MUST renseigner le kilométrage de l'épreuve à partir de
  la distance publiée par la source.

**Intégration**

- **FR-023**: Le système MUST déclarer Sporthive comme fournisseur supporté, de
  sorte que la détection de fournisseur, le badge du formulaire et l'import de
  masse le reconnaissent sans liste tenue séparément.
- **FR-024**: Le système MUST rendre les échecs d'import Sporthive dans le
  détail des épreuves en erreur des bilans de la CLI, avec leur cause.
- **FR-025**: Le système MUST respecter le cache de fraîcheur du projet : une
  épreuve fraîche n'est pas re-sollicitée auprès de la source.

### Key Entities

- **Événement** : la manifestation désignée par l'URL. Porte le nom, la date, le
  lieu et le pays. N'est pas enregistré en tant que tel : il se décompose en
  épreuves.
- **Course** : une épreuve au sein de l'événement, avec son propre classement,
  son intitulé, son nombre de classés et sa distance. Correspond à une épreuve du
  modèle du projet.
- **Participation** : une ligne de classement — nom, dossard, club, catégorie,
  genre, temps, rangs, statut et segments. Sur les courses de relais, décrit une
  équipe et non une personne.
- **Segment** : une portion chronométrée d'une course (natation, transition,
  vélo, course à pied), avec sa discipline normalisée et sa durée.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Le lien Sporthive du Sheet, aujourd'hui ignoré, est importé sans
  intervention manuelle et fait apparaître le membre du club concerné dans les
  vues restreintes au club.
- **SC-002**: Pour chacune des 32 courses du panel sondé, le nombre de
  participations enregistrées est exactement égal au nombre de classés annoncé
  par la source.
- **SC-003**: Les 172 participations non classées du panel (129 abandons,
  35 non-partants, 8 disqualifications) reçoivent leur statut réel, et aucune
  n'est enregistrée comme finisher.
- **SC-004**: Aucune des 10 360 participations du panel n'est enregistrée sous
  une épreuve n'appartenant pas à l'événement désigné par son URL.
- **SC-005**: Un participant de triathlon voit ses cinq segments affichés dans
  l'ordre de la course ; un participant d'une course d'enfants voit ses quatre
  segments avec la course à pied à sa place.
- **SC-006**: Une URL Sporthive non importable produit un message nommant la
  cause, et l'import de masse poursuit le reste du lot.
- **SC-007**: Les tests unitaires du fournisseur s'exécutent sans aucun accès
  réseau, et la suite unitaire du projet reste verte.

## Assumptions

- **L'API publique reste ouverte** : aucune clé, aucun jeton, aucune
  authentification n'est requise aujourd'hui. Si la plateforme fermait cet accès,
  la feature deviendrait caduque — aucune voie de repli n'est prévue, la page
  publique n'étant qu'une coquille JavaScript.
- **Le volume immédiat reste faible** : un seul lien dans le Sheet. Le coût de
  lecture (une requête pour dix participants, soit une centaine de requêtes pour
  l'épreuve du Sheet) est jugé acceptable à ce volume ; il le serait moins si
  Sporthive devenait un fournisseur majoritaire.
- **Les sous-classements dupliqués sont acceptés** : sur les événements qui en
  publient, un athlète peut apparaître dans deux épreuves distinctes du même
  événement. Décision prise en connaissance de cause (cf. Clarifications).
- **Les fiches d'athlète issues des relais portent un nom d'équipe** : la source
  ne publie pas la composition des équipes, et l'entité d'équipe qu'elle expose
  n'est pas renseignée sur ces lignes.
- **Le découpage nom / prénom reste imparfait** : la source publie un nom
  complet unique, avec des conventions contradictoires selon les pays, et
  n'expose aucun champ séparé. Le découpage réutilise l'outil existant du projet,
  avec sa limite connue.
- **Aucune date de naissance n'est disponible**, ce qui laisse le
  dédoublonnement d'athlète reposer sur le seul couple nom / prénom, comme pour
  les autres fournisseurs qui n'en publient pas.
- **Réutilisation de l'existant** : registre de fournisseurs par hôte,
  classifieur de disciplines, normalisation des durées, traduction des statuts,
  qualification des noms d'épreuve, définition d'appartenance au club et
  construction des segments sont réutilisés tels quels, non réécrits.
