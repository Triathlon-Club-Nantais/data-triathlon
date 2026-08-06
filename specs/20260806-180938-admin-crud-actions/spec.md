# Feature Specification: Actions d'administration sur les épreuves, les athlètes et les résultats

**Feature Branch**: `feat-admin-actions-crud-sur-les-courses-athl-tes`

**Created**: 2026-08-06

**Status**: Draft

**Input**: issue #117 — sous-issue de l'épique #81 (Panel Admin), dépend de #115 (RBAC, livré) et #116 (écran de connexion, livré).

## Contexte

Toutes les données du site arrivent par une seule porte : l'import automatique
d'une épreuve à partir de son URL de chronométrage. Cette porte n'a aucune
sortie de secours. Aujourd'hui, un administrateur qui constate une erreur
— une épreuve importée depuis une mauvaise URL, un coureur dont le scraper a
mal lu le nom, un résultat rattaché à un homonyme — n'a aucun moyen d'agir
depuis l'application : il faut ouvrir la base de production à la main.

Cette feature ouvre quatre gestes correctifs, et quatre seulement, avec une
contrepartie : **chacun laisse une trace nominative et datée**.

## Clarifications

### Session 2026-08-06

- Q: Comment l'administrateur désigne-t-il le coureur de destination lors d'un rattachement de résultat ? → A: Une recherche réservée aux administrateurs, restituant ce qui distingue deux fiches homonymes (identité complète dont date de naissance, club, nombre de résultats). Les dates de naissance restent hors des routes publiques.
- Q: Avant de confirmer une suppression d'épreuve, que doit annoncer la modale au sujet des fiches coureur purgées ? → A: Avant. La confirmation annonce l'épreuve, le nombre de résultats **et** le nombre de fiches coureur qui disparaîtront — l'ampleur annoncée doit être l'ampleur réelle, puisqu'il n'y a pas de retour en arrière.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retirer une épreuve importée par erreur (Priority: P1)

Un administrateur repère dans le catalogue une épreuve qui n'aurait jamais dû
y entrer : URL de chronométrage erronée, épreuve d'un autre club, doublon d'une
épreuve déjà présente sous un autre libellé. Il la supprime, et tous les
résultats qu'elle portait disparaissent avec elle — une épreuve sans ses
résultats n'a aucun sens, et des résultats sans leur épreuve fausseraient les
statistiques du club.

**Why this priority**: c'est le seul défaut de la chaîne d'import qui
**pollue durablement les chiffres publics** du club (nombre d'épreuves,
podiums, classements). Les deux autres gestes corrigent une donnée ; celui-ci
retire du bruit que rien d'autre ne sait retirer.

**Independent Test**: importer une épreuve de test, la supprimer depuis le
back-office, vérifier qu'elle a disparu du catalogue public **et** que ses
résultats ne sont plus comptés nulle part. Livrable seul.

**Acceptance Scenarios**:

1. **Given** une épreuve portant N résultats, **When** l'administrateur la
   supprime et confirme, **Then** l'épreuve et ses N résultats ont disparu, et
   les statistiques du club ne les comptent plus.
2. **Given** l'écran de suppression, **When** l'administrateur déclenche la
   suppression, **Then** une confirmation explicite lui est demandée, nommant
   l'épreuve, le nombre de résultats et le nombre de fiches coureur qui seront
   détruits.
3. **Given** une épreuve dont certains coureurs n'ont couru qu'elle, **When**
   l'administrateur ouvre la confirmation, **Then** le nombre annoncé de fiches
   coureur correspond exactement à celui effectivement supprimé.
4. **Given** une suppression confirmée, **When** l'administrateur cherche à
   revenir en arrière, **Then** aucune annulation n'est proposée, mais
   l'opération figure au journal d'audit avec son auteur et sa date.
5. **Given** une épreuve déjà supprimée (ou un identifiant inconnu), **When**
   la suppression est rejouée, **Then** le système répond « introuvable » en
   français, sans erreur technique.

---

### User Story 2 - Rattacher un résultat au bon coureur (Priority: P2)

Le scraper identifie un coureur par son nom, son prénom et sa date de
naissance. Quand la source écrit « J. Dupont » ici et « Jean Dupont » là, deux
fiches coureur naissent pour une seule personne, et l'historique se coupe en
deux. L'administrateur rattache le résultat mal placé à la bonne fiche.

