# Feature Specification: Bouton de signalement (bug / feedback)

**Feature Branch**: `feat/267-bouton-signalement`

**Created**: 2026-08-12

**Status**: Livrée (PR #315)

**Input**: User description: "Bouton de signalement (bug / feedback) accessible à tous, remonté dans le panel admin. Ajouter sur le site un bouton de signalement qui ouvre un petit formulaire (titre, description, type bug/feedback, contexte auto-joint) accessible sans compte. Les signalements atterrissent dans le panel admin sous une nouvelle section « Retours utilisateurs » avec liste triable, vue détail, et actions de statut. Pas d'intégration GitHub automatique en v1. Issue GitHub #267."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Signaler un bug ou un retour depuis n'importe quelle page (Priority: P1)

Un visiteur du site (membre du club ou non, connecté ou non) rencontre un
problème ou a une idée d'amélioration pendant qu'il consulte les résultats. Il
clique sur un bouton de signalement toujours visible, remplit un petit
formulaire (titre, description, type) et l'envoie, sans avoir besoin de créer
de compte.

**Why this priority**: C'est la fonctionnalité qui justifie toute la feature —
sans un moyen de signaler à faible friction, aucun retour n'arrive côté club.
Sans elle, le reste (panel admin) n'a rien à afficher.

**Independent Test**: Peut être testé seul en ouvrant n'importe quelle page du
site sans être connecté, en soumettant le formulaire, et en vérifiant que le
signalement est bien enregistré côté serveur avec le statut initial « nouveau ».

**Acceptance Scenarios**:

1. **Given** un visiteur non connecté sur une page quelconque du site, **When**
   il ouvre le bouton de signalement, remplit un titre, une description et
   choisit le type « bug », puis valide, **Then** le signalement est enregistré
   avec le statut « nouveau », l'URL de la page courante et le user-agent
   collectés automatiquement, et aucun email n'est associé au signalement.
2. **Given** un membre connecté via le SSO du club, **When** il soumet un
   signalement de type « feedback », **Then** le signalement enregistré porte
   l'identité de l'utilisateur connecté (email) en plus du contexte automatique.
3. **Given** le formulaire ouvert, **When** l'utilisateur tente de valider sans
   avoir renseigné le titre ou la description, **Then** la soumission est
   refusée et les champs manquants sont signalés avant tout envoi au serveur.
4. **Given** un signalement soumis avec succès, **When** la confirmation
   s'affiche, **Then** l'utilisateur comprend sans ambiguïté que son message a
   bien été transmis (pas de simple fermeture silencieuse du formulaire).

---

### User Story 2 - Consulter la liste des retours utilisateurs dans le panel admin (Priority: P1)

Un membre du club disposant des droits d'administration ouvre le panel admin
et retrouve, dans une nouvelle section « Retours utilisateurs », l'ensemble des
signalements reçus, avec la possibilité de les trier par date, type ou statut
pour prioriser son traitement.

**Why this priority**: Sans surface de consultation, les signalements collectés
par l'US1 ne servent à rien — c'est le second maillon indispensable du parcours
complet « signaler → traiter ».

**Independent Test**: Peut être testé seul en pré-remplissant des signalements
en base et en vérifiant que l'écran `/admin/retours-utilisateurs` les liste et
les trie correctement, à condition de disposer du droit d'accès requis.

**Acceptance Scenarios**:

1. **Given** plusieurs signalements en base de types et statuts variés, **When**
   un administrateur habilité ouvre la section « Retours utilisateurs »,
   **Then** il voit la liste complète avec, pour chaque ligne, au minimum la
   date, le type, le titre et le statut.
2. **Given** la liste affichée, **When** l'administrateur trie par date, par
   type ou par statut, **Then** l'ordre d'affichage reflète le critère choisi.
3. **Given** un utilisateur du panel admin sans le droit d'accès à cette
   section, **When** il tente d'atteindre `/admin/retours-utilisateurs`,
   **Then** l'accès lui est refusé, de la même manière que pour les autres
   écrans d'administration protégés par un pouvoir dédié.

---

### User Story 3 - Traiter un signalement depuis sa vue détail (Priority: P2)

Un administrateur ouvre un signalement précis pour lire l'intégralité de son
contenu et de son contexte, puis fait avancer son statut (« en cours »,
« traité », « ignoré ») au fil de son traitement.

**Why this priority**: Complète le cycle de traitement ouvert par l'US2 ; utile
dès que le volume de signalements dépasse ce qu'une simple liste permet de
suivre, mais la feature reste utilisable (lecture seule) sans cette capacité.

**Independent Test**: Peut être testé seul en ouvrant le détail d'un
signalement existant, en vérifiant l'affichage complet (titre, description,
URL de la page, user-agent, email si présent), puis en changeant son statut et
en confirmant que le changement persiste et se reflète dans la liste de l'US2.

**Acceptance Scenarios**:

