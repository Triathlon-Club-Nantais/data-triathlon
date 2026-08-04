# Feature Specification: RBAC — rôles composables et protection des ressources d'administration

**Feature Branch**: `feat-auth-rbac-r-les-administrateur-validateur-e`

**Created**: 2026-08-04 · **Révisée**: 2026-08-04 (v2)

**Status**: Draft

**Input**: issue #115 (sous-issue de l'épique #81), son commentaire d'arbitrage du 2026-08-02, la discussion GitHub #143, et les arbitrages produit du 2026-08-04.

---

## Ce qui a changé depuis la v1, et ce que ça annule

La v1 de cette spec reposait sur l'arbitrage du 2026-08-02 : une association
`(user, role)` **sans organisation**, deux rôles figés en code, la notion
d'organisation explicitement hors périmètre.

Trois arbitrages produit du 2026-08-04 l'annulent :

1. **Le multi-club se fera** — un rôle est relatif à une organisation. Le modèle
   définitif est posé maintenant, avec une seule organisation en donnée.
2. **Il y aura plus de trois rôles**, et des permissions **par fonctionnalité** —
   donc une indirection rôle → permissions, et non une garde nommant des rôles.
3. **Les rôles sont éditables à chaud** — créés, nommés, composés et supprimés
   depuis l'application, sans redéploiement.

Ce troisième point n'est pas un confort : `render.yaml` porte
`autoDeploy: false`, et les issues **#170** et **#95** (toutes deux ouvertes)
disent que « c'est en code, donc il faut redéployer » est le coût administratif
le plus lourd du projet. Une matrice de droits en dur reconduirait exactement
ce frottement sur l'objet le plus susceptible de changer.

**Ce qui survit de la v1** : la distinction 401 / 403, la garde posée route par
route, le refus d'une garde globale ou de préfixe, le fait que
`POST /admin/pending-providers` soit publique, la commande d'amorçage, et le
modèle du verdict de fiabilité (deux colonnes, composées).

---

## Contexte hérité

Le socle d'authentification (#114, livré) ouvre une session par délégation à
GitHub et dépose l'utilisateur courant derrière une dépendance qui rend **401**
quand aucune session valide n'accompagne la requête. **Aucune route ne s'en sert
encore** : c'est l'objet de cette feature.

Deux faits de terrain structurent tout le reste.

**Le préfixe `/admin/` ne décrit pas l'audience.**
`POST /admin/pending-providers` est le **signalement anonyme** émis par le
formulaire d'ajout d'épreuve du site public quand un visiteur colle une URL dont
le chronométreur n'est pas supporté. Une garde posée sur le préfixe supprimerait
cette fonctionnalité sans que rien ne la nomme.

**Deux routes destructives sont ouvertes à Internet.**
`POST /participations` crée un résultat et `DELETE /participations/{id}` le
supprime, l'une comme l'autre sans aucune authentification. Le filet de #114,
écrit pour prouver l'absence de régression sur le site public, **impose
aujourd'hui qu'elles le restent** — il verrouille l'anomalie au lieu de la
signaler. Les fermer entre dans le périmètre de cette feature.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fermer les ressources d'administration (Priority: P1)

Un exploitant du club consulte les chronométreurs signalés par les visiteurs et
marque comme traités ceux qu'il a instruits ; il corrige aussi à la main des
résultats mal importés. Aujourd'hui, n'importe qui sur Internet peut lire cette
liste, la vider, et supprimer des participations. Après cette feature, seul un
porteur du pouvoir correspondant le peut ; un visiteur anonyme est éconduit comme
non connecté, un utilisateur connecté sans pouvoir comme non autorisé — et les
deux réponses diffèrent, parce qu'elles appellent deux gestes différents : se
connecter, ou demander un droit.

**Why this priority**: c'est la fermeture d'un trou réel, et elle démontre la
chaîne complète — session → rôle → pouvoir → décision — sur laquelle toutes les
sous-issues suivantes de l'épique #81 se brancheront.