**Why this priority**: c'est le besoin nommé explicitement par le demandeur sur
l'épique #81 (« pouvoir associer le résultat d'une course à un coureur »).
Il vient après P1 parce qu'il corrige un historique individuel, quand P1
corrige les chiffres publics du club.

**Independent Test**: créer deux fiches coureur pour une même personne,
déplacer un résultat de l'une vers l'autre, vérifier que la fiche cible
affiche désormais ce résultat et que la fiche source ne l'affiche plus.
Livrable seul.

**Acceptance Scenarios**:

1. **Given** un résultat rattaché au coureur A, **When** l'administrateur le
   rattache au coureur B, **Then** le résultat apparaît dans l'historique de B
   et disparaît de celui de A.
2. **Given** un rattachement effectué, **When** on consulte le journal
   d'audit, **Then** l'opération y figure avec l'auteur, le résultat concerné,
   le coureur d'origine et le coureur de destination.
3. **Given** un coureur de destination inexistant, **When** le rattachement est
   demandé, **Then** il est refusé avec un message français explicite et rien
   n'est modifié.
4. **Given** un résultat déjà rattaché au coureur visé, **When** le
   rattachement est redemandé, **Then** l'opération est sans effet et ne crée
   pas d'incohérence.

---

### User Story 3 - Corriger l'identité d'un coureur (Priority: P3)

Une fiche coureur porte un nom tronqué, un prénom en majuscules accidentelles
ou une date de naissance absente parce que la source ne la publiait pas.
L'administrateur corrige ces trois champs depuis le back-office.

**Why this priority**: gêne cosmétique dans la plupart des cas, mais c'est le
geste le plus risqué des trois — l'identité d'un coureur est aussi la clé qui
empêche les doublons. Il vient donc en dernier, une fois les deux autres
stabilisés.

**Independent Test**: renommer un coureur depuis le back-office et vérifier que
son nom corrigé s'affiche partout où il apparaissait. Livrable seul.

**Acceptance Scenarios**:

1. **Given** une fiche coureur, **When** l'administrateur corrige son nom, son
   prénom ou sa date de naissance et valide, **Then** la correction est visible
   sur toutes les pages qui affichent ce coureur, et son historique de
   résultats est intact.
2. **Given** une correction qui rendrait la fiche identique à une autre fiche
   existante (mêmes nom, prénom et date de naissance), **When**
   l'administrateur valide, **Then** la modification est refusée avec un
   message français nommant la fiche en conflit, et rien n'est modifié.
3. **Given** une correction validée, **When** on consulte le journal d'audit,
   **Then** l'opération y figure avec l'auteur et les valeurs avant/après.

---

### User Story 4 - Corriger le libellé d'une épreuve (Priority: P4)

Les sources de chronométrage nomment la même course différemment d'une année à
l'autre, se trompent de date, ou publient un type d'épreuve incohérent avec ce
qui a été couru. L'administrateur corrige le nom, la date, le type et le
caractère relais de l'épreuve.

**Why this priority**: c'est le geste le plus lourd de conséquences des quatre
— ces quatre champs **sont** la clé qui distingue deux épreuves l'une de
l'autre, et une correction mal faite fusionne ou dédouble un pan du catalogue.
Il vient en dernier parce qu'il exige que les trois autres, et surtout leur
journal d'audit, soient déjà éprouvés.

**Independent Test**: renommer une épreuve depuis le back-office et vérifier
que le catalogue public, ses résultats et les statistiques suivent le nouveau
libellé sans qu'aucun résultat ne change de main. Livrable seul.

**Acceptance Scenarios**:

1. **Given** une épreuve, **When** l'administrateur corrige son nom, sa date,
   son type ou son caractère relais et valide, **Then** la correction est
   visible partout où l'épreuve apparaît, et ses résultats lui restent tous
   rattachés.
2. **Given** une correction qui rendrait l'épreuve identique à une autre
   épreuve existante (mêmes nom, date, type et caractère relais), **When**
   l'administrateur valide, **Then** la modification est refusée avec un
   message français nommant l'épreuve en conflit, et rien n'est modifié.
3. **Given** une correction validée, **When** on consulte le journal d'audit,
   **Then** l'opération y figure avec l'auteur et les valeurs avant/après.
4. **Given** une correction du type d'épreuve, **When** elle est validée,
   **Then** les statistiques et les filtres par discipline reflètent le
   nouveau type.

---

### Edge Cases

