# Feature Specification: RBAC — rôles composables et protection des ressources d'administration

**Feature Branch**: `feat-auth-rbac-r-les-administrateur-validateur-e`

**Created**: 2026-08-04 · **Révisée**: 2026-08-05 (v3)

**Status**: Draft

**Input**: issue #115 (sous-issue de l'épique #81), son commentaire d'arbitrage du 2026-08-02, la discussion GitHub #143, les arbitrages produit du 2026-08-04, et la revue de @MathieuHerrmann sur la PR #193 avec les arbitrages du 2026-08-05.

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

## Ce que la revue du 2026-08-05 change, et ce qu'elle ne change pas

La revue de @MathieuHerrmann sur la PR #193 approuve le modèle et lève sept
points. Aucun ne remet en cause la v2 ; quatre la précisent, deux l'étendent, un
est écarté par un raisonnement plutôt que par un choix.

**Intégré sans discussion** — quatre trous de formulation, tous gratuits :
la symétrique en retrait de la règle de pose du caractère d'administration
(FR-010), le fait qu'un retrait de pouvoir n'invalide pas la session de son
porteur (Edge Cases), la convention de nommage des codes de pouvoir (FR-040), et
l'enrichissement de la session en cours par les **rôles** portés et non seulement
les pouvoirs (FR-020) — sans quoi une interface ne peut pas afficher « connecté
en tant qu'administrateur » sans un second appel.

**Un troisième rôle est semé** : `moderator`, porteur des deux pouvoirs de
signalement. Arbitrage du 2026-08-05, contre l'argument que FR-006 le rendra
définitivement présent. Les deux pouvoirs sont couplés et décrivent une fonction
organisationnelle entière ; les composer à la main le premier jour est un rite de
passage sans valeur, et l'oubli du pouvoir de lecture est le bug attendu.

**Les groupes d'appartenance sortent du périmètre**, vers l'issue **#197**.
Un groupe dit à quoi on **appartient**, un rôle ce qu'on **peut faire** : ce sont
deux objets, et aucune agrégation de rôles ne rend « liste-moi les membres du
Codir ». Mais leur retard est **gratuit**, ce qui est l'exact inverse du
raisonnement qui fait poser les rôles maintenant : tant qu'un groupe ne porte
aucun droit, la table n'intersecte aucune décision d'accès, donc aucun test de
garde n'est à défaire. #197 porte ce jalon — « avant qu'un groupe porte un
droit » —, seul moment où le coût cesse d'être nul.

**Trois limites sont nommées** plutôt que débattues dans six mois : pas de refus
explicite, pas de compte machine, pas d'attribution qui expire (Out of Scope).

### Le point écarté : le patron d'évolution des rôles semés

La revue demande de trancher entre trois voies pour l'enrichissement futur de
`validator` — organique, figé avec un `validator_v2`, ou agrégation par étiquette
à la façon de Kubernetes. **La question se dissout** dès qu'on répond à celle qui
la précède : *une migration a-t-elle le droit de recomposer un rôle existant ?*

Non. À partir du moment où FR-004 rend un rôle éditable à chaud, sa composition
est une **donnée d'exploitation**, pas un livrable. Une migration qui ajouterait
un pouvoir à `validator` écraserait une décision d'exploitant, silencieusement.
La règle est donc : **on sème une fois, on ne recompose jamais** (FR-041).

Cela rend les trois voies sans objet. Un pouvoir nouvellement livré atteint
l'administrateur **immédiatement** par `is_superuser` (FR-009) et atteint
`validator` quand un exploitant l'y ajoute — en un appel, depuis l'interface.
L'argument avancé contre la voie organique — « les définitions divergent entre
installations semées à des dates différentes » — suppose un parc d'installations.
Il y en a une. Et le patron GitLab (`validator_v2`) existe parce que GitLab doit
à des millions d'installations un contrat de compatibilité que ce projet ne doit
à personne.

### Le point tranché autrement : la portée de l'inventaire des pouvoirs

La revue propose « voie AWS » (inventaire réservé aux gestionnaires) contre
« voie Kubernetes » (inventaire lisible par tout connecté, les codes vivant de
toute façon dans un dépôt public). **L'argument du secret ne départage rien** :
il n'y en a pas.

Ce qui départage est ailleurs. La seconde voie créerait une classe de ressource
qui n'existe nulle part ailleurs dans cette feature — « authentifié, mais aucun
pouvoir exigé » — pour un consommateur qui n'existe pas : le seul lecteur de
l'inventaire général est l'écran de composition des rôles, et il faut `roles:read`
pour aller au bout du geste. L'auto-inspection, elle, est déjà servie par la
session en cours (FR-020). L'inventaire reste donc derrière `roles:read`
(FR-003), non par prudence mais par absence de besoin.

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

