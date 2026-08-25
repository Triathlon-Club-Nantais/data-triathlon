# Feature Specification: la page épreuve — répartitions honnêtes, synthèses navigables, temps douteux signalés

**Feature Branch**: `feat/486-page-epreuve`

**Created**: 2026-08-25

**Status**: Draft

**Input**: Lot #486 de l'epic #460 — entrées `RES-7`, `RES-10`, `RES-11` du § 6 de
`docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`, qui reste le **point de
vérité des constats**. Ce document ne les duplique pas : il en tire ce qui doit être
livré, et se re-tranche en re-sondant si les deux divergent.

## Contexte

`/courses/[id]` est l'écran de résultats d'une épreuve. Il porte trois cartes de synthèse
(répartition genre, répartition par catégorie, top clubs), une distribution des temps, et
le classement paginé. Les trois constats portent sur un même défaut de **franchise
d'affichage** : ce que les cartes omettent n'est pas dit, ce qu'elles présentent comme
sûr ne l'est pas toujours, et ce qu'elles montrent ne mène nulle part.

Trois faits mesurés servent de repères :

- Course 214 : la carte « Répartition par catégorie » affiche huit barres totalisant
  **86,1 %**. `categories_total` vaut 498, les huit catégories rendues n'en couvrent que
  431 — **67 athlètes (13,9 %) n'apparaissent nulle part**, et rien ne le signale.
- Course 214 : le premier du classement affiche « Natation 00:00:31 · Vélo 00:00:34 ·
  Course 00:19:18 » pour un total de **01:06:18**. Les inters ne se rapprochent pas du
  total, et l'écran n'émet aucun signal.
- Course 340 : la liste des clubs est vide, mais son en-tête « Club / Athlètes » est
  rendu quand même, au-dessus de « Clubs non renseignés. ».

L'incohérence de fiabilité est **interne au produit** : la donnée existe déjà. L'API
publie `is_reliable` et `quality_issues` sur chaque épreuve, le produit sait déjà les
mettre en phrases françaises, et le profil athlète les affiche — mais la page épreuve, la
liste des épreuves et le détail de participation ne les lisent pas.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Le lecteur voit qu'un chiffre est douteux avant de s'y fier (Priority: P1)

Un visiteur ouvre le résultat d'une épreuve. Certaines épreuves ont été importées depuis
un chronométreur dont les données comportent des anomalies connues du produit (dossards en
doublon, trous dans le classement, rangs partagés, finishers sans temps). Aujourd'hui
l'écran présente ces chiffres exactement comme les autres. Après ce lot, l'écran dit ce
qu'il sait : l'épreuve porte une marque « données douteuses » qui, consultée, énumère les
anomalies constatées ; et une ligne du classement dont les inters ne rendent pas compte du
temps total porte un marqueur discret expliquant l'écart.

**Why this priority**: sur un produit de résultats, un chiffre visiblement faux présenté
sur le même ton qu'un chiffre juste ne discrédite pas seulement la ligne — il discrédite
le tableau entier. C'est la seule des trois entrées classée **impact fort** par l'audit,
et le mécanisme existe déjà à côté : rien à produire, seulement à lire là où la donnée est
affichée.

**Independent Test**: se vérifie seul, sur une épreuve dont `is_reliable` est faux et une
épreuve saine, sans qu'aucune des deux autres histoires soit livrée. La valeur rendue est
entière : le lecteur sait quand douter.

**Acceptance Scenarios**:

1. **Given** une épreuve dont le produit a relevé au moins une anomalie de fiabilité,
   **When** le visiteur ouvre `/courses/[id]`, **Then** l'en-tête de la page porte une
   marque « données douteuses », et le détail de cette marque énumère les anomalies en
   français, avec leur nombre.
2. **Given** une épreuve sans anomalie relevée, **When** le visiteur ouvre la page,
   **Then** aucune marque n'est affichée — l'absence de signal reste l'état normal, et ne
   se paie d'aucun encombrement.
