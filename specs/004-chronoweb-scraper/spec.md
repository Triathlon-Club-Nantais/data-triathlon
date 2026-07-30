# Feature Specification: Support de chronoweb.com comme fournisseur de résultats

**Feature Branch**: `feat-scrapers-supporter-chronoweb.com-html-stati`

**Created**: 2026-07-29

**Status**: Draft

**Input**: Issue [#55](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/55)
(sous-issue de #33, section B « nouveaux moteurs »).

**Source de vérité technique**: `docs/superpowers/specs/2026-07-29-chronoweb-sondage.md`
— sondage du HTML réel effectué le 29/07/2026 (21 événements, 89 épreuves,
31 642 lignes, 14 015 participants, millésimes 2015 → 2026). Il **prime** sur
l'énoncé de l'issue, dont l'affirmation centrale est fausse, et sur cette spec en
cas de divergence factuelle.

## Contexte métier

Les membres du club déposent dans un formulaire l'URL des résultats des épreuves
qu'ils ont courues. **7 de ces liens** pointent chronoweb.com, chronométreur
basé à Limoges qui couvre le triathlon du Centre-Ouest et du Sud (Oléron,
Altriman, Dijon, Chalain, Limoges, Toulouse) : 222 événements publiés sur son
catalogue.

Aujourd'hui ces liens échouent — aucun provider ne les reconnaît, ils partent au
fallback Playwright qui n'en tire rien — et les résultats des membres concernés
sont absents de l'application.

Le rendement est inhabituellement élevé : une URL chronoweb désigne un
**événement entier**, pas une épreuve. Les 2 événements réellement pointés par le
Sheet (Triathlon d'Oléron 2024, Altriman 2025) portent à eux seuls **7 épreuves
et 2 428 participants**.

## Clarifications

### Session 2026-07-29

- Q: Les transitions T1/T2 ne sont pas publiées mais se recalculent exactement
  (cumul − intervalle − cumul précédent). Les renseigne-t-on ? → A: **Oui**. La
  soustraction est vérifiée : jamais négative sur 17 497 écarts mesurés, et égale
  au caractère près au « Changement » de la fiche individuelle sur les cas
  contrôlés. Un triathlon chronoweb sort donc avec ses 5 segments complets, sans
  requête supplémentaire. Une transition dont un point encadrant manque reste
  vide — elle ne s'invente pas.
- Q: La ville n'est que dans le catalogue `/resultats.php` (170 Ko, contre 4,5 Mo
  pour la page d'un gros événement). Fait-on la requête d'appoint ? → A: **Oui**,
  son échec étant non bloquant. La commune publiée (« St Georges d'Oléron ») est
  plus juste que celle déduite du nom d'épreuve (« Oléron »), comme pour
  runnerbreizh.
- Q: Certains événements publient des classements dérivés (« Challenge 1er
  Tour ») en plus des épreuves réelles. Les filtre-t-on ? → A: **Non**, on
  importe toutes les épreuves publiées. Aucun critère fiable ne distingue un
  classement dérivé d'une vraie épreuve mono-segment — un trail n'a lui aussi
  qu'un point de chronométrage — et filtrer risquerait de jeter de vraies
  courses.
- Q: Quelle langue pour le code du nouveau fournisseur, la constitution
  (principe I : anglais technique) et `AGENTS.md` (français) divergeant ? → A:
  **Anglais**, comme la constitution et comme les fournisseurs les plus récents :
  docstrings et commentaires techniques en anglais ; vocabulaire métier, messages
  d'erreur destinés à l'opérateur et textes utilisateur en français.
- Q: Sous quelle forme enregistrer les temps intermédiaires — segments
  canoniques ré-étiquetés par discipline, ou libellés bruts de la source ? → A:
  **Motif reconnu → segments canoniques de la discipline** (86 des 89 épreuves du
  panel : natation/vélo/course en triathlon, course/vélo/course en duathlon,
  natation/course en aquathlon), **sinon libellés de la source**. L'affichage
  reste ainsi homogène avec les autres fournisseurs, et une épreuve au motif
  inhabituel (aquathlon relais à 8 points) conserve toutes ses étapes plutôt que
  d'être tronquée.
- Q: Sous quelle identité importer une ligne d'épreuve par équipes, dont la
  colonne « Nom » porte un nom d'équipe ? → A: **Libellé entier en nom, prénom
  vide.** Mesuré sur les 707 équipes du panel : la convention de découpage
  nom/prénom des individus en mutile 52 (« LIMOGES METROPOLE 2 » → prénom
  « 2 » ; « LES 3 ALLURES » → nom « LES ») et fusionnerait deux équipes d'un
  même club sous une seule identité. Même traitement que les lignes non
  identifiées de runnerbreizh.

### Session 2026-07-30

- Q: Qu'enregistre-t-on comme rangs pour un participant absent du point final
  (1,42 % du panel, ~23 lignes sur Dijon 2026) ? → A: **Aucun rang.** Un rang
  intermédiaire est un vrai rang de la source, mais issu d'une autre population
  que le classement : il entre en collision avec les rangs des finishers, que
  l'indice de fiabilité compte comme rangs dupliqués — l'épreuve ressortirait
  peu fiable alors que l'import est juste, exactement la limite subie par
  runnerbreizh sur ses relais. Les rangs de chaque point restent conservés dans
  les données brutes, rien n'est jeté.
- Q: Les transitions calculées valent-elles aussi pour une épreuve au motif de
  points non reconnu, rendue en libellés de la source ? → A: **Oui, partout où
  elles sont déductibles.** Sur un motif reconnu elles occupent les slots
  canoniques ; sur un motif non reconnu elles s'intercalent sous le libellé de la
  source (« Changement »). Un temps mort de relais est du temps de course réel, et
  rien en aval ne le rattraperait — le dépôt a déjà payé la leçon inverse (un slot
  omis du gabarit jetait sans bruit le temps qui s'y trouvait). Une valeur nulle
  reste non enregistrée. *Re-sondé le 2026-07-30* : sur l'aquathlon relais à
  8 points du panel, les 7 écarts sont **tous nuls** pour les 14 équipes — ses
  points sont contigus. Il sort donc à **8** segments, la répétition d'un libellé
  étant déjà désambiguïsée en aval.
- Q: En import de masse, la requête d'appoint pour la commune est-elle
  mutualisée entre les événements d'un même batch ? → A: **Non, une par
  événement, sans état partagé.** Le Sheet porte 5 URLs chronoweb distinctes,
  mais **2 événements seulement** (Oléron 2024, Altriman 2025) : au plus
  ~340 Ko de catalogue par campagne, face à des pages de classement de plusieurs
  mégaoctets. Le gain est du même ordre que celui déjà écarté au nom de la
  simplicité — plus faible encore, en réalité. Un
  cache mutualisé survivrait par ailleurs à l'import qui l'a rempli, rendant le
  comportement dépendant de l'ordre des imports — ce qu'aucun fournisseur du
  projet ne fait.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Importer un événement chronoweb depuis un lien collé (Priority: P1)

Un membre du club colle dans le formulaire « Ajouter » l'URL d'une page de
résultats chronoweb. L'application reconnaît le fournisseur et importe **toutes
les épreuves de l'événement** — pas seulement celle qu'affichait la page — avec
tous leurs participants, leurs temps, leurs rangs et leurs segments.

**Why this priority**: C'est le cœur de l'issue et la seule chose qui débloque
les liens du Sheet. Sans elle, rien d'autre n'a de valeur.

**Independent Test**: Coller l'URL du Triathlon d'Oléron 2024 et constater que
les 3 épreuves (854 participants) sont importées, que les temps et rangs d'un
participant vérifié à la main correspondent à ceux du site, et que chaque épreuve
est une course distincte.

**Acceptance Scenarios**:

1. **Given** une URL désignant l'épreuve « Triathlon M » d'un événement qui en
   compte trois, **When** l'import s'exécute, **Then** les trois épreuves sont
   importées, chacune comme une course distincte portant son propre nom.
2. **Given** un événement de 8 épreuves et 1 622 participants, **When** l'import
   s'exécute, **Then** l'ensemble est importé sans qu'aucune page supplémentaire
   ne soit demandée au site pour le classement.
3. **Given** un participant ayant franchi les trois points d'une épreuve qui en
   compte trois, **When** l'utilisateur consulte sa participation, **Then** son
   temps total est celui du point final, ses rangs (général et catégorie) sont
   ceux du point final, et ses segments sont les durées publiées pour chaque
   point, complétées des deux transitions.
4. **Given** un participant d'un duathlon dont les points sont
   course / vélo / course, **When** l'utilisateur consulte sa participation,
   **Then** les segments sont affichés sous les libellés de la discipline, sans
   qu'un segment de natation soit inventé.
5. **Given** une épreuve déjà importée et un second import lancé après expiration
   du cache, **When** l'import s'exécute, **Then** aucun participant n'est
   dupliqué.
6. **Given** un participant présent au point vélo mais absent du point final,
   **When** l'utilisateur consulte sa participation, **Then** elle apparaît en
   abandon, sans temps total et **sans rang**, et le rang qu'il occupait au vélo
   n'apparaît dans aucun classement.

---

### User Story 2 - Importer les liens du Sheet quelle que soit leur forme (Priority: P2)

L'opérateur lance l'import de masse depuis le Google Sheet. Les liens chronoweb
sont traités qu'ils désignent une épreuve, une vue filtrée ou la **fiche
individuelle** d'un participant, et la même épreuve soumise sous deux formes
n'est pas importée deux fois.

**Why this priority**: 2 des 5 URLs chronoweb distinctes du Sheet sont des fiches
individuelles, et 3 des 5 portent des paramètres d'affichage. Sans ce traitement,
40 % des liens resteraient en échec à chaque campagne. La valeur dépend de P1.

**Independent Test**: Soumettre les 4 formes d'URL réellement présentes dans le
Sheet pour les deux événements concernés et constater qu'elles produisent un
import complet et identique.

**Portée**: le fournisseur canonicalise ce qu'il scrape ; la clé du cache TTL,
elle, reste l'URL soumise (comme pour runnerbreizh).

**Acceptance Scenarios**:

1. **Given** une URL de fiche individuelle (`resultats_participant.php`, avec un
   dossard), **When** l'import s'exécute, **Then** l'événement entier auquel
   appartient ce participant est importé.
2. **Given** une URL portant des paramètres d'affichage (épreuve sélectionnée,
   catégorie, point de passage), **When** l'import s'exécute, **Then** l'import
   n'est amputé d'aucune épreuve ni d'aucun point.
3. **Given** deux URLs du Sheet désignant le même événement sous deux formes,
   **When** l'import de masse s'exécute, **Then** aucune course ni participation
   n'est dupliquée.

---

### User Story 3 - Comprendre pourquoi un lien chronoweb n'est pas importable (Priority: P3)

L'opérateur soumet un lien chronoweb qui ne désigne pas des résultats
consultables (archive de résultats en téléchargement, identifiant d'événement
inconnu). Il obtient un message qui nomme la cause et la forme d'URL attendue,
plutôt qu'un échec muet ou un import vide.

**Why this priority**: 1 des 7 liens du Sheet pointe une archive ZIP. Sans
message explicite, l'opérateur ne peut pas corriger la source et le lien restera
en échec à chaque campagne.

**Independent Test**: Soumettre l'URL d'archive présente dans le Sheet puis une
URL d'événement inexistant, et vérifier que chacune produit un message distinct
et actionnable dans le détail des épreuves en erreur.

**Acceptance Scenarios**:

1. **Given** une URL pointant un fichier de résultats à télécharger, **When**
   l'import s'exécute, **Then** l'épreuve est signalée en erreur avec un message
   nommant la forme d'URL attendue, et aucune donnée partielle n'est enregistrée.
2. **Given** une URL dont l'identifiant d'événement n'existe pas côté site,
   **When** l'import s'exécute, **Then** l'échec est signalé comme événement
   introuvable, et non comme événement vide.
3. **Given** l'URL d'un événement réel dont aucun classement n'est publié,
   **When** l'import s'exécute, **Then** l'opération se conclut sans erreur, avec
   zéro participant importé.

---

### Edge Cases

Tous constatés lors du sondage, avec leur traitement attendu :

- **Une ligne n'est pas un participant** — chaque ligne du tableau est le passage
  d'un concurrent à un point de chronométrage. Un participant qui a franchi trois
  points occupe trois lignes ; les compter comme trois participants triplerait
  l'effectif de chaque épreuve.
- **Non-finishers sans libellé** — la source ne publie aucun `DNF`/`DNS`/`DSQ`.
  Les 1,42 % de concurrents absents du point final n'ont ni temps total ni rang
  final : ils sont importés comme abandons par l'heuristique existante, **sans
  rang** — leur rang au dernier point franchi n'est pas promu en rang de
  classement, sous peine de doublonner celui d'un finisher et de faire ressortir
  toute l'épreuve comme peu fiable. **DNS et DSQ sont indistinguables** — limite
  de la source, pas du fournisseur.
- **Point intermédiaire manquant chez un finisher** — mesuré : 439 passages au
  vélo pour 445 à l'arrivée sur une même épreuve. Le segment concerné reste vide,
  ce n'est ni un abandon ni une erreur de lecture.
- **Rang illisible au texte** — la cellule de classement superpose le rang
  général et le rang de catégorie (masqué) : lue naïvement elle rend « 11 » pour
  un premier de sa catégorie et « 11837 » pour un 118ᵉ / 37ᵉ.
- **Deux conventions de catégorie dans le même champ** — 81 codes, préfixés
  (`MSE`, `FV1`) ou suffixés (`SEM`, `V1F`, `M0F`). `M0F` désigne une femme
  malgré son `M` initial : déduire le genre du premier caractère les
  masculiniserait toutes.
- **Catégories d'équipe** — `MIXT`, `DUOX`, `DUOM`, `DUOF` décrivent une
  composition d'équipe, pas une personne : aucun genre n'en est déduit. `MASC` et
  `FEM` apparaissent aussi **hors relais** comme catégories « toutes classes ».
- **Relais : une ligne par équipe** — le nom d'équipe occupe la colonne du nom
  et est enregistré tel quel, sans prénom (52 des 707 équipes du panel sont
  mutilées par la convention de découpage des individus). Contrairement à
  runnerbreizh, aucun rang n'est dupliqué, donc l'indice de fiabilité de
  l'épreuve n'est pas dégradé.
- **Épreuve à plus de cinq segments** — un aquathlon relais du panel alterne 8
  points (natation/course × 4). Les segments doivent tous être conservés, sans
  troncature à cinq, transitions déductibles comprises — soit **8** sur cette
  épreuve, dont les temps morts mesurés sont nuls (donc non enregistrés). Un
  libellé qui se répète (« Natation » quatre fois) ne doit écraser aucun temps.
- **Événement sans classement publié** — le site répond en succès, avec le nom et
  la date de l'événement mais aucun tableau. C'est un import vide, pas une
  erreur ; un identifiant inconnu, lui, ne rend aucun nom d'événement et doit
  échouer.
- **Le même événement publié deux fois** — deux identifiants distincts servent le
  même couple d'épreuves (2015). Les contraintes d'unicité existantes absorbent
  le doublon ; rien à traiter, mais à savoir avant de conclure à un bug de
  comptage.
- **Fiche individuelle cassée à la source** — sur les épreuves à un seul point,
  la page de détail renvoie des avertissements PHP à la place du nom et du temps.
  L'import ne doit dépendre d'elle en aucun cas.
- **Mojibake résiduel** — 4 noms sur 31 642 portent une lettre mal recodée à la
  source (`VÈronique`). Conservés tels quels ; la réconciliation d'identité
  existante corrigera si un autre fournisseur publie la graphie juste.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système MUST reconnaître les URLs chronoweb.com et les router
  vers le traitement dédié, sur la seule base du nom d'hôte.
- **FR-002**: Le système MUST importer **toutes les épreuves** de l'événement
  désigné, quelle que soit l'épreuve sélectionnée par l'URL soumise, et MUST
  enregistrer chacune comme une course distincte dont le nom porte le libellé de
  l'épreuve.
- **FR-003**: Le système MUST obtenir la totalité d'un classement d'événement en
  une seule requête au site, sans pagination ni exécution de JavaScript.
- **FR-004**: Le système MUST regrouper les lignes d'un même dossard au sein
  d'une épreuve en un seul participant.
- **FR-005**: Le système MUST retenir, comme temps total et comme rangs (général
  et catégorie) d'un participant, ceux du **point final** de l'épreuve, et
  MUST NOT lui attribuer de rang lorsqu'il ne l'a pas franchi : un rang
  intermédiaire appartient à une autre population que celle du classement.
- **FR-006**: Le système MUST enregistrer, pour chaque participant : nom, prénom,
  dossard, catégorie, genre, temps total, rang général, rang de catégorie et
  temps de segment.
- **FR-007**: Le système MUST enregistrer un segment par point de chronométrage
  franchi, en utilisant la durée de segment publiée par le site et non le temps
  cumulé.
- **FR-008**: Le système MUST enregistrer les transitions comme segments
  supplémentaires partout où elles sont déductibles des temps publiés — motif de
  points reconnu ou non —, et MUST NOT en enregistrer lorsqu'un des points
  encadrants manque. Sur un motif non reconnu, la transition porte le libellé
  publié par la source pour ce temps mort.
- **FR-009**: Le système MUST conserver tous les segments d'une épreuve qui en
  compte plus de cinq, sans troncature.
- **FR-010**: Le système MUST rattacher les segments à la discipline de
  l'épreuve lorsque la suite des points correspond à un motif de discipline
  connu, et MUST NOT enregistrer de segment pour une discipline que l'épreuve ne
  comporte pas. À défaut de motif reconnu, il MUST conserver les libellés
  publiés par la source.
- **FR-011**: Le système MUST déduire le genre de la catégorie en traitant les
  deux conventions de codage observées, et MUST NOT déduire de genre d'une
  catégorie d'équipe.
- **FR-012**: Le système MUST marquer comme épreuve par équipes celles dont le
  libellé les annonce comme telles, et MUST y enregistrer l'identité de chaque
  ligne sous le libellé publié dans son intégralité, sans prénom.
- **FR-013**: Le système MUST déterminer la discipline et la taille de chaque
  épreuve à partir de son libellé, en s'appuyant sur le nom de l'événement
  lorsque le libellé ne nomme aucun sport.
- **FR-014**: Le système MUST enregistrer la date de l'événement telle que
  publiée, pour toutes les épreuves de cet événement.
- **FR-015**: Le système MUST conserver la commune publiée par le catalogue du
  site lorsqu'elle est disponible, et MUST poursuivre l'import sans erreur
  lorsqu'elle ne l'est pas. Cette recherche MUST être refaite à chaque import
  d'événement, sans état conservé entre deux imports.
- **FR-016**: Le système MUST accepter les URLs de fiche individuelle en les
  ramenant à leur événement.
- **FR-017**: Le système MUST refuser, avec un message nommant la forme d'URL
  attendue, toute URL chronoweb qui ne désigne pas des résultats consultables.
- **FR-018**: Le système MUST signaler un identifiant d'événement inconnu comme
  une erreur explicite, distincte d'un événement sans classement publié, ce
  dernier devant se conclure par un import vide sans erreur.
- **FR-019**: Le système MUST NOT dépendre de la page de détail d'un participant
  pour produire un import.
- **FR-020**: Le système MUST NOT émettre plus de deux requêtes vers le site par
  import d'événement.

### Key Entities

- **Événement** : ce que désigne une URL chronoweb. Porte un nom, une date, une
  commune, et de 1 à 8 épreuves.
- **Épreuve** : une course au sein d'un événement (« Triathlon M », « 53 km »,
  « Aquathlon Team Relais »). Devient une course de l'application, avec sa
  discipline, sa taille et son propre classement.
- **Point de chronométrage** : une station de mesure au sein d'une épreuve,
  ordonnée. Porte un libellé de discipline (natation, vélo, course). Chaque
  passage publie un temps cumulé, une durée de segment et deux rangs.
- **Participant** : l'union des passages d'un même dossard dans une épreuve. Sans
  club ni date de naissance — la source ne les publie pas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Les 6 liens chronoweb exploitables du Sheet (sur 7) aboutissent à
  un import réussi ; le septième est signalé en erreur avec un message
  actionnable.
- **SC-002**: L'import de l'URL du Triathlon d'Oléron 2024 enregistre 3 épreuves
  et 854 participants — les effectifs publiés par le site, sans multiplication
  par le nombre de points de chronométrage.
- **SC-003**: Sur les épreuves du panel de sondage, 100 % des participants ayant
  franchi le point final ont un temps total et un rang général, et 100 % de ceux
  ne l'ayant pas franchi sont marqués comme non-finishers, **sans aucun rang** —
  aucun rang général n'apparaît donc deux fois dans une épreuve individuelle.
- **SC-004**: Un événement de 1 600 participants et 8 épreuves est importé sans
  qu'aucun participant ne soit dupliqué ni omis.
- **SC-005**: Pour un triathlon dont les trois points sont publiés, la somme des
  segments enregistrés d'un participant égale son temps total.
- **SC-006**: Aucune régression : la suite de tests unitaires passe sans réseau,
  et les fournisseurs existants restent détectés comme avant.
- **SC-007**: L'aquathlon relais à 8 points du panel est importé avec ses **8**
  temps intermédiaires, aucun n'étant écrasé par la répétition d'un libellé
  (« Natation » y apparaît quatre fois). Le chiffre est **mesuré** : re-sondé le
  2026-07-30, les 7 temps morts de cette épreuve sont nuls sur ses 14 équipes —
  un temps mort nul n'est pas enregistré (FR-008), d'où 8 et non 15.

## Assumptions

- La structure HTML mesurée le 29/07/2026 est stable : elle est identique sur
  les 89 épreuves du panel et sur des millésimes allant de 2015 à 2026.
- Le club des participants restera absent : il n'apparaît nulle part sur le site.
  Les participations chronoweb seront donc hors du périmètre `scope=club`
  (dashboard, page club, statistiques). C'est assumé, comme pour runnerbreizh.
- L'ordre des points de chronométrage suit l'ordre croissant de leur identifiant,
  vérifié sur 8 930 participants sans contre-exemple.
- Le volume par requête (jusqu'à 4,5 Mo) reste supportable par l'infrastructure
  d'import, qui traite déjà des payloads comparables.
- Le `Crawl-delay` du site vise les robots d'indexation ; un import ponctuel de
  une à deux requêtes par événement n'entre pas dans ce cadre. Aucun balayage du
  catalogue n'est prévu.
- La correction des deux limites du classifieur partagé mises en évidence par le
  sondage (« 53 km » d'un trail classé course à pied, épreuve dont ni le libellé
  ni l'événement ne nomment de sport repliée sur triathlon) est **hors
  périmètre** : elle affecte tous les fournisseurs et relève d'un ticket dédié.
