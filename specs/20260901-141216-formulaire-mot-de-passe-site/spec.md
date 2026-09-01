# Feature Specification: Ouvrir le formulaire de crédit d'un athlète au mot de passe du site

**Feature Branch**: `809-formulaire-mot-de-passe-site`

**Created**: 2026-09-01

**Status**: Draft

**Input**: Issue GitHub #809 — corrige une décision d'accès erronée de #778
(sous-issue fusionnée de l'epic #776, désormais fermé). `POST
/api/v1/volunteer-actions` (formulaire public de crédit d'un athlète pour le
quota de saison) exige aujourd'hui une session SSO individuelle en plus du
mot de passe partagé du site. Recadrage produit explicite : le mot de passe
partagé doit suffire à soumettre une déclaration — la connexion SSO
individuelle est réservée à l'étape de validation admin (#779, inchangée).
Mécanisme visé, désigné explicitement par l'utilisateur : reprendre le même
fonctionnement que le formulaire de retour utilisateur (`POST /feedback`,
#267) — auteur optionnel, jamais exigé — en y ajoutant un champ de
rattachement à un athlète (déjà présent dans le formulaire existant, à
conserver).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Créditer un athlète sans compte personnel (Priority: P1)

Un visiteur qui a seulement saisi le mot de passe partagé du site (jamais
connecté via SSO) ouvre `/benevolat`, recherche un athlète, décrit une
activité de bénévolat qu'il a constatée, et soumet la déclaration — sans
jamais être invité à se connecter.

**Why this priority**: c'est la demande explicite de l'issue — sans cette
correction, le formulaire reste inutilisable par la majorité des visiteurs
qui n'ont qu'un mot de passe partagé, pas de compte SSO personnel.

**Independent Test**: avec uniquement le cookie du mot de passe du site (pas
de session SSO), `POST /api/v1/volunteer-actions` avec un `athlete_id`
valide, un titre et une description rend `201` ; côté écran, la section
« Créditer un athlète pour le quota de saison » de `/benevolat` s'affiche et
se soumet sans jamais présenter d'invite de connexion.

**Acceptance Scenarios**:

1. **Given** un visiteur ayant saisi le mot de passe du site, sans session
   SSO, **When** il ouvre `/benevolat`, **Then** la section de crédit d'un
   athlète s'affiche directement — pas d'invite « Se connecter ».
2. **Given** ce même visiteur, **When** il recherche un athlète, en choisit
   un, saisit titre et description et soumet, **Then** la déclaration est
   enregistrée avec le statut « en attente », comme aujourd'hui.
3. **Given** un appel direct à `POST /api/v1/volunteer-actions` avec
   uniquement le cookie du mot de passe du site (aucun cookie de session
   SSO), **When** la requête est envoyée avec un corps valide, **Then** elle
   rend `201`, pas `401`.
4. **Given** un visiteur connecté via SSO qui soumet la même déclaration,
   **When** elle est enregistrée, **Then** son identité reste tracée comme
   aujourd'hui (comportement inchangé pour un visiteur déjà connecté).

---

### Edge Cases

- Un appel sans **aucun** cookie — ni mot de passe du site, ni session SSO —
  continue de rendre `401` : la garde retirée est celle de la session
  individuelle, pas celle du mot de passe partagé (inchangée, posée en amont
  sur tout le routeur).
- Deux visiteurs anonymes distincts soumettant chacun une déclaration ne
  sont pas différenciés dans la file d'attente admin au-delà de ce que la
  déclaration elle-même porte (athlète visé, titre, description, horodatage)
  — il n'existe pas d'identité individuelle à afficher quand l'auteur n'est
  pas connecté, au même titre que les signalements du formulaire de retour
  utilisateur.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un visiteur ayant seulement
  franchi le mot de passe partagé du site (sans session SSO individuelle)
  de soumettre une déclaration de bénévolat créditant un athlète de son
  choix.
- **FR-002**: Le système NE DOIT PLUS exiger de session SSO individuelle
  pour cette soumission — le mot de passe partagé du site reste, lui,
  requis (inchangé).
- **FR-003**: Le système DOIT continuer à permettre la recherche d'un
  athlète sans session SSO individuelle (déjà le cas, à ne pas régresser).
- **FR-004**: Le système DOIT continuer à exiger une session SSO
  individuelle **et** le pouvoir dédié pour instruire (accepter/refuser)
  une déclaration en attente — l'étape de validation admin (#779) n'est pas
  concernée par ce recadrage.
- **FR-005**: Le système DOIT, quand un visiteur est malgré tout connecté
  via SSO au moment de la soumission, continuer à tracer son identité comme
  aujourd'hui — le retrait de l'obligation ne doit pas dégrader le cas où
  l'identité est disponible.
- **FR-006**: Le système DOIT permettre l'enregistrement d'une déclaration
  sans identité individuelle associée, sur le même principe que le
  formulaire de retour utilisateur existant (auteur optionnel).

### Key Entities *(include if feature involves data)*

- **VolunteerAction** (existant) : le champ qui trace l'auteur d'une
  déclaration passe d'obligatoire à optionnel — une déclaration reste
  valide sans identité individuelle associée.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des visiteurs n'ayant saisi que le mot de passe du site
  peuvent soumettre une déclaration de crédit d'athlète sans être invités à
  se connecter.
- **SC-002**: 0 % des soumissions valides (athlète existant, titre et
  description renseignés) provenant d'un visiteur sans session SSO
  n'échouent pour une raison d'authentification individuelle.
- **SC-003**: 100 % des déclarations, connectées ou non, restent instruites
  exclusivement par un titulaire du pouvoir de validation dédié, sans
  changement de ce contrôle.

## Assumptions

- Le formulaire d'auto-déclaration existant sur la même page (#751,
  déclaration nominative liée à l'auteur connecté) reste hors périmètre et
  continue d'exiger une session SSO — seule la section de crédit d'un
  athlète tiers (#778) est concernée par ce recadrage.
- Aucune limite de débit dédiée n'est ajoutée par cette sous-issue : la
  route reste derrière le mot de passe partagé du site (contrairement au
  formulaire de retour utilisateur, exposé sans aucune garde), ce qui borne
  déjà la surface d'abus à ceux qui connaissent ce mot de passe.
- L'affichage admin (file d'attente #779, liste des actions validées #781)
  doit rester correct pour une déclaration sans auteur individuel connu —
  aucun changement de comportement visible au-delà d'un repli d'affichage
  pour l'identité absente, sur le patron déjà en place pour les champs
  optionnels de ces écrans.