**Independent Test**: appeler chaque ressource protégée sans cookie, avec la
session d'un utilisateur sans rôle, puis avec celle d'un administrateur, et
constater trois issues distinctes. Le formulaire public d'ajout d'épreuve
continue de signaler un chronométreur inconnu sans aucune session.

**Acceptance Scenarios**:

1. **Given** aucune session, **When** on demande la liste des chronométreurs
   signalés, **Then** l'accès est refusé pour absence de session (401).
2. **Given** une session valide d'un utilisateur sans aucun rôle, **When** on
   demande cette même liste, **Then** l'accès est refusé pour autorisation
   insuffisante (403), **jamais** 401.
3. **Given** une session d'un porteur du pouvoir correspondant, **When** il
   demande cette liste, **Then** elle est rendue.
4. **Given** aucune session, **When** on supprime une participation, **Then**
   l'accès est refusé (401) — cette route cesse d'être publique.
5. **Given** aucune session, **When** on crée une participation, **Then**
   l'accès est refusé (401).
6. **Given** aucune session, **When** un visiteur colle dans le formulaire public
   une URL de chronométreur non supporté, **Then** le signalement est enregistré
   comme aujourd'hui — cette route **reste publique**.
7. **Given** une session d'un compte désactivé, **When** il appelle une ressource
   protégée, **Then** l'accès est refusé pour absence de session (401) : la
   désactivation ferme la session, le pouvoir n'est même pas consulté.

---

### User Story 2 - Amorcer le premier administrateur hors ligne (Priority: P1)

Une installation neuve n'a aucun administrateur. Personne ne peut donc en nommer
un par l'application : les ressources qui distribuent les rôles exigent
elles-mêmes un pouvoir. L'exploitant amorce le premier depuis la ligne de
commande, sur la machine qui héberge l'application.

**Why this priority**: sans elle, US1 est livrée mais inaccessible. Les deux
forment le MVP.

**Independent Test**: sur une base neuve où un utilisateur s'est connecté une
fois, lancer la commande avec son adresse, puis constater qu'il franchit les
ressources protégées.

**Acceptance Scenarios**:

1. **Given** une base où un utilisateur existe, **When** l'exploitant lance la
   commande d'amorçage avec son adresse et un rôle, **Then** le rôle lui est
   attribué et la commande le confirme en nommant l'utilisateur touché.
2. **Given** un utilisateur qui porte déjà le rôle, **When** la commande est
   relancée, **Then** elle réussit sans créer de doublon et le dit.
3. **Given** une adresse inconnue, **When** la commande est lancée, **Then** elle
   échoue en erreur d'usage, en expliquant qu'un utilisateur naît d'une
   **connexion** et ne se crée pas depuis la ligne de commande.
4. **Given** une adresse portée par **plusieurs** utilisateurs — l'identité
   applicative n'impose aucune unicité d'adresse —, **When** la commande est
   lancée, **Then** elle refuse d'agir au hasard et rend les candidats avec de
   quoi les départager.
5. **Given** n'importe quel état, **When** on cherche à obtenir un premier
   pouvoir par une requête HTTP, **Then** c'est impossible.

---

### User Story 3 - Composer un rôle sans redéploiement (Priority: P1)

Le président du club crée un rôle « Modérateur bénévolat », le nomme, coche ce
qu'il a le droit de faire dans une liste rangée par fonctionnalité, et l'attribue
à deux membres. Aucun développeur n'intervient, aucune mise en production n'a
lieu, et c'est effectif à la requête suivante des intéressés.

**Why this priority**: c'est l'exigence produit qui a fait rouvrir cette spec.
Livrée par l'API dans cette feature, elle sera pilotable par un écran à la
sous-issue d'interface de l'épique #81 — sans migration de données ni
modification du modèle.

**Independent Test**: créer un rôle, lui donner un pouvoir, l'attribuer, vérifier
que le porteur franchit la ressource correspondante et aucune autre, puis retirer
le pouvoir du rôle et vérifier que la ressource lui est refusée à la requête
suivante, **sans reconnexion**.

**Acceptance Scenarios**:

1. **Given** une session d'un porteur du pouvoir de gestion des rôles, **When**
   il crée un rôle nommé librement, **Then** le rôle existe et ne porte aucun
   pouvoir.
