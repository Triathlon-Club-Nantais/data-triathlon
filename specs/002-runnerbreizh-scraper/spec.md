# Feature Specification: Support de runnerbreizh.fr comme fournisseur de résultats

**Feature Branch**: `tjarrier/feat-scrapers-supporter-runnerbreizh.fr-html-sta`

**Created**: 2026-07-27

**Status**: Draft

**Input**: Issue [#56](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/56)
(sous-issue de #33, section B « nouveaux moteurs »).

**Source de vérité technique**: `docs/superpowers/specs/2026-07-27-runnerbreizh-sondage.md`
— sondage du HTML réel effectué le 27/07/2026 (7 épreuves, 3 types, 2 millésimes,
19 requêtes). Il **prime** sur l'énoncé de l'issue, dont deux affirmations sont
périmées, et sur cette spec en cas de divergence factuelle.

## Contexte métier

Les membres du club déposent dans un formulaire l'URL des résultats des épreuves
qu'ils ont couru. **10 de ces liens** pointent runnerbreizh.fr — le plus gros
volume des fournisseurs encore non supportés après RaceResult. Le site couvre le
triathlon breton et publie aussi des épreuves hors Bretagne (Embrun, Les Sables,
Gravelines) : le volume est structurellement récurrent pour un club nantais.

Aujourd'hui ces 10 liens échouent : aucun provider ne les reconnaît, ils partent
au fallback Playwright qui n'en tire rien d'exploitable. Les résultats des
membres concernés sont absents de l'application.

## Clarifications

### Session 2026-07-27

- Q: Le site nomme ses épreuves « Triathlon de Plouescat S (0.75/20/5) » — que
  stocke-t-on comme nom d'épreuve ? → A: **Sans les distances** (« Triathlon de
  Plouescat S »), le kilométrage total allant dans le champ de distance. Mesuré :
  l'extraction de ville pour la carte rend « Plouescat » sur le nom nettoyé,
  contre « Plouescat S (0.75/20/5) » — introuvable — sur le nom intégral. Le nom
  nettoyé est aussi celui qu'un autre fournisseur publierait pour la même épreuve,
  ce qui évite un doublon d'épreuve.
- Q: Sous quelle identité d'athlète importer les lignes anonymes
  (`?DOSSARD #43637`) ? → A: **Libellé brut en nom, prénom vide**. Un athlète
  distinct par ligne, immédiatement reconnaissable comme non identifié.
- Q: Quelle langue pour le code du nouveau fournisseur, la constitution
  (principe I : anglais technique) et `AGENTS.md` (français) divergeant ? → A:
  **Anglais**, comme la constitution : docstrings et commentaires techniques en
  anglais ; vocabulaire métier, messages d'erreur destinés à l'opérateur et
  textes utilisateur en français.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Importer une épreuve runnerbreizh depuis un lien collé (Priority: P1)

Un membre du club colle dans le formulaire « Ajouter » l'URL d'une page de
résultats runnerbreizh. L'application reconnaît le fournisseur, importe **tous**
les participants de l'épreuve — pas seulement ceux de la page affichée — et les
rend consultables sur la fiche de l'épreuve et sur les fiches d'athlètes.

**Why this priority**: C'est le cœur de l'issue et la seule chose qui débloque
les 10 liens du Sheet. Sans elle, rien d'autre n'a de valeur.

**Independent Test**: Coller une URL runnerbreizh d'épreuve connue, constater que
le nombre de participants importés égale le nombre de classés annoncé par le site,
et que les temps, rangs et segments d'un participant vérifié à la main
correspondent.

**Acceptance Scenarios**:

1. **Given** une épreuve runnerbreizh de 356 classés répartis sur 8 pages,
   **When** l'utilisateur soumet l'URL de sa première page,
   **Then** les 356 participants sont importés en une seule opération.
2. **Given** l'URL d'une épreuve dont le nom porte la discipline et la taille
   (« Triathlon de Plouescat S »), **When** l'import s'exécute, **Then** l'épreuve
   est enregistrée avec sa date réelle, sa discipline, sa taille et son
   kilométrage.
3. **Given** un participant dont le site publie trois temps de segment,
   **When** l'utilisateur consulte sa participation, **Then** les trois segments
   sont affichés sous les libellés correspondant à la discipline de l'épreuve
   (natation/vélo/course pour un triathlon, course 1/vélo/course 2 pour un
   duathlon, natation/course pour un aquathlon).
4. **Given** une épreuve déjà importée et un second import lancé après expiration
   du cache, **When** l'import s'exécute, **Then** aucun participant n'est
   dupliqué, bien que le site ne publie aucun dossard.

---

### User Story 2 - Importer les 10 liens du Sheet sans intervention manuelle (Priority: P2)

L'opérateur lance l'import de masse depuis le Google Sheet. Les liens
runnerbreizh sont traités quelle que soit la page sur laquelle le contributeur
les a copiés, et la même épreuve soumise sous deux formes différentes n'est pas
importée deux fois.

**Why this priority**: 8 des 10 liens réels portent `&page=2` ou `&page=3` — sans
ce traitement, l'import de masse manquerait silencieusement les premières pages,
c'est-à-dire les meilleurs classés. La valeur est réelle mais dépend de P1.

**Independent Test**: Soumettre les 4 formes d'URL réellement présentes dans le
Sheet pour une même épreuve et constater qu'elles produisent un import complet et
identique, et une seule épreuve en base.

**Portée**: le fournisseur canonicalise ce qu'il scrape ; la clé du cache TTL,
elle, reste l'URL soumise (cf. scénario 3).

**Acceptance Scenarios**:

1. **Given** un lien pointant la page 2 d'une épreuve, **When** l'import
   s'exécute, **Then** les participants de la page 1 sont également importés.
2. **Given** un lien portant un filtre de sexe ou un ordre de tri, **When**
   l'import s'exécute, **Then** l'épreuve entière est importée, sans amputation
   par le filtre.
3. **Given** la même épreuve présente deux fois dans le Sheet sous deux formes
   d'URL, **When** l'import de masse s'exécute, **Then** une seule épreuve est
   enregistrée, sans participation dupliquée. La seconde occurrence est **re-scrapée**
   avant de constater que tout est déjà en base : la clé du cache est l'URL soumise,
   décidée en amont du fournisseur — faire converger les deux graphies relève d'une
   canonicalisation dans le service d'import, hors périmètre ici.

---

### User Story 3 - Comprendre pourquoi un lien runnerbreizh n'est pas importable (Priority: P3)

L'opérateur soumet un lien runnerbreizh qui ne désigne pas une épreuve (fiche
coureur, page inexistante). Il obtient un message qui nomme la cause et la forme
d'URL attendue, plutôt qu'un échec muet ou un import vide.

