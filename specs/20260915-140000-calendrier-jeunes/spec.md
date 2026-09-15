# Feature Specification: Calendrier des entraînements jeunes

**Feature Branch**: `868-calendrier-jeunes`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Calendrier des entraînements jeunes (#868, sous-issue de l'epic #863) : modèle de données pour un entraînement jeunes (date, éventuellement heure/lieu/type) et sa liste de participants inscrits, route(s) backend et écran frontend calendrier mobile-first, protégés par le pouvoir jeunes:read (consultation) et jeunes:write (création/modification). Le calendrier doit pouvoir être peuplé par le futur flux d'appel de présence (#869) : une séance créée/consultée via l'appel doit apparaître dans le calendrier — donc le modèle et les routes CRUD/consultation d'un entraînement et de sa liste de participants doivent être posés maintenant, sans implémenter le flux d'appel présent/absent lui-même (hors périmètre, #869 dédiée). Les participants d'un entraînement référencent des jeunes (profils gérés par la sous-issue parallèle #867, pas encore mergée) : ne pas bloquer sur ce détail, documenter la dépendance."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consulter le calendrier des entraînements (Priority: P1)

Un encadrant jeunes (porteur du pouvoir `jeunes:read`) ouvre l'écran calendrier
et voit la liste des séances d'entraînement à venir et passées, chacune avec sa
date, son lieu et son type, ainsi que le nombre de jeunes inscrits.

**Why this priority**: C'est la valeur minimale de l'epic #863 — sans écran de
consultation, aucune autre capacité (créer une séance, y inscrire des jeunes,
y faire l'appel en #869) n'a de support visible.

**Independent Test** : peut être testé seul en créant quelques entraînements
via l'API puis en vérifiant qu'ils s'affichent, triés par date, sur l'écran
mobile-first du calendrier.

**Acceptance Scenarios**:

1. **Given** trois entraînements en base à des dates différentes, **When** un
   encadrant ouvre le calendrier, **Then** les trois séances s'affichent
   triées par date, chacune avec sa date, son heure, son lieu et son type
   quand ils sont renseignés.
2. **Given** un entraînement sans lieu ni type renseignés, **When** il
   s'affiche dans le calendrier, **Then** l'écran ne montre aucun texte vide
   ni « undefined » à la place des champs absents.
3. **Given** un visiteur sans le pouvoir `jeunes:read`, **When** il tente
   d'atteindre l'écran calendrier ou l'API sous-jacente, **Then** l'accès est
   refusé (401 sans session, 403 avec une session qui ne porte pas le
   pouvoir).

---

### User Story 2 - Créer et modifier une séance d'entraînement (Priority: P2)

Un encadrant porteur du pouvoir `jeunes:write` crée une nouvelle séance
(date obligatoire, heure/lieu/type optionnels) ou corrige une séance
existante depuis le calendrier.

**Why this priority**: Le calendrier n'a d'utilité que si les encadrants
peuvent le tenir à jour eux-mêmes — c'est la capacité d'écriture minimale sur
laquelle #869 (l'appel de présence) s'appuiera pour créer une séance à la
volée.

**Independent Test**: peut être testé seul en créant une séance par l'écran,
en vérifiant qu'elle apparaît dans la liste (US1), puis en la modifiant et en
vérifiant que la correction est reflétée.

**Acceptance Scenarios**:

1. **Given** un encadrant sur l'écran calendrier, **When** il crée une séance
   avec une date valide, **Then** la séance apparaît dans le calendrier avec
   zéro participant inscrit.
2. **Given** une séance existante, **When** l'encadrant corrige sa date, son
   heure, son lieu ou son type, **Then** le calendrier reflète la correction
   sans dupliquer la séance.
3. **Given** un porteur du seul pouvoir `jeunes:read` (sans `jeunes:write`),
   **When** il consulte le calendrier, **Then** aucune commande de création ou
   de modification ne lui est proposée, et l'API refuse la requête si elle
   est tentée directement (403).

---

### User Story 3 - Consulter et gérer la liste des participants inscrits (Priority: P2)

Un encadrant porteur du pouvoir `jeunes:write` inscrit ou désinscrit un jeune à
une séance ; tout porteur de `jeunes:read` consulte la liste des participants
inscrits à une séance donnée.

**Why this priority**: C'est la donnée que #869 (l'appel de présence) doit
pouvoir lire et peupler — sans liste de participants, l'appel de présence n'a
rien sur quoi cocher présent/absent.

**Independent Test**: peut être testé seul en inscrivant un jeune (identifié
par son identifiant) à une séance, en vérifiant qu'il apparaît dans la liste
de cette séance et dans aucune autre, puis en le désinscrivant.

**Acceptance Scenarios**:

1. **Given** une séance sans participant, **When** un encadrant y inscrit un
   jeune, **Then** ce jeune apparaît dans la liste des participants de cette
   séance, et le compteur d'inscrits de la séance augmente d'un.
2. **Given** un jeune déjà inscrit à une séance, **When** un encadrant tente
   de l'inscrire une seconde fois à la même séance, **Then** l'opération est
   sans effet (idempotente), sans doublon dans la liste.
3. **Given** un jeune inscrit à une séance, **When** un encadrant le
   désinscrit, **Then** il n'apparaît plus dans la liste des participants de
   cette séance, sans affecter son inscription à une autre séance.

### Edge Cases

- Une séance sans participant s'affiche avec un compteur à zéro, jamais une
  absence de compteur.
- Une tentative d'inscription d'un jeune inexistant est refusée (404) plutôt
  que silencieusement acceptée : la liste de participants ne doit jamais
  référencer un jeune qui n'existe pas.
- Deux séances à la même date restent deux entrées distinctes du calendrier,
  triées ensuite par heure quand elle est renseignée, par ordre de création
  sinon.
- Un identifiant de séance inconnu dans une requête d'inscription rend 404,
  jamais un succès silencieux. **Limite assumée de ce lot** : l'existence du
  jeune référencé n'est pas vérifiable tant que la table de profils de #867
  n'existe pas encore en base — voir `research.md` §Dépendance sur le profil
  jeune. Une fois #867 mergée et la contrainte resserrée par une migration de
  suivi, un `jeune_id` inexistant sera lui aussi refusé, sans changement de
  cette route.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre de créer un entraînement jeunes avec au
  minimum une date, et optionnellement une heure de début, un lieu et un type
  de séance.
- **FR-002**: Le système DOIT permettre de consulter la liste des
  entraînements jeunes, triée par date (puis par heure quand elle est
  renseignée), à quiconque porte le pouvoir `jeunes:read`.
- **FR-003**: Le système DOIT permettre de consulter le détail d'un
  entraînement jeunes précis, y compris sa liste de participants inscrits, à
  quiconque porte le pouvoir `jeunes:read`.
- **FR-004**: Le système DOIT permettre de modifier la date, l'heure, le lieu
  et le type d'un entraînement existant, réservé aux porteurs de
  `jeunes:write`.
- **FR-005**: Le système DOIT réserver la création et la modification d'un
  entraînement aux porteurs du pouvoir `jeunes:write`, et refuser (403) toute
  tentative par un porteur du seul `jeunes:read`.
- **FR-006**: Le système DOIT permettre d'inscrire un jeune (par son
  identifiant) à un entraînement, réservé aux porteurs de `jeunes:write`.