## Clarifications

### Session 2026-08-05

- Q: Veux-tu qu'une table `permissions` liste les codes en base, en plus des
  lignes `role_permissions` qui y sont déjà ? → A: Non. Les codes de pouvoir
  **sont** déjà des chaînes stockées en base — c'est le vocabulaire du modèle qui
  laissait croire l'inverse, et c'est lui qui est corrigé.

**Ce que ce point tranche, et qui se reprend facilement** : « les pouvoirs sont
en base » et « la *liste* des pouvoirs possibles est en base » sont deux choses
différentes.

| | Où | Modifiable à chaud |
| --- | --- | --- |
| Le code porté par un rôle (`"quality:override"`) | **En base**, une ligne de `role_permissions` | **Oui** |
| La liste des codes qui existent | **Dans l'application** (FR-002) | Non — un pouvoir naît de la ligne qui le vérifie |

Une table listant les codes possibles n'ajouterait **aucune capacité** à
l'exploitant : elle dupliquerait en base un inventaire que l'application détient
déjà, avec un chemin d'écriture au démarrage dont la variante destructive efface
des attributions en production sans bruit (`research.md` §D3).

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

Le président du club crée un rôle « Archiviste », le nomme, coche ce
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
5. **Given** deux administrateurs actifs, **When** l'un retire à l'autre son rôle
   d'administration, **Then** l'opération aboutit. La règle de pose est
   symétrique : qui porte le caractère d'administration peut aussi le retirer,
   à autrui comme à soi. Seul l'invariant du dernier administrateur borne ce
   geste.
