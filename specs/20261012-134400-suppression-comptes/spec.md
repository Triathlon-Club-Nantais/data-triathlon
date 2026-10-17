# Feature Specification: Suppression des comptes (sur demande et après 5 ans d'inactivité)

**Feature Branch**: `feat/1326-account-deletion` (empilée sur `feat/1323-entra-external-id`, cible finale `epic/1312-member-accounts`)

**Created**: 2026-10-12

**Status**: Draft

**Input**: Issue #1326, epic #1312. Depuis l'ouverture de la connexion (#1322), toute personne qui se connecte laisse un compte, conservé sans limite. Un utilisateur doit pouvoir supprimer son compte, et un compte sans rôle inactif depuis 5 ans doit être supprimé automatiquement. Hors périmètre : suppression des résultats sportifs (oppositions, #334), suppression automatique dans l'annuaire Entra.

## Clarifications

### Session 2026-10-12

Décisions du mainteneur avant la spec, ou tranchées par l'option la plus sûre.

- Q: Que veut dire « supprimé » ? → A: suppression **physique** de la ligne du compte et de tout ce qui lui appartient (identités, sessions, rôles, groupes) ; les références facultatives d'autres données vers le compte sont mises à vide.
- Q: Que faire d'un compte encore cité par une donnée qui exige son existence (validation de saison, paires ou cas ignorés, configuration d'accès, journal d'administration) ? → A: il n'est jamais supprimé en silence ni ces traces avec lui. L'expiration le saute et le compte dans son rapport ; la suppression volontaire refuse avec un message invitant à contacter le club.
- Q: Qu'est-ce qu'une activité ? → A: l'ouverture d'une session ou son usage par une requête authentifiée ; la date de dernière activité est mise à jour au plus une fois par jour et par compte. Pour les comptes existants, la dernière ouverture de session connue, à défaut la date de création, sert de point de départ.
- Q: Les comptes porteurs d'un rôle expirent-ils ? → A: non, ils sont exclus de l'expiration ; ils restent supprimables sur demande, sauf le dernier administrateur.
- Q: Durée ? → A: 5 ans sans activité, à la date près du calendrier (un 29 février compte pour le 28).
- Q (revue de PR #1357): Comment finir la suppression dans l'annuaire Entra ? → A: la ligne de journal garde les identifiants Microsoft (`oid`) du compte supprimé, 12 mois, à cette seule fin ; jamais de comparaison de l'annuaire avec une base.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un utilisateur supprime son compte (Priority: P1)

Depuis son menu, un utilisateur connecté choisit « Supprimer mon compte », lit ce qui sera effacé, confirme, et se retrouve déconnecté sur l'espace public. S'il se reconnecte plus tard, un compte neuf, sans rôle, est créé.

**Why this priority**: droit à l'effacement, exigible dès que la connexion est ouverte à tous.

**Independent Test**: créer un compte avec identité, sessions, groupe et fiche athlète rattachée, appeler la suppression : la ligne du compte et ses dépendances n'existent plus, la session courante ne vaut plus rien, la fiche athlète existe toujours.

**Acceptance Scenarios**:

1. **Given** un utilisateur connecté, **When** il confirme la suppression, **Then** son compte, ses identités, ses sessions, ses rôles et ses appartenances aux groupes sont supprimés, son cookie de session est effacé et il est redirigé vers l'espace public.
2. **Given** un utilisateur qui a déclaré des actions de bénévolat ou posé des données à références facultatives, **When** il supprime son compte, **Then** ces données restent et ne pointent plus vers lui.
3. **Given** le dernier administrateur, **When** il demande la suppression, **Then** elle est refusée (conflit) avec un message français, rien n'est supprimé.
4. **Given** un utilisateur encore cité par une donnée qui exige son existence, **When** il demande la suppression, **Then** elle est refusée avec un message l'invitant à contacter le club, rien n'est supprimé.
5. **Given** un anonyme, **When** il appelle la suppression, **Then** il reçoit 401.
6. **Given** un compte supprimé, **When** la même personne se reconnecte, **Then** un compte neuf est créé, sans rôle ni groupe (aucun appariement par adresse).

---

### User Story 2 - Les comptes inactifs depuis 5 ans disparaissent (Priority: P1)

Le traitement de purge périodique supprime les comptes sans rôle qui n'ont pas été utilisés depuis 5 ans, et rend compte de ce qu'il a supprimé et sauté.

**Why this priority**: c'est la durée de conservation que la politique de confidentialité doit pouvoir annoncer.

**Independent Test**: comptes avec dates de dernière activité variées, avec et sans rôle, avec et sans référence obligatoire ; une passe à blanc puis réelle de la purge : seuls les comptes éligibles disparaissent, le rapport donne supprimés et sautés.

**Acceptance Scenarios**:

1. **Given** un compte sans rôle dont la dernière activité date de plus de 5 ans, **When** la purge s'exécute, **Then** il est supprimé physiquement comme en US1.
2. **Given** un compte sans rôle actif il y a moins de 5 ans, **When** la purge s'exécute, **Then** il est conservé.
3. **Given** un compte porteur d'un rôle, inactif depuis plus de 5 ans, **When** la purge s'exécute, **Then** il est conservé.
4. **Given** un compte éligible encore cité par une donnée qui exige son existence, **When** la purge s'exécute, **Then** il est conservé et compté comme « sauté » dans le rapport.
5. **Given** la purge en passe à blanc, **When** elle s'exécute, **Then** elle compte sans rien supprimer.
6. **Given** le compte système des bénévoles, **When** la purge s'exécute, **Then** il n'est jamais supprimé.

---

### User Story 3 - L'activité est tenue à jour (Priority: P1)

Chaque connexion et chaque usage d'une session repoussent la date de dernière activité du compte, sans écrire en base à chaque requête.

**Why this priority**: sans elle, l'expiration supprimerait des comptes actifs.

**Independent Test**: une connexion pose la date ; deux requêtes authentifiées le même jour n'écrivent qu'une fois ; une requête le lendemain la repousse.

**Acceptance Scenarios**:

1. **Given** une connexion réussie, **When** la session s'ouvre, **Then** la date de dernière activité du compte vaut maintenant.
2. **Given** une session utilisée plusieurs fois le même jour, **When** les requêtes s'enchaînent, **Then** la date n'est écrite qu'une fois ce jour-là.
3. **Given** des comptes créés avant cette fonctionnalité, **When** elle est déployée, **Then** leur date de dernière activité vaut leur dernière ouverture de session connue, à défaut leur date de création.

### Edge Cases

- Suppression volontaire pendant que d'autres sessions du même compte sont ouvertes ailleurs : toutes deviennent invalides.
- Compte rattaché à une fiche athlète : la fiche reste, seul le lien disparaît.
- Compte dont l'adresse figure encore dans la liste d'autorisation : la ligne d'autorisation reste (elle n'est pas un compte) ; une nouvelle connexion crée un compte neuf qui ne réclame pas un rôle déjà réclamé.
- Compte dont l'adresse figure dans la liste d'adhérents : la liste reste ; le compte neuf redevient adhérent à la reconnexion.
- Deux demandes de suppression simultanées du même compte : une seule aboutit, l'autre ne casse rien.
- Utilisateur de l'annuaire Entra : non supprimé automatiquement ; la procédure d'exploitation rappelle l'étape manuelle.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT conserver pour chaque compte une date de dernière activité, initialisée pour les comptes existants à leur dernière ouverture de session connue, à défaut à leur date de création.
- **FR-002**: L'ouverture d'une session DOIT poser la date de dernière activité ; l'usage d'une session par une requête authentifiée DOIT la repousser au plus une fois par jour et par compte.
- **FR-003**: Un utilisateur connecté DOIT pouvoir supprimer son compte après confirmation ; la suppression est physique et emporte ses identités, sessions, rôles et appartenances aux groupes, détache sa fiche athlète, et met à vide les références facultatives d'autres données vers lui.
- **FR-004**: La suppression d'un compte encore cité par une donnée qui exige son existence DOIT être refusée sans rien supprimer (volontaire : conflit avec message français invitant à contacter le club ; expiration : compte sauté et compté).
- **FR-005**: La suppression du dernier administrateur DOIT être refusée (conflit), conformément à l'invariant du dernier administrateur.
- **FR-006**: Le compte système des bénévoles NE DOIT JAMAIS être supprimé.
- **FR-007**: La purge périodique DOIT supprimer les comptes sans rôle dont la dernière activité est antérieure à maintenant moins 5 ans, avec passe à blanc, et compter supprimés et sautés dans son rapport.
- **FR-008**: Après suppression volontaire, le cookie de session DOIT être effacé et l'utilisateur renvoyé vers l'espace public.
- **FR-009**: Chaque suppression DOIT être tracée dans le journal d'administration sans y conserver l'adresse ni le nom du compte supprimé (identifiant seul, origine : demande ou expiration, et identifiants Microsoft `entra_oids` des connexions Entra, conservés avec le journal à la seule fin de supprimer l'utilisateur de l'annuaire).
- **FR-010**: La décision de base légale et la politique de confidentialité DOIVENT annoncer la conservation des comptes (5 ans sans activité, suppression sur demande depuis le menu) et la procédure d'exploitation DOIT rappeler la suppression manuelle de l'utilisateur dans l'annuaire Entra.

