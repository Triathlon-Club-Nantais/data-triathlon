# Feature Specification: Liste d'autorisation en base, gérée depuis le back-office

**Feature Branch**: `auth-liste-dautorisation-en-base-et-gestion-depu`

**Created**: 2026-08-06

**Status**: Draft

**Input**: issue [#170](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/170) et son commentaire du 2026-08-06. Refs #114 (socle SSO), #115 (rôles et pouvoirs).

## Le frottement, mesuré

La liste des adresses autorisées à ouvrir une session vit aujourd'hui dans une
**variable d'environnement**, lue une fois pour toutes au démarrage du serveur.
Conséquence directe : **ajouter un contributeur exige un redéploiement**. Pour un
club dont les membres arrivent au fil de la saison, c'est le geste le plus
fréquent de l'administration, et c'est le plus coûteux — il suppose un accès au
tableau de bord d'hébergement, une variable modifiée à la main, et une coupure
de service de quelques minutes.

Retirer un accès souffre du même défaut, avec un enjeu de sécurité en plus : le
geste n'est pas à la portée de la personne qui administre le club.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autoriser un contributeur sans redéployer (Priority: P1)

Une personne habilitée ouvre le back-office, saisit l'adresse d'un nouveau
contributeur dans la liste des accès, et l'enregistre. Le contributeur se
connecte dans la foulée avec son compte externe. Aucun redéploiement, aucune
variable d'environnement, aucune coupure.

**Why this priority**: c'est le besoin qui ouvre l'issue et le geste le plus
fréquent de l'administration. Livré seul, il supprime déjà le redéploiement.

**Independent Test**: sur une installation où une personne habilitée est
connectée, ajouter une adresse depuis l'écran, puis ouvrir une session avec le
compte externe portant cette adresse — sans redémarrer le serveur entre les deux.

**Acceptance Scenarios**:

1. **Given** une personne habilitée connectée au back-office et une adresse
   absente de la liste, **When** elle ajoute cette adresse, **Then** l'adresse
   apparaît dans la liste affichée et le titulaire du compte correspondant peut
   ouvrir une session sans que le serveur ait redémarré.
2. **Given** une adresse déjà présente dans la liste, **When** une personne
   habilitée l'ajoute de nouveau, **Then** l'opération réussit et la liste ne
   comporte toujours qu'une seule entrée pour cette adresse.
3. **Given** une adresse présente sous une casse différente (« Contributeur@Exemple.FR »),
   **When** le titulaire se connecte en présentant « contributeur@exemple.fr »,
   **Then** la connexion est acceptée.
4. **Given** une saisie qui n'est pas une adresse électronique, **When** elle est
   soumise, **Then** elle est refusée avec un message en français et la liste
   reste inchangée.
5. **Given** une personne connectée **sans** le pouvoir requis, **When** elle
   tente d'ajouter une adresse, **Then** l'opération est refusée et la liste
   reste inchangée.
6. **Given** un visiteur anonyme, **When** il appelle la ressource de gestion des
   accès, **Then** il obtient un refus d'authentification, jamais la liste.

---

### User Story 2 - Retirer un accès, et qu'il soit réellement fermé (Priority: P2)

Une personne habilitée retire une adresse de la liste. Le titulaire de cette
adresse perd l'accès **immédiatement** : ses sessions ouvertes ne survivent pas
au retrait, et une nouvelle connexion est refusée.

**Why this priority**: un écran qui affiche « retiré » pendant que la personne
conserve l'accès pendant plusieurs jours est pire qu'une absence d'écran — il
fait croire à une fermeture qui n'a pas eu lieu. Le retrait n'a de valeur que
s'il est effectif au geste.

**Independent Test**: connecter deux comptes, en retirer un depuis l'écran, et
vérifier que sa requête suivante est refusée sans qu'il se soit déconnecté.

**Acceptance Scenarios**:

1. **Given** un contributeur autorisé et connecté, **When** une personne
   habilitée retire son adresse, **Then** la requête authentifiée suivante de ce
   contributeur est refusée, sans qu'il ait eu à se déconnecter ni que le serveur
   ait redémarré.
2. **Given** ce même contributeur retiré, **When** il relance une connexion,
   **Then** elle est refusée pour compte non autorisé.
3. **Given** une adresse absente de la liste, **When** une personne habilitée
   demande son retrait, **Then** l'opération est un succès et la liste reste
   inchangée.
4. **Given** une organisation dont il ne reste qu'un seul administrateur actif,
   **When** on tente de retirer l'adresse de cet administrateur, **Then** le
   retrait est refusé en le nommant, et l'accès reste ouvert.
5. **Given** deux administrateurs actifs, **When** l'un retire l'adresse de
   l'autre, **Then** le retrait est accepté.

---

### User Story 3 - Amorcer ou débloquer une installation depuis le serveur (Priority: P3)

Sur une installation neuve, personne n'est encore autorisé : personne ne peut se
connecter, donc personne ne peut ouvrir le back-office pour autoriser quelqu'un.
Une commande exécutée sur le serveur inscrit la première adresse et rompt ce
cercle. La même commande est le rattrapage hors ligne si l'écran devient
inaccessible.

**Why this priority**: sans elle, la fonctionnalité est un verrou refermé sur
lui-même. Elle est en P3 parce qu'elle n'est empruntée qu'une fois par
installation — l'installation de production, elle, est reprise automatiquement
(FR-013).

**Independent Test**: sur une base vierge, exécuter la commande, puis ouvrir une
session avec le compte correspondant.

**Acceptance Scenarios**:

1. **Given** une base sans aucune adresse autorisée, **When** la commande est
   exécutée avec une adresse, **Then** l'adresse figure dans la liste et le
   titulaire peut ouvrir une session.
2. **Given** une adresse déjà autorisée, **When** la commande est relancée avec
   la même adresse, **Then** elle réussit sans créer de doublon et le dit.
3. **Given** une saisie qui n'est pas une adresse électronique, **When** la
   commande est exécutée, **Then** elle sort en erreur d'usage sans rien écrire.

---

### Edge Cases

- **La liste est vide.** Aucune connexion n'aboutit — c'est le comportement
  attendu (FR-004), jamais « tout le monde ». La page de connexion continue
  d'afficher ses moyens de connexion : c'est au retour du fournisseur que le
  refus tombe, avec le code « compte non autorisé » déjà en place. Le prix est
  assumé et mesuré en FR-011.
- **Une adresse est retirée pendant que son titulaire navigue.** Sa requête
  suivante est refusée (US2). Il n'y a pas de fenêtre de grâce.
- **Une adresse est retirée puis remise.** Le titulaire retrouve l'accès, avec
  ses rôles : le retrait ferme l'accès, il n'efface ni l'utilisateur, ni ses
  attributions, ni son historique.
- **Deux personnes portent la même adresse.** Le modèle l'autorise (l'adresse
  n'est pas une clé d'identité). Un retrait les ferme **toutes**, un ajout les
  rouvre toutes : la liste porte sur l'adresse, pas sur la personne.