2. **Given** un rôle existant, **When** on modifie l'ensemble de ses pouvoirs,
   **Then** le changement s'applique **à la requête suivante** de tous ses
   porteurs, sans reconnexion.
3. **Given** un rôle attribué à au moins une personne, **When** on tente de le
   supprimer, **Then** l'opération est refusée en nommant le nombre de porteurs.
4. **Given** un rôle livré avec l'application, **When** on tente de le supprimer,
   **Then** l'opération est refusée — mais son libellé et ses pouvoirs restent
   modifiables.
5. **Given** un rôle quelconque, **When** on le renomme, **Then** aucune
   attribution n'est perdue.
6. **Given** un pouvoir qui n'existe pas dans l'application, **When** on tente de
   l'ajouter à un rôle, **Then** l'opération est rejetée comme entrée invalide,
   sans rien écrire.
7. **Given** un exploitant qui ne porte **pas** un pouvoir donné, **When** il
   tente de l'accorder à un rôle, **Then** l'opération est refusée : on ne
   distribue que ce qu'on porte soi-même.
8. **Given** une opération quelconque sur les rôles ou les attributions,
   **When** elle aboutit, **Then** elle laisse une trace nommant qui a agi, sur
   quoi, et dans quel sens.

---

### User Story 4 - Ne jamais fermer la porte de l'intérieur (Priority: P1)

Quoi qu'un administrateur fasse depuis l'application — retirer une attribution,
supprimer un rôle, retirer à un rôle son caractère d'administration, se retirer
lui-même —, l'installation conserve au moins un administrateur actif.

**Why this priority**: l'édition à chaud multiplie les façons de se verrouiller
dehors. Sans cette histoire, la réparation passe par un accès direct à la base de
production.

**Independent Test**: avec le compte du seul administrateur, tenter chacune des
quatre opérations et constater un refus explicite à chaque fois ; nommer un
second administrateur, refaire les quatre, et constater qu'elles aboutissent.

**Acceptance Scenarios**:

1. **Given** un unique administrateur actif, **When** il se retire son rôle,
   **Then** l'opération est refusée avec un message qui le dit.
2. **Given** un unique administrateur actif, **When** on supprime le rôle qui le
   rend administrateur, **Then** refus.
3. **Given** un unique administrateur actif, **When** on retire à son rôle le
   caractère d'administration, **Then** refus.
4. **Given** deux administrateurs actifs, **When** l'un se retire, **Then**
   l'opération aboutit.
5. **Given** une installation sans aucun administrateur (obtenue par un chemin
   que l'application ne contrôle pas), **When** l'exploitant lance la commande
   d'amorçage, **Then** elle rétablit la situation sans session.

---

### User Story 5 - Le pouvoir de trancher la qualité (Priority: P2)

Un membre à qui l'on confie le tri de la qualité peut marquer une épreuve comme
fiable ou douteuse, sans pouvoir ni supprimer une donnée, ni instruire les
signalements, ni distribuer des rôles.

**Why this priority**: c'est le premier pouvoir métier distinct de
l'administration, et il donne au système sa démonstration : deux rôles, deux
périmètres réellement différents.

**Independent Test**: avec une session portant le seul pouvoir de qualité,
marquer une épreuve, puis constater un refus sur les signalements et sur la
gestion des rôles.

**Acceptance Scenarios**:

1. **Given** une session portant le pouvoir de qualité, **When** elle marque une
   épreuve comme fiable ou douteuse, **Then** l'opération aboutit et le verdict
   remplace celui calculé.
2. **Given** cette même session, **When** elle appelle une ressource exigeant un
   autre pouvoir, **Then** 403.
3. **Given** un verdict posé à la main, **When** l'épreuve est ré-importée,
   **Then** le verdict humain est conservé et le verdict calculé est rafraîchi.
4. **Given** un verdict posé à la main, **When** il est levé, **Then** l'épreuve
   reprend **immédiatement** son verdict calculé, à jour.

---

### Edge Cases

- **Un utilisateur porte plusieurs rôles.** L'union de leurs pouvoirs s'applique.
- **Un compte est désactivé.** Ses sessions tombent (invariant de #114, une
  jointure), ses rôles dorment, la réactivation les rend. Il ne compte plus comme
  administrateur actif.
- **Un utilisateur est supprimé.** Ses attributions disparaissent avec lui.
- **Un rôle est modifié pendant qu'une session l'utilise.** La décision étant
  prise à chaque requête, le changement s'applique à la requête suivante. Une
  requête déjà en vol s'achève.
- **Un pouvoir est retiré de l'application par une livraison.** Les rôles qui le
  référençaient conservent une ligne inerte : plus rien ne l'interroge. Elle est
  visible et purgeable, jamais bloquante.
- **Un pouvoir est ajouté par une livraison.** Il est immédiatement disponible
  dans la liste, et l'administrateur le détient d'office — sans migration ni
  recochage.
- **Deux exploitants attribuent le même rôle simultanément.** Idempotent : une
  seule attribution, jamais un doublon ni une erreur exposée.
- **Une ressource d'administration est ajoutée sans garde.** Le filet doit la
  refuser : toute ressource sous le préfixe d'administration est soit gardée,
  soit déclarée publique explicitement.

---

## Requirements *(mandatory)*

### Pouvoirs, rôles et attributions

- **FR-001**: Le système DOIT distinguer trois choses : le **pouvoir** (ce que
  l'application sait vérifier), le **rôle** (un nom donné à un ensemble de
  pouvoirs) et l'**attribution** (une personne porte un rôle dans une
  organisation).