**Why this priority**: 1 des 10 liens du Sheet est une fiche coureur. Sans
message explicite, l'opérateur ne peut pas corriger la source et le lien restera
en échec à chaque campagne d'import.

**Independent Test**: Soumettre une URL de fiche coureur puis une URL d'épreuve
inexistante, et vérifier que chacune produit un message distinct et actionnable,
visible dans le détail des épreuves en erreur.

**Acceptance Scenarios**:

1. **Given** une URL de fiche coureur (palmarès d'une personne), **When** l'import
   s'exécute, **Then** l'épreuve est signalée en erreur avec un message indiquant
   la forme d'URL de résultats attendue, et aucune donnée partielle n'est
   enregistrée.
2. **Given** une URL d'épreuve dont l'identifiant n'existe pas côté site,
   **When** l'import s'exécute, **Then** l'échec est signalé comme épreuve
   introuvable, et non comme épreuve vide.

---

### Edge Cases

Tous constatés lors du sondage, avec leur traitement attendu :

- **Participants anonymes** — 3 lignes sur 322 portent le libellé `?DOSSARD #43637`
  au lieu d'un nom. Elles sont **importées** sous ce libellé : les écarter
  créerait des trous dans le classement, ce que l'indice de fiabilité de l'épreuve
  interprète comme une anomalie et qui masquerait le ratio de place de tous les
  participants de l'épreuve.
- **Nom mutilé par la source** — `PROD?HOMME Anais` : le `?` est présent dans le
  HTML servi. Le nom est conservé tel quel ; la graphie correcte, si elle arrive
  par un autre fournisseur, sera réconciliée par le mécanisme existant de
  réconciliation d'identité.
- **Relais / duo** — le site publie une ligne par équipier, les deux partageant
  temps et rang. Les deux participations sont importées et l'épreuve est marquée
  comme relais. Conséquence connue et acceptée : deux finishers au même rang font
  sortir l'épreuve comme « non fiable » selon la règle actuelle de l'indice de
  qualité, qui ne tolère les rangs partagés qu'entre solos et relais, pas au sein
  d'un même groupe. Corriger cette règle est hors périmètre.
- **Discipline sans vélo** — en aquathlon la colonne « Vélo » existe mais est
  vide : aucun segment vélo ne doit être enregistré.
- **Libellés de colonnes trompeurs** — les en-têtes sont identiques quelle que
  soit la discipline (en duathlon, « 1ère épreuve » est une course à pied). Les
  segments sont donc rattachés à la discipline de l'épreuve, jamais au libellé
  affiché.
- **Page au delà de la dernière** — le site répond en succès avec un tableau vide
  plutôt qu'une erreur : c'est le signal d'arrêt de la pagination.
- **Total annoncé trompeur en relais** — le compteur de classés compte des équipes
  (31) et non des lignes (62) : il ne peut pas servir à borner la pagination.
- **Épreuve republiée** — certaines pages mentionnent un chronométreur tiers déjà
  supporté par l'application, avec des données plus riches (dossards, clubs). La
  mention ne lie que l'accueil du chronométreur, jamais l'épreuve : aucune URL
  source n'est reconstructible. L'information est **journalisée** à destination de
  l'opérateur, qui seul peut fournir le lien natif.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système MUST reconnaître les URLs de résultats runnerbreizh.fr
  et les router vers le traitement dédié, sur la seule base du nom d'hôte.
- **FR-002**: Le système MUST importer **tous** les classés d'une épreuve, en
  parcourant l'intégralité des pages, quelle que soit la page désignée par l'URL
  soumise.
- **FR-003**: Le système MUST ignorer les paramètres de vue de l'URL soumise
  (page, ordre de tri, filtre de sexe) et repartir de la première page, de sorte
  qu'un filtre présent dans le lien n'ampute jamais l'import.
- **FR-004**: Le système MUST arrêter le parcours des pages au premier tableau
  sans ligne de résultat, et MUST NOT déduire le nombre de pages du total de
  classés annoncé.
- **FR-005**: Le système MUST enregistrer, pour chaque participant : nom, prénom,
  catégorie, genre, temps total, rang général, rang de catégorie, et les temps de
  segment publiés.
- **FR-006**: Le système MUST rattacher les temps de segment à la discipline de
  l'épreuve et non aux libellés de colonnes du site, et MUST NOT enregistrer de
  segment pour une colonne vide.
- **FR-007**: Le système MUST enregistrer l'épreuve avec son nom, sa date réelle,
  sa discipline, sa taille lorsqu'elle est exprimée dans le nom, et son
  kilométrage.
- **FR-007a**: Le nom d'épreuve enregistré MUST NOT contenir le détail des
  distances par segment que le site accole entre parenthèses (« Triathlon de
  Plouescat S », pas « Triathlon de Plouescat S (0.75/20/5) »), afin que
  l'extraction de ville utilisée par la carte trouve la localité et qu'une même
  épreuve publiée par un autre fournisseur ne crée pas de doublon. Le kilométrage
  total, publié à part par le site, MUST alimenter le champ de distance de
  l'épreuve.
- **FR-008**: Le système MUST marquer comme relais une épreuve dont le format
  désigne une équipe, et importer une participation par équipier.
- **FR-009**: Le système MUST conserver les informations d'analyse propres au
  fournisseur (rang par segment, écart au vainqueur du segment, vitesse moyenne,
  rang avant la dernière course à pied, évolution de rang, total de classés) dans
  les données brutes de la participation, sans créer de champ dédié.
- **FR-010**: Le système MUST rejeter une URL de fiche coureur avec un message en
  français nommant la forme d'URL attendue, sans import partiel.
- **FR-011**: Le système MUST signaler distinctement une épreuve introuvable
  (identifiant inconnu côté site, réponse en succès mais sans résultat).
- **FR-012**: Le système MUST journaliser un avertissement lorsque la page
  mentionne un chronométreur tiers déjà supporté par l'application.
- **FR-013**: Le système MUST rester idempotent au réimport bien qu'aucun dossard
  ne soit publié, en s'appuyant sur le mécanisme de déduplication par athlète
  existant, sans le modifier.
- **FR-014**: Le système MUST importer les lignes de participants anonymes sous
  leur libellé source **intégral comme nom, sans prénom**, et sans leur inventer
  de dossard.
- **FR-015**: Le système MUST NOT renseigner de club pour ces participations, et
  MUST NOT écraser le club déjà connu d'un athlète.

### Key Entities

Aucune entité nouvelle. Le fournisseur alimente le modèle existant :

- **Épreuve (`Course`)** — une URL de résultats runnerbreizh = **une** épreuve.
- **Participation** — une ligne du classement ; sans dossard, sans club.
- **Athlète (`Athlete`)** — dédoublonné par nom et prénom ; date de naissance
  inconnue de ce fournisseur.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Les 4 épreuves distinctes des 10 liens runnerbreizh du Sheet
  s'importent avec succès, contre 0 aujourd'hui.
- **SC-002**: Pour chaque épreuve du panel de sondage, le nombre de participants
  importés égale le nombre de classés annoncé par le site — aux relais près, où
  il en vaut le double (une ligne par équipier).
- **SC-003**: Un second import de la même épreuve, cache court-circuité, n'ajoute
  aucun participant ni aucun athlète.
- **SC-004**: Un lien pointant une page intermédiaire produit exactement le même
  résultat que le lien de la première page de la même épreuve.
- **SC-005**: Une URL non supportée du même site (fiche coureur, identifiant
  inconnu) produit un message d'erreur qui nomme la cause, visible dans le détail
  des épreuves en erreur de la CLI.
- **SC-006**: Le coût réseau d'un import est de `nombre de pages + 1` requêtes,
  sans requête par participant.
- **SC-007**: La suite de tests unitaires reste verte et sans accès réseau ; les
  tests d'accès réel au site restent isolés derrière le marqueur d'intégration.
- **SC-008**: Le nom enregistré permet d'extraire la commune pour **4 des 7**
  épreuves du panel de sondage, contre **0 sur 7** si le détail des distances
  était conservé. Les 3 restantes (« Triskel Race Cross Duathlon de Guidel XS »,
  « TriBreizh en Duo L », « Duathlon Nozéen S Open ») butent sur une limite de
  l'heuristique d'extraction de ville existante — nom d'épreuve sans toponyme, ou
  préfixe de marque — et non sur ce fournisseur : hors périmètre.

## Assumptions

- **Arbitrages déjà rendus** (27/07/2026, cf. sondage) : l'absence de club est
  une limite acceptée — les participations runnerbreizh resteront hors du
  périmètre club (dashboard, page club, statistiques club) et le club **n'est pas
  inféré** depuis la fiche de l'athlète ; une URL de fiche coureur est refusée
  explicitement, sans import des épreuves de son palmarès.
- Le site reste en HTML statique, sans JavaScript nécessaire, sans session ni
  cookie requis : trois cookies sont posés, aucun n'est nécessaire pour obtenir
  les résultats.
- La structure de 8 colonnes est stable entre 2025 et 2026 et entre disciplines ;
  un changement de markup se traiterait comme une régression de scraper, détectée
  par les tests d'intégration.
- Les disciplines annoncées par le site se limitent à triathlon, duathlon et
  aquathlon sur le panel observé. Une discipline inconnue doit dégrader
  proprement (épreuve importée, discipline déduite du nom) plutôt qu'échouer.
- Le fournisseur ne publie que des classés : aucun abandon, non-partant ou
  disqualifié n'apparaît sur le panel. Le statut est donc déduit par
  l'heuristique existante et le scraper ne se prononce pas.
- **Langue du code : arbitré** (cf. Clarifications) — le principe I de la
  constitution s'applique, malgré les 9 scrapers existants en français :
  docstrings et commentaires techniques du nouveau module en anglais, vocabulaire
  métier, messages d'erreur destinés à l'opérateur et textes utilisateur en
  français. Le module est le premier du dossier à suivre la convention cible ;
  aucun fichier existant n'est réécrit (règle de transition du principe I).