3. **Given** une épreuve dont les temps intermédiaires publiés ne couvrent pas
   l'intégralité du parcours — un segment que le chronométreur n'a pas publié, constaté
   sur l'ensemble des lignes —, **When** le visiteur ouvre la page, **Then** l'écran le
   dit **une fois**, au niveau de l'épreuve, et non sur chaque ligne.
4. **Given** une ligne de classement dont l'écart entre le temps total et la somme de ses
   inters s'éloigne nettement de celui des autres lignes de la même épreuve, **When** le
   visiteur lit cette ligne, **Then** elle porte un marqueur discret dont le texte
   explique que ses temps intermédiaires ne rendent pas compte de son temps total ;
   **And** les temps restent affichés tels que le chronométreur les a publiés, sans être
   corrigés ni masqués.
5. **Given** une ligne dont un inter manque, dont le total manque, ou dont l'épreuve
   compte trop peu de lignes comparables pour établir une référence, **When** l'écart ne
   peut pas être situé, **Then** aucun marqueur n'est posé — le produit ne signale que ce
   qu'il a mesuré.
6. **Given** la liste des épreuves, **When** l'une d'elles porte des anomalies de
   fiabilité, **Then** sa ligne porte la même marque, avec le même vocabulaire, sans
   quitter la liste pour l'apprendre.

---

### User Story 2 - Les répartitions disent ce qu'elles omettent (Priority: P2)

Un visiteur lit les cartes de synthèse d'une épreuve. Elles ne montrent qu'un extrait —
les huit catégories les plus représentées, les neuf premiers clubs — mais rien ne le dit,
et les pourcentages laissent croire à un tout. Après ce lot, chaque carte nomme sa portée
et rend visible son reste : une part « Autres » calculée par différence, un pied qui
compte les clubs non listés, et un en-tête qui disparaît quand il n'y a rien à
surmonter.

**Why this priority**: n'empêche aucune tâche, mais fait mentir un chiffre — 86,1 %
présentés comme 100 %. Sur un produit dont la promesse est la restitution de résultats,
un total faux coûte plus que son effort de correction, qui est faible.

**Independent Test**: se vérifie seul, sur une épreuve à plus de huit catégories, une à
moins de huit, et une sans club renseigné.

**Acceptance Scenarios**:

1. **Given** une épreuve dont les catégories renseignées dépassent le nombre de barres
   affichées, **When** le visiteur lit la carte, **Then** une dernière part « Autres (N) »
   rend compte de la différence, **And** l'ensemble des parts affichées totalise 100 %.
2. **Given** une épreuve dont toutes les catégories renseignées tiennent dans les barres
   affichées, **When** le visiteur lit la carte, **Then** aucune part « Autres » n'est
   ajoutée — un reste nul ne se dessine pas.
3. **Given** une épreuve dont les clubs renseignés dépassent le nombre de lignes
   affichées, **When** le visiteur lit la carte « Top clubs », **Then** un pied indique
   combien de clubs ne sont pas listés.
4. **Given** une épreuve dont aucun participant ne porte de club, **When** le visiteur lit
   la carte, **Then** l'en-tête de colonnes n'est pas rendu, et seul l'état d'absence
   s'affiche.
5. **Given** n'importe quelle épreuve, **When** le visiteur lit les titres des deux
   cartes, **Then** ils énoncent leur portée (« les huit catégories les plus
   représentées », « les neuf clubs les plus représentés ») plutôt qu'un tout.

---

### User Story 3 - Les synthèses mènent au classement, et leurs codes s'expliquent (Priority: P3)

Un visiteur voit « BLAIN TRIATHLON 33 » ou « V2 12,0 % » et veut voir ces athlètes. Rien
n'est cliquable : la seule sélection offerte par le classement est « tous » ou « TCN ».
Et les codes de catégorie — S2, V1, V3, PoM, CA, JU — ne sont expliqués nulle part : un
parent qui consulte le résultat de son enfant ne sait pas ce que « PoM » désigne. Après ce
lot, chaque ligne de club et chaque part de catégorie ouvre le classement filtré sur cette
valeur, avec un repère retirable qui dit ce qui est filtré, et chaque code porte son
libellé complet.

