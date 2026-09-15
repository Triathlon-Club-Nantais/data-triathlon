# Feature Specification: Appel de présence jeunes

**Feature Branch**: `869-appel-jeunes`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Appel bouclant sur les jeunes inscrits à une séance d'entraînement (calendrier #868, modèle Entrainement/EntrainementParticipant déjà posé), pour marquer chacun présent/absent, mobile-first, utilisé par les encadrants. Deux appels par séance : un appel de début, dont l'état présent/absent est persistant, et un appel de fin qui reboucle sur la présence du début pour vérifier qu'aucun jeune n'est manquant, sans persistance propre. L'appel de début peut peupler le calendrier (créer la séance et y inscrire les participants). Accès facile au profil d'un jeune depuis l'appel. Note de séance (texte libre, rattachée à l'entraînement) et note sur un jeune en particulier (réutilisant le journal de bord de #867). Garde par `jeunes:read`/`jeunes:write`. Unifier les deux entrées de navigation « Jeunes » existantes en une seule section avec sous-liens profils/calendrier/appel."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Réaliser l'appel de début d'une séance (Priority: P1)

Un encadrant jeunes (porteur du pouvoir `jeunes:write`) ouvre l'écran d'appel
pour la séance du jour — créée à cette occasion si elle n'existe pas encore au
calendrier — et pointe chaque jeune inscrit comme présent ou absent. Un jeune
qui se présente sans être encore inscrit à la séance peut être ajouté et
pointé présent en un seul geste.

**Why this priority**: C'est la valeur fondatrice de l'issue #869 — sans
appel de début persistant, aucune autre capacité (appel de fin, notes, accès
profil) n'a de donnée sur laquelle s'appuyer. Seule, cette user story livre
déjà l'usage de terrain principal : savoir qui est là.

**Independent Test**: peut être testé seul en ouvrant l'appel d'une séance
sans aucun pointage, en marquant plusieurs jeunes présents et absents, puis en
vérifiant que ce statut est conservé après rechargement de l'écran.

**Acceptance Scenarios**:

1. **Given** une séance existante avec trois jeunes inscrits, aucun pointage
   encore fait, **When** un encadrant ouvre l'appel et marque deux jeunes
   présents et un absent, **Then** le statut de chacun est enregistré
   immédiatement et reste affiché après rechargement de l'écran.
2. **Given** aucune séance créée pour la date du jour, **When** un encadrant
   ouvre l'écran d'appel depuis la navigation, **Then** une séance datée
   d'aujourd'hui est créée (ou proposée à la création en un geste) et son
   appel de début s'ouvre, vide.
3. **Given** une séance dont l'appel est en cours, **When** l'encadrant
   ajoute un jeune non encore inscrit et le marque présent, **Then** ce jeune
   apparaît inscrit à la séance et pointé présent, sans double saisie.
4. **Given** un jeune déjà marqué absent, **When** l'encadrant corrige son
   statut en présent, **Then** seul le dernier statut enregistré fait foi
   (aucun historique des changements n'est conservé).
5. **Given** un visiteur porteur de `jeunes:read` seul, **When** il ouvre
   l'écran d'appel, **Then** il voit les statuts déjà enregistrés mais ne peut
   ni les modifier, ni ajouter un jeune, ni ajouter une note.
6. **Given** un visiteur sans le pouvoir `jeunes:read`, **When** il tente
   d'atteindre l'écran d'appel ou l'API sous-jacente, **Then** l'accès est
   refusé (401 sans session, 403 avec une session qui ne porte pas le
   pouvoir).

---

### User Story 2 - Vérifier la présence en fin de séance (Priority: P2)

Un encadrant reboucle, en fin de séance, sur la liste des jeunes marqués
présents à l'appel de début, pour confirmer visuellement qu'aucun n'est
reparti sans supervision — sans que cette vérification modifie l'historique
de présence enregistré le matin.

**Why this priority**: Complète la valeur de l'appel de début par le contrôle
qui motive l'epic (sécurité des mineurs en fin de séance), mais reste sans
objet tant qu'aucun appel de début n'a eu lieu — d'où sa priorité après US1.

**Independent Test**: peut être testé seul en ouvrant l'appel de fin d'une
séance déjà pointée le matin, en cochant les jeunes retrouvés, et en vérifiant
qu'aucune écriture ne modifie le statut de présence de l'appel de début.

**Acceptance Scenarios**:

1. **Given** une séance dont l'appel de début a marqué quatre jeunes présents
   et un absent, **When** l'encadrant ouvre l'appel de fin, **Then** seuls les
   quatre jeunes marqués présents apparaissent à vérifier — le jeune absent le
   matin n'y figure pas.
2. **Given** l'appel de fin ouvert, **When** l'encadrant coche trois des
   quatre jeunes comme retrouvés, **Then** l'écran signale visuellement qu'un
   jeune reste à confirmer, sans écrire aucune donnée tant que ce geste n'a
   pas été fait pour tous.
3. **Given** l'appel de fin entièrement recoché, **When** l'encadrant recharge
   l'écran ou le referme puis le rouvre, **Then** l'appel de fin repart vierge
   — son résultat n'a jamais été conservé, contrairement à l'appel de début.
4. **Given** une séance dont l'appel de début n'a encore pointé aucun jeune,
   **When** l'encadrant ouvre l'appel de fin, **Then** l'écran indique qu'il
   n'y a rien à vérifier plutôt que d'afficher une liste vide muette.

---

### User Story 3 - Enrichir l'appel de contexte sur un jeune (Priority: P3)

Pendant l'appel, un encadrant ajoute une note texte libre sur la séance
entière (observations, incidents) ou sur un jeune en particulier (versée à
son journal de bord), et ouvre le profil complet d'un jeune en un geste
lorsqu'il a besoin d'une information (contact d'urgence, historique) que
l'écran d'appel ne montre pas.

**Why this priority**: Valeur additive et explicitement demandée par
l'issue, mais qui ne conditionne ni l'appel de début ni celui de fin —
un encadrant peut faire l'appel sans jamais écrire de note.

**Independent Test**: peut être testé seul en ajoutant une note de séance,
une note sur un jeune, puis en ouvrant son profil depuis l'appel, et en
vérifiant que la note du jeune apparaît dans son journal de bord existant.

**Acceptance Scenarios**:

1. **Given** l'écran d'appel d'une séance, **When** l'encadrant saisit une
   note de séance et l'enregistre, **Then** cette note reste associée à la
   séance et visible à la réouverture de l'écran.
2. **Given** un jeune inscrit à l'appel, **When** l'encadrant lui ajoute une
   note texte, **Then** cette note apparaît dans le journal de bord du profil
   de ce jeune, datée du jour.
3. **Given** un jeune inscrit à l'appel, **When** l'encadrant ouvre son
   profil depuis l'écran d'appel, **Then** il atteint la fiche complète du
   jeune (contact d'urgence, âge, journal de bord) en un seul geste.

---

### Edge Cases

- Une séance existante n'a aucun jeune inscrit : l'écran d'appel affiche un
  état vide explicite et invite à ajouter un jeune, plutôt qu'une liste vide
  muette.
- Deux encadrants ouvrent l'appel de la même séance en même temps : le
  dernier statut de présence enregistré pour un jeune donné fait foi (pas de
  fusion ni de conflit bloquant), cohérent avec le reste du dépôt.
- Un jeune retiré d'une séance après avoir été pointé perd son statut de
  présence avec son inscription — rien à conserver, l'inscription elle-même
  disparaît.
- Aucun profil de jeune n'existe encore dans le club : l'écran d'appel ne
  peut proposer personne à ajouter ; créer un profil reste hors périmètre
  (#867).
- Une note de séance ou de jeune vide (texte blanc) n'est pas enregistrée.
- L'appel de fin d'une séance déjà entièrement recochée puis rouverte dans un
  second onglet repart vierge dans les deux — aucun état partagé entre eux.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre de marquer chaque jeune inscrit à une
  séance comme présent ou absent lors de l'appel de début.
- **FR-002**: Le statut présent/absent de chaque jeune DOIT être conservé
  après l'appel de début et rester consultable à toute réouverture ultérieure
  de l'écran ou de l'API.
- **FR-003**: Le système DOIT permettre d'ouvrir l'appel de début pour la
  séance du jour même si aucune séance n'existe encore à cette date au
  calendrier, en la créant à cette occasion.
- **FR-004**: Le système DOIT permettre d'ajouter, depuis l'écran d'appel, un
  jeune non encore inscrit à la séance, en l'inscrivant au même geste que son
  premier pointage.
- **FR-005**: Le système DOIT permettre de corriger le statut présent/absent
  d'un jeune à tout moment après l'appel de début ; seul le dernier statut
  enregistré fait foi, sans historique des changements.
- **FR-006**: Le système DOIT proposer un appel de fin qui présente à nouveau
  la liste des seuls jeunes marqués présents à l'appel de début, pour
  vérification visuelle.
- **FR-007**: Le résultat de l'appel de fin NE DOIT PAS modifier le statut de
  présence enregistré à l'appel de début, ni être conservé au-delà de la
  session d'utilisation de l'écran.
- **FR-008**: Le système DOIT permettre d'ajouter et de modifier une note
  texte libre rattachée à la séance entière, consultable tant que la séance
  existe.
- **FR-009**: Le système DOIT permettre, pendant l'appel, d'ajouter une note
  texte libre datée à un jeune en particulier, versée à son journal de bord
  existant (#867) — sans introduire de second mécanisme de notes.
- **FR-010**: Le système DOIT permettre d'atteindre le profil complet d'un
  jeune en un seul geste depuis l'écran d'appel.
- **FR-011**: L'écran d'appel DOIT rester pleinement utilisable depuis un
  écran de téléphone (mobile-first), sans défilement horizontal.
- **FR-012**: Toute lecture de l'état d'appel (statuts de présence, notes)
  DOIT exiger le pouvoir `jeunes:read` ; toute écriture (marquer
  présent/absent, ajouter un jeune, ajouter une note) DOIT exiger
  `jeunes:write`.
- **FR-013**: La navigation DOIT présenter les profils, le calendrier et
  l'appel comme trois destinations d'une seule section « Jeunes », plutôt que
  deux sections distinctes comme c'est le cas aujourd'hui.

### Key Entities *(include if feature involves data)*

- **Séance d'entraînement** (entité existante, #868) — porte désormais une
  note de séance en texte libre, en plus de sa date, heure, lieu et type déjà
  posés.
- **Inscription d'un jeune à une séance** (entité existante, #868) — porte
  désormais le statut de l'appel de début pour ce jeune sur cette séance :
  présent, absent, ou pas encore pointé.
- **Entrée de journal de bord** (entité existante, #867, réutilisée) — une
  note ajoutée à un jeune pendant l'appel en est une occurrence, datée du
  jour, comme toute autre entrée.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un encadrant peut réaliser l'appel de début complet d'une
  séance de dix jeunes déjà inscrits en moins de 2 minutes depuis un
  téléphone.
- **SC-002**: Le statut de présence saisi par un encadrant à l'appel de
  début reste identique après fermeture et réouverture de l'écran, dans 100 %
  des cas.
- **SC-003**: Aucune écriture de l'appel (présence, ajout de jeune, note) ne
  peut réussir pour une session qui ne porte pas `jeunes:write` — vérifié pour
  chacune des trois écritures.
- **SC-004**: Un encadrant atteint la destination « Appel » en un seul niveau
  de navigation depuis n'importe quel écran du site, au même endroit que
  « Calendrier » et « Profils ».
- **SC-005**: Un encadrant retrouve, depuis l'appel de fin, uniquement les
  jeunes marqués présents à l'appel de début — jamais un jeune marqué absent
  ni un jeune non pointé.

## Assumptions

- Le club dispose déjà d'au moins un profil de jeune créé pour qu'un appel
  ait un sens ; créer un profil reste hors périmètre de cette feature (#867
  le couvre déjà).
- Un seul appel de début par séance : les corrections successives de statut
  écrasent la précédente, sans conserver d'historique des changements — non
  demandé par l'issue.
- « Aujourd'hui », pour la création automatique de la séance du jour, se
  calcule côté client (date locale du navigateur de l'encadrant) : c'est sa
  journée sur le terrain qui compte, pas la date UTC du serveur.
- L'appel de fin est un contrôle réalisé dans une seule session d'écran ; il
  n'est pas conçu pour être repris après fermeture — un rafraîchissement le
  réinitialise, ce qui est le comportement voulu (FR-007).
- Le modèle de données du profil et du journal de bord (#867) et celui du
  calendrier (#868) sont posés et mergés sur `epic/863-jeunes` ; cette feature
  construit dessus sans les modifier au-delà de l'ajout de la note de séance
  et du statut de présence.
