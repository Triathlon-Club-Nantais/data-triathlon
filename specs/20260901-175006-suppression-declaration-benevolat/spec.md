# Feature Specification: Suppression d'une déclaration de crédit de bénévolat

**Feature Branch**: `818-suppression-declaration-benevolat`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Permettre à un admin de supprimer une déclaration de crédit d'athlète (VolunteerAction), qu'elle soit en attente ou déjà validée. Issue #818 (epic #815)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Supprimer une déclaration depuis la file d'attente (Priority: P1)

Un admin consulte l'écran de validation (`/admin/benevolat`, file d'attente des
déclarations en attente, livré par #817) et constate qu'une déclaration ne
doit jamais être traitée (erreur de saisie, doublon, athlète non concerné).
Il la supprime directement, sans avoir à d'abord la valider ou la refuser.

**Why this priority**: C'est la surface où la majorité des déclarations
litigieuses est repérée en premier — c'est le principal cas d'usage nommé par
l'issue.

**Independent Test**: Depuis la file d'attente, déclencher la suppression
d'une déclaration en attente et vérifier qu'elle disparaît de la liste et
n'est plus récupérable par l'API.

**Acceptance Scenarios**:

1. **Given** une déclaration en attente affichée dans la file d'attente,
   **When** l'admin déclenche sa suppression et confirme le geste destructif,
   **Then** la déclaration disparaît de la file d'attente et n'apparaît plus
   dans aucune liste (compteur de saison de l'athlète inchangé, puisqu'une
   déclaration en attente n'est pas encore comptée).
2. **Given** le dialogue de confirmation de suppression est ouvert,
   **When** l'admin l'annule,
   **Then** la déclaration reste inchangée dans la file d'attente.

---

### User Story 2 - Supprimer une déclaration validée depuis la fiche athlète (Priority: P2)

Un admin consulte la fiche d'un athlète et sa liste de déclarations de
bénévolat validées (livrée par #781). Il constate qu'une déclaration validée
est erronée (mauvaise course, doublon, geste non éligible) et la supprime.

**Why this priority**: Cas moins fréquent qu'une correction en amont (P1),
mais nécessaire : une fois validée, une déclaration erronée n'a aujourd'hui
aucun chemin de retrait et fausse durablement le quota de saison de
l'athlète.

**Independent Test**: Depuis la fiche d'un athlète, déclencher la suppression
d'une déclaration validée et vérifier qu'elle disparaît de sa liste et que
son quota de saison se recalcule sans elle.

**Acceptance Scenarios**:

1. **Given** une déclaration validée affichée sur la fiche d'un athlète,
   **When** l'admin déclenche sa suppression et confirme le geste destructif,
   **Then** la déclaration disparaît de la liste et le quota de saison de
   l'athlète se recalcule sans elle.
2. **Given** le dialogue de confirmation de suppression est ouvert,
   **When** l'admin l'annule,
   **Then** la déclaration reste inchangée sur la fiche athlète.

---

### Edge Cases

- Suppression d'une déclaration déjà supprimée entre-temps par un autre admin
  (double clic, deux onglets) : la seconde tentative échoue proprement sans
  casser l'écran (déclaration absente signalée, liste rafraîchie).
- Suppression d'une déclaration refusée (statut `rejected`, si ce statut
  existe déjà dans le flux de validation) : le geste doit rester disponible,
  au même titre qu'en attente ou validée — un refus n'efface pas la trace,
  seule la suppression le fait.
- Un admin sans le pouvoir requis tente l'appel API directement (hors UI) :
  la suppression est refusée et journalisée comme les autres gestes gardés
  d'`admin_actions.py`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un admin habilité de supprimer
  définitivement une déclaration de crédit de bénévolat (`VolunteerAction`),
  quel que soit son statut (en attente, validée, refusée).
- **FR-002**: Le geste de suppression DOIT être exposé depuis la file
  d'attente de l'écran de validation admin (#817) pour les déclarations en
  attente.
- **FR-003**: Le geste de suppression DOIT être exposé depuis la liste des
  déclarations de bénévolat sur la fiche d'un athlète (#781) pour les
  déclarations déjà traitées (validées ou refusées).
- **FR-004**: Le système DOIT demander une confirmation explicite avant toute
  suppression (geste destructif, irréversible).
- **FR-005**: Une déclaration supprimée ne DOIT plus apparaître dans aucune
  liste ni compter dans le quota de saison de l'athlète.
- **FR-006**: Le système DOIT journaliser chaque suppression (qui, quand,
  quelle déclaration), sur le même patron que les autres gestes admin
  destructifs déjà en place.
- **FR-007**: Le système DOIT refuser la suppression à un utilisateur qui n'a
  pas le pouvoir requis, avec le même message d'erreur que pour un geste de
  validation refusé.
- **FR-008**: Une tentative de suppression d'une déclaration déjà supprimée
  ou inexistante DOIT échouer proprement (erreur explicite, pas d'exception
  non gérée) sans affecter les autres déclarations.

### Key Entities

- **VolunteerAction** : la déclaration de crédit de bénévolat d'un athlète
  pour le quota de saison. Porte un statut (en attente / validée / refusée)
  et est aujourd'hui dépourvue de tout chemin de suppression.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Un admin peut supprimer une déclaration erronée, depuis la
  file d'attente comme depuis la fiche athlète, en moins de trois clics
  (déclencher, confirmer).
- **SC-002** : Une déclaration supprimée n'apparaît plus dans aucune liste ni
  dans aucun quota de saison, sans rechargement manuel de la page.
- **SC-003** : 100 % des suppressions laissent une trace journalisée
  exploitable (qui, quand, quelle déclaration).
- **SC-004** : Une tentative de suppression sans le pouvoir requis échoue
  systématiquement, sans exposer plus d'information qu'un refus de
  validation classique.

## Assumptions

- Le pouvoir requis pour supprimer une déclaration est le même que celui
  requis pour la valider (`athletes:volunteer_validate`) — pas de nouveau
  pouvoir dédié pour ce geste destructif, conformément à la proposition de
  l'issue #818. À revisiter si un audit de sécurité futur l'exige.
- Les deux surfaces d'exposition proposées par l'issue (file d'attente et
  fiche athlète) sont toutes deux dans le périmètre — ce sont les deux seuls
  endroits où une déclaration est aujourd'hui visible côté admin, et rien
  n'indique qu'il faille en exclure une.
- Le geste suit le patron `DangerConfirm`/`useDangerConfirm` déjà en place
  côté frontend pour les autres suppressions (couleur destructive,
  confirmation explicite), conformément à `frontend/AGENTS.md` §
  Gestes destructifs.
- La suppression est définitive (pas de corbeille ni de restauration) — en
  cohérence avec les autres gestes destructifs déjà en place dans le projet
  (ex. suppression d'une source inactive, #742).
