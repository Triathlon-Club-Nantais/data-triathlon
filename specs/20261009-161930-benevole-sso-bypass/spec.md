# Feature Specification: Accès bénévoles sans mot de passe pour l'administrateur qui le gère

**Feature Branch**: `feat/1272-benevole-access-sso-bypass`

**Created**: 2026-10-09

**Status**: Draft

**Input**: Issue #1272. Un utilisateur SSO authentifié qui détient le pouvoir `benevole_access:manage` accède à la page de vérification des résultats (`/benevoles`) et à ses ressources sans saisir le mot de passe partagé des bénévoles. Le critère est un pouvoir, jamais un rôle (FR-017 du socle d'autorisation). Sans ce pouvoir, comportement inchangé. Les gestes d'un tel administrateur sont journalisés à son nom. Hors périmètre : le mot de passe partagé lui-même (gestion, rotation, plafond de débit) et la garde du site.

## Clarifications

### Session 2026-10-09

Questions tranchées en autonomie par l'option recommandée (voie Spec Kit choisie par l'utilisateur, consigne d'autonomie).

- Q: Quand un administrateur détient le pouvoir et porte aussi un cookie bénévoles valide, à qui le geste est-il attribué au journal ? → A: à son identité SSO ; le cookie ne sert qu'à qui n'est pas admis par pouvoir (gain de traçabilité visé par l'issue).
- Q: Un utilisateur connecté sans le pouvoir et sans cookie reçoit-il un 403 (droit manquant) ou le 401 actuel ? → A: le 401 actuel, même code et même message qu'un anonyme ; l'issue l'exige et un 403 révélerait le chemin par pouvoir.
- Q: Que devient le bouton « Se déconnecter » de la page bénévoles pour un administrateur admis par pouvoir ? → A: il est masqué ; ce geste ne retire que le cookie bénévoles et ne peut pas lui ôter l'accès, l'afficher promettrait une déconnexion qui n'a pas lieu.
- Q: Faut-il tracer chaque lecture faite par un administrateur admis par pouvoir ? → A: non ; seules les écritures vont au journal d'administration, comme pour les bénévoles. Les lectures ne sont pas journalisées aujourd'hui.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'administrateur qui gère le mot de passe bénévoles entre sans le saisir (Priority: P1)

Un administrateur connecté par SSO, qui détient le pouvoir de consulter et de remplacer le mot de passe bénévoles, ouvre la page de vérification des résultats. La file s'affiche directement, sans formulaire de mot de passe, et il peut valider, rejeter, corriger, renommer ou réattribuer comme un bénévole.

**Why this priority**: c'est la demande. Lui faire saisir un secret qu'il peut déjà lire et remplacer ne protège rien et lui coûte un geste à chaque visite.

**Independent Test**: se connecter par SSO avec un compte qui détient le pouvoir, sans cookie bénévoles, ouvrir la page : la file s'affiche et une validation réussit.

**Acceptance Scenarios**:

1. **Given** un utilisateur connecté qui détient le pouvoir et aucun cookie bénévoles, **When** il ouvre la page de vérification, **Then** la file s'affiche sans formulaire de mot de passe.
2. **Given** le même utilisateur, **When** il appelle n'importe quelle ressource gardée de la page (file, rejetés, historique, compteur, recherche d'athlètes, validation, rejet, annulation de rejet, correction de champs, renommage, réattribution), **Then** la ressource répond comme pour un bénévole muni du cookie.
3. **Given** un utilisateur dont le rôle superutilisateur franchit tout pouvoir, **When** il ouvre la page, **Then** il entre aussi, puisque le pouvoir lui est effectivement acquis.

---

### User Story 2 - Sans le pouvoir, rien ne change (Priority: P1)

Un visiteur anonyme, ou un utilisateur connecté qui ne détient pas le pouvoir, n'accède à la page qu'avec le mot de passe partagé, exactement comme aujourd'hui.

**Why this priority**: la garde ne doit pas s'ouvrir à qui n'en a pas le droit. Une régression ici ouvrirait la modération des résultats.

**Independent Test**: appeler une ressource gardée connecté sans le pouvoir et sans cookie : refus identique à celui d'un anonyme ; puis avec le cookie : accès.

**Acceptance Scenarios**:

1. **Given** un utilisateur connecté sans le pouvoir et sans cookie bénévoles, **When** il appelle une ressource gardée, **Then** il reçoit le même refus « non authentifié » qu'un anonyme.
2. **Given** un anonyme muni d'un cookie bénévoles valide, **When** il appelle une ressource gardée, **Then** l'accès est accordé, comme aujourd'hui.
3. **Given** un utilisateur connecté sans le pouvoir mais muni d'un cookie bénévoles valide, **When** il appelle une ressource gardée, **Then** l'accès est accordé au titre du cookie.
4. **Given** une session SSO expirée, révoquée ou invalide et aucun cookie, **When** une ressource gardée est appelée, **Then** le refus est le même 401.
5. **Given** la configuration du mot de passe absente et un utilisateur sans le pouvoir, **When** il appelle une ressource gardée, **Then** le refus est le même 401 (fail closed).

