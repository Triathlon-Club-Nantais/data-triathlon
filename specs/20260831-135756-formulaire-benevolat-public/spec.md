# Feature Specification: Formulaire public de déclaration de bénévolat

**Feature Branch**: `778-formulaire-benevolat`

**Created**: 2026-08-31

**Status**: Draft

**Input**: Issue GitHub #778 (sous-issue de l'epic #776) — « feat(benevolat):
public declaration form with athlete search ». Aujourd'hui, seul un admin
détenant `athletes:volunteer_manage` peut déclarer une action de bénévolat
pour un athlète, en un clic, sans titre ni description
(`SeasonValidationPanel.tsx:47-69`, `VolunteerAction` — `athlete_id, season,
declared_by_user_id, created_at`). L'objectif de cette sous-issue est
d'ouvrir cette déclaration à tout adhérent connecté, via un formulaire
public avec recherche d'athlète, titre et description — sans encore
implémenter la validation admin (sous-issue #779) ni retirer le bouton
existant (sous-issue #780).

**Distinction avec `VolunteerDeclaration` (#751, PR #769, livrée le
2026-08-31)** : cette dernière trace la vie associative d'un **membre**
(`user_id`), sans rapport avec le quota de saison. `VolunteerAction` reste
liée à l'**athlète** (`athlete_id`) et au quota de validation de saison (3
courses + 1 bénévolat, #709). Les deux tables restent indépendantes —
décision confirmée avec l'utilisateur au moment de ce spec malgré la
ressemblance de surface (titre + description + statut de validation).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Déclarer une action de bénévolat pour un athlète (Priority: P1)

Un adhérent connecté (aucun pouvoir RBAC particulier requis) veut signaler
qu'un athlète — lui-même ou un tiers — a effectué une action de bénévolat.
Il recherche l'athlète par nom et prénom, saisit un titre et une
description, puis valide. La déclaration est enregistrée à l'état « en
attente » (la validation admin proprement dite est hors périmètre, voir
#779).

**Why this priority**: C'est la raison d'être de cette sous-issue — sans
formulaire public, la déclaration reste un geste d'admin. C'est aussi un
livrable autonome : la trace existe dès cette étape, même avant que #779
n'ajoute l'instruction admin.

**Independent Test**: Un adhérent connecté ouvre le formulaire, recherche un
athlète par au moins 2 caractères de son nom ou prénom, le sélectionne,
saisit un titre et une description non vides, valide, et reçoit une
confirmation.

**Acceptance Scenarios**:

1. **Given** un adhérent connecté sur le formulaire de déclaration, **When**
   il saisit au moins 2 caractères dans le champ de recherche d'athlète,
   **Then** la liste des athlètes correspondants s'affiche (nom, prénom),
   insensible à la casse et aux accents.
2. **Given** un adhérent connecté ayant sélectionné un athlète, **When** il
   saisit un titre et une description non vides puis valide, **Then** une
   nouvelle déclaration est créée pour cet athlète, à l'état « en attente »,
   et une confirmation s'affiche.
3. **Given** un adhérent connecté sur le formulaire, **When** il tente de
   valider sans avoir sélectionné d'athlète, ou avec un titre ou une
   description vide, **Then** la validation est refusée avec un message
   d'erreur explicite, sans requête serveur inutile.
4. **Given** un visiteur non connecté, **When** il tente d'accéder au
   formulaire ou d'appeler son endpoint, **Then** l'accès est refusé (401).

---

### User Story 2 - Rechercher un athlète sans exposer de données sensibles (Priority: P2)

Le champ de recherche d'athlète du formulaire ne doit pas devenir une
nouvelle voie d'accès à des données réservées aux admins (ex. date de
naissance), ni nécessiter le mot de passe partagé bénévoles (`/benevoles`)
qui n'a aucun rapport avec cette fonctionnalité.

**Why this priority**: Sécurité et cohérence avec le patron existant
(`GET /benevoles/athletes`, lui-même un jumeau restreint de `GET
/athletes`) — nécessaire dès la première mise en production du formulaire,
mais secondaire au flux principal de l'US1.

**Independent Test**: Un adhérent connecté recherche un athlète et vérifie
que seuls nom et prénom apparaissent dans les résultats (pas de date de
naissance ni d'autre champ admin).

**Acceptance Scenarios**:

1. **Given** un adhérent connecté, **When** il recherche un athlète par nom,
   **Then** les résultats ne contiennent que les champs publics (nom,
   prénom, identifiant) — jamais la date de naissance.
2. **Given** un adhérent connecté sans le mot de passe partagé bénévoles,
   **When** il utilise la recherche du formulaire, **Then** l'accès
   fonctionne (gardé par sa seule session, pas par ce mot de passe).

---

### Edge Cases

- Recherche avec moins de 2 caractères → aucune requête déclenchée côté
  client, ou refus explicite côté serveur (paramétrage identique à
  `GET /benevoles/athletes`).
- Aucun athlète ne correspond à la recherche → état vide explicite, pas
  d'erreur.
- Titre ou description dépassant une longueur raisonnable → refus avec
  message d'erreur, pas de troncature silencieuse (cohérent avec #751).
- Double soumission (double-clic) → le bouton se désactive pendant la
  requête, pas de déclaration dupliquée par un simple double-clic.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT ajouter les champs `title` et `description`
  au modèle `VolunteerAction`, tous deux obligatoires pour toute nouvelle
  déclaration créée via le nouveau formulaire public.
- **FR-002**: Le système DOIT ajouter un champ `status` à `VolunteerAction`,
  avec une valeur par défaut « en attente » — la transition vers un autre
  état (validée/refusée) est hors périmètre de cette sous-issue (#779).
- **FR-003**: Le système DOIT permettre à tout adhérent connecté (session
  valide, aucun pouvoir RBAC requis) de créer une déclaration de bénévolat
  pour l'athlète de son choix, avec titre et description.
- **FR-004**: Le système DOIT refuser la création d'une déclaration dont le
  titre ou la description est vide.
- **FR-005**: Le système DOIT refuser l'accès au formulaire et à son
  endpoint à un visiteur non connecté (401).
- **FR-006**: Le système DOIT permettre la recherche d'un athlète par nom
  et/ou prénom, à partir de 2 caractères, insensible à la casse et aux
  accents — même comportement que `GET /benevoles/athletes` mais sans sa
  garde par mot de passe partagé.
- **FR-007**: Les résultats de recherche d'athlète DOIVENT se limiter aux
  champs publics (nom, prénom, identifiant) — pas de date de naissance ni
  d'autre champ réservé aux admins.
- **FR-008**: Le système NE DOIT PAS retirer ni modifier le bouton
  d'administration existant (`DeclarerBenevolat` de `SeasonValidationPanel`)
  — son retrait est le périmètre exclusif de la sous-issue #780.
- **FR-009**: Le système NE DOIT PAS implémenter l'instruction admin
  (accepter/refuser, permission de lecture dédiée) — périmètre exclusif de
  la sous-issue #779.

### Key Entities *(include if feature involves data)*

- **VolunteerAction** (existant, étendu) : action de bénévolat liée à un
  athlète et une saison. Nouveaux attributs : `title`, `description`,
  `status` (défaut « en attente »). Reste indépendant de
  `VolunteerDeclaration` (#751).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un adhérent connecté peut déclarer une action de bénévolat
  pour un athlète (recherche + titre + description) en moins d'une minute.
- **SC-002**: 100 % des déclarations créées via le nouveau formulaire ont un
  titre et une description non vides — aucune déclaration incomplète n'est
  jamais persistée.
- **SC-003**: 100 % des tentatives d'accès au formulaire ou à son endpoint
  par un visiteur non connecté sont refusées.
- **SC-004**: La recherche d'athlète ne renvoie jamais de champ réservé aux
  admins (date de naissance) dans le nouveau contexte public.

## Assumptions

- Le statut « en attente » posé par défaut sur toute nouvelle ligne
  n'affecte pas (encore) le calcul du quota de saison
  (`has_volunteer_action`) : ce calcul, aujourd'hui basé sur la simple
  existence d'une ligne, n'est modifié que par #779 quand la notion de
  validation devient effective. Avant #779, une déclaration « en attente »
  compte donc déjà pour le quota — comportement transitoire assumé, corrigé
  par #779.
- Le bouton admin existant (`DeclarerBenevolat`) continue d'insérer des
  lignes sans fixer explicitement `title`/`description`/`status` : ces champs
  restent optionnels au niveau service pour ce chemin existant, seul le
  nouveau formulaire les impose. #780 retirera ce bouton une fois #778
  posé.
- La saison de la déclaration reste celle en cours (`currentSeason()`),
  comme pour le bouton admin actuel — pas de sélecteur de saison dans le
  formulaire.
- Aucune notification (email, etc.) n'est envoyée à la création d'une
  déclaration.
- Le nouveau formulaire est accessible depuis une page dédiée (pas
  nécessairement la fiche athlète) — l'emplacement précis de l'UI (nouvelle
  route vs. entrée dans un menu existant) reste à trancher au plan
  (`/speckit-plan`), cette spec ne contraint que le comportement, pas la
  navigation.