- **Une fiche coureur qui perd son dernier résultat** (suppression d'épreuve ou
  rattachement) est supprimée dans la foulée — voir FR-022. Le geste admin ne
  doit pas fabriquer lui-même les fiches fantômes que la feature sert à
  résorber.
- **Une épreuve supprimée dont l'URL de chronométrage est réimportée** revient
  dans le catalogue, avec ses résultats. C'est le comportement attendu de la
  chaîne d'import, pas un défaut : la suppression retire une donnée, elle
  n'interdit pas une source. L'écran de confirmation ne doit donc pas laisser
  croire à un bannissement définitif de l'URL.
- **Une correction d'épreuve qui la rend identique à ce que produirait un
  import** : le prochain import se rattachera à l'épreuve corrigée au lieu d'en
  créer une nouvelle. Attendu, et c'est même l'usage principal du geste
  (résorber un doublon de libellé).
- **Deux fiches coureur réellement homonymes** (mêmes nom et prénom, même club,
  personnes différentes) : le sélecteur doit donner de quoi les départager
  — date de naissance et nombre de résultats — sinon le geste censé résorber un
  doublon fusionne deux personnes distinctes, sans annulation possible.
- **Rattachement d'un résultat vers un coureur qui court déjà cette épreuve** :
  la même personne se retrouverait deux fois classée sur la même course. Le
  système doit refuser plutôt que produire une incohérence visible publiquement.
- **Deux administrateurs agissent en même temps** sur la même épreuve : le
  second reçoit « introuvable », pas une erreur technique.
- **Correction d'identité vidant un champ obligatoire** (nom ou prénom vide,
  espaces seuls) : refusée.
- **Utilisateur connecté mais sans le pouvoir requis** : l'action est refusée
  côté serveur, et le bouton correspondant n'est pas proposé côté écran.
- **Journal d'audit et suppression** : la trace d'une épreuve supprimée doit
  rester lisible après la disparition de l'épreuve — le journal ne peut pas
  dépendre de l'existence de ce qu'il décrit.

## Requirements *(mandatory)*

### Functional Requirements

**Gestes**

- **FR-001**: Un administrateur habilité DOIT pouvoir supprimer définitivement
  une épreuve du catalogue.
- **FR-002**: La suppression d'une épreuve DOIT emporter la totalité des
  résultats qu'elle porte, sans laisser de résultat orphelin.
- **FR-003**: Un administrateur habilité DOIT pouvoir rattacher un résultat
  existant à un autre coureur existant.
- **FR-004**: Un administrateur habilité DOIT pouvoir corriger le nom, le
  prénom et la date de naissance d'un coureur.
- **FR-005**: Le système DOIT refuser une correction d'identité qui rendrait
  deux fiches coureur identiques sur le triplet (nom, prénom, date de
  naissance), et l'annoncer par un message en français désignant la fiche en
  conflit.
- **FR-006**: Le système DOIT refuser un rattachement vers un coureur qui
  possède déjà un résultat sur la même épreuve.
- **FR-007**: Le système DOIT refuser toute action portant sur une entité
  inexistante par un message « introuvable » en français.
- **FR-008**: Le système NE DOIT PAS offrir la modification des temps, des
  rangs ou du statut d'un résultat, ni la création manuelle d'une épreuve, ni
  la suppression en masse — hors périmètre (voir *Hors périmètre*).
- **FR-020**: Un administrateur habilité DOIT pouvoir corriger le nom, la date,
  le type et le caractère relais d'une épreuve.
- **FR-021**: Le système DOIT refuser une correction d'épreuve qui rendrait
  deux épreuves identiques sur le quadruplet (nom, date, type, relais), et
  l'annoncer par un message en français désignant l'épreuve en conflit.
- **FR-022**: Toute fiche coureur qui perd son dernier résultat du fait d'une
  action de cette feature DOIT être supprimée dans la même opération.
- **FR-023**: Une correction d'épreuve NE DOIT modifier aucun résultat : ni
  leur rattachement, ni leurs temps, ni leurs rangs.
- **FR-024**: Le système DOIT offrir une recherche de coureurs **réservée aux
  administrateurs**, restituant pour chaque fiche ce qui la distingue d'une
  homonyme : identité complète (dont la date de naissance), club et nombre de
  résultats. C'est elle qui alimente le choix du coureur de destination d'un
  rattachement.
- **FR-025**: La date de naissance d'un coureur NE DOIT PAS être exposée par
  une lecture accessible sans habilitation.

