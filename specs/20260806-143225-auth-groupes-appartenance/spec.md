# Feature Specification: Groupes d'appartenance — modéliser avant qu'un groupe porte un droit

**Feature Branch**: `feat-auth-groupes-dappartenance-mod-liser-avant`

**Created**: 2026-08-06

**Status**: Draft

**Input**: issue #197 (sous-issue de l'épique #81), née de la revue de
@MathieuHerrmann sur la PR #193 et de l'arbitrage du 2026-08-05 — voie « issue
sœur jalonnée » plutôt qu'intégration dans #115.

---

## Ce que cette feature livre, et pourquoi maintenant

Un **groupe** dit à quoi on **appartient** : Codir, techniciens, arbitres,
commission bénévolat. Un **rôle** — livré par #115 — dit ce qu'on **peut faire**.
Ce sont deux objets distincts, au sens de GitHub Teams, des user groups Slack ou
d'une OU LDAP.

Trois différences interdisent de détourner les rôles de #115 pour porter
l'appartenance :

- **un groupe existe même vide de droits** — un rôle sans pouvoir n'a aucun sens ;
- **« lister les membres de X »** n'est rendu proprement par aucune agrégation de
  rôles : il faudrait convention-nommer un rôle « codir » et le détourner de sa
  fonction ;
- **l'appartenance et la distribution de droits ont des propriétaires métier
  différents** — le Codir se compose au CA, les droits applicatifs s'attribuent
  par un exploitant.

**Le raisonnement de calendrier est l'inverse exact de celui de #115.** Là-bas,
retarder le modèle coûtait la réécriture de tous les tests de routes gardées.
Ici, **tant qu'un groupe ne porte aucun droit, la table n'intersecte aucune
décision d'accès** : aucun test de garde ne la mentionne, aucune route protégée
ne la lit. Le coût du retard est nul — et il cesse de l'être le jour où un groupe
porte un droit, ou le jour où un écran doit lister les membres d'une commission.
C'est le jalon que cette feature honore, **avant** que l'un des deux se présente.

Corollaire assumé, et c'est la borne de la v1 : cette feature livre un modèle et
son administration, **pas** une capacité nouvelle de la décision d'accès. Le
passage « un groupe porte N rôles, l'union s'applique à ses membres » (patron
GitHub Teams) est hors périmètre et ne se décide pas ici.

---

## Clarifications

### Session 2026-08-06

- Q: Un groupe peut-il être **global**, partagé par toutes les organisations,
  comme un rôle de #115 ? → A: Non. L'organisation d'un groupe est
  **obligatoire**.
- Q: Que fait la suppression d'un groupe qui compte encore des membres ? → A:
  Elle est **refusée**, en nommant le nombre de membres — symétrique du refus de
  #115 sur un rôle encore attribué.

**Ce que la première réponse tranche, et qui se reprend facilement** : le patron
de #115 est repris à la lettre *partout sauf ici*. Un rôle est une **définition
réutilisable** — « validateur » a le même sens dans deux clubs, d'où
`organisation_id` nullable et, comme deux `NULL` sont distincts pour SQLite comme
pour PostgreSQL, l'index partiel double dialecte qui garde son slug. Un groupe
est une **composition**, celle d'un club précis : « Codir » sans club ne désigne
rien. La colonne est donc non nulle, une seule contrainte d'unicité suffit, et
l'appartenance n'a pas à porter d'organisation — le groupe la porte déjà. C'est
la quatrième différence avec les rôles, en plus des trois nommées par #197.

**Ce que la seconde préserve** : la composition d'une commission est une donnée
qu'aucune migration ne reconstitue et qu'aucun autre système ne détient. Le fait
qu'aucun **droit** ne soit perdu ne rend pas la perte indolore — c'est la liste
qui a de la valeur, et c'est précisément ce que cette feature existe pour tenir.
Vider un groupe reste libre et sans aucune restriction (FR-019) : le geste
destructeur en deux temps est le seul coût, et il est explicite.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tenir la composition des commissions (Priority: P1)