**Why this priority**: ouvre l'exploration de données **déjà calculées**, mais c'est la
seule des trois entrées qui demande un appui côté API de lecture, donc la plus coûteuse.
Elle se pose en dernier, sur une page dont les deux autres histoires ont déjà rétabli la
franchise.

**Independent Test**: se vérifie seul, en partant d'une carte de synthèse et en arrivant
sur un classement dont le contenu correspond à la valeur cliquée.

**Acceptance Scenarios**:

1. **Given** la carte « Top clubs » d'une épreuve, **When** le visiteur active la ligne
   d'un club, **Then** le classement n'affiche plus que les participants de ce club,
   **And** un repère nommant ce club apparaît, **And** ce repère peut être retiré pour
   revenir au classement entier.
2. **Given** la carte des catégories, **When** le visiteur active une part, **Then** le
   classement n'affiche plus que les participants de cette catégorie, avec le même repère
   retirable.
3. **Given** un classement filtré sur un club ou une catégorie, **When** le visiteur lit
   l'écran, **Then** le nombre de résultats de la sélection est annoncé face au total de
   l'épreuve, sur le motif de ligne d'état déjà en place pour la recherche.
4. **Given** un classement filtré sur une valeur qui ne rend aucun participant, **When**
   l'écran s'affiche, **Then** l'état d'absence nomme le filtre en cause et offre le retour
   au classement entier — il ne parle pas de « recherche » quand aucune recherche n'a été
   faite.
5. **Given** un code de catégorie affiché à l'écran, **When** le visiteur cherche à savoir
   ce qu'il désigne, **Then** le libellé complet lui est accessible sans quitter la page,
   **And** cet accès fonctionne au doigt et au clavier, pas seulement au survol.
6. **Given** un partage d'adresse d'un classement filtré, **When** le destinataire ouvre
   ce lien, **Then** il voit la même sélection — le filtre vit dans l'adresse.

---

### Edge Cases

- **Reste négatif ou incohérent** : si le dénominateur publié est inférieur à la somme des
  parts affichées, aucune part « Autres » n'est dessinée plutôt qu'une part négative.
- **Dénominateur nul** : une épreuve sans aucune catégorie renseignée garde son état
  d'absence actuel, sans part « Autres » à 100 %.
- **Épreuve marquée douteuse mais sans anomalie énumérable** : la marque reste, et son
  détail dit qu'aucune anomalie n'est détaillée plutôt que d'afficher une liste vide.
- **Code d'anomalie inconnu du produit** : il reste visible avec son compteur, sans être
  avalé — un nouveau code côté serveur ne doit pas disparaître de l'écran en attendant sa
  traduction.
- **Cumul de sélections** : un filtre club, un filtre catégorie et une recherche par nom
  peuvent être actifs ensemble ; les repères le disent tous les trois, et chacun se retire
  indépendamment.
- **Filtre club croisé avec la portée TCN** : sélectionner un club autre que le TCN alors
  que la portée « TCN » est active donnerait un classement vide par construction ; l'écran
  doit rendre ce cas lisible plutôt que d'afficher une absence sans cause.
- **Valeur de filtre inconnue dans l'adresse** : une adresse portant un club ou une
  catégorie qui n'existe pas sur cette épreuve rend un classement vide **expliqué**, jamais
  une erreur.
- **Catégorie hors table de correspondance** : un code que la table ne connaît pas
  s'affiche tel quel, sans libellé inventé.
- **Écart total/inters juste au seuil** : le marqueur se pose **au-delà** de 2 %, pas à
  2 % exactement.
- **Épreuve de type relais** : la somme des inters d'un relayeur n'a pas le même sens ;
  le contrôle d'écart ne doit pas produire un marqueur systématique sur ces épreuves.

## Requirements *(mandatory)*

### Functional Requirements

#### Fiabilité affichée (US1)

- **FR-001**: La page d'une épreuve MUST afficher une marque « données douteuses » dans
  son en-tête dès lors que le produit a relevé au moins une anomalie de fiabilité sur cette
  épreuve.