**Habilitation**

- **FR-009**: Chacun des quatre gestes DOIT être protégé individuellement par
  un pouvoir dédié, vérifié côté serveur, jamais par un préfixe d'URL commun.
- **FR-010**: Les pouvoirs ajoutés DOIVENT apparaître dans l'inventaire des
  pouvoirs offert à la composition des rôles, avec un libellé et une
  description en français.
- **FR-011**: L'interface NE DOIT PAS proposer un geste que l'utilisateur
  connecté n'a pas le pouvoir d'accomplir.

**Traçabilité**

- **FR-012**: Chaque geste réussi DOIT être consigné dans un journal d'audit
  avec, au minimum : l'auteur, la nature de l'action, le type et l'identifiant
  de l'entité visée, et l'horodatage. Une demande qui ne change rien — rattacher
  un résultat au coureur qui le porte déjà — **n'est pas un geste** : elle
  réussit sans rien consigner. Le journal ne se remplit pas de non-événements.
- **FR-013**: Le journal DOIT conserver le contexte utile à la relecture d'une
  action (valeurs avant/après pour une correction, coureur d'origine et de
  destination pour un rattachement, désignation de l'épreuve et nombre de
  résultats détruits pour une suppression, fiches coureur purgées par
  ricochet).
- **FR-014**: Une entrée du journal DOIT rester lisible après la disparition de
  l'entité qu'elle décrit.
- **FR-015**: Une action refusée NE DOIT PAS produire d'entrée au journal, et
  NE DOIT rien modifier.

**Interface**

- **FR-016**: Le back-office DOIT offrir un écran listant les épreuves, d'où
  tous les gestes de cette feature sont atteignables — ceux qui portent sur un
  résultat ou sur un coureur en descendant d'une épreuve vers ses résultats,
  puis vers leurs coureurs.
- **FR-017**: Toute action destructive DOIT être précédée d'une confirmation
  explicite nommant ce qui va être détruit et son ampleur **réelle** : pour une
  suppression d'épreuve, son libellé, le nombre de résultats **et** le nombre de
  fiches coureur qui disparaîtront par ricochet (FR-022).
- **FR-026**: Le système DOIT pouvoir chiffrer l'impact d'une suppression
  d'épreuve **avant** de l'exécuter, sans rien modifier.
- **FR-018**: L'interface NE DOIT PAS proposer d'annulation après coup : les
  gestes sont irréversibles et c'est le journal d'audit qui en tient lieu de
  garantie.
- **FR-019**: Le résultat de chaque action (succès ou refus) DOIT être
  restitué à l'écran en français.

### Key Entities

- **Épreuve** : une course importée, identifiée par son nom, sa date, son type
  et son caractère relais ; porte des résultats.
- **Coureur** : une personne, identifiée de manière unique par le triplet nom /
  prénom / date de naissance ; porte un historique de résultats.
- **Résultat** : la performance d'un coureur sur une épreuve (rangs, temps,
  club au moment de la course) ; rattaché à exactement un coureur et une
  épreuve.
- **Entrée de journal d'audit** *(nouveau)* : la trace d'une altération
  manuelle — auteur, action, type et identifiant de l'entité, horodatage,
  contexte. Écrite par le système, jamais modifiable.
- **Pouvoir** *(existant, à étendre)* : l'unité d'habilitation vérifiée avant
  chaque geste, attribuée aux rôles.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un administrateur corrige une donnée erronée (les quatre gestes
  confondus) **sans aucun accès direct à la base de données** — l'accès manuel
  en production passe de nécessaire à jamais requis pour ces quatre cas.
- **SC-002**: Chacun des quatre gestes s'accomplit en **moins de 30 secondes**
  et **moins de 5 interactions** depuis l'arrivée sur le back-office.
- **SC-003**: **100 %** des altérations manuelles de données sont retrouvables
  dans le journal d'audit avec leur auteur et leur date.
- **SC-004**: **Aucune** action de cette feature ne peut laisser la base dans
  un état incohérent : ni résultat sans épreuve, ni deux fiches coureur
  identiques, ni deux épreuves identiques, ni deux résultats du même coureur
  sur la même épreuve, ni fiche coureur sans résultat. Vérifié par des tests
  automatisés dédiés à chacun de ces cinq invariants.
- **SC-005**: **Aucun** des quatre gestes n'est accessible à un utilisateur non
  habilité, ni depuis l'interface, ni en sollicitant directement le service.
  Aucune date de naissance n'est lisible sans habilitation (FR-025).
