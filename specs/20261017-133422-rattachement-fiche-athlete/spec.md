# Feature Specification: Revendiquer sa fiche athlète

**Feature Branch**: `feat/1325-claim-athlete` (empilée sur `epic/1312-member-accounts`)

**Created**: 2026-10-17

**Status**: Draft

**Input**: Issue #1325, epic #1312, sondage `docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md` (section Éligibilité). « Choisir cet athlète » est stocké dans le navigateur sans contrôle (`tcn-athlete`) et alimente « Ma saison ». `users.athlete_id` existe mais n'est jamais écrit. Un utilisateur connecté doit pouvoir demander le rattachement de sa fiche, un responsable le valider ou le refuser, et l'utilisateur se détacher. Hors périmètre : alertes de résultats (#467), modification de la fiche par l'utilisateur, équipes relais (discussion #208).

## Clarifications

### Session 2026-10-17

Décisions du mainteneur avant la spec, ou tranchées par l'option la plus sûre.

- Q: La liste d'adresses d'adhérents valide-t-elle d'office un rattachement ? → A: **non, jamais**. La liste ne porte que des adresses, sans nom : un adhérent pourrait se faire attribuer la fiche d'un autre. Toute demande passe par la file du back-office. La liste reste ce qu'elle est (#1334) : elle rend le compte adhérent, et la file l'affiche comme indice.
- Q: Le statut adhérent change-t-il ? → A: il se dérive de la liste **ou** d'un rattachement validé (sondage, Éligibilité), jamais d'une colonne de statut sur `users`. Se détacher retire la part du rattachement.
- Q: Une fiche peut-elle être rattachée à plusieurs comptes ? → A: oui, une même personne peut avoir plusieurs comptes (GitHub, Google, code e-mail : une identité inconnue crée toujours un compte, #114). Le responsable juge chaque demande ; la file signale les comptes déjà rattachés à la fiche.
- Q: Que devient la sélection gardée dans le navigateur ? → A: pour un compte rattaché, la fiche du compte la remplace partout où elle servait, et la sélection locale est effacée. Un visiteur sans compte rattaché (code d'accès seul, compte sans rattachement) garde la sélection locale : la majorité des adhérents entre encore par le code.
- Q: Combien de demandes ? → A: une seule demande en cours par compte. Une nouvelle demande remplace la précédente, en attente ou refusée.
- Q: Comment l'utilisateur apprend-il la décision ? → A: à sa prochaine visite (statut sur son compte), sans e-mail ni notification.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un utilisateur demande le rattachement de sa fiche (Priority: P1)

Sur une fiche athlète, un utilisateur connecté et sans rattachement choisit « C'est moi ». La demande part dans la file du back-office ; il voit qu'elle est en attente et peut l'annuler.

**Why this priority**: sans demande, rien à valider ; c'est l'entrée du parcours.

**Independent Test**: un compte connecté demande la fiche 42 : une demande en attente existe pour ce compte et cette fiche, la fiche n'est pas encore rattachée, le compte la voit « en attente ».

**Acceptance Scenarios**:

1. **Given** un utilisateur connecté sans rattachement, **When** il demande le rattachement d'une fiche, **Then** une demande en attente est enregistrée et son compte affiche « demande en attente » avec le nom de la fiche.
2. **Given** une demande en attente, **When** l'utilisateur l'annule, **Then** elle disparaît et rien n'est rattaché.
3. **Given** une demande en attente ou refusée, **When** l'utilisateur demande une autre fiche, **Then** la nouvelle demande remplace l'ancienne.
4. **Given** un utilisateur déjà rattaché, **When** il demande une autre fiche, **Then** la demande est refusée (conflit) : il doit d'abord se détacher.
5. **Given** un anonyme, **When** il demande un rattachement, **Then** il reçoit 401, et la fiche ne lui propose pas « C'est moi ».
6. **Given** une fiche inexistante, **When** un utilisateur la demande, **Then** il reçoit 404.

---

### User Story 2 - Un responsable valide ou refuse (Priority: P1)

Dans le back-office, le porteur d'un nouveau pouvoir dédié voit la file des demandes, avec pour chacune le compte (nom affiché, adresse), la fiche demandée, et les indices : licencié TCN de la saison rattaché à la fiche (nom, prénom), adresse du compte présente dans la liste d'adhérents, autres comptes déjà rattachés à la fiche. Il valide ou refuse. Une pastille du rail compte les demandes en attente.

**Why this priority**: c'est le contrôle qui rend le rattachement fiable.

**Independent Test**: une demande en attente ; validation par un porteur du pouvoir : le compte est rattaché à la fiche, la demande sort de la file, le journal d'administration trace le geste. Refus : rien n'est rattaché, la demande est marquée refusée.

**Acceptance Scenarios**:

1. **Given** une demande en attente, **When** le responsable la valide, **Then** le compte est rattaché à la fiche, la demande sort de la file et le geste est journalisé.
2. **Given** une demande en attente, **When** il la refuse, **Then** rien n'est rattaché, l'utilisateur voit « demande refusée » et le geste est journalisé.
3. **Given** une demande déjà traitée ou annulée, **When** un second responsable la traite, **Then** il reçoit 404 (ou conflit), sans double effet.
4. **Given** un connecté sans le pouvoir, **When** il lit ou traite la file, **Then** il reçoit 403 ; la pastille ne lui est pas rendue.
5. **Given** une fiche liée à un licencié TCN de la saison en cours, **When** la file l'affiche, **Then** le nom du licencié apparaît comme indice ; sinon l'indice dit « aucun licencié de la saison ».

---

### User Story 3 - L'Accueil personnel lit la fiche du compte (Priority: P2)

Un utilisateur rattaché retrouve « Ma saison » et toutes les surfaces qui lisaient l'athlète choisi (classements, roster, filtres) sur **sa** fiche, sans rien choisir ; le sélecteur ne lui propose plus d'en changer. Sa sélection locale est effacée.

**Why this priority**: c'est la récompense visible du rattachement, mais le rattachement a déjà de la valeur sans elle (statut adhérent, contrôle).

**Independent Test**: compte rattaché à la fiche 42 avec une sélection locale sur la fiche 7 : les surfaces lisent la fiche 42 et la sélection locale est vide.

**Acceptance Scenarios**:

1. **Given** un compte rattaché, **When** il ouvre l'accueil, **Then** « Ma saison » montre sa fiche, sans invitation à choisir.
2. **Given** un compte rattaché avec une sélection locale différente, **When** une page se charge, **Then** la sélection locale est effacée et la fiche du compte prévaut.
3. **Given** un visiteur sans compte rattaché, **When** il navigue, **Then** la sélection locale fonctionne comme avant.

---

### User Story 4 - L'utilisateur se détache (Priority: P2)

Depuis son compte, un utilisateur rattaché choisit « Me détacher de ma fiche », confirme, et redevient un compte sans fiche.

**Why this priority**: réversibilité exigée par l'issue, et par la minimisation (RGPD).

**Independent Test**: compte rattaché ; détachement : le compte ne porte plus de fiche, le statut adhérent ne tient plus qu'à la liste.

**Acceptance Scenarios**:

1. **Given** un compte rattaché, **When** il se détache, **Then** le compte ne porte plus de fiche, la fiche et ses résultats restent.
2. **Given** un compte rattaché absent de la liste d'adhérents, **When** il se détache, **Then** il n'est plus adhérent.
3. **Given** un compte sans rattachement, **When** il appelle le détachement, **Then** rien ne change (idempotent).

### Edge Cases

- Fiche fusionnée pendant qu'une demande l'attend : la demande suit la fiche conservée.
- Fiche supprimée (opposition, purge) pendant qu'une demande l'attend : la demande disparaît avec elle.
- Compte supprimé (#1326) : ses demandes disparaissent avec lui ; un rattachement n'empêche pas la suppression.
- Compte désactivé : il ne se connecte plus, ses demandes restent dans la file et le responsable peut les refuser.
- Le compte système des bénévoles ne demande jamais rien (il n'a pas de session).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Un utilisateur connecté MUST pouvoir demander le rattachement d'une fiche athlète existante ; une seule demande par compte, une nouvelle remplaçant l'ancienne (en attente ou refusée).
- **FR-002**: Un compte déjà rattaché MUST NOT pouvoir déposer de demande (conflit, message français).
- **FR-003**: L'utilisateur MUST pouvoir annuler sa demande en attente.
- **FR-004**: Aucune demande MUST NOT être validée d'office, quelle que soit la présence de l'adresse dans la liste d'adhérents.
- **FR-005**: Un nouveau pouvoir dédié MUST garder la lecture et le traitement de la file ; il est de type administration.
- **FR-006**: La file MUST afficher, par demande : compte (nom affiché, adresse), fiche (nom, prénom, club), licencié TCN de la saison en cours rattaché à la fiche s'il existe, présence de l'adresse du compte dans la liste d'adhérents de la saison, nombre de comptes déjà rattachés à la fiche, date de la demande.
- **FR-007**: Valider MUST rattacher le compte à la fiche et retirer la demande ; refuser MUST marquer la demande refusée sans rien rattacher ; les deux gestes MUST être journalisés dans le journal d'administration, dans la transaction de leur effet.
- **FR-008**: Traiter une demande qui n'est plus en attente MUST échouer sans effet.
- **FR-009**: Une pastille du rail admin MUST compter les demandes en attente, pour les seuls porteurs du pouvoir.
- **FR-010**: La session (`/auth/me`) MUST exposer, de façon additive, la fiche rattachée (identifiant, nom, prénom) et l'état de la demande en cours (en attente ou refusée, avec la fiche visée).
- **FR-011**: Le statut adhérent MUST se dériver de la liste d'adhérents **ou** d'un rattachement, sans colonne de statut.
- **FR-012**: L'utilisateur MUST pouvoir se détacher ; le détachement est idempotent et journalisé côté serveur (journal applicatif, pas le journal d'administration, qui ne trace que les gestes d'administration).
- **FR-013**: Pour un compte rattaché, l'interface MUST lire la fiche du compte là où elle lisait la sélection locale (la sélection locale antérieure est remplacée par la fiche du compte) et ne plus proposer d'en choisir une autre ; au détachement, la sélection locale est vidée.
- **FR-014**: Une fusion de fiches MUST reporter les demandes sur la fiche conservée ; la suppression d'une fiche MUST emporter ses demandes ; la suppression d'un compte MUST emporter ses demandes.
- **FR-015**: La politique de confidentialité MUST mentionner le lien entre un compte et une fiche athlète (finalité, durée : celle du compte, détachable à tout moment).
- **FR-016**: Les messages visibles MUST être en français ; les routes publiques existantes ne changent pas de contrat (ajouts seulement).

### Key Entities

- **Demande de rattachement**: un compte, une fiche, un état (en attente, refusée), sa date de création et de dernière décision. Une au plus par compte.
- **Rattachement**: le lien validé compte → fiche (`users.athlete_id`, déjà en base). Plusieurs comptes peuvent viser la même fiche.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un utilisateur dépose une demande en deux gestes depuis une fiche (« C'est moi », confirmer).
- **SC-002**: Un responsable traite une demande en un geste depuis la file, avec tous les indices sous les yeux, sans ouvrir d'autre écran.
- **SC-003**: 100 % des rattachements passent par une validation humaine journalisée.
- **SC-004**: Un compte rattaché ne voit jamais la fiche d'une sélection locale antérieure.

## Assumptions

- Le pouvoir s'appelle `athlete_claims:review` et rejoint le rôle administrateur par la mécanique existante du catalogue (le superutilisateur le porte d'office).
- La demande refusée reste visible de son auteur jusqu'à sa prochaine demande ou la suppression de son compte ; aucune purge propre n'est ajoutée (la ligne ne porte qu'un compte et une fiche, et suit le compte).
- Le bouton « C'est moi » vit sur la fiche athlète ; l'état (en attente, refusée, rattachée, se détacher) vit dans le menu du compte.
- La connexion d'un adhérent par Entra (#1323) n'est pas un prérequis : un compte GitHub peut aussi demander.