- **FR-002**: Le détail de cette marque MUST énumérer les anomalies relevées en français,
  avec leur nombre, en réutilisant les formulations déjà en service ailleurs dans le
  produit — un même code d'anomalie ne doit pas se dire de deux façons selon l'écran.
- **FR-003**: Un code d'anomalie que le produit ne sait pas traduire MUST rester affiché
  avec son compteur.
- **FR-004**: La liste des épreuves MUST porter la même marque sur les épreuves
  concernées, avec le même vocabulaire.
- **FR-005**: La page d'une épreuve MUST signaler, **au niveau de l'épreuve**, que les
  temps intermédiaires publiés ne couvrent pas l'intégralité du parcours, quand l'écart
  entre temps total et somme des inters est constaté sur l'ensemble de ses lignes.
- **FR-006**: Une ligne de classement MUST porter un marqueur discret quand son écart
  s'éloigne nettement de celui des autres lignes de la même épreuve — jamais sur le seul
  fait qu'un écart existe, cet écart étant le plus souvent une propriété de l'épreuve et
  non de la ligne.
- **FR-007**: Les seuils de ces deux signaux MUST être ceux établis par le sondage
  `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`, qui en est le point de
  vérité : le seuil de 2 % proposé par l'audit est écarté, mesures à l'appui.
- **FR-008**: Le texte de ces marqueurs MUST expliquer l'écart en français, et MUST être
  accessible au lecteur d'écran comme au survol.
- **FR-009**: Le produit MUST NOT corriger, recalculer ni masquer les temps publiés par le
  chronométreur : le marqueur informe, il ne réécrit pas la donnée.
- **FR-010**: Le contrôle d'écart MUST être omis — sans marqueur — quand le temps total ou
  l'un des temps intermédiaires manque ou est illisible, quand l'épreuve est un relais,
  ou quand l'épreuve compte trop peu de lignes comparables pour établir une référence.
- **FR-011**: L'écart d'une ligne et la référence de son épreuve MUST être calculés en
  **un seul endroit** du système : deux implémentations parallèles de la même règle
  divergeraient, comme l'ont fait les trois listes du critère club de #76.

#### Franchise des répartitions (US2)

- **FR-012**: La carte de répartition par catégorie MUST rendre visible la part des
  participants non couverts par les catégories affichées, sous la forme d'une part
  « Autres (N) » calculée par différence entre le dénominateur publié et la somme des
  parts affichées.
- **FR-013**: Cette part MUST être omise quand la différence est nulle ou négative.
- **FR-014**: L'ensemble des parts affichées, part « Autres » comprise, MUST totaliser
  100 % du dénominateur publié.
- **FR-015**: La carte des clubs MUST indiquer combien de clubs ne figurent pas dans la
  liste affichée, et MUST omettre cette mention quand la liste est exhaustive.
- **FR-016**: L'en-tête de colonnes de la carte des clubs MUST NOT être rendu quand la
  liste est vide.
- **FR-017**: Les titres des cartes de répartition MUST énoncer leur portée plutôt que de
  laisser croire à un tout.
- **FR-018**: La description destinée aux lecteurs d'écran MUST inclure la part
  « Autres » et le nombre de clubs non listés, au même titre que ce qui est dessiné.

#### Synthèses navigables (US3)

- **FR-019**: Chaque ligne de club de la carte des clubs MUST être un contrôle activable
  qui filtre le classement sur ce club.
- **FR-020**: Chaque part de la carte des catégories MUST être un contrôle activable qui
  filtre le classement sur cette catégorie.
- **FR-021**: Un filtre actif MUST être représenté par un repère nommant la valeur
  filtrée, retirable indépendamment des autres sélections, sur le motif déjà en service
  pour la recherche du classement.
- **FR-022**: L'API de lecture MUST accepter un filtre par club et un filtre par catégorie
  sur le classement d'une épreuve, cumulables entre eux, avec la recherche par nom et avec
  la portée club.