- **FR-002**: L'inventaire des pouvoirs DOIT être déterminé par l'application
  elle-même. Un pouvoir NE PEUT PAS être créé depuis l'interface : il n'existe
  que parce qu'une ressource le vérifie.
- **FR-003**: Cet inventaire DOIT être consultable, en français, groupé par
  fonctionnalité, et s'enrichir de lui-même à chaque livraison.
- **FR-004**: Les rôles DOIVENT être créables, nommables, modifiables et
  supprimables **sans redéploiement**.
- **FR-005**: Un rôle DOIT pouvoir être renommé sans perdre ses attributions.
- **FR-006**: Un rôle livré avec l'application NE DOIT PAS être supprimable, mais
  DOIT rester modifiable (libellé, pouvoirs).
- **FR-007**: La suppression d'un rôle encore attribué DOIT être refusée, en
  nommant le nombre de porteurs.
- **FR-008**: Un rôle DOIT pouvoir être **propre à une organisation** ou partagé
  par toutes. Un rôle propre à une organisation NE DOIT PAS être attribuable
  ailleurs.
- **FR-009**: Un rôle PEUT porter le caractère d'**administration**, qui lui
  accorde tout pouvoir, **y compris ceux ajoutés après sa création**. C'est ce
  qui garantit qu'une fonctionnalité livrée est administrable immédiatement.
- **FR-010**: Le caractère d'administration NE DOIT être posable que par
  quelqu'un qui le porte déjà.
- **FR-011**: Nul NE DOIT accorder un pouvoir qu'il ne porte pas lui-même.
- **FR-012**: Une attribution DOIT être unique et idempotente.
- **FR-013**: La suppression d'un utilisateur DOIT emporter ses attributions.
- **FR-014**: Ajouter un rôle ou un pouvoir NE DOIT exiger aucune migration des
  données existantes.

### Décision d'accès

- **FR-015**: Le système DOIT refuser en **401** toute requête sans session
  valide sur une ressource protégée, et en **403** toute requête portant une
  session valide dont le porteur n'a pas le pouvoir exigé. Ces deux issues NE
  DOIVENT PAS être confondues.
- **FR-016**: La décision DOIT être prise à chaque requête à partir de l'état
  courant, jamais d'une valeur figée à l'ouverture de session.
- **FR-017**: Une ressource protégée DOIT nommer le **pouvoir** qu'elle exige, et
  non un rôle.
- **FR-018**: Le système NE DOIT PAS protéger par un mécanisme posé globalement
  sur l'application ni sur un ensemble de ressources défini par son seul préfixe.