- **Espaces et casse à la saisie.** « ` Contributeur@Exemple.FR ` » et
  « `contributeur@exemple.fr` » désignent la même entrée, à l'ajout comme au
  retrait comme à la connexion.
- **Une tentative refusée reste hors base.** Elle est journalisée côté serveur,
  adresse comprise, et rien n'en est conservé (hors périmètre, voir plus bas).

## Requirements *(mandatory)*

### Functional Requirements

**La liste et son effet**

- **FR-001** : la liste des adresses autorisées MUST être conservée en base de
  données, et non dans la configuration du serveur.
- **FR-002** : elle MUST être relue à **chaque** tentative de connexion, sans
  cache : une adresse ajoutée est effective à la connexion suivante, une adresse
  retirée l'est aussitôt.
- **FR-003** : la comparaison d'adresses MUST ignorer la casse et les espaces de
  bordure, à l'enregistrement comme à la vérification.
- **FR-004** : une liste vide MUST interdire toute connexion. « Vide » ne
  signifie jamais « tout le monde ».
- **FR-005** : une adresse MUST être unique dans la liste ; l'ajout d'une adresse
  déjà présente est un succès sans doublon.
- **FR-006** : la liste MUST **autoriser** une adresse, sans jamais servir à
  rattacher une identité externe à un utilisateur existant. Une identité externe
  inconnue crée toujours un nouvel utilisateur (invariant de #114, FR-003).

**La gestion depuis le back-office**

- **FR-007** : le back-office MUST offrir la consultation de la liste, l'ajout
  d'une adresse et le retrait d'une adresse.
- **FR-008** : ces trois gestes MUST être réservés aux porteurs d'un **pouvoir**
  du catalogue applicatif, jamais à un nom de rôle. Le rôle `admin` étant
  superutilisateur, il franchit ce pouvoir sans qu'aucune donnée soit à modifier.
- **FR-009** : une requête anonyme MUST être refusée pour absence
  d'authentification, une requête authentifiée sans le pouvoir pour absence de
  droit — dans cet ordre.
- **FR-010** : une saisie qui n'est pas une adresse électronique MUST être
  refusée, avec un message en français, sans rien écrire.
- **FR-011** : le garde de configuration qui décide si un moyen de connexion peut
  être proposé MUST cesser de compter la liste d'autorisation. Il ne MUST plus
  éprouver que la clé de signature et l'origine de retour. En conséquence, la
  ressource publique qui énumère les moyens de connexion n'interroge **aucune**
  table.
- **FR-012** : le réglage d'environnement portant la liste MUST être supprimé du
  code, du modèle d'environnement et de la documentation. Aucune double source de
  vérité n'est conservée : plus rien dans l'application ne le lit.
  **Une exception, bornée à une livraison** : l'entrée reste déclarée dans la
  configuration d'hébergement, parce que c'est elle que lit la reprise de FR-013.
  La retirer du même geste ferait dépendre la mise en production d'un
  comportement non vérifié de l'hébergeur, sans rattrapage — le plan d'hébergement
  n'ouvre pas de shell. Elle se retire dans une livraison suivante, une fois la
  reprise constatée.

**La reprise et l'amorçage**

- **FR-013** : la mise en service MUST reprendre les adresses actuellement
  déclarées dans l'environnement de production, sans intervention manuelle et
  sans fenêtre pendant laquelle plus personne ne pourrait se connecter.
- **FR-014** : une commande exécutable sur le serveur, sans session, MUST
  permettre d'inscrire une adresse. Comme la commande d'attribution de rôle
  existante, elle ne vérifie aucun pouvoir : l'accès au serveur *est* le
  privilège.
- **FR-015** : cette commande MUST être idempotente et MUST respecter les
  contrats de sortie de la CLI (sortie parsable, codes de sortie).

**Ce que le retrait ferme**

- **FR-016** : retirer une adresse MUST fermer l'accès de ses titulaires
  immédiatement, sessions ouvertes comprises.
- **FR-017** : retirer une adresse MUST NOT supprimer l'utilisateur, ses rôles
  ni son historique — un retrait est réversible.
- **FR-018** : un retrait qui ferait perdre à une organisation son dernier
  administrateur actif MUST être refusé, en le nommant. L'invariant est le même
  que celui qui garde le retrait d'un rôle (#115) et il MUST être réutilisé, non
  réécrit : la contrainte porte sur la **perte** du dernier administrateur, pas
  sur son absence.
- **FR-019** : les routes publiques existantes MUST rester ouvertes ; aucune ne
  se ferme du fait de cette évolution.

### Key Entities

- **Adresse autorisée** : une adresse électronique qui a le droit d'ouvrir une
  session, la date à laquelle elle a été inscrite, et de qui vient l'inscription
  quand elle vient du back-office. Ne porte ni rôle, ni identité : elle autorise,
  elle ne désigne personne.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : autoriser un nouveau contributeur ne demande **aucun**
  redéploiement ni redémarrage — le nombre d'interventions sur l'hébergement pour
  ce geste passe de 1 à 0.
- **SC-002** : une personne habilitée ajoute une adresse en moins de 30 secondes
  depuis le back-office, sans quitter la page d'administration.
- **SC-003** : une adresse ajoutée est utilisable pour se connecter dès la
  tentative suivante ; une adresse retirée ferme l'accès de son titulaire dès sa
  requête suivante.
- **SC-004** : sur une base neuve, une installation passe de « personne ne peut
  se connecter » à « le premier administrateur est connecté » par une seule
  commande serveur, sans édition de fichier de configuration.
- **SC-005** : la mise en production ne comporte aucune fenêtre pendant laquelle
  un contributeur actuellement autorisé se verrait refuser la connexion.

## Assumptions

- **Le volume reste petit.** La liste compte quelques dizaines d'entrées, celles
  des contributeurs d'un club. Ni pagination, ni recherche, ni tri ne sont
  nécessaires — l'écran affiche la liste entière.
- **Un seul écran, pas de refonte.** La gestion prend place comme un **second
  bloc** sur la page d'administration existante, à côté des chronométreurs
  signalés. Aucune navigation de back-office n'est introduite : ce chantier
  appartient aux issues qui ajouteront les écrans suivants (#117, #118, #119, #47).
- **La liste porte des adresses, pas des domaines.** L'autorisation d'un domaine
  entier (« toute adresse `@triclunantais.fr` ») n'est pas demandée et n'est pas
  livrée.
- **Aucune invitation n'est envoyée.** Inscrire une adresse n'envoie pas de
  courriel ; la personne est prévenue par ailleurs et se connecte d'elle-même.
- **La certification de l'adresse par le fournisseur reste la première porte.**
  L'ordre de #114 est inchangé : adresse certifiée, **puis** liste
  d'autorisation, **puis** résolution de l'identité.
- **Le catalogue de pouvoirs s'étend sans migration** (#115) : ajouter le pouvoir
  de FR-008 est un ajout de code, et le rôle superutilisateur le franchit
  d'emblée.

## Hors périmètre

- **La table des tentatives de connexion refusées.** Demandée en revue de #168 et
  écartée avec son raisonnement complet dans
  `specs/20260801-145428-auth-socle-sso/data-model.md`, §« Ce qu'aucune table
  n'enregistre » : ce serait la seule écriture en base pilotée par un visiteur
  non authentifié, sur des données personnelles de tiers non consentants, et son
  écran d'administration rendrait du texte d'origine externe. Le refus continue
  de journaliser l'adresse soumise côté serveur, et rien n'est conservé. Si elle
  revient dans le périmètre, elle a besoin d'une limitation de débit, d'un
  plafond ou d'une rétention, et d'un rendu échappé.
- **La révocation d'urgence des sessions** (#169) — cette feature ferme l'accès
  d'une adresse retirée, elle n'outille pas l'incident.
- **Les groupes d'appartenance** (#197) : la liste reste une liste d'adresses.
- **L'autorisation par domaine, l'invitation par courriel, la pagination et la
  recherche** dans l'écran — voir Assumptions.