- **SC-006**: Un refus (conflit, entité absente, droit manquant) laisse la base
  **strictement inchangée** dans **100 %** des cas.
- **SC-007**: L'ampleur annoncée avant une suppression (résultats et fiches
  coureur) correspond à l'ampleur constatée après, dans **100 %** des cas.

## Hors périmètre

Exclusions explicites, à traiter en sous-issues séparées si le besoin se
confirme :

- Modifier les temps, les rangs ou le statut d'un résultat — le silence sur les
  valeurs mesurées est délibéré (cf. la note de `AGENTS.md` sur `rescrape-db`).
- Créer manuellement une épreuve — la voie reste l'import. La création manuelle
  d'un **résultat**, elle, existe déjà (pouvoir « Créer un résultat ») et n'est
  pas touchée par cette feature.
- Toute suppression en masse.
- La fusion automatique de deux fiches coureur en doublon (la correction
  d'identité **refuse** le conflit, elle ne le résout pas).
- Un annuaire de coureurs administrable : la correction d'identité part d'un
  résultat d'épreuve. La recherche réservée de FR-024 sert le rattachement, et
  rien d'autre — lui donner un second rôle rendrait cette story dépendante de
  la précédente sans qu'aucun scénario ne l'exige.
- La consultation du journal d'audit depuis une interface : cette feature
  **écrit** le journal ; le lire est un besoin distinct.

## Assumptions

- **Le socle d'habilitation de #115 est réutilisé tel quel** : les quatre
  gestes ajoutent des pouvoirs à l'inventaire existant et n'introduisent aucun
  mécanisme d'autorisation concurrent. L'issue #117 mentionnait une garde par
  rôle (« administrateur ») ; le socle livré vérifie des **pouvoirs**, pas des
  rôles, et c'est cette forme qui fait foi.
- **Des pouvoirs distincts plutôt qu'un seul** : supprimer une épreuve, la
  renommer, corriger une identité et rattacher un résultat ne sont ni le même
  geste ni le même risque — le dépôt sépare déjà « créer un résultat » de
  « supprimer un résultat » pour cette raison. Le découpage exact (un pouvoir
  par geste, ou un pouvoir d'écriture partagé entre les deux corrections)
  relève du plan.
- **La correction d'identité est limitée au triplet identifiant** (nom, prénom,
  date de naissance) ; les autres attributs d'un coureur ne sont pas éditables
  dans ce périmètre.
- **Le journal d'audit est en écriture seule** dans cette feature : pas de
  purge, pas de rétention configurable, pas d'écran de consultation.
- **Une action et sa trace sont indissociables** : si la trace ne peut pas être
  écrite, l'action n'a pas lieu.
- **L'écran d'administration existant est étendu**, pas remplacé : le
  back-office possède déjà une page d'accueil et un écran de signalements.
- **Le volume est celui d'un club** : quelques centaines d'épreuves, gestes
  ponctuels, aucun besoin de traitement par lot ni de pagination sophistiquée
  au-delà de ce que le catalogue offre déjà.

## Décisions tranchées

Deux points ne pouvaient pas être tranchés par défaut. Arbitrés par le
mainteneur le 2026-08-06.

### Q1 — La correction des métadonnées d'une épreuve fait-elle partie du MVP ?

**Oui, sur les quatre champs** (nom, date, type, relais) → *User Story 4*,
FR-020, FR-021, FR-023.

L'issue #117 était contradictoire avec elle-même : sa liste d'actions retenues
en nommait trois, son périmètre technique en citait quatre, et aucun critère
d'acceptation ne couvrait la quatrième. La contradiction est levée en faveur du
périmètre technique — mais le geste porte sur la clé d'unicité des épreuves, il
est donc encadré comme la correction d'identité d'un coureur : refus explicite
en cas de collision, et priorité la plus basse des quatre.

### Q2 — Que deviennent les fiches coureur qui perdent leur dernier résultat ?

**Purge automatique** → FR-022.

Une fiche sans résultat n'est pas fausse, mais elle encombre la recherche de
coureurs et prolonge la vie des doublons que la feature sert justement à
résorber. La purge est le seul choix qui empêche le geste correctif de
fabriquer lui-même le déchet qu'il combat. Le dépôt sait déjà purger les fiches
sans résultat, ce qui écarte l'objection du coût.