- **FR-007**: L'inscription d'un jeune déjà inscrit à un entraînement DOIT
  être idempotente — aucun doublon, aucune erreur.
- **FR-008**: Le système DOIT permettre de désinscrire un jeune d'un
  entraînement, réservé aux porteurs de `jeunes:write`, et rester sans effet
  si le jeune n'était pas inscrit.
- **FR-009**: Toute route de consultation ou d'écriture DOIT être fermée à
  quiconque ne porte pas le pouvoir requis (401 sans session, 403 avec une
  session insuffisante), avant même toute logique métier.
- **FR-010**: Le modèle de données DOIT permettre à un futur flux d'appel de
  présence (#869, hors périmètre ici) de créer un entraînement et de consulter
  sa liste de participants inscrits sans modification du modèle posé ici.
- **FR-011**: L'écran calendrier frontend DOIT être utilisable sur un écran de
  largeur mobile (mobile-first), au même titre que les autres écrans du
  back-office jeunes.

### Key Entities *(include if feature involves data)*

- **Entraînement (séance jeunes)**: une séance d'entraînement jeunes —
  date (obligatoire), heure de début, lieu et type de séance (tous trois
  optionnels, texte libre). Porte une liste de participants inscrits.
- **Participant inscrit**: l'inscription d'un jeune à un entraînement précis —
  référence l'entraînement et le jeune inscrit. Un jeune ne peut être inscrit
  qu'une fois à un même entraînement. Le profil du jeune référencé (identité,
  contact d'urgence…) est porté par la sous-issue parallèle #867, dont la
  table peut ne pas encore exister au moment de l'implémentation — voir
  `research.md` pour la dépendance et le traitement retenu.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un encadrant peut créer une séance et la retrouver dans le
  calendrier en moins de 30 secondes, sans quitter l'écran calendrier.
- **SC-002**: 100 % des tentatives d'accès au calendrier ou à ses actions
  d'écriture par un visiteur sans le pouvoir requis sont refusées.
- **SC-003**: Le calendrier reste lisible et utilisable sans défilement
  horizontal sur un écran de 375 px de large (mobile-first).
- **SC-004**: Une double inscription du même jeune à la même séance ne produit
  jamais de doublon visible dans la liste des participants.

## Assumptions

- Le pouvoir `jeunes:read` autorise la seule consultation (calendrier, détail
  de séance, liste de participants) ; `jeunes:write` autorise en plus la
  création et la modification d'une séance ainsi que l'inscription et la
  désinscription d'un participant — cohérent avec la description des deux
  pouvoirs déjà posée dans `core/permissions.py` (#866).
- Le flux d'appel de présence proprement dit (marquer un participant
  présent/absent) est hors périmètre de cette issue (#869 dédiée) : cette
  feature ne pose que le modèle et les routes de consultation/gestion d'un
  entraînement et de sa liste de participants inscrits.
- Un « type de séance » et un « lieu » restent du texte libre à ce stade —
  aucune nomenclature fermée n'a été demandée par l'issue, et en fermer une
  maintenant serait une anticipation non demandée.
- Le profil détaillé d'un jeune (nom, âge, contact d'urgence…) n'est pas du
  ressort de cette feature — seule la relation d'inscription à un
  entraînement l'est. Si la table de profils de #867 n'est pas encore mergée
  au moment de l'implémentation, la référence au jeune reste posée sans
  contrainte d'intégrité référentielle en base, resserrée par une migration
  de suivi une fois #867 mergée (détail dans `research.md`).
- L'écran frontend est un nouvel écran du périmètre `jeunes`, gardé par
  `jeunes:read`/`jeunes:write` côté client (garde d'apparence, non de
  sécurité — la sécurité reste au serveur), sur le même patron que les écrans
  de back-office existants.