- **FR-023**: Ces nouveaux paramètres MUST être facultatifs et sans effet quand ils sont
  absents : le contrat publié de `/api/v1` ne change pas pour les appelants existants.
- **FR-024**: Le classement filtré MUST annoncer le nombre de résultats de la sélection
  face au total de l'épreuve.
- **FR-025**: L'état d'absence d'un classement filtré MUST nommer le filtre en cause et
  offrir le retour au classement entier ; il MUST NOT parler de recherche quand aucune
  recherche n'est active.
- **FR-026**: Les filtres actifs MUST vivre dans l'adresse de la page, de sorte qu'un lien
  partagé restitue la même sélection.
- **FR-027**: Un code de catégorie affiché MUST donner accès à son libellé complet sans
  quitter la page.
- **FR-028**: Cet accès MUST être utilisable au doigt et au clavier, pas seulement au
  survol de la souris.
- **FR-029**: Un code absent de la table de correspondance MUST rester affiché tel quel,
  sans libellé inventé.

#### Contraintes transverses

- **FR-030**: Aucune règle d'identité visuelle ne MUST être rouverte : ni palette, ni
  couple typographique, ni dégradé.
- **FR-031**: Les nouveaux contrôles MUST respecter le plancher de cible tactile déjà en
  vigueur dans le produit.
- **FR-032**: Tout changement de contenu du classement provoqué par un filtre MUST être
  annoncé au lecteur d'écran par le mécanisme d'annonce déjà en place.

### Key Entities

- **Épreuve** : porte un verdict de fiabilité et un relevé d'anomalies (code → nombre).
  Ces deux informations existent déjà et sont publiées ; ce lot les lit, il n'en produit
  aucune.
- **Synthèse d'épreuve** : agrégats portant sur l'épreuve **entière**, indépendants de la
  recherche et des filtres en cours. Elle publie un extrait des catégories et des clubs
  ainsi que le dénominateur total des catégories — c'est cet écart entre extrait et
  dénominateur que ce lot rend visible.
- **Ligne de classement** : un participant, son temps total et ses temps intermédiaires.
  L'écart entre le total et la somme des intermédiaires est une propriété **dérivée**,
  jamais stockée — mais calculée **une seule fois**, du côté qui voit toutes les lignes,
  et non recalculée à l'affichage (cf. `FR-011`).