- **FR-019**: Le refus pour pouvoir insuffisant DOIT porter un message en
  français, sans divulguer quels pouvoirs existent ni lesquels le demandeur
  porte.
- **FR-020**: La session en cours DOIT permettre de connaître les pouvoirs
  effectifs de son porteur, afin qu'une interface n'ait pas à les deviner en
  collectant des refus.

### Ressources protégées et ressources publiques

- **FR-021**: La consultation des chronométreurs signalés et le marquage d'un
  signalement comme traité DOIVENT exiger un pouvoir.
- **FR-022**: L'enregistrement d'un signalement DOIT rester **accessible sans
  session** : il est émis par le formulaire public.
- **FR-023**: La création et la suppression d'une participation DOIVENT exiger un
  pouvoir. Elles sont aujourd'hui ouvertes sans authentification.
- **FR-024**: Toutes les autres ressources existantes DOIVENT rester accessibles
  sans session, sans exception ni régression.
- **FR-025**: Le système DOIT conserver un filet automatique, dérivé de
  l'application, interdisant qu'une ressource publique se mette à exiger une
  session, **et** exigeant que toute ressource d'administration soit gardée ou
  déclarée publique explicitement.
- **FR-026**: Le système DOIT disposer d'un filet automatique refusant qu'un
  pouvoir déclaré ne soit vérifié nulle part, ou qu'une ressource exige un
  pouvoir inexistant.

### Amorçage et continuité

- **FR-027**: Le système DOIT offrir une commande d'exploitation attribuant un
  rôle à un utilisateur désigné par son adresse.
- **FR-028**: Cette commande NE DOIT PAS créer d'utilisateur.
- **FR-029**: Cette commande DOIT être idempotente et le signaler.
- **FR-030**: Face à plusieurs utilisateurs partageant l'adresse, elle DOIT
  refuser d'agir et rendre de quoi les départager.
- **FR-031**: Aucune ressource accessible sans pouvoir NE DOIT permettre d'en
  obtenir un.
- **FR-032**: Le système DOIT refuser toute opération qui laisserait
  l'organisation sans aucun administrateur actif, **quel que soit le chemin**
  employé.

### Audit

- **FR-033**: Toute création, modification ou suppression de rôle, et toute
  attribution ou retrait, DOIT être journalisée avec l'auteur, la cible et le
  sens de l'opération.
- **FR-034**: Un refus pour pouvoir insuffisant DOIT être journalisé avec la
  ressource visée et l'utilisateur concerné.
- **FR-035**: Les journaux NE DOIVENT contenir aucun jeton de session ni aucun
  secret.

### Qualité des données

- **FR-036**: Un porteur du pouvoir de qualité DOIT pouvoir fixer à la main le
  verdict de fiabilité d'une épreuve.
- **FR-037**: Le verdict humain et le verdict calculé DOIVENT être conservés
  **distinctement**. Un import ultérieur rafraîchit le calculé sans toucher à
  l'humain.
- **FR-038**: Le verdict rendu au public NE DOIT PAS changer de forme : les
  consommateurs actuels continuent de lire le même champ, de même sens.
- **FR-039**: Un verdict humain DOIT pouvoir être levé, l'épreuve reprenant
  immédiatement son verdict calculé, à jour.

### Key Entities

- **Organisation** : un club. Porte son identité. **Ne possède aucune donnée
  sportive** — courses, athlètes et participations sont un commun partagé.
- **Pouvoir** : ce que l'application sait vérifier. Vit dans l'application, porte
  un libellé français et une fonctionnalité de rattachement. N'est pas une donnée
  administrable.
- **Rôle** : un nom libre et un ensemble de pouvoirs, éventuellement propre à une
  organisation. Peut être livré avec l'application (non supprimable) et peut
  porter le caractère d'administration.
- **Attribution** : cette personne porte ce rôle dans cette organisation.
- **Verdict manuel de fiabilité** : ce qu'un humain a tranché sur une épreuve,
  conservé à part du verdict calculé.

---

## Success Criteria *(mandatory)*