Le secrétaire du club crée un groupe « Codir », y ajoute les sept membres élus au
CA, puis en retire un qui démissionne en cours de mandat. Il crée ensuite
« Arbitres » et « Commission bénévolat ». Aucun de ces groupes n'accorde quoi que
ce soit : ils disent qui compose quoi.

**Why this priority**: c'est la capacité entière de la feature. Sans elle,
l'information vit dans un tableur qu'aucun écran du club ne peut lire.

**Independent Test**: créer un groupe, y ajouter deux personnes, en retirer une,
renommer le groupe, et constater que l'appartenance restante a survécu au
renommage.

**Acceptance Scenarios**:

1. **Given** une session portant le pouvoir de composition des groupes, **When**
   elle crée un groupe nommé librement, **Then** le groupe existe et **ne compte
   aucun membre**.
2. **Given** un groupe existant, **When** on le renomme ou change sa description,
   **Then** aucune appartenance n'est perdue.
3. **Given** un groupe existant, **When** on y ajoute un utilisateur déjà membre,
   **Then** l'opération est sans effet et ne crée pas de doublon.
4. **Given** un membre d'un groupe, **When** on l'en retire, **Then** il ne perd
   **rien d'autre** — ni session, ni rôle, ni autre appartenance.
5. **Given** un groupe dont on retire le dernier membre, **When** l'opération
   aboutit, **Then** le groupe subsiste, vide, et **aucune règle ne s'y oppose**.
6. **Given** un groupe portant déjà un slug dans une organisation, **When** on en
   crée un second avec le même slug dans la même organisation, **Then**
   l'opération est rejetée.
7. **Given** un groupe comptant encore des membres, **When** on tente de le
   supprimer, **Then** l'opération est refusée en nommant le nombre de membres.
8. **Given** ce même groupe une fois vidé, **When** on le supprime, **Then**
   l'opération aboutit.

---

### User Story 2 - Lister les membres d'une commission (Priority: P1)

Un exploitant ouvre le groupe « Codir » et obtient la liste nominative de ses
membres. C'est la capacité que l'issue nomme comme irréductible à une agrégation
de rôles, et la seule raison pour laquelle le groupe est un objet et non une
convention de nommage.

**Why this priority**: US1 sans US2 livre une table que personne ne lit. Les deux
forment le MVP.

**Independent Test**: peupler un groupe, demander sa composition, et constater
qu'elle nomme exactement ses membres — sans passer par les rôles, et sans que
l'appelant ait besoin d'un pouvoir de gestion des rôles.

**Acceptance Scenarios**:

1. **Given** une session portant le pouvoir de consultation des groupes, **When**
   elle demande la liste des groupes, **Then** elle l'obtient.
2. **Given** cette même session, **When** elle demande un groupe précis, **Then**
   elle obtient ses membres.
3. **Given** une session portant le **seul** pouvoir de consultation des groupes,
   **When** elle tente de créer un groupe ou d'y ajouter quelqu'un, **Then**
   l'accès est refusé pour autorisation insuffisante (403).
4. **Given** aucune session, **When** on demande la liste des groupes, **Then**
   l'accès est refusé pour absence de session (401), **jamais** 403.

---

### User Story 3 - Savoir à quoi on appartient (Priority: P2)

Un membre connecté voit ses appartenances dans la description de sa session,
comme il y voit déjà ses rôles depuis #115 — sans appel supplémentaire, et sans
qu'aucun pouvoir lui soit exigé pour se lire lui-même.

**Why this priority**: c'est ce qui rendra un futur écran capable d'écrire
« membre du Codir » sans un second appel que l'intéressé n'aurait pas le droit de
faire. La valeur est réelle mais dépend de US1 pour exister.

**Independent Test**: ajouter un utilisateur à deux groupes, ouvrir une session
en son nom, et constater que la description de sa session nomme les deux — puis
le retirer d'un groupe et constater le changement **à la requête suivante**, sans
reconnexion.

**Acceptance Scenarios**:

1. **Given** une session d'un utilisateur membre de deux groupes, **When** elle
   se décrit, **Then** les deux groupes y figurent.
2. **Given** une session d'un utilisateur membre d'aucun groupe, **When** elle se
   décrit, **Then** le champ est vide et la réponse reste valide.
