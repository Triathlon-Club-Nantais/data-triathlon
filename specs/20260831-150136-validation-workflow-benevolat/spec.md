# Feature Specification: Workflow de validation admin des actions de bénévolat

**Feature Branch**: `779-validation-workflow-benevolat`

**Created**: 2026-08-31

**Status**: Draft

**Input**: Issue GitHub #779 (sous-issue de l'epic #776) — « feat(backend):
volunteer action admin validation workflow ». Depuis #778, `VolunteerAction`
porte un statut (`status`, défaut « en attente »), mais rien ne le consulte
ni ne le fait évoluer : le chemin admin existant continue de créer des
lignes sans jamais les instruire, et le calcul du quota de saison
(`has_volunteer_action`) reste indifférent au statut — une déclaration
compte dès qu'elle existe, quel que soit son état. Cette sous-issue donne
enfin un sens au statut : un admin habilité consulte les déclarations en
attente et les accepte ou les refuse ; seule une déclaration acceptée
compte pour le quota.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un admin consulte les déclarations en attente (Priority: P1)

Un admin habilité veut voir la liste des déclarations de bénévolat en
attente d'instruction (athlète crédité, titre, description, auteur, date),
pour décider lesquelles accepter.

**Why this priority**: Sans visibilité sur la file d'attente, aucune
instruction n'est possible — c'est le préalable de toute décision.

**Independent Test**: Un admin habilité ouvre la liste ; elle contient
toutes les déclarations à l'état « en attente », tous athlètes confondus.

**Acceptance Scenarios**:

1. **Given** plusieurs déclarations existent à des statuts variés, **When**
   un admin habilité consulte la liste des déclarations en attente,
   **Then** seules celles à l'état « en attente » apparaissent.
2. **Given** un membre standard sans le pouvoir dédié, **When** il tente de
   consulter la liste, **Then** l'accès est refusé.

---

### User Story 2 - Un admin accepte une déclaration en attente (Priority: P1)

Un admin habilité accepte une déclaration en attente, ce qui la fait
compter immédiatement pour le quota de saison de l'athlète crédité.

**Why this priority**: C'est la raison d'être de la feature — sans accepter,
aucune déclaration self-service ne peut jamais devenir utile au quota.

**Independent Test**: Un admin accepte une déclaration « en attente » ; son
statut passe à « validée » et `has_volunteer_action` devient vrai pour
l'athlète et la saison concernés (si ce n'était pas déjà le cas par une
autre ligne).

**Acceptance Scenarios**:

1. **Given** une déclaration à l'état « en attente », **When** un admin
   habilité l'accepte, **Then** son statut passe à « validée » et elle
   compte désormais pour le quota de saison de l'athlète crédité.
2. **Given** une déclaration déjà « validée », **When** un admin l'accepte
   à nouveau, **Then** l'opération est sans effet (idempotente), pas
   d'erreur.
3. **Given** un membre standard sans le pouvoir dédié, **When** il tente
   d'accepter une déclaration, **Then** l'accès est refusé.

---

### User Story 3 - Un admin refuse une déclaration en attente (Priority: P2)

Un admin habilité refuse une déclaration en attente jugée non fondée
(doublon, erreur manifeste), qui ne doit jamais compter pour le quota.

**Why this priority**: Complète le workflow — sans refus, une déclaration
non fondée reste indéfiniment « en attente », polluant la file.

**Independent Test**: Un admin refuse une déclaration « en attente » ; son
statut passe à « refusée » et elle ne compte jamais pour le quota.

**Acceptance Scenarios**:

1. **Given** une déclaration à l'état « en attente », **When** un admin
   habilité la refuse, **Then** son statut passe à « refusée » et elle ne
   compte jamais pour le quota de saison.
2. **Given** une déclaration déjà « refusée », **When** un admin la refuse
   à nouveau, **Then** l'opération est sans effet (idempotente).
3. **Given** une déclaration déjà « validée », **When** un admin tente de
   la refuser, **Then** le refus est accepté et fait redescendre le statut
   à « refusée » — un admin peut revenir sur une décision (voir
   Assumptions).

---

### Edge Cases

- Une déclaration créée par le chemin admin existant (#709, sans titre ni
  description) apparaît-elle dans la file d'attente ? → Oui, à l'identique
  d'une déclaration self-service : le statut ne distingue pas l'origine.
