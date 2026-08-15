# Feature Specification: Gestion admin du mot de passe partagé bénévoles

**Feature Branch**: `20260815-173645-admin-mdp-benevoles`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "Faire évoluer la gestion du mot de passe partagé de la page bénévoles (#271) : au lieu d'une variable d'environnement (BENEVOLE_SHARED_PASSWORD), le mot de passe doit être géré depuis le back-office par un administrateur habilité (nouveau pouvoir RBAC dédié). Il doit être stocké en base sous forme hachée et salée, jamais en clair, et jamais récupérable — un administrateur ne peut que le remplacer (en saisir un nouveau) ou en faire générer un nouveau de façon sécurisée (affiché une seule fois à la génération, à communiquer aux bénévoles hors-bande). Changer le mot de passe doit invalider toutes les sessions bénévoles en cours, comme aujourd'hui — mais puisque le mécanisme actuel signe le cookie de session avec le mot de passe en clair lui-même comme clé HMAC, et qu'un hachage à sens unique ne permet plus ça, il faudra un secret de session distinct, tourné (régénéré) à chaque changement de mot de passe, pour préserver cette propriété sans jamais avoir besoin de relire le mot de passe en clair. Cette feature dépend du code de #271 (non encore fusionné dans main) : la branche part de la branche #271 actuelle, pas de main."

## Dépendances *(à documenter, pas à résoudre dans ce cadrage)*