3. **Given** un consommateur existant de la description de session, **When** le
   champ des groupes s'y ajoute, **Then** rien de ce qu'il lisait ne change de
   forme ni de sens.

---

### User Story 4 - Un groupe n'accorde rien (Priority: P1)

Un exploitant crée un groupe, y met un utilisateur, et **rien** ne change pour
lui : pas un pouvoir de plus, pas une ressource de plus franchie. C'est ce qui
borne cette feature à sa v1 et rend son retard gratuit jusqu'ici.

**Why this priority**: c'est la garantie qui autorise à livrer le modèle sans
toucher au mécanisme de décision de #115. Sans elle vérifiée, la feature aurait
dû être instruite comme une modification du contrôle d'accès.

**Independent Test**: donner à un utilisateur sans aucun rôle l'appartenance à
tous les groupes existants, et constater qu'il est refusé exactement sur les
mêmes ressources qu'avant.

**Acceptance Scenarios**:

1. **Given** un utilisateur sans rôle, membre de tous les groupes, **When** il
   appelle une ressource protégée quelconque, **Then** il est refusé (403).
2. **Given** l'application entière, **When** on cherche une décision d'accès qui
   consulte les groupes, **Then** il n'en existe aucune — vérifié
   automatiquement, pas par lecture.
3. **Given** le pouvoir d'attribuer les appartenances, **When** son porteur
   ajoute quelqu'un à un groupe, **Then** aucune règle de non-amplification ne
   s'applique : il n'y a aucun pouvoir à amplifier.

---

### Edge Cases

- **Un utilisateur est supprimé.** Ses appartenances disparaissent avec lui
  (AC5). Le groupe subsiste, avec un membre de moins.
- **Un compte est désactivé.** Ses appartenances **dorment mais restent** : elles
  ne décident rien, il n'y a donc rien à protéger. La réactivation les rend
  telles quelles.
- **Un groupe est vidé entièrement.** Aucun invariant ne s'y oppose — vider un
  groupe ne verrouille personne dehors, contrairement au dernier administrateur
  de #115.
- **Un utilisateur appartient à plusieurs groupes.** État normal, sans union ni
  agrégation à calculer : il n'y a rien à unir.
- **Deux exploitants ajoutent le même membre simultanément.** Idempotent : une
  seule appartenance, jamais un doublon ni une erreur exposée.
- **Un membre est retiré pendant qu'il est connecté.** Sa session n'est **pas**
  invalidée : rien de ce qu'il peut faire n'en dépend. La description de sa
  session change à la requête suivante.
- **Une ressource de groupe est ajoutée sans garde.** Le filet de #115 doit la
  refuser, exactement comme pour les rôles.
- **Un groupe est supprimé alors qu'il compte des membres.** Refus, en nommant le
  nombre de membres (FR-011). Le vider d'abord est libre, et le refus tombe.

---

## Requirements *(mandatory)*

### Groupes et appartenances

- **FR-001**: Le système DOIT distinguer le **groupe** (à quoi on appartient) du
  **rôle** de #115 (ce qu'on peut faire). Aucune relation NE DOIT exister entre
  les deux objets dans cette feature.
