# Feature Specification: Comptes membres, socle (liste d'adhérents, connexion ouverte, Entra External ID)

**Feature Branch**: `epic/1312-member-accounts` (une branche et une PR par sous-issue : #1334, #1322, #1323)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Epic #1312, sous-issues #1334, #1322 et #1323. Le sondage `docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md` **prime** sur cette spec ; toute divergence se tranche en re-sondant. Ouvrir la connexion aux adhérents du club : une liste d'e-mails d'adhérents importée depuis l'export AssoConnect fait foi pour reconnaître un adhérent ; ouvrir une session n'exige plus d'être inscrit dans la liste d'autorisation du back-office ; un nouveau moyen de connexion, Entra External ID (Google et code à usage unique par e-mail), décrit en infrastructure as code sous contrainte de budget zéro. Hors périmètre : rattachement de fiche athlète (#1325), suppression de compte (#1326), domaine de connexion personnalisé, extensions personnalisées Entra, liaison de plusieurs identités à un même utilisateur.

## Clarifications

### Session 2026-10-11

Décisions prises avant la spec avec l'utilisateur (périmètre, voie Spec Kit, livraison par branche d'epic) ou tranchées par l'option recommandée du sondage.

- Q: Quelle liste fait foi pour reconnaître un adhérent ? → A: une liste d'e-mails d'adhérents dédiée, importée depuis l'export AssoConnect ou complétée à la main, **distincte** de la liste d'autorisation du back-office (sources, cycle de vie et conservation différents ; les fondre ferait d'un contributeur externe un adhérent).
- Q: Dans ce lot, qu'est-ce qu'un compte adhérent ? → A: un compte dont l'adresse vérifiée retenue figure dans la liste d'adhérents qui compte. Le rattachement validé de fiche athlète (#1325) s'ajoutera comme seconde voie.
- Q: Quelle liste compte à une date donnée ? → A: celle de la saison en cours (bascule au 1ᵉʳ septembre) ; tant que la saison en cours n'a reçu aucune adresse **importée**, celle de la saison précédente continue de compter, pour ne pas fermer tous les adhérents entre la rentrée et le premier import ; une adresse ajoutée à la main pour la saison en cours compte aussi, sans faire basculer la liste (revue de #1334 : un seul ajout manuel en septembre fermait sinon tous les adhérents).
- Q: Un import efface-t-il les ajouts manuels ? → A: non. Un import remplace les adresses importées de sa saison ; les adresses ajoutées à la main restent jusqu'à leur retrait.
- Q: Le statut adhérent est-il figé à la connexion ? → A: non, il est réévalué à chaque requête : retirer une adresse de la liste prend effet immédiatement, sans révoquer de session.
- Q: Quel moyen de connexion ajouter ? → A: Entra External ID (Google et code par e-mail envoyé par Microsoft), gratuit jusqu'à 50 000 utilisateurs actifs par mois ; décrit en infrastructure as code ; sans domaine personnalisé ni SMS (facturés).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'administrateur tient la liste des adhérents à partir de l'export AssoConnect (Priority: P1) · #1334

Un administrateur exporte les contacts depuis AssoConnect, téléverse le fichier dans le back-office et voit la liste des adresses d'adhérents de la saison mise à jour. Il peut aussi ajouter ou retirer une adresse à la main.

**Why this priority**: sans liste, aucun adhérent ne peut être reconnu ; c'est la donnée dont dépendent les deux autres histoires.

**Independent Test**: téléverser un fichier d'export contenant une colonne d'adresses, constater que la liste de la saison les contient, puis qu'un second import sans l'une d'elles la retire ; vérifier qu'une adresse ajoutée à la main survit à l'import.

**Acceptance Scenarios**:

1. **Given** un administrateur habilité et un export AssoConnect (CSV ou tableur) contenant une colonne d'e-mails, **When** il l'importe pour la saison en cours, **Then** chaque adresse valide est enregistrée normalisée (casse et espaces), les doublons sont fusionnés, et un compte rendu indique ajoutées, retirées, inchangées et lignes ignorées.
2. **Given** une liste déjà importée pour la saison, **When** un nouvel import ne contient plus une adresse importée auparavant, **Then** cette adresse cesse de compter.
3. **Given** une adresse ajoutée à la main, **When** un import de la même saison ne la contient pas, **Then** elle reste dans la liste.
4. **Given** un fichier sans colonne d'e-mails reconnaissable, **When** il est importé, **Then** l'import est refusé avec un message en français et la liste est inchangée.
5. **Given** un utilisateur sans le pouvoir de gérer la liste, **When** il tente de la lire, de l'importer ou de la modifier, **Then** l'accès est refusé.
6. **Given** un exploitant ayant accès au serveur, **When** il lance l'import en ligne de commande avec le même fichier, **Then** le résultat est identique à celui du back-office et le compte rendu est lisible par une machine.
7. **Given** le traitement de purge périodique, **When** il s'exécute, **Then** les listes antérieures à la saison précédente sont supprimées.

---

### User Story 2 - Un adhérent se connecte et le site s'ouvre sans code partagé (Priority: P1) · #1322

Un adhérent dont l'adresse figure dans la liste se connecte avec un moyen proposé sur la page de connexion. Il n'est inscrit nulle part dans la liste d'autorisation du back-office. Il accède au site sans saisir le code d'accès partagé, et n'obtient aucun pouvoir d'administration.

**Why this priority**: c'est la valeur visible de l'epic pour les adhérents, et le préalable au rattachement de fiche (#1325).

**Independent Test**: avec un fournisseur de test, se connecter sous une adresse vérifiée présente dans la liste d'adhérents mais absente de la liste d'autorisation : la session s'ouvre, le site répond sans code d'accès, toute route du back-office refuse.

**Acceptance Scenarios**:

1. **Given** une adresse vérifiée absente de la liste d'autorisation, **When** la personne se connecte, **Then** la session s'ouvre (là où elle était refusée jusqu'ici) et le compte n'a aucun rôle.
2. **Given** un compte connecté dont l'adresse figure dans la liste d'adhérents qui compte, **When** il consulte le site sans code d'accès partagé, **Then** le site répond comme avec le code.
3. **Given** un compte connecté dont l'adresse ne figure pas dans la liste d'adhérents, **When** il consulte le site sans code d'accès, **Then** le site reste fermé exactement comme pour un anonyme, et la page d'accès l'explique sans révéler le contenu de la liste.
4. **Given** un adhérent connecté, **When** son adresse est retirée de la liste, **Then** sa requête suivante n'est plus dispensée du code d'accès, sans qu'il soit déconnecté.
5. **Given** une adresse inscrite dans la liste d'autorisation avec un rôle du premier jour, **When** la personne se connecte pour la première fois, **Then** elle reçoit ce rôle comme aujourd'hui.
6. **Given** une adresse non vérifiée par le fournisseur, **When** la personne tente de se connecter, **Then** la connexion est refusée comme aujourd'hui.
7. **Given** un compte désactivé (adresse retirée de la liste d'autorisation, par exemple), **When** il tente de se connecter, **Then** la connexion est refusée comme aujourd'hui.
8. **Given** un compte connecté sans rôle, **When** la connexion se termine, **Then** il arrive sur l'espace public du site et non sur un écran d'administration inutilisable.

---

### User Story 3 - Se connecter avec Google ou un code reçu par e-mail (Priority: P2) · #1323

Sur la page de connexion, un bouton propose de se connecter via le service d'identité du club (Entra External ID). La personne choisit Google ou reçoit un code par e-mail, puis revient connectée sur le site.

**Why this priority**: GitHub ne convient pas aux adhérents ; sans moyen familier, l'ouverture de la connexion (US2) ne sert à personne. Elle vient après US2 car elle s'appuie sur la même règle d'ouverture.

**Independent Test**: avec un fournisseur d'identité simulé qui émet des jetons signés, parcourir l'aller-retour complet : le jeton est validé, le compte est résolu par son identifiant chez le fournisseur, l'adresse vérifiée est retenue. Le test réel sur le tenant est un prérequis de mise en production (FR-021).

**Acceptance Scenarios**:

1. **Given** le fournisseur configuré, **When** la page de connexion se charge, **Then** elle propose ce moyen à côté de GitHub ; non configuré, il n'apparaît pas.
2. **Given** un retour de parcours avec un jeton d'identité valide (signature, émetteur, audience, nonce, expiration) portant une adresse vérifiée, **When** il est traité, **Then** la session s'ouvre selon les règles de US2.
3. **Given** un jeton dont la signature, l'émetteur, l'audience, le nonce ou l'expiration est invalide, **When** il est traité, **Then** la connexion est refusée avec un code d'erreur de l'ensemble fermé existant, sans détail du fournisseur.
4. **Given** un jeton sans adresse ou dont l'adresse n'est pas établie comme vérifiée, **When** il est traité, **Then** la connexion est refusée pour adresse non vérifiée.
5. **Given** une personne déjà connue chez ce fournisseur qui a changé d'adresse, **When** elle se reconnecte, **Then** elle retrouve le même compte (résolution par l'identifiant du fournisseur, jamais par l'adresse).
6. **Given** une adresse déjà portée par un compte GitHub, **When** une personne se connecte par Entra avec cette adresse, **Then** un compte distinct est créé (aucun appariement par adresse).
7. **Given** l'infrastructure décrite dans le dépôt, **When** un exploitant la déploie sur la souscription du club, **Then** le tenant externe, l'application et les moyens de connexion sont créés sans ressource facturée, et la procédure documente chaque étape que l'outillage ne couvre pas.

### Edge Cases

- Fichier d'import avec plusieurs colonnes ressemblant à un e-mail : la première colonne reconnue par son en-tête est lue, les autres ignorées.
- Adresse syntaxiquement invalide dans l'import : ligne ignorée et comptée, l'import continue.
- Import vide (en-tête seul) : refusé, pour ne pas vider la liste de la saison par erreur.
- Même adresse importée et ajoutée à la main : une seule entrée, qui reste manuelle tant qu'elle n'est pas retirée.
- Rentrée de septembre avant tout import : la liste de la saison précédente continue de compter.
- Adhérent dont l'adresse AssoConnect diffère de celle de son compte : non reconnu ; l'administrateur ajoute l'adresse du compte à la main (en attendant #1325).
- Compte GitHub existant d'un exploitant qui est aussi adhérent : cumule rôle et statut adhérent, l'un n'implique pas l'autre.
- Adresse inscrite à la liste d'autorisation avec un rôle du premier jour alors qu'un compte porte déjà cette adresse (adhérent connecté avant) : l'inscription avec rôle est refusée (409) avec un message qui renvoie à l'écran « Rôles des utilisateurs » ; le rôle n'est jamais donné par l'adresse.
- Adresse inscrite que le fournisseur cesse de certifier au profit d'une autre : le compte garde l'adresse inscrite, pour que son retrait le désactive encore.
- Création massive de comptes sans droit par des inconnus : le plafond de débit des routes de connexion s'applique ; un compte sans rôle ni statut adhérent n'ouvre rien.
- Fournisseur Entra indisponible ou clés de signature introuvables : refus avec le code « fournisseur indisponible », aucune session.
- Rotation des clés de signature du fournisseur : un jeton signé par une clé nouvelle est accepté après rafraîchissement des clés publiques.
- Le compte système partagé des bénévoles n'est jamais adhérent.

## Requirements *(mandatory)*

### Functional Requirements

**Liste d'adhérents (#1334)**

- **FR-001**: Le système DOIT conserver une liste d'adresses e-mail d'adhérents par saison, chaque entrée portant son adresse normalisée, sa saison et son origine (import ou ajout manuel), distincte de la liste d'autorisation du back-office.
- **FR-002**: Un administrateur habilité DOIT pouvoir importer un fichier CSV ou tableur issu de l'export AssoConnect pour une saison ; seule la colonne d'adresses e-mail est lue, toute autre colonne est ignorée et n'est jamais stockée.
- **FR-003**: Un import DOIT remplacer les entrées importées de sa saison par celles du fichier, sans toucher aux entrées manuelles, et rendre un compte rendu (ajoutées, retirées, inchangées, lignes ignorées).
- **FR-004**: Un import sans colonne d'e-mails reconnaissable ou sans aucune adresse valide DOIT être refusé sans modifier la liste.
- **FR-005**: Un administrateur habilité DOIT pouvoir consulter la liste d'une saison, y ajouter une adresse et en retirer une.
- **FR-006**: Le même import DOIT être disponible en ligne de commande, avec un compte rendu parsable et des codes de sortie conformes aux conventions de la CLI.
- **FR-007**: La gestion de la liste DOIT être gardée par un pouvoir dédié ; le rôle superutilisateur le franchit sans migration.
- **FR-008**: La saison qui compte à une date donnée est la saison en cours dès qu'elle contient au moins une entrée importée, sinon la saison précédente. Une adresse « compte » si elle figure dans la saison qui compte ou dans la saison en cours (avant le premier import, la saison en cours ne porte que des ajouts manuels, qui comptent donc en plus de la liste précédente).
- **FR-009**: La purge périodique DOIT supprimer les entrées des saisons antérieures à la saison précédente.
- **FR-010**: La base légale et la politique de confidentialité DOIVENT décrire ce traitement (finalité : reconnaître un adhérent à la connexion ; données : adresse e-mail et saison ; conservation : saison en cours et précédente ; accès : administrateurs habilités).

**Connexion ouverte (#1322)**

- **FR-011**: Ouvrir une session NE DOIT PLUS exiger d'inscription dans la liste d'autorisation ; une adresse vérifiée par le fournisseur reste exigée.
- **FR-012**: La liste d'autorisation DOIT continuer de porter le rôle du premier jour, réclamé une seule fois à la création du compte, et la désactivation d'un compte DOIT continuer de refuser sa connexion.
- **FR-013**: Un compte DOIT être adhérent si son adresse retenue figure dans la liste qui compte (FR-008) ; ce statut est dérivé à chaque requête, jamais enregistré sur le compte, et le compte système des bénévoles ne l'est jamais.
- **FR-014**: Une session d'un compte adhérent DOIT dispenser du code d'accès partagé, sur l'interface comme sur l'API ; une session d'un compte non adhérent NE DOIT PAS en dispenser.
- **FR-015**: Un compte sans rôle n'obtient aucun pouvoir : toute ressource gardée par un pouvoir lui répond par un refus.
- **FR-016**: À la connexion, quand le fournisseur certifie plusieurs adresses, l'adresse retenue DOIT être, dans l'ordre, la première inscrite à la liste d'autorisation, sinon la première qui compte dans la liste d'adhérents, sinon la principale.
- **FR-017**: Après connexion, un compte sans rôle DOIT arriver sur l'espace public, et l'interface NE DOIT PAS lui présenter d'entrée vers le back-office.

**Entra External ID (#1323)**

- **FR-018**: Le système DOIT proposer un moyen de connexion « Entra External ID » par code d'autorisation avec PKCE, annoncé par la liste des moyens dès qu'il est configuré et absent sinon.
- **FR-019**: Le jeton d'identité DOIT être validé (signature par les clés publiques du fournisseur, émetteur, audience, nonce lié au parcours, expiration) avant toute ouverture de session ; tout échec DOIT se traduire par un code de l'ensemble fermé existant.
- **FR-020**: Le compte DOIT être résolu par l'identifiant stable du fournisseur, jamais par l'adresse ; seule une adresse établie comme vérifiée est présentée aux règles de connexion.
- **FR-021**: La mise en production DOIT être précédée d'un constat sur le tenant réel qu'une adresse vérifiée est présente dans le jeton pour une connexion Google et pour une connexion par code e-mail ; le résultat est consigné dans le sondage. En cas d'échec, le repli est Google en direct, sans changer les règles de connexion.
- **FR-022**: Toute sortie réseau du fournisseur DOIT passer par le transport sortant gardé du projet.
- **FR-023**: Le tenant externe, l'application et ses moyens de connexion DOIVENT être décrits dans le dépôt en infrastructure as code, déployables sur la souscription existante sans ressource facturée (ni domaine personnalisé, ni SMS) ; toute étape non couverte par l'outillage DOIT être documentée comme procédure.
- **FR-024**: Les réglages du fournisseur DOIVENT être documentés par environnement, et la politique de confidentialité DOIT citer Microsoft comme sous-traitant.

### Key Entities

- **Adresse d'adhérent**: une adresse e-mail normalisée rattachée à une saison, avec son origine (import ou manuel) et sa date d'ajout. Ne porte ni nom ni autre donnée de l'export.
- **Compte (utilisateur)**: existant. Gagne un statut adhérent **dérivé** de son adresse retenue et de la liste qui compte ; ne porte toujours aucun rôle en colonne.
- **Identité**: existante. Un nouveau fournisseur `entra` y range l'identifiant stable du fournisseur.
- **Liste d'autorisation**: existante. Ne conditionne plus l'ouverture d'un compte ; reste la porte du back-office et du rôle du premier jour.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un administrateur met à jour la liste de la saison à partir d'un export AssoConnect de 300 adresses en moins de 2 minutes, sans intervention technique.
- **SC-002**: 100 % des adhérents dont l'adresse du compte figure dans la liste accèdent au site sans code partagé après connexion.
- **SC-003**: 0 compte non adhérent et sans rôle n'accède au site sans code ni à une ressource du back-office (vérifié par tests sur l'inventaire des routes).
- **SC-004**: Le retrait d'une adresse de la liste prend effet dès la requête suivante de l'adhérent concerné.
- **SC-005**: Le coût mensuel ajouté de l'infrastructure reste à 0 € jusqu'à 50 000 utilisateurs actifs par mois.
- **SC-006**: Un adhérent sans compte GitHub se connecte par Google ou par code e-mail en moins d'une minute.

## Assumptions

- L'export AssoConnect des contacts contient une colonne d'adresses e-mail identifiable par son en-tête (colonnes exactes non vérifiées par le sondage ; la reconnaissance accepte plusieurs libellés usuels).
- Le club dispose d'un administrateur Azure capable de déployer l'infrastructure sur la souscription « Abonnement TCN » et de créer le client OAuth Google nécessaire à la fédération.
- Le test réel sur tenant (FR-021) est mené par l'exploitant après livraison du code ; le code se teste sans réseau contre un fournisseur simulé.
- La garde du code d'accès partagé (#509) et la garde par pouvoir (#115) restent orthogonales ; seule s'ajoute la dispense pour un compte adhérent.
- La navigation par espaces (#1295) n'est pas encore sur `main` ; l'arrivée d'un compte sans rôle sur l'espace public se fait avec la navigation en place au moment de l'implémentation.