### Key Entities

- **Compte (utilisateur)**: gagne une date de dernière activité. Supprimé physiquement avec ses identités, sessions, rôles et groupes.
- **Données à référence obligatoire**: validations de saison, paires et cas ignorés, configurations d'accès, journal d'administration ; leur présence bloque la suppression.
- **Données à référence facultative**: actions de bénévolat, clubs connus, oppositions, configuration d'accès au site, etc. ; mises à vide à la suppression.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un utilisateur supprime son compte en moins de 30 secondes et 2 gestes depuis son menu.
- **SC-002**: Après suppression, 0 donnée personnelle du compte (adresse, nom, identifiants de fournisseur) ne subsiste dans les tables du compte (compte, identités, sessions, rôles, groupes) ni dans la ligne de journal de la suppression. Restent, par décision : l'adresse dans la liste d'autorisation ou d'adhérents (ce ne sont pas des comptes, cf. Edge Cases) et les lignes antérieures du journal d'administration, purgées à 12 mois.
- **SC-003**: Aucun compte sans rôle n'a une dernière activité de plus de 5 ans après une passe de purge, hors comptes sautés et signalés.
- **SC-004**: La tenue de l'activité ajoute au plus une écriture par compte et par jour.

## Assumptions

- La purge `purge-retention` tourne chaque semaine dans le batch de production (déjà en place).
- Le journal d'administration est conservé 12 mois : un compte inactif depuis 5 ans n'y est normalement plus cité.
- Les suppressions dans l'annuaire Entra restent manuelles (le flux client credentials est un module payant d'Entra External ID).