- **FR-002**: Un groupe DOIT porter un identifiant stable, un libellé
  renommable, une description facultative, et l'**organisation** à laquelle il
  appartient. Cette organisation est **obligatoire** : un groupe global n'a pas
  de sens, là où un rôle global en a un (#115).
- **FR-003**: Les groupes DOIVENT être créables, modifiables et supprimables
  **sans redéploiement**, comme les rôles de #115.
- **FR-004**: Un groupe DOIT pouvoir exister **vide** — sans membre, et sans
  qu'aucun droit ne lui soit attaché. C'est ce qui le distingue d'un rôle.
- **FR-005**: Aucun groupe NE DOIT être livré avec l'application. La composition
  d'un Codir est une donnée d'exploitation qu'aucune migration ne devine, et un
  groupe semé « pour l'exemple » serait à supprimer à la main sur la seule
  installation qui existe.
- **FR-006**: Le libellé et la description d'un groupe DOIVENT être modifiables
  sans perdre aucune appartenance. Son identifiant stable NE DOIT PAS être
  modifiable.
- **FR-007**: Deux groupes d'une même organisation NE DOIVENT PAS porter le même
  identifiant stable.
- **FR-008**: Une appartenance DOIT être **unique et idempotente** : ajouter deux
  fois le même membre au même groupe NE DOIT ni créer de doublon, ni échouer.
- **FR-009**: Retirer un membre d'un groupe NE DOIT rien retirer d'autre — ni
  session, ni rôle, ni autre appartenance.
- **FR-010**: La suppression d'un utilisateur DOIT emporter ses appartenances.
- **FR-011**: La suppression d'un groupe **encore peuplé** DOIT être **refusée**,
  en nommant le nombre de membres — symétrique de la règle de #115 sur un rôle
  encore attribué. Aucun droit n'est pourtant perdu : ce qu'on protège est la
  **composition**, donnée qu'aucune migration ne reconstitue. Vider le groupe au
  préalable reste libre (FR-019).
- **FR-012**: Le système DOIT rendre la composition d'un groupe — la liste
  nominative de ses membres — en une seule ressource. C'est la capacité qui
  justifie l'objet.
- **FR-013**: Créer un groupe ou une appartenance NE DOIT exiger aucune migration
  des données existantes.

### Pouvoirs et décision d'accès

- **FR-014**: Trois pouvoirs DOIVENT s'ajouter à l'inventaire de #115 —
  consulter, composer et attribuer les groupes — **sans aucune modification de
  son mécanisme de décision**.
- **FR-015**: Chaque ressource de groupe DOIT nommer le pouvoir qu'elle exige, et
  être gardée route par route. Les issues 401 (sans session) et 403 (session sans
  pouvoir) restent celles de #115 et NE DOIVENT PAS être confondues.
- **FR-016**: **Aucune décision d'accès NE DOIT consulter les groupes**, et cette
  absence DOIT être vérifiée automatiquement. C'est la borne de la v1 : elle
  cesse le jour où un groupe porte un rôle, et ce jour-là est une autre issue.
- **FR-017**: Un groupe NE DOIT porter aucun caractère d'administration — il n'y
  a pas d'équivalent de `is_superuser` pour un objet qui n'accorde rien.
- **FR-018**: Aucune règle de non-amplification NE DOIT s'appliquer aux
  appartenances : il n'y a aucun pouvoir à amplifier. Ajouter ou retirer un
  membre n'exige que le pouvoir d'attribution.
- **FR-019**: Aucun invariant de dernier membre NE DOIT exister. Un groupe peut
  être vidé entièrement — cela ne verrouille personne dehors.
- **FR-020**: Le filet d'inventaire des routes de #115 DOIT classer les nouvelles
  ressources : gardées, ou déclarées publiques nommément. Aucune NE DOIT être
  publique.
- **FR-021**: Le filet de catalogue de #115 DOIT constater que chacun des trois
  pouvoirs est vérifié par au moins une garde.

### Exposition et audit

- **FR-022**: La description de la session en cours DOIT rendre les groupes de
  son porteur, **en champ additif** : les consommateurs actuels NE DOIVENT
  constater aucun changement de forme ni de sens. Cette lecture N'EXIGE aucun
  pouvoir — elle ne porte que sur soi-même, comme les rôles de #115.
- **FR-023**: Toute création, modification ou suppression de groupe, et tout
  ajout ou retrait de membre, DOIT être journalisée avec l'auteur, la cible et le
  sens de l'opération, dans la même forme que #115.

### Key Entities

- **Groupe** : un nom d'appartenance dans une organisation — Codir, arbitres,
  commission bénévolat. Porte un identifiant stable, un libellé renommable et une
  description. **N'accorde rien.**
- **Appartenance** : cette personne est membre de ce groupe. Unique par couple.
  Ne porte pas d'organisation : celle-ci est portée par le groupe.

---

## Success Criteria *(mandatory)*

- **SC-001**: un exploitant crée un groupe, le peuple, le renomme et retire un
  membre **sans redéploiement**, et sans qu'aucune migration soit nécessaire.
- **SC-002**: la composition d'un groupe est obtenue en une seule demande, et
  nomme exactement ses membres.
- **SC-003**: 100 % des ressources de groupe refusent un visiteur anonyme et un
  utilisateur sans le pouvoir exigé, vérifié par le contrôle **dérivé de
  l'application** de #115, pas par une liste tenue à la main.
- **SC-004**: chacun des trois pouvoirs de groupe est vérifié par au moins une
  ressource, et aucune ressource n'exige un pouvoir inexistant — vérifié
  automatiquement.
- **SC-005**: appartenir à tous les groupes ne fait franchir **aucune** ressource
  qu'on ne franchissait pas déjà.
- **SC-006**: aucune décision d'accès de l'application ne lit les groupes,
  vérifié automatiquement.
- **SC-007**: un membre connecté connaît ses appartenances sans appel
  supplémentaire, et un changement lui parvient à la requête suivante, sans
  reconnexion.
- **SC-008**: la suppression d'un utilisateur ne laisse aucune appartenance
  orpheline.
- **SC-009**: aucune réponse existante de l'application ne change de forme.

---

## Assumptions

- **L'organisation est portée par le groupe, et par lui seul.** Un rôle peut être
  global, donc son attribution doit dire dans quel club elle vaut ; un groupe ne
  le peut pas (arbitrage du 2026-08-06), donc son appartenance n'a nulle part où
  varier et ne porte pas d'organisation.
- **La lecture se présente sous deux formes** — la liste des groupes et le détail
  d'un groupe avec ses membres — servies par le même pouvoir de consultation.
  Compter cela pour deux ressources plutôt qu'une ne change rien au périmètre :
  #115 sépare déjà de la même façon la liste et le détail d'un rôle.
- **Aucun écran n'est livré.** Les ressources existent et sont utilisables ; les
  écrans relèvent de l'épique #81 et n'exigeront aucune modification du modèle.
- **L'audit reste dans les journaux applicatifs**, pas dans une table — décision
  héritée de #115, que cette feature ne rouvre pas.
- **Une appartenance ne se périme pas.** Pas de « membre du Codir jusqu'en
  juin » : une appartenance dure jusqu'à son retrait. Même arbitrage que pour les
  attributions de #115.
- **Les groupes ne sont pas cloisonnés par organisation à la lecture**, pour la
  même raison que les rôles : il y a une organisation en donnée, et aucune
  ressource n'est cloisonnée par club dans le projet à ce jour.

---

## Dependencies

- **#115 (livré, sur cette branche)** : fournit l'inventaire des pouvoirs, le
  mécanisme de garde route par route, le filet d'inventaire des routes, le filet
  de catalogue et le patron de table `(organisation, slug, name, description)`.
  Cette feature **n'en modifie rien** — elle s'y ajoute.
- **#114 (livré)** : sessions, utilisateur courant, refus en 401. La description
  de session est enrichie d'un champ, le parcours de connexion n'est pas touché.
- **#81 (épique Panel Admin)** : les écrans de gestion des groupes en dépendront.
- **Débloque** la v2 « un groupe porte N rôles » — qui, elle, entre dans la
  décision d'accès et exige que cette modélisation existe déjà.

---

## Out of Scope

- **Attacher des rôles à un groupe** (patron GitHub Teams), et l'union de leurs
  pouvoirs appliquée aux membres. C'est ce passage qui ferait entrer les groupes
  dans la décision d'accès ; il ne se décide pas ici, et FR-016 verrouille son
  absence par un test.
- **Les groupes imbriqués** (un groupe membre d'un autre).
- **Les écrans d'administration des groupes** — épique #81.
- **Le semis de groupes livrés avec l'application** (FR-005).
- **Les appartenances qui expirent**, et toute notion de mandat daté.
- **Le rapprochement avec `scope=club`** — un prédicat sur un libellé scrapé,
  toujours sans rapport avec une relation applicative (#95).
- **Un rôle de membre au sein d'un groupe** (« président du Codir ») : un groupe
  dit qui en est, pas qui y fait quoi.
