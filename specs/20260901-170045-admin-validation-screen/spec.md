# Feature Specification: Écran de validation admin des déclarations de crédit d'athlète

**Feature Branch**: `816-retrait-auto-declaration` (implémentée avec #816, même fenêtre de travail)

**Created**: 2026-09-01

**Status**: Draft

**Input**: Issue GitHub #817 (sous-issue de l'epic #815). Le workflow de
validation admin des déclarations de crédit d'un athlète (#779) n'a jamais eu
d'écran — l'API existe et fonctionne, mais aucun composant frontend ne
l'appelle. Implémentée immédiatement après #816 (retrait de
l'auto-déclaration), dans la même fenêtre de travail, pour que
`/admin/benevolat` ne traverse jamais d'état vide sur une branche partagée
(décision produit de #816).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instruire les déclarations en attente (Priority: P1)

Un administrateur titulaire du pouvoir de validation ouvre
`/admin/benevolat` et voit la liste des déclarations de crédit d'athlète en
attente — qui, pour quel athlète, quelle activité — et peut accepter ou
refuser chacune.

**Why this priority**: c'est la raison d'être de la sous-issue — sans cet
écran, une déclaration soumise depuis `/benevolat` (#778/#809) reste en
attente indéfiniment, sans aucun moyen de l'instruire.

**Independent Test**: se connecter avec un compte titulaire du pouvoir de
validation, ouvrir `/admin/benevolat`, voir au moins une déclaration en
attente créée au préalable, cliquer « Accepter » sur l'une d'elles — elle
disparaît de la liste (son statut n'est plus « en attente »).

**Acceptance Scenarios**:

1. **Given** un administrateur titulaire du pouvoir de validation,
   **When** il ouvre `/admin/benevolat` et qu'au moins une déclaration est
   en attente, **Then** il voit, pour chacune, l'athlète concerné, le titre
   et la description de l'activité, et la date de la déclaration.
2. **Given** cet administrateur, **When** il clique « Accepter » sur une
   déclaration, **Then** elle disparaît de la liste des déclarations en
   attente.
3. **Given** cet administrateur, **When** il clique « Refuser » sur une
   déclaration, **Then** elle disparaît de la liste des déclarations en
   attente.
4. **Given** aucune déclaration en attente, **When** l'administrateur ouvre
   `/admin/benevolat`, **Then** un état vide explicite s'affiche — pas une
   page blanche.
5. **Given** un visiteur sans le pouvoir de validation (même connecté),
   **When** il tente d'accéder au contenu de cet écran, **Then** il ne voit
   ni la liste ni les boutons — le back-office refuse déjà côté API
   (comportement existant, #779, inchangé).

---

### Edge Cases

- Une déclaration acceptée ou refusée par un autre administrateur pendant
  que cette page est ouverte n'est reflétée qu'au prochain chargement de la
  liste — pas de mise à jour temps réel attendue (hors périmètre).
- L'athlète d'une déclaration a pu changer de nom depuis la déclaration : le
  nom affiché est celui **courant** de la fiche athlète, pas un instantané
  au moment de la déclaration — cohérent avec le reste du dépôt (`Athlete.
  nom`/`.prenom` ne sont pas historisés ailleurs non plus).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT afficher, à un titulaire du pouvoir de
  validation, la liste des déclarations de crédit d'athlète en attente sur
  `/admin/benevolat`.
- **FR-002**: Chaque déclaration affichée DOIT identifier l'athlète
  concerné par son nom, en plus du titre, de la description et de la date.
- **FR-003**: Le système DOIT permettre d'accepter ou de refuser chaque
  déclaration en attente, individuellement.
- **FR-004**: Une déclaration acceptée ou refusée NE DOIT PLUS apparaître
  dans la liste des déclarations en attente.
- **FR-005**: Le système DOIT afficher un état vide explicite quand aucune
  déclaration n'est en attente.
- **FR-006**: Le système NE DOIT PAS introduire de nouveau mécanisme de
  contrôle d'accès — le pouvoir de validation existant (#779) reste la
  seule garde.

### Key Entities *(include if feature involves data)*

- **VolunteerAction** (existant) : gagne un moyen de lecture de l'identité
  de l'athlète concerné, jusqu'ici absent de sa représentation admin —
  aucune nouvelle donnée stockée, l'identité vient de la relation déjà
  existante vers `Athlete`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des déclarations en attente affichées identifient
  l'athlète concerné sans que l'administrateur ait à consulter une autre
  page.
- **SC-002**: Un administrateur peut accepter ou refuser une déclaration en
  au plus deux gestes (ouvrir la page, cliquer un bouton).
- **SC-003**: `/admin/benevolat` ne rend jamais une page vide ou une erreur
  pour un titulaire du pouvoir de validation, qu'il y ait ou non des
  déclarations en attente.

## Assumptions

- Retirer une déclaration de la liste après un geste (accepter/refuser)
  suffit comme confirmation visuelle — pas de message de succès
  supplémentaire requis au-delà du patron déjà établi ailleurs dans le
  back-office (toast).
- Aucune pagination n'est nécessaire au lancement — le volume de
  déclarations en attente est faible (geste occasionnel, pas un flux à
  fort volume), cohérent avec l'absence de pagination sur l'API existante
  (`GET /admin/volunteer-actions/pending`).
- La suppression d'une déclaration (geste distinct, destructif) est hors
  périmètre — sous-issue #818.