6. **Given** une installation sans aucun administrateur (obtenue par un chemin
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
- **Un pouvoir est retiré à quelqu'un de connecté.** Sa **session n'est pas
  invalidée** : il reste connecté, il garde son identité, et seul le pouvoir
  tombe — à la requête suivante. Fermer la session serait une punition
  disproportionnée et déconnecterait quelqu'un qui a peut-être encore d'autres
  rôles. La fermeture de session reste le geste de #114 : désactiver le compte.
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
- **FR-002**: L'**inventaire** des pouvoirs DOIT être déterminé par l'application
  elle-même. Un pouvoir NE PEUT PAS être créé depuis l'interface : il n'existe
  que parce qu'une ressource le vérifie. Cela ne dit rien du **stockage** : le
  code qu'un rôle porte est bien une donnée conservée en base et modifiable à
  chaud (FR-004). Ce qui n'est pas en base, c'est la liste des codes qui
  existent.
- **FR-003**: Cet inventaire DOIT être consultable, en français, groupé par
  fonctionnalité, et s'enrichir de lui-même à chaque livraison. Sa consultation
  DOIT exiger le pouvoir de lecture des rôles : son seul usage est de composer un
  rôle. Connaître ses **propres** pouvoirs relève de FR-020, qui n'exige rien.
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
- **FR-010**: Le caractère d'administration NE DOIT être posable **ni retirable**
  que par quelqu'un qui le porte déjà. La règle est symétrique, et vaut envers
  autrui comme envers soi-même : seul FR-032 borne le retrait.
- **FR-011**: Nul NE DOIT accorder un pouvoir qu'il ne porte pas lui-même. La
  règle s'applique **aux seuls pouvoirs de l'inventaire**, à l'octroi comme au
  retrait. Un pouvoir **absent de l'inventaire** DOIT rester retirable et ne
  DOIT jamais empêcher d'attribuer le rôle qui le porte : sans cette borne, un
  rôle ayant survécu à la suppression d'une fonctionnalité deviendrait
  immodifiable et inattribuable pour tout le monde, superutilisateur compris —
  et, s'il est livré avec l'application (FR-006) ou déjà attribué (FR-007), il
  serait aussi indélébile.
- **FR-012**: Une attribution DOIT être unique et idempotente.
- **FR-013**: La suppression d'un utilisateur DOIT emporter ses attributions.
- **FR-014**: Ajouter un rôle ou un pouvoir NE DOIT exiger aucune migration des
  données existantes.
- **FR-040**: Un code de pouvoir DOIT suivre la forme `<domaine>:<geste>`, où le
  geste nomme **l'acte métier** et non l'opération technique quand les deux
  diffèrent. `lecture` et `écriture` restent légitimes là où le geste n'a pas
  d'autre nom ; `quality:override` n'est pas à réécrire en `courses:update`, qui
  décrirait une écriture générique que personne ne détient.
- **FR-041**: Le système DOIT être livré avec trois rôles : administration,
  qualité et tri des signalements. Une migration ultérieure NE DOIT **jamais**
  recomposer un rôle déjà semé : dès lors qu'un rôle est éditable à chaud
  (FR-004), sa composition est une donnée d'exploitation, qu'une migration
  écraserait sans que personne ne le voie. Un pouvoir livré plus tard atteint
  l'administration d'office (FR-009) et les autres rôles par décision humaine.
  **Cette règle a un coût récurrent et un seuil.** Le projet prévoit plus d'un
  pouvoir nouveau par mois : chacun qui devrait revenir à un rôle
  non-administrateur demande un geste manuel, avec un mode de panne silencieux —
  personne ne constate l'oubli avant qu'un porteur se plaigne. Le coût reste nul
  tant que les pouvoirs nouveaux ouvrent des **domaines nouveaux**, qui vont à
  l'administration d'office ou justifient un rôle créé à chaud. **Le déclencheur
  de réouverture est donc précis** : le jour où un domaine déjà couvert par un
  rôle non-administrateur gagne un troisième pouvoir, cette règle est à
  réexaminer — l'issue de rechange est l'absorption par domaine, une colonne dont
  `is_superuser` serait le cas particulier « absorbe tout ».
- **FR-042**: Un pouvoir référencé par un rôle mais absent de l'inventaire NE
  DOIT rien accorder, NE DOIT PAS faire échouer la décision d'accès, NE DOIT
  bloquer **ni la modification ni l'attribution** du rôle qui le porte (FR-011),
  et DOIT être signalé comme périmé à la lecture du rôle. C'est l'unique cas où
  la base et l'application peuvent diverger, et il se produit à chaque
  suppression de fonctionnalité — c'est donc la seule dette permanente du choix
  de tenir la politique en base plutôt qu'en code.

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
  effectifs de son porteur **et les rôles qu'il porte**, afin qu'une interface
  n'ait pas à les deviner en collectant des refus, ni à faire un second appel
  pour écrire « connecté en tant qu'administrateur ». Cette lecture N'EXIGE aucun
  pouvoir : elle ne porte que sur soi-même.

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
- **Les rôles semés ne bougent plus après leur semis** (FR-041). Leur
  composition initiale est un point de départ raisonnable, pas un contrat : un
  exploitant peut la modifier dès le premier jour, et c'est cette version-là qui
  fait foi ensuite. Corollaire assumé : deux installations semées à des dates
  différentes peuvent diverger. Il y en a une.
- **Les pouvoirs à venir ouvriront surtout des domaines nouveaux** (arbitrage du
  2026-08-05). C'est ce qui rend FR-041 gratuit : un domaine neuf n'appartient à
  aucun rôle existant, il revient à l'administration par `is_superuser` ou
  justifie un rôle créé à chaud. Si cette hypothèse se dément — un domaine déjà
  couvert gagnant un troisième pouvoir —, FR-041 est à rouvrir, et non à
  contourner par des `PATCH` mensuels qu'on finira par oublier.

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
- **Prérequis de #197** (groupes d'appartenance) : celle-ci en reprend le
  catalogue de pouvoirs, le mécanisme de garde, le filet d'inventaire des routes
  et le patron de table. #197 ne peut pas commencer avant, et ne doit pas
  commencer après qu'un groupe ait besoin de porter un droit.

---

## Out of Scope

- Le cloisonnement des **données** par club (aucune donnée n'appartient à un
  club).
- Les écrans d'administration des rôles et des comptes.
- Le CRUD administratif sur les courses et les athlètes.
- Une table d'audit en base.
- Le rapprochement de `scope=club` et des organisations (#95).
- La liste d'autorisation en base (#170) et la révocation d'urgence (#169).
- **Les groupes d'appartenance (#197)** — Codir, techniciens, arbitres. Un
  groupe existe même vide de droits ; tant qu'il n'en porte aucun, il
  n'intersecte pas la décision d'accès, et son retard ne coûte rien.
- **Le refus explicite.** Aucun moyen d'interdire nommément un pouvoir à
  quelqu'un qui le tiendrait d'un autre rôle : on retire le rôle. C'est le
  modèle de Kubernetes, et l'inverse d'AWS IAM.
- **Les comptes machine et les jetons personnels.** Tout accès passe par une
  session ouverte par délégation à GitHub. Un webhook, un cron externe ou un
  script d'intégration continue ne peuvent pas appeler les ressources
  d'administration.
- **Les attributions qui expirent.** Pas de « validateur pendant trente jours » :
  une attribution dure jusqu'à son retrait.