- **SC-001**: 100 % des ressources d'administration refusent un visiteur anonyme
  et un utilisateur sans pouvoir, vérifié par un contrôle **dérivé de
  l'application**, pas d'une liste tenue à la main.
- **SC-002**: 100 % des ressources publiques existantes répondent sans session,
  y compris le signalement d'un chronométreur non supporté.
- **SC-003**: aucune route ne permet plus de créer ou de supprimer une
  participation sans session.
- **SC-004**: un visiteur anonyme et un utilisateur connecté sans pouvoir
  obtiennent deux issues distinctes sur la même ressource.
- **SC-005**: un exploitant crée un rôle, le compose et l'attribue **sans
  redéploiement**, et le changement est effectif à la requête suivante du
  porteur, sans reconnexion.
- **SC-006**: une fonctionnalité livrée est administrable le jour même, sans
  migration de données ni recochage.
- **SC-007**: aucune séquence d'opérations effectuée depuis l'application ne peut
  laisser l'installation sans administrateur.
- **SC-008**: sur une installation neuve, un exploitant obtient le premier
  administrateur en une seule commande, sans requête HTTP ni écriture manuelle en
  base.
- **SC-009**: aucun pouvoir déclaré n'est inutilisé, et aucune ressource n'exige
  un pouvoir inexistant — vérifié automatiquement.
- **SC-010**: chaque opération de gestion des droits est retrouvable dans les
  journaux avec son auteur et sa cible.

---

## Assumptions

- **Le multi-club est modélisé, pas exploité.** Une organisation existe en
  donnée ; aucune ressource n'est cloisonnée par club dans cette feature, parce
  qu'aucune donnée n'appartient à un club. Le cloisonnement viendra avec les
  premières données de club, s'il en naît.
- **Les données restent un commun public.** `Course` est unique par son identité
  d'épreuve : deux clubs important la même épreuve obtiennent la même ligne.
  Aucune donnée sportive ne reçoit d'appartenance à une organisation.
- **`scope=club` n'est pas une organisation.** C'est un prédicat sur un libellé
  **scrapé**, pas une relation applicative — deux fournisseurs ne publient aucun
  club, donc un membre y est hors de `scope=club` tout en étant membre de
  l'organisation. Les deux notions restent séparées ; leur rapprochement est
  l'objet de #95.
- **L'audit se fait dans les journaux applicatifs**, pas dans une table.
- **Aucun écran d'administration n'est livré.** Les ressources existent et sont
  utilisables ; les écrans relèvent de la sous-issue d'interface de #81 et
  n'exigeront **aucune** modification du modèle. Un correctif d'affichage est
  toutefois inclus : l'écran d'administration existant présente aujourd'hui un
  refus comme une liste vide.
- **La liste d'adresses autorisées de #114 reste en amont.** Elle décide qui peut
  *se connecter* ; les rôles décident ce qu'on peut *faire*. Une adresse
  autorisée sans rôle est un état normal.

---

## Dependencies

- **#114 (livré)** : sessions, utilisateur courant, refus en 401. Le parcours de
  connexion n'est pas modifié ; la réponse décrivant la session en cours est
  enrichie (FR-020).
- **Filet de #114 à faire évoluer** : il interdit aujourd'hui tout refus sur
  l'inventaire des routes — y compris sur les deux routes destructives. Il doit
  passer à « toute ressource d'administration est classée, et celles qui exigent
  un pouvoir refusent l'anonyme » (FR-025).
- **Bloque** : « Actions admin CRUD », « Re-scrape à la demande » et
  « Revalidation qualité » de l'épique #81.
- **Prépare** : #170 (liste d'autorisation en base) et #95 (libellés club en
  base), qui deviendront des pouvoirs et des écrans du même back-office.

---

## Out of Scope

- Le cloisonnement des **données** par club (aucune donnée n'appartient à un
  club).
- Les écrans d'administration des rôles et des comptes.
- Le CRUD administratif sur les courses et les athlètes.
- Une table d'audit en base.
- Le rapprochement de `scope=club` et des organisations (#95).
- La liste d'autorisation en base (#170) et la révocation d'urgence (#169).