- **Référence d'écart de l'épreuve** : l'écart typique de ses lignes, qui distingue « le
  chronométreur ne publie pas ce segment » (toutes les lignes s'écartent pareil) de
  « cette ligne est fausse » (elle s'écarte de ses voisines). Nouvelle, et calculée sur
  l'épreuve entière — donc hors de portée d'un écran qui ne reçoit que vingt lignes.
- **Sélection du classement** : l'ensemble des restrictions actives — recherche par nom,
  portée club, club, catégorie. Elle vit dans l'adresse et détermine à la fois les lignes
  rendues et les repères affichés.
- **Table des catégories** : correspondance entre un code de catégorie et son libellé
  complet. Nouvelle, et de portée volontairement limitée aux codes réellement rencontrés.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur toute épreuve, la somme des parts affichées dans la répartition par
  catégorie vaut 100 %, aux arrondis d'affichage près — le cas mesuré à 86,1 % sur la
  course 214 ne se reproduit sur aucune épreuve.
- **SC-002**: Aucune carte de synthèse ne rend d'en-tête de colonnes au-dessus d'une liste
  vide.
- **SC-003**: 100 % des épreuves portant au moins une anomalie de fiabilité l'annoncent
  sur leur page **et** sur leur ligne dans la liste des épreuves.
- **SC-004**: La ligne de tête de la course 214 — 31 s + 34 s + 19 min 18 s pour
  1 h 06 min 18 s, soit **69,3 % d'écart** — est signalée, et un test la fige en fixture
  pour que la règle ne puisse pas cesser de la capter sans que la suite le dise.
- **SC-005**: Sur les 4 150 lignes évaluables de la base de dev, **aucune** ne porte de
  marqueur d'écart : le taux de fausse alerte mesuré est nul, contre **8,02 % (333 lignes,
  dont 285 sur une seule épreuve saine)** avec le seuil de 2 % proposé par l'audit.
- **SC-006**: Les 5 épreuves sur 25 dont les inters ne couvrent pas tout le parcours le
  disent **une fois** en tête de page, et non sur chacune de leurs lignes.
- **SC-007**: Depuis une carte de synthèse, voir les participants d'un club ou d'une
  catégorie demande **une seule activation**, contre aucun chemin possible aujourd'hui.
- **SC-008**: Un visiteur qui ne connaît pas la nomenclature peut obtenir le libellé
  complet de n'importe quel code de catégorie affiché, sur écran tactile comme au clavier.
- **SC-009**: Un lien partagé vers un classement filtré restitue exactement la même
  sélection chez son destinataire.
- **SC-010**: Les appelants existants de l'API de lecture obtiennent des réponses
  inchangées quand ils n'emploient pas les nouveaux paramètres.

## Assumptions

- **La donnée de fiabilité est prise telle quelle.** `is_reliable` et `quality_issues`
  sont produits par le serveur et publiés ; ce lot ne rejuge ni leur calcul, ni leur
  seuil. Si le verdict est faux, c'est un sujet distinct.
- **Le seuil de 2 % de l'audit est écarté**, et remplacé par la règle établie dans
  `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md` : mesuré sur les 4 150
  lignes évaluables de la base de dev, il signalait 8,02 % du classement, dont 285 lignes
  d'une épreuve que le produit tient pour fiable. Le sondage **prime** sur l'audit, la spec
  et le plan ; toute divergence se retranche en re-sondant.
- **La captation reste établie par le cas de l'audit, pas par la base de dev.** La
  règle retenue signale zéro ligne sur la base de dev — donc zéro fausse alerte, mais
  aucune preuve qu'elle capte. Le cas de la course 214 (69,3 % d'écart) doit être figé en
  fixture, et le seuil re-sondé sur la base de production avant d'être tenu pour calibré.
- **La garde du split illisible n'est pas dans ce lot.** Elle a été posée par #472, close,
  et le classement rend déjà « — ⚠ » sur une valeur non parsable. Ce lot s'y adosse et ne
  la duplique pas.
- **Le motif de repère retirable et de ligne d'état existe déjà**, livré par le lot #485
  pour la recherche du classement. Les filtres club et catégorie s'y branchent plutôt que
  d'inventer un second motif.
- **La marque de fiabilité dans la liste des épreuves fait partie du périmètre**, bien
  qu'elle touche un autre écran que `/courses/[id]` : l'entrée `RES-10` la nomme
  explicitement, et la scinder laisserait le même défaut sur l'écran le plus visité.
- **Le détail de participation n'est pas dans le périmètre** de la marque de fiabilité,
  bien que l'audit note qu'il ne la lit pas non plus : cet écran vient d'être repris par le
  lot #462, et l'y rajouter élargirait la couture de fichiers au-delà de ce qu'un lot
  supporte. À verser à un lot ultérieur si le manque se confirme.
- **La table des libellés de catégorie est bornée aux codes réellement rencontrés** dans
  les données importées, non à la nomenclature fédérale complète. Un code absent se rend
  tel quel.
- **Le nombre de catégories et de clubs affichés ne change pas.** Ce lot rend visible ce
  qui est omis ; il n'élargit pas l'extrait.
- **La synthèse reste indépendante de la sélection.** Filtrer le classement sur un club ne
  doit pas faire tomber l'histogramme ni les répartitions à cette sélection — c'est un
  invariant existant, et les filtres nouveaux ne l'entament pas.

## Dependencies

- **#472 — close** : la garde d'affichage du split non parsable. Prérequis déclaré par
  l'epic, satisfait.
- **#485 — close** : les commandes de liste du classement (repère retirable, ligne d'état,
  saut de page). Les filtres de ce lot s'y adossent.
- **Aucune dépendance sortante** : aucun lot ouvert de l'epic #460 n'attend celui-ci.