- Que se passe-t-il pour le quota si un athlète a plusieurs déclarations,
  certaines validées et d'autres non, sur la même saison ? → Le quota reste
  satisfait dès qu'**une seule** compte comme validée (cohérent avec le
  journal existant, research.md D4 de #709/#778) — jamais un décompte.
- Un admin peut-il accepter/refuser une déclaration créditant un athlète
  qu'il ne suit pas ? → Oui, aucune restriction par club ou par athlète : le
  pouvoir est global, comme `athletes:volunteer_manage`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un admin habilité de consulter
  la liste des déclarations `VolunteerAction` à l'état « en attente »
  (athlète, titre, description, auteur, date de création).
- **FR-002**: Le système DOIT refuser l'accès à cette liste à quiconque
  n'est pas habilité.
- **FR-003**: Le système DOIT permettre à un admin habilité de faire passer
  une déclaration de l'état « en attente » à « validée ».
- **FR-004**: Cette transition DOIT être idempotente : accepter une
  déclaration déjà « validée » ne produit aucune erreur ni effet
  supplémentaire.
- **FR-005**: Le système DOIT permettre à un admin habilité de faire passer
  une déclaration de l'état « en attente » (ou « validée », voir US3
  Scenario 3) à « refusée ».
- **FR-006**: Cette transition DOIT être idempotente : refuser une
  déclaration déjà « refusée » ne produit aucune erreur ni effet
  supplémentaire.
- **FR-007**: Le système DOIT refuser à quiconque n'est pas habilité
  d'accepter ou de refuser une déclaration.
- **FR-008**: Le calcul du quota de saison (`has_volunteer_action`) DOIT ne
  compter que les déclarations à l'état « validée » — ni « en attente », ni
  « refusée ».
- **FR-009**: Le pouvoir d'instruction (consulter/accepter/refuser) DOIT
  être distinct de `athletes:volunteer_manage` (création directe, #709) et
  de `benevolat:read`/`benevolat:manage` (#751, domaine indépendant —
  `VolunteerDeclaration`, sans rapport avec le quota de saison).

### Key Entities *(include if feature involves data)*

- **VolunteerAction** (existant, #778) : `status` passe désormais par trois
  valeurs significatives — « en attente » (défaut), « validée », « refusée »
  — au lieu d'un champ posé sans être jamais lu.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des déclarations « validées » comptent pour le quota de
  saison de l'athlète crédité ; 100 % des « en attente » ou « refusées » ne
  comptent jamais.
- **SC-002**: 100 % des tentatives de consultation, d'acceptation ou de
  refus par un compte non habilité sont refusées.
- **SC-003**: Un admin habilité peut instruire (accepter ou refuser) une
  déclaration en attente en un seul geste, sans étape intermédiaire.

## Assumptions

- **Vocabulaire des statuts** : `"en_attente"` / `"validee"` / `"refusee"`,
  cohérent avec le couple déjà posé par #751 (`VolunteerDeclaration.status`)
  et #778 (`VolunteerAction.status`) — pas les mots anglais bruts du
  brouillon de l'issue (« pending/validated/rejected »), qui rouvriraient
  une divergence de vocabulaire dans le même domaine.
- **Une seule permission nouvelle**, pas un couple lecture/décision séparé
  comme #751 (`benevolat:read`/`benevolat:manage`) : l'issue demande « une
  nouvelle permission dédiée » (singulier), et le volume attendu (quota
  d'un club) ne justifie pas de séparer qui peut voir la file de qui peut
  décider.
- **Refuser une déclaration déjà validée est autorisé** (US3 Scenario 3) :
  un admin peut revenir sur une acceptation antérieure (erreur constatée a
  posteriori) — pas de verrou une fois « validée ». Symétriquement, valider
  une déclaration « refusée » n'est pas couvert par cette itération (hors
  périmètre : aucun scénario ni FR ne l'exige) — seul le sens
  attente→validée et attente/validée→refusée est requis.
- **Pas de motif de refus tracé**, ni de notification à l'auteur — cohérent
  avec l'absence de ces éléments sur `VolunteerDeclaration` (#751).
- **Le chemin de création admin existant (#709) n'est pas modifié** : il
  continue de créer des lignes à l'état « en attente » par défaut ; les
  instruire suit désormais le même chemin que les lignes self-service.
- **La fiche athlète (affichage de la liste des actions validées) est hors
  périmètre** — sous-issue #781.