---

### User Story 3 - Les gestes de l'administrateur sont tracés à son nom (Priority: P2)

Quand l'administrateur reconnu par son pouvoir valide, rejette, corrige, renomme ou réattribue, le journal d'administration enregistre son identité, et non plus le compte système partagé des bénévoles.

**Why this priority**: gain de traçabilité ; le geste reste possible sans lui, mais on sait désormais qui l'a fait.

**Independent Test**: valider un résultat en attente en tant qu'administrateur reconnu, lire le journal : l'auteur est cet administrateur.

**Acceptance Scenarios**:

1. **Given** un administrateur reconnu par son pouvoir, **When** il valide, rejette, annule un rejet, corrige, renomme ou réattribue, **Then** l'entrée du journal porte son identité.
2. **Given** un bénévole entré par le cookie seul, **When** il fait le même geste, **Then** l'entrée du journal porte le compte système, comme aujourd'hui.

---

### Edge Cases

- Un administrateur détenant le pouvoir **et** un cookie bénévoles valide : son identité SSO prime, le geste lui est attribué.
- Un administrateur perd le pouvoir pendant que la page est ouverte : l'appel suivant est refusé (401) s'il n'a pas de cookie, et la page bascule sur le formulaire.
- L'administrateur reconnu ne voit pas le bouton « Se déconnecter » de la page bénévoles : ce geste ne retire que le cookie bénévoles et ne lui ôterait pas l'accès.
- Les lectures de l'administrateur reconnu (file, rejetés, historique, compteur, recherche) ne sont pas journalisées, comme celles des bénévoles.
- La route d'ouverture de session par mot de passe et celle de fermeture restent inchangées.
- Le refus ne révèle jamais l'existence du chemin par pouvoir : même code et même message qu'aujourd'hui.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système MUST accorder l'accès à chaque ressource gardée de la page bénévoles à un utilisateur dont la session SSO est valide et qui détient effectivement le pouvoir `benevole_access:manage`, sans exiger le cookie bénévoles.
- **FR-002**: Le critère d'accès par SSO MUST être ce pouvoir, jamais un rôle nommé.
- **FR-003**: Pour tout autre appelant (anonyme, session invalide, connecté sans le pouvoir), le système MUST appliquer la garde actuelle à l'identique : cookie bénévoles valide exigé, configuration absente refusée, même code et même message de refus.
- **FR-004**: Un cookie bénévoles valide MUST continuer d'ouvrir l'accès, que l'appelant soit connecté ou non.
- **FR-005**: Tout geste d'écriture fait par un utilisateur admis au titre du pouvoir MUST être journalisé sous son identité ; tout geste fait au titre du cookie seul MUST rester journalisé sous le compte système.
- **FR-006**: Quand l'appelant est à la fois admis par pouvoir et muni du cookie, son identité SSO MUST primer pour la journalisation.
- **FR-007**: La page de vérification MUST afficher directement la file, sans formulaire de mot de passe, à un utilisateur admis au titre du pouvoir.
- **FR-008**: Le contrat public de l'API (chemins, corps, codes de réponse) MUST rester inchangé : seul l'ensemble des appelants admis s'élargit.
- **FR-009**: La page de vérification MUST masquer le bouton « Se déconnecter » à un utilisateur connecté qui détient le pouvoir.
- **FR-010**: Le refus opposé à un connecté sans le pouvoir et sans cookie MUST être le 401 d'un anonyme, jamais un 403.

### Key Entities

- **Acteur d'un geste bénévole**: l'identité inscrite au journal d'administration pour chaque écriture de la page ; l'utilisateur SSO admis par pouvoir, sinon le compte système « Bénévoles (accès partagé) ».

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un administrateur détenant le pouvoir atteint la file de validation en zéro saisie de mot de passe.
- **SC-002**: 100 % des appels aux ressources gardées faits sans cookie par un connecté sans le pouvoir sont refusés, avec la réponse d'un anonyme.
- **SC-003**: 100 % des gestes faits par un administrateur admis par pouvoir apparaissent au journal sous son identité.
- **SC-004**: Aucun test existant de la page bénévoles ni de la garde par mot de passe ne change d'attendu.

## Assumptions

- Le pouvoir `benevole_access:manage` existe déjà au catalogue et sa résolution (rôles, superutilisateur) est celle du socle d'autorisation, réutilisée telle quelle.
- La garde du site ne s'applique pas aux ressources bénévoles (exemption existante), et reste hors périmètre.
- La route d'ouverture de session par mot de passe, son plafond de débit et la gestion du mot de passe sont inchangés.
- Le compteur de la pastille de navigation, déjà demandé pour les comptes d'administration, profite de l'élargissement sans changement propre.