1. **Given** un signalement avec un email associé (utilisateur connecté lors de
   l'envoi), **When** l'administrateur ouvre sa vue détail, **Then** il voit le
   titre, la description complète, le type, l'URL de la page d'origine, le
   user-agent et l'email.
2. **Given** un signalement soumis anonymement, **When** l'administrateur ouvre
   sa vue détail, **Then** aucun champ d'identification n'est affiché à la
   place de l'email absent (pas de valeur factice ni d'erreur d'affichage).
3. **Given** un signalement au statut « nouveau », **When** l'administrateur le
   marque comme « traité » ou « ignoré », **Then** le nouveau statut est
   immédiatement reflété dans la vue détail et dans la liste.

---

### User Story 4 - Pré-remplir une création d'issue/discussion GitHub (Priority: P3)

Depuis la vue détail d'un signalement, un administrateur clique sur une action
« Promouvoir » qui lui ouvre une page de création d'issue GitHub pré-remplie
avec le titre et la description du signalement, à finaliser et publier
manuellement sur GitHub — puis colle en retour l'URL de l'issue créée pour la
garder associée au signalement.

**Why this priority**: Confort explicitement identifié comme secondaire par
l'issue (« sinon reporté à une itération ultérieure ») : aucune intégration
GitHub automatique n'est requise, et son absence ne bloque ni l'US1, ni l'US2,
ni l'US3.

**Independent Test**: Peut être testé seul en ouvrant un signalement existant,
en déclenchant l'action « Promouvoir », en vérifiant que le lien généré pointe
vers une création d'issue GitHub avec titre et description pré-remplis, puis en
enregistrant une URL de retour sur le signalement.

**Acceptance Scenarios**:

1. **Given** un signalement de type « bug » ouvert en vue détail, **When**
   l'administrateur clique sur « Promouvoir en issue GitHub », **Then** un lien
   s'ouvre vers la création d'une nouvelle issue GitHub dont le titre et le
   corps reprennent le titre et la description du signalement.
2. **Given** une issue GitHub créée manuellement à partir de ce lien, **When**
   l'administrateur colle son URL dans le signalement, **Then** cette URL est
   enregistrée et affichée avec le signalement pour les consultations
   suivantes.

---

### Edge Cases

- Que se passe-t-il si le formulaire est soumis avec un titre ou une
  description dépassant la longueur raisonnable attendue (ex. plusieurs
  dizaines de milliers de caractères) ? La soumission doit être refusée
  proprement, sans provoquer d'erreur serveur.
- Que se passe-t-il si le champ honeypot (piège anti-bot invisible) est
  renseigné ? Le signalement est silencieusement rejeté ou ignoré côté serveur
  (voir FR-010), sans indice donné à l'émetteur automatisé.
- Que se passe-t-il si une même IP dépasse le seuil de signalements autorisé
  sur une courte période ? Les envois suivants sont refusés avec un message
  clair, jusqu'à expiration de la fenêtre de limitation (voir FR-011).
- Que se passe-t-il si l'utilisateur ferme la page juste après avoir cliqué sur
  « envoyer » ? L'enregistrement du signalement ne doit pas dépendre du
  maintien de la page ouverte au-delà de la confirmation de réception.
- Que se passe-t-il si un signalement est soumis depuis une page qui n'a pas
  d'URL exploitable (cas limite technique) ? Le signalement reste valide ; le
  champ URL peut être vide plutôt que de bloquer l'envoi.
- Que se passe-t-il si un administrateur retire son propre droit d'accès à la
  section « Retours utilisateurs » pendant qu'il la consulte ? Comportement
  identique aux autres écrans du panel admin déjà protégés par pouvoir.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT afficher un bouton de signalement accessible
  depuis n'importe quelle page publique du site, sans nécessiter de compte ni
  de connexion.
- **FR-002**: Le bouton DOIT ouvrir un formulaire comportant un titre
  (obligatoire, court), une description (obligatoire, multi-lignes) et un choix
  de type entre « bug » et « feedback » (un seul choix possible).
- **FR-003**: Le système DOIT refuser la soumission tant que le titre ou la
  description sont vides, avant tout envoi au serveur.
- **FR-004**: Le système DOIT joindre automatiquement à chaque signalement
  l'URL de la page courante et le user-agent du navigateur, sans action de
  l'utilisateur.
- **FR-005**: Le système DOIT associer l'email de l'utilisateur au signalement
  uniquement s'il est connecté via le SSO au moment de l'envoi ; un utilisateur
  non connecté ne DOIT laisser aucune trace d'identité dans le signalement.
- **FR-006**: Le système DOIT attribuer à tout nouveau signalement le statut
  initial « nouveau ».
- **FR-007**: Le système DOIT confirmer visuellement à l'émetteur que son
  signalement a bien été enregistré.
- **FR-008**: Le panel admin DOIT exposer une section « Retours utilisateurs »
  listant l'ensemble des signalements, accessible uniquement aux comptes
  disposant du pouvoir dédié à cette section (même mécanisme de contrôle
  d'accès que les autres écrans du panel admin).
- **FR-009**: La liste des signalements DOIT pouvoir être triée par date, par
  type et par statut.
- **FR-010**: Le système DOIT inclure un mécanisme anti-bot invisible
  (honeypot) dans le formulaire public : toute soumission renseignant ce champ
  piège est écartée sans être présentée comme un signalement valide.
- **FR-011**: Le système DOIT limiter le nombre de signalements acceptés par
  adresse IP sur une fenêtre de temps glissante, afin de contenir les
  soumissions automatisées ou abusives d'un formulaire ouvert sans compte ; le
  dépassement du seuil DOIT être communiqué clairement à l'émetteur plutôt que
  silencieusement ignoré.
- **FR-012**: La vue détail d'un signalement DOIT afficher le titre, la
  description complète, le type, la date de création, l'URL de page et le
  user-agent collectés, ainsi que l'email si l'émetteur était connecté.
- **FR-013**: Un administrateur habilité DOIT pouvoir faire passer un
  signalement par les statuts « nouveau », « en cours », « traité » et
  « ignoré ».
- **FR-014**: La vue détail DOIT proposer une action générant un lien de
  création d'issue GitHub pré-rempli (titre et description repris du
  signalement), sans appeler d'API GitHub ni créer l'issue automatiquement.
- **FR-015**: Un administrateur habilité DOIT pouvoir enregistrer sur le
  signalement l'URL d'une issue ou discussion GitHub créée manuellement, pour
  la retrouver lors de consultations ultérieures.
- **FR-016**: Le système NE DOIT PAS créer, modifier ou interroger la moindre
  ressource GitHub par programmation dans cette itération.

### Key Entities *(include if feature involves data)*

- **Signalement** : un retour utilisateur unique. Porte un type (bug ou
  feedback), un titre, une description, le statut de traitement (nouveau, en
  cours, traité, ignoré), le contexte de collecte (URL de la page, user-agent),
  éventuellement l'identité de l'émetteur s'il était connecté, une éventuelle
  URL GitHub associée après promotion manuelle, et sa date de création.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un visiteur non connecté peut soumettre un signalement complet
  (titre, description, type) en moins d'une minute depuis n'importe quelle page
  du site.
- **SC-002**: 100 % des signalements soumis avec succès sont visibles dans le
  panel admin sans délai perceptible par l'administrateur (rafraîchissement
  normal de la liste).
