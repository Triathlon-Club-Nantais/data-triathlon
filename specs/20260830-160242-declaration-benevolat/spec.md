# Feature Specification: Déclaration de bénévolat

**Feature Branch**: `20260830-160242-declaration-benevolat`

**Created**: 2026-08-30

**Status**: Draft

**Input**: Issue GitHub #751 — « feat(benevolat): ajouter une déclaration de
bénévolat (titre + description), suppressible ». Il n'existe aujourd'hui
aucun moyen de déclarer une activité de bénévolat pour un membre du club. Le
groupe d'appartenance « commission bénévolat » ne fait que dire une
appartenance, pas une activité, et n'accorde aujourd'hui aucun droit d'accès
(le système de groupes exclut délibérément le contrôle d'accès en v1). La
page `/benevoles` existante (#271, #490, #609) est un dispositif de
vérification des résultats de course, sans rapport. Point d'arbitrage
explicite de l'issue : contrairement au journal d'audit `AdminActionLog`
(#501, immuable — « jamais modifiable : ni mise à jour, ni suppression »),
une déclaration de bénévolat **doit** être suppressible (erreur de saisie,
doublon, retrait par son auteur).

Permissions et workflow de validation tranchés avec l'utilisateur au moment
du spec (voir Assumptions) :

- Une auto-déclaration (un membre déclare sa propre activité) part à l'état
  **« en attente de validation »**.
- Une déclaration créée par un **admin**, pour lui-même ou pour n'importe
  quel autre membre, est **validée d'office** — pas de file d'attente.
- La suppression est ouverte à l'auteur de la déclaration et à un admin.
- La consultation : chaque membre voit ses propres déclarations ; un admin
  voit celles de tous les membres.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Déclarer sa propre activité de bénévolat (Priority: P1)

Un membre du club veut garder une trace qu'il a effectué une activité de
bénévolat (ex. tenue d'un poste de ravitaillement, aide à la vérification des
résultats d'une épreuve), en saisissant un titre et une description. Cette
auto-déclaration part à l'état « en attente de validation ».

**Why this priority**: C'est la raison d'être de la feature — sans cette
capacité, rien d'autre n'a de sens. C'est aussi un MVP livrable seul (même
sans validation admin implémentée, la trace existe déjà).

**Independent Test**: Un membre connecté saisit un titre et une description,
valide, et retrouve sa déclaration — marquée « en attente » — dans sa liste
personnelle.

**Acceptance Scenarios**:

1. **Given** un membre connecté sur la page de déclaration, **When** il
   saisit un titre et une description non vides et valide, **Then** la
   déclaration est enregistrée à l'état « en attente de validation » et
   apparaît immédiatement dans sa liste de déclarations.
2. **Given** un membre connecté, **When** il tente de valider avec un titre
   ou une description vide, **Then** la déclaration est refusée avec un
   message d'erreur explicite, sans être enregistrée.
3. **Given** un membre standard (non-admin) connecté, **When** il tente de
   déclarer une activité au nom d'un autre membre, **Then** l'action est
   refusée — seule sa propre déclaration est possible pour un non-admin.

---

### User Story 2 - Un admin déclare pour n'importe quel membre, validée d'office (Priority: P2)

Un admin veut enregistrer une activité de bénévolat pour lui-même ou pour un
autre membre (ex. bénévolat constaté de visu, ou saisi a posteriori pour le
compte d'un tiers), sans passer par la file d'attente de validation.

**Why this priority**: Complète le workflow de validation — sans cette
capacité, aucune déclaration ne peut jamais atteindre l'état « validée »
autrement que par l'étape de validation de l'US3.

**Independent Test**: Un admin crée une déclaration en choisissant le membre
concerné (lui-même ou un tiers) ; elle apparaît immédiatement à l'état
« validée », sans étape supplémentaire.

**Acceptance Scenarios**:

1. **Given** un admin connecté, **When** il crée une déclaration pour
   lui-même, **Then** elle est enregistrée directement à l'état « validée ».
2. **Given** un admin connecté, **When** il crée une déclaration pour un
   autre membre du club, **Then** elle est enregistrée directement à l'état
   « validée » et apparaît dans la liste personnelle de ce membre.

---

### User Story 3 - Un admin valide ou rejette une déclaration en attente (Priority: P2)

Un admin passe en revue les auto-déclarations en attente et les valide, ou
les rejette (en les supprimant — pas d'état « rejetée » distinct dans cette
itération, voir Assumptions).

**Why this priority**: Sans cette capacité, une auto-déclaration (US1) reste
bloquée indéfiniment à l'état « en attente » — le workflow de validation
choisi resterait incomplet.

**Independent Test**: Un admin ouvre la liste des déclarations en attente,
valide l'une d'elles (elle passe à « validée ») et en supprime une autre
(elle disparaît).

**Acceptance Scenarios**:

1. **Given** une déclaration à l'état « en attente de validation », **When**
   un admin la valide, **Then** son état passe à « validée » et elle le
   reste (visible comme telle pour son auteur).
2. **Given** une déclaration à l'état « en attente de validation » jugée non
   fondée par un admin, **When** il la supprime, **Then** elle disparaît
   définitivement de toutes les listes.

---

### User Story 4 - Supprimer une déclaration (Priority: P3)

Un membre veut retirer une déclaration qu'il a lui-même créée par erreur
(faute de saisie, doublon), qu'elle soit en attente ou déjà validée ; un
admin peut faire de même sur la déclaration de n'importe quel membre.

**Why this priority**: Complète le point d'arbitrage central de l'issue,
mais recouvre en partie l'US3 pour le cas « en attente » — l'aspect
réellement nouveau ici est la suppression d'une déclaration **déjà
validée**, moins fréquent.

**Independent Test**: L'auteur d'une déclaration validée la supprime et
vérifie qu'elle disparaît définitivement de sa liste.

**Acceptance Scenarios**:

1. **Given** une déclaration (« en attente » ou « validée ») appartenant au
   membre connecté, **When** il la supprime, **Then** elle disparaît
   immédiatement et définitivement (pas de corbeille, pas de trace d'audit
   conservée).
2. **Given** une déclaration appartenant à un autre membre, **When** un
   membre standard (non-admin, non-auteur) tente de la supprimer, **Then**
   la suppression est refusée.

---

### User Story 5 - Consulter les déclarations (Priority: P3)

Un membre consulte la liste de ses propres déclarations (avec leur statut) ;
un admin dispose en plus d'une vue d'ensemble sur les déclarations de tous
les membres.

**Why this priority**: Utile pour vérifier ce qui a été déclaré et suivre la
validation, mais non bloquant pour le MVP (US1 seule livre déjà de la
valeur : la trace existe et est visible à son auteur).

**Independent Test**: Un membre standard consulte sa liste et ne voit que
ses propres déclarations ; un admin consulte une vue d'ensemble et voit
celles de tous les membres, avec auteur et statut.

**Acceptance Scenarios**:

1. **Given** un membre ayant créé plusieurs déclarations, **When** il ouvre
   sa liste de déclarations, **Then** il voit toutes ses déclarations
   (quel que soit leur statut), triées de la plus récente à la plus
   ancienne, avec leur statut affiché.
2. **Given** un admin, **When** il ouvre la vue d'ensemble, **Then** il voit
   les déclarations de tous les membres, avec le membre concerné et le
   statut de chacune.

---

### Edge Cases

- Que se passe-t-il quand un membre n'a encore aucune déclaration ? → état
  vide invitant à en créer une.
- Que se passe-t-il si le titre ou la description dépasse une longueur
  raisonnable ? → refus avec message d'erreur, pas de troncature silencieuse.
- Que se passe-t-il si un membre tente de supprimer une déclaration déjà
  supprimée (double-clic, onglet dupliqué) ? → l'opération échoue proprement
  (déjà absente), sans erreur serveur.
- Que se passe-t-il si un admin tente de valider une déclaration déjà
  validée ? → opération sans effet (idempotente), pas d'erreur.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un membre connecté de créer une
  déclaration de bénévolat pour lui-même, comportant un titre et une
  description ; cette déclaration est créée à l'état « en attente de
  validation ».
- **FR-002**: Le système DOIT refuser la création d'une déclaration dont le
  titre ou la description est vide.
- **FR-003**: Le système DOIT refuser à un membre standard (non-admin) de
  créer une déclaration au nom d'un autre membre.
- **FR-004**: Le système DOIT permettre à un admin de créer une déclaration
  au nom de n'importe quel membre (lui-même inclus), directement à l'état
  « validée », sans passer par l'étape de validation.
- **FR-005**: Le système DOIT permettre à un admin de faire passer une
  déclaration de l'état « en attente de validation » à l'état « validée ».
- **FR-006**: Le système DOIT permettre à l'auteur d'une déclaration, ou à un
  admin, de supprimer une déclaration, quel que soit son statut.
- **FR-007**: Le système DOIT refuser la suppression d'une déclaration par un
  membre standard qui n'en est pas l'auteur.
- **FR-008**: La suppression d'une déclaration DOIT être définitive et ne
  laisser subsister aucune trace consultable — à la différence du journal
  d'audit `AdminActionLog`, cette entrée n'a pas vocation probatoire.
- **FR-009**: Le système DOIT permettre à un membre de consulter la liste de
  ses propres déclarations, avec leur statut respectif.
- **FR-010**: Le système DOIT permettre à un admin de consulter la liste des
  déclarations de tous les membres, avec le membre concerné et le statut de
  chacune.
- **FR-011**: Le système NE DOIT PAS proposer de modification (édition) du
  titre ou de la description d'une déclaration existante dans cette
  itération — seules la création, la validation, la consultation et la
  suppression sont couvertes.

### Key Entities *(include if feature involves data)*

- **Déclaration de bénévolat** : trace qu'une activité de bénévolat a eu
  lieu. Attributs : titre, description, membre concerné (celui dont
  l'activité est tracée), membre déclarant (celui qui a créé l'entrée — peut
  différer du membre concerné quand un admin déclare pour un tiers), statut
  (« en attente de validation » / « validée »), date de création.
  Suppressible par son auteur ou un admin ; pas de mise à jour (édition)
  prévue dans cette itération.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un membre peut créer une déclaration de bénévolat (titre +
  description) en moins d'une minute depuis la page dédiée.
- **SC-002**: Une déclaration supprimée n'apparaît plus dans aucune liste
  consultable, immédiatement après la suppression.
- **SC-003**: 100 % des déclarations créées ont un titre et une description
  non vides — aucune déclaration incomplète n'est jamais persistée.
- **SC-004**: 100 % des auto-déclarations (créées par un membre standard
  pour lui-même) sont créées à l'état « en attente » ; 100 % des
  déclarations créées par un admin sont créées à l'état « validée ».

## Assumptions

- Seuls les champs titre et description sont couverts par cette itération —
  l'issue mentionne explicitement que le détail (date, épreuve, mission)
  reste à spécifier plus tard si le besoin se confirme ; pas de lien vers une
  épreuve ou une mission précise pour l'instant.
- Pas de fonctionnalité d'édition (mise à jour) dans cette itération — seules
  création, validation, consultation et suppression sont dans le périmètre.
- Rejeter une déclaration en attente se fait par suppression (pas d'état
  « rejetée » distinct, ni de motif de refus tracé) — plus simple, cohérent
  avec le principe de suppression déjà retenu pour la feature ; à revoir si
  le besoin de tracer un motif de refus se confirme à l'usage.
- Le rôle habilité à créer pour un tiers, valider, consulter la vue
  d'ensemble et supprimer la déclaration d'un tiers est le rôle **admin**
  existant du produit — pas un nouveau rôle « commission bénévolat », le
  système de groupes actuel n'accordant aujourd'hui aucun droit d'accès (v1).
- `AdminActionLog` et la page `/benevoles` existante ne sont pas modifiés
  par cette feature (hors périmètre explicite de l'issue).
- Pas de notification (email, etc.) à la création, à la validation ou à la
  suppression d'une déclaration.
- **Indépendance vis-à-vis de `VolunteerAction` (#709/#741)** : un modèle
  `VolunteerAction` existe déjà (mergé le jour même) pour un usage distinct —
  preuve minimale, non suppressible, déclarée par un admin pour le quota de
  validation de saison (3 courses + 1 bénévolat). Décidé avec l'utilisateur :
  cette feature reste **indépendante**, nouvelle table dédiée, sans lien
  fonctionnel avec le quota de saison ni risque sur #709/#741 déjà livrées.