- **Bloquée par #271** (page de vérification des résultats bénévoles) : cette
  feature remplace le mécanisme d'accès qu'#271 introduit
  (`BENEVOLE_SHARED_PASSWORD`, cookie signé HMAC avec le mot de passe en
  clair comme clé). #271 n'est pas encore fusionnée dans `main` au moment de
  ce cadrage (PR #368, ouverte) — cette branche part directement de la
  branche d'#271 plutôt que de `main`, et devra être rebasée si #271 change
  encore avant sa fusion.
- **S'appuie sur le socle RBAC** (#115) : le nouveau pouvoir attribué à un
  administrateur suit exactement le modèle déjà en place pour les pouvoirs
  existants (`core/permissions.py`, écran `/admin/droits`) — aucune extension
  de ce socle n'est nécessaire.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un administrateur définit un nouveau mot de passe bénévoles (Priority: P1)

Un administrateur habilité ouvre l'écran de gestion des accès du
back-office et saisit un nouveau mot de passe pour l'accès partagé des
bénévoles. Une fois enregistré, ce mot de passe remplace l'ancien : toute
tentative de connexion bénévole avec l'ancien mot de passe échoue désormais,
et toutes les sessions bénévoles déjà ouvertes cessent d'être valides.

**Why this priority**: C'est le geste qui remplace directement ce que fait
aujourd'hui la modification manuelle d'une variable d'environnement suivie
d'un redéploiement — sans lui, la feature ne livre rien de plus que le
mécanisme actuel.

**Independent Test**: Peut être testé seul en définissant un mot de passe
depuis l'écran, en vérifiant qu'une connexion bénévole avec l'ancien mot de
passe échoue et qu'une connexion avec le nouveau réussit, et qu'une session
bénévole ouverte avant le changement échoue à la requête suivante.

**Acceptance Scenarios**:

1. **Given** un administrateur habilité sur l'écran de gestion des accès,
   **When** il saisit et enregistre un nouveau mot de passe pour l'accès
   bénévoles, **Then** ce mot de passe est accepté par la page bénévoles dès
   l'enregistrement.
2. **Given** un mot de passe bénévoles déjà en place et des sessions
   bénévoles ouvertes, **When** un administrateur le remplace, **Then**
   l'ancien mot de passe n'est plus accepté et les sessions déjà ouvertes ne
   permettent plus aucune action sur la page bénévoles.
3. **Given** un utilisateur du back-office sans le pouvoir dédié, **When**
   il tente d'accéder à cette gestion ou de la modifier, **Then** l'accès est
   refusé.

---

### User Story 2 - Un administrateur fait générer un mot de passe sécurisé (Priority: P2)

Plutôt que de saisir lui-même un mot de passe, l'administrateur déclenche la
génération d'un mot de passe aléatoire et suffisamment robuste. Ce mot de
passe s'affiche une seule fois, immédiatement après la génération ;
l'administrateur le copie pour le transmettre aux bénévoles par un canal
existant du club (hors de cet écran). Une fois l'écran quitté ou rechargé,
ce mot de passe ne peut plus être ni affiché ni retrouvé nulle part dans
l'application.

**Why this priority**: Réduit le risque qu'un administrateur choisisse un
mot de passe faible ou déjà utilisé ailleurs, mais le geste manuel de la
Story 1 reste la voie de secours si la génération ne convient pas (rotation
d'urgence avec un mot de passe imposé, par exemple) — secondaire à la
capacité de base de remplacer le mot de passe.

**Independent Test**: Peut être testé seul en déclenchant la génération, en
vérifiant que le mot de passe affiché fonctionne bien pour une connexion
bénévole, et qu'aucune requête ultérieure ne permet de le récupérer en clair.

**Acceptance Scenarios**:

1. **Given** un administrateur habilité, **When** il déclenche la
   génération d'un mot de passe, **Then** un mot de passe est affiché une
   seule fois, immédiatement, et fonctionne pour une connexion bénévole.
2. **Given** un mot de passe qui vient d'être généré et affiché, **When**
   l'administrateur quitte ou recharge l'écran, **Then** ce mot de passe
   n'est plus consultable nulle part dans l'application, par personne.

---

### Edge Cases

- Le mot de passe bénévoles n'a jamais été défini (première installation, ou
  juste après cette migration depuis la variable d'environnement) : la page
  bénévoles doit rester fermée à toute connexion (comportement fail-closed
  déjà en place), sans qu'aucun mot de passe par défaut ne soit introduit en
  silence.
- Un administrateur perd ou oublie le mot de passe en cours : aucune
  procédure de récupération n'existe par conception (le mot de passe n'est
  jamais stocké de façon réversible) — seul un remplacement (Story 1) ou une
  nouvelle génération (Story 2) résout la situation, ce qui est le
  comportement attendu, pas un défaut à corriger.
- Deux administrateurs modifient le mot de passe presque simultanément : le
  dernier enregistrement fait foi, sans état incohérent.
- Un bénévole a une action en cours (formulaire de renommage ou de
  réattribution rempli mais non enregistré) au moment où le mot de passe est
  changé par un administrateur : sa session suivante échoue proprement
  (retour à l'écran de connexion), sans perte de données silencieuse côté
  serveur — l'écran bénévoles gère déjà l'expiration de session en cours
  d'action (#271).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un administrateur possédant un
  pouvoir dédié de définir un nouveau mot de passe pour l'accès partagé des
  bénévoles, en le saisissant.
- **FR-002**: Le système DOIT permettre à ce même administrateur de faire
  générer un nouveau mot de passe de façon sécurisée, sans le saisir
  lui-même.
- **FR-003**: Un mot de passe nouvellement généré DOIT être affiché en clair
  **une seule fois**, immédiatement après sa génération, et ne DOIT plus être
  récupérable ensuite par aucun moyen (ni par un autre écran, ni par une
  route de l'API).
- **FR-004**: Le système NE DOIT PAS stocker le mot de passe bénévoles sous
  une forme permettant de le retrouver en clair — ni par un administrateur,
  ni par quiconque ayant accès à la base de données.
- **FR-005**: Le système DOIT exiger un pouvoir dédié, distinct des pouvoirs
  déjà existants, pour consulter l'état de cette configuration ou la
  modifier (définir ou générer un mot de passe).
- **FR-006**: Le remplacement du mot de passe (par saisie ou par génération)
  DOIT invalider immédiatement toute session bénévole ouverte avant ce
  remplacement.
- **FR-007**: Le système DOIT continuer de refuser toute connexion bénévole
  tant qu'aucun mot de passe n'a jamais été défini (comportement fail-closed
  d'#271, préservé).
- **FR-008**: Le mécanisme de connexion et de vérification de session côté
  bénévoles (formulaire, cookie, garde des routes) DOIT continuer de
  fonctionner à l'identique pour un bénévole, sans changement perceptible
  côté page `/benevoles`.
- **FR-009**: Chaque remplacement de mot de passe (saisie ou génération)
  DOIT être tracé — quel administrateur, quand — sur le même patron que les
  autres gestes d'administration du dépôt, sans jamais consigner le mot de
  passe lui-même, ni en clair ni sous une forme qui permettrait de le
  reconstituer.

*Hors périmètre de cette spec :*

- La distribution du mot de passe aux bénévoles une fois généré ou saisi
  (communication hors-bande, canal existant du club) — hors de cette
  application.
- Toute notion de mot de passe individuel par bénévole : le mécanisme reste
  un secret **partagé**, unique, comme décidé pour #271 — cette feature n'en
  change pas la nature, seulement la façon dont il est administré.
- La variable d'environnement `BENEVOLE_SHARED_PASSWORD` : son retrait du
  code est une conséquence attendue de cette feature, mais le geste
  opérationnel de la retirer des environnements de déploiement (Render)
  n'est pas dans ce cadrage.

### Key Entities *(include if feature involves data)*

- **Configuration d'accès bénévoles** — l'état actuel du mot de passe
  partagé : sous une forme qui permet de vérifier une tentative de connexion
  sans jamais permettre de retrouver le mot de passe lui-même, plus la date
  et l'auteur du dernier remplacement.
- **Session bénévole** — déjà définie par #271 ; cette feature change ce qui
  la rend valide (elle doit continuer de dépendre de l'état courant de la
  configuration d'accès, de façon à ce qu'un remplacement invalide les
  sessions déjà ouvertes) sans changer sa nature pour un bénévole.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un administrateur habilité peut remplacer le mot de passe
  bénévoles (par saisie ou génération) en moins d'une minute, sans
  intervention technique (pas de redéploiement, pas d'accès serveur).
- **SC-002**: 100 % des sessions bénévoles ouvertes avant un remplacement de
  mot de passe échouent à leur premier geste suivant ce remplacement.
- **SC-003**: 0 mot de passe bénévoles n'est récupérable en clair après son
  enregistrement, dans 100 % des cas — ni par une route de l'API, ni par une
  requête directe en base au moyen des seules données stockées.
- **SC-004**: Un utilisateur du back-office sans le pouvoir dédié n'obtient
  aucune information sur la configuration d'accès bénévoles ni aucun moyen
  de la modifier, dans 100 % des tentatives.

## Assumptions

- Le mécanisme d'accès reste un **mot de passe partagé unique**, pas un
  système à mots de passe individuels — cette feature ne rouvre pas
  l'arbitrage produit d'#271 sur ce point (research.md §D1 de cette
  feature), elle en change seulement l'administration.
- L'écran de gestion vit dans le back-office existant, aux côtés des autres
  gestions d'accès du même registre (adresses autorisées, révocation de
  sessions) — le pouvoir dédié suit le modèle RBAC déjà en place (#115),
  sans nouvelle mécanique d'habilitation.
- Aucune exigence de complexité minimale n'est imposée sur un mot de passe
  saisi manuellement par un administrateur au-delà de ce qui est déjà
  raisonnable pour un secret partagé de cette nature — la génération
  sécurisée (Story 2) est le chemin recommandé pour un secret robuste, la
  saisie manuelle reste une échappatoire assumée (rotation d'urgence,
  préférence humaine).
- Aucune limite de fréquence n'est posée sur le remplacement du mot de passe
  — un administrateur peut le changer aussi souvent que nécessaire.