- **SC-003**: Un administrateur peut retrouver un signalement précis parmi
  plusieurs dizaines en moins de 10 secondes grâce au tri par date, type ou
  statut.
- **SC-004**: Les soumissions automatisées de test (champ piège rempli, ou
  volume dépassant le seuil configuré) n'apparaissent jamais comme des
  signalements valides dans la liste admin.
- **SC-005**: Aucune adresse email n'apparaît sur un signalement soumis par un
  utilisateur non connecté, vérifié sur 100 % des signalements de ce type.

## Assumptions

- **Anti-spam v1** : un honeypot (champ caché, invisible pour un humain) combiné
  à une limitation simple par adresse IP suffisent en v1 pour un formulaire
  public sans compte. Un captcha visible est explicitement écarté à ce stade
  (frein à la friction que l'issue veut minimiser) ; l'issue laisse ce point
  ouvert et cette combinaison est le choix le plus simple compatible avec son
  périmètre v1.
- **Vie privée** : seuls l'URL de la page, le user-agent et — si l'utilisateur
  est connecté au moment de l'envoi — son email sont collectés. Aucune autre
  donnée de profil, aucune IP affichée en clair dans la vue détail, aucun
  fingerprinting au-delà de ce qui sert la limitation de débit.
- **Contrôle d'accès admin** : l'accès à la section « Retours utilisateurs »
  suit le même modèle de pouvoirs (RBAC) que les sections existantes du panel
  admin — un pouvoir dédié à créer, plutôt qu'une exception au modèle en place.
- **Intégration GitHub** : hors périmètre v1 toute création automatique
  d'issue ou de discussion. L'action « Promouvoir » se limite à générer un lien
  pré-rempli à ouvrir manuellement, et à permettre l'enregistrement manuel de
  l'URL obtenue en retour — cohérent avec la mention de l'issue selon laquelle
  même ce pré-remplissage peut être reporté « si ce n'est pas simple » ; il est
  retenu ici car il ne demande qu'une construction d'URL, sans appel réseau.
- **Longueurs de champs** : le titre est court (quelques dizaines de
  caractères), la description peut être plus longue mais reste bornée à une
  taille raisonnable pour éviter les abus — les seuils exacts sont un détail
  d'implémentation, pas une contrainte métier.
- **Disponibilité du bouton** : le bouton de signalement est présent sur
  l'ensemble du site public, y compris pour les visiteurs non membres du club —
  cohérent avec l'objectif de baisser la friction énoncé par l'issue.
- **Aucun accusé de réception par email** : l'émetteur ne reçoit pas de suivi
  par email après sa soumission (pas d'email demandé aux anonymes) ; la seule
  confirmation est celle affichée immédiatement après l'envoi.
