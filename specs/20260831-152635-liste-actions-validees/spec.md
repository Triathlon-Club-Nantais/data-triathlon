# Feature Specification: Liste des actions de bénévolat validées sur la fiche athlète

**Feature Branch**: `781-liste-actions-validees-fiche-athlete`

**Created**: 2026-08-31

**Status**: Draft

**Input**: Issue GitHub #781 (sous-issue de l'epic #776) — « feat(athletes):
list validated volunteer actions on athlete profile ». Aucune liste des
actions de bénévolat d'un athlète n'est exposée aujourd'hui — seul un
booléen `has_volunteer_action` existe côté quota de saison. Cette
sous-issue affiche, sur la fiche athlète, aux admins détenant la
permission de lecture posée par #779 (`athletes:volunteer_validate`), le
détail (titre + description) des actions déjà validées.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un admin habilité consulte les actions validées d'un athlète (Priority: P1)

Un admin détenant le pouvoir d'instruction des déclarations de bénévolat
ouvre la fiche d'un athlète et y voit la liste de ses actions de
bénévolat déjà validées (titre, description), sans avoir à recouper le
journal d'administration.

**Why this priority**: C'est la seule user story de cette sous-issue —
sans elle, la feature n'existe pas.

**Independent Test**: Un admin habilité ouvre la fiche d'un athlète ayant
au moins une action validée ; la liste apparaît avec titre et
description. Un athlète sans action validée affiche un état vide
explicite plutôt qu'aucune section.

**Acceptance Scenarios**:

1. **Given** un athlète ayant une action de bénévolat à l'état « validée »,
   **When** un admin détenant `athletes:volunteer_validate` ouvre sa
   fiche, **Then** la liste affiche cette action (titre et description).
2. **Given** un athlète ayant des actions « en attente » ou « refusées »
   mais aucune « validée », **When** un admin habilité ouvre sa fiche,
   **Then** la liste affiche un état vide explicite — les actions non
   validées n'apparaissent jamais.
3. **Given** un visiteur (connecté ou non) sans le pouvoir
   `athletes:volunteer_validate`, **When** il ouvre la fiche d'un
   athlète, **Then** aucune trace de cette section n'apparaît — ni
   liste, ni état vide, ni message de pouvoir manquant (patron
   `ParticipationAdminActions`, #439).
4. **Given** un athlète ayant plusieurs actions validées sur plusieurs
   saisons, **When** un admin habilité ouvre sa fiche, **Then** toutes
   apparaissent, triées de la plus récente à la plus ancienne — aucun
   filtre de saison n'est proposé dans cette itération.

---

### Edge Cases

- Une action validée par le chemin admin existant (#709, sans titre ni
  description) apparaît-elle dans la liste ? → Oui, avec un repli
  d'affichage explicite (ex. « — ») plutôt qu'une cellule vide muette.
- Athlète sans aucune action de bénévolat (jamais déclarée) → même état
  vide que « aucune validée » (US1 Scenario 2) — la liste ne distingue
  pas « jamais déclarée » de « déclarée mais non validée ».

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un titulaire de
  `athletes:volunteer_validate` de consulter la liste des actions de
  bénévolat d'un athlète dont le statut est « validée », avec leur titre
  et leur description.
- **FR-002**: Le système NE DOIT PAS inclure dans cette liste les actions
  à l'état « en attente » ou « refusée ».
- **FR-003**: Le système NE DOIT rendre aucune trace de cette
  fonctionnalité (section, message, état vide) à un visiteur qui ne
  détient pas `athletes:volunteer_validate`.
- **FR-004**: Le système NE DOIT PAS appliquer de filtre de saison à
  cette liste — toutes les actions validées de l'athlète, triées de la
  plus récente à la plus ancienne.
- **FR-005**: Le système DOIT afficher un état vide explicite quand
  l'athlète n'a aucune action validée.

### Key Entities *(include if feature involves data)*

- **VolunteerAction** (existant depuis #778/#779) : cette sous-issue
  n'ajoute aucun champ — elle expose en lecture les lignes déjà
  `status == "validee"` d'un athlète donné.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des actions affichées dans la liste sont à l'état
  « validée » — jamais « en attente » ni « refusée ».
- **SC-002**: 100 % des visiteurs sans `athletes:volunteer_validate` ne
  voient aucune trace de la section, quel que soit l'état de l'athlète
  consulté.
- **SC-003**: Un admin habilité peut lire titre et description de chaque
  action validée d'un athlète sans quitter sa fiche.

## Assumptions

- **Aucun geste d'écriture dans cette sous-issue** — lecture seule,
  cohérent avec le titre de l'issue et son périmètre exclu (« la
  validation elle-même »).
- **Pas de pagination** : le volume attendu par athlète (quelques actions
  par saison) ne justifie pas de limiter l'affichage.
- **Présentation visuelle simplifiée par rapport à `EventsTable.tsx`** :
  même famille de patron (`.tcn-table`, rôles ARIA table/rowgroup/row/
  cell) mais sans la duplication grille/cartes responsive complète — deux
  colonnes de texte (titre, description) ne débordent pas un écran
  étroit comme le font Date/Place/Format sur `EventsTable`, donc la
  complexité du seuil de bascule (#461) n'est pas justifiée ici
  (Principe VI).
- **Le pouvoir de lecture est le même que celui d'instruction** —
  `athletes:volunteer_validate` (#779, research.md D2) — pas un nouveau
  pouvoir dédié à la seule lecture ; l'issue #779 avait explicitement
  tranché pour un pouvoir unique couvrant consultation et décision.
