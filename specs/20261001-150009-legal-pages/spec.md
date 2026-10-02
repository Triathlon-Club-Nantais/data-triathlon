# Feature Specification: Textes légaux du site (mentions légales, confidentialité, CGU)

**Feature Branch**: `feat/332-333-legal-basis-and-pages`

**Created**: 2026-10-01

**Status**: Draft

**Input**: Issue #333 (epic #313). Publier les mentions légales, la politique de
confidentialité et les conditions générales d'utilisation, accessibles depuis
toutes les pages, y compris sans le code d'accès. La politique publie la
décision `docs/superpowers/specs/2026-10-01-base-legale-decision.md` (#332), qui
prime sur cette spec pour tout fait juridique ou mesuré.

## Clarifications

### Session 2026-10-01

- Q: Quelle adresse donner pour l'exercice des droits ? → A: `president@triathlon-club-nantais.com`.
- Q: Combien de temps conserver les résultats nominatifs ? → A: tant que le service existe (archive sportive du club), sauf opposition.
- Q: Quelles durées pour les signalements, le journal d'administration, les profils jeunes ? → A: 12 mois, 12 mois, durée de l'adhésion plus une saison ; les purges sont suivies dans une issue dédiée.
- Q: Conseil extérieur avant publication ? → A: sollicité (référent fédéral) sans bloquer la publication.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un athlète non adhérent sait ce que le club fait de ses résultats (Priority: P1)

Une personne a couru une épreuve où des membres du TCN étaient inscrits. Elle
apprend que son nom figure dans l'outil du club. Elle n'a pas le code d'accès.
Elle doit pouvoir lire, sans rien saisir, qui traite ses données, lesquelles,
pourquoi, combien de temps, et comment s'opposer à leur publication.

**Why this priority**: c'est l'obligation d'information que la base légale
retenue (intérêt légitime) rend non négociable, et le motif exact de la sanction
CNIL de 2014 contre la Fédération Française d'Athlétisme. Sans elle, le
traitement n'a pas de base tenable.

**Independent Test**: depuis un navigateur sans aucun cookie, ouvrir l'adresse
de la page d'accès du site : un lien « Confidentialité » est visible, il ouvre
la politique complète sans demander le code.

**Acceptance Scenarios**:

1. **Given** un visiteur sans code d'accès, **When** il arrive sur le site,
   **Then** le pied de page affiche les liens vers les trois textes, et chacun
   s'ouvre sans demander le code.
2. **Given** la politique de confidentialité ouverte, **When** le visiteur la
   lit, **Then** il y trouve, nommés : le responsable de traitement, les
   données collectées et leur provenance, la finalité, la base légale
   (intérêt légitime) et sa justification, les durées de conservation, les
   destinataires et sous-traitants, ses droits, l'adresse à laquelle les
   exercer, et le droit de réclamation auprès de la CNIL.
3. **Given** un athlète qui veut que ses résultats soient retirés, **When** il
   lit la section sur ses droits, **Then** il sait à quelle adresse écrire,
   quoi indiquer pour être identifié (nom, prénom, épreuve) et dans quel délai
   une réponse lui est due.

---

### User Story 2 - Un adhérent sait qui édite le service et ce qu'il s'engage à faire (Priority: P2)

Un adhérent qui utilise le site, saisit un résultat à la main ou envoie un
signalement, peut consulter les mentions légales (qui édite, qui héberge, qui
contacter) et les CGU (ce qui est attendu de lui, ce que le club ne garantit
pas).

**Why this priority**: obligation légale pour tout site édité (mentions
légales) et cadre de la saisie manuelle et des signalements, mais sans enjeu de
base légale.

**Independent Test**: depuis n'importe quelle page du site, cliquer
« Mentions légales » puis « Conditions d'utilisation » dans le pied de page et
vérifier les rubriques attendues.

**Acceptance Scenarios**:

1. **Given** les mentions légales ouvertes, **When** l'adhérent les lit,
   **Then** il y trouve l'éditeur (Triathlon Club Nantais, adresse du siège,
   SIRET), le directeur de la publication, les hébergeurs avec leurs
   coordonnées, et un contact.
2. **Given** les CGU ouvertes, **When** l'adhérent les lit, **Then** il y
   trouve : l'objet du site et son accès réservé, ce qu'il s'engage à déclarer
   lors d'une saisie manuelle (un résultat réel, le sien ou celui d'un membre
   qui l'a chargé de le faire, avec une preuve quand elle existe), le cadre
   des signalements, et les limites de responsabilité sur des données issues
   de chronométreurs tiers.

---

### User Story 3 - Le club sait quand et quoi il a publié (Priority: P3)

Un responsable du club veut savoir quelle version d'un texte était en ligne à
une date donnée, et le lecteur veut savoir si le texte a changé récemment.

**Why this priority**: preuve de l'information délivrée en cas de
réclamation ; utile mais sans effet sur la conformité immédiate.

**Independent Test**: chaque page affiche une date « Dernière mise à jour » ;
l'historique du dépôt montre chaque modification du texte.

**Acceptance Scenarios**:

1. **Given** l'une des trois pages, **When** le lecteur l'ouvre, **Then** il
   voit sa date de dernière mise à jour en tête de texte.
2. **Given** une modification du texte, **When** elle est livrée, **Then** la
   date affichée change dans la même modification.

---

### Edge Cases

- Visiteur sans code d'accès qui ouvre directement l'adresse d'un des trois
  textes : la page s'affiche, sans passer par l'écran de saisie du code.
- Pages d'administration et espace bénévoles, qui ont leurs propres barrières :
  le pied de page et ses liens y sont aussi présents.
- Petit écran (320 px de large) : les trois liens restent visibles et
  cliquables dans le pied de page, sans défilement horizontal.
- Le droit d'opposition est annoncé alors que son traitement outillé (#334)
  n'est pas encore livré : la page décrit la démarche par écrit, qui est
  traitée à la main par le club, sans promettre de bouton.
- Une durée de conservation annoncée dont la purge automatique n'existe pas
  encore : le texte annonce la durée retenue par la décision ; l'écart est
  suivi dans une issue dédiée, pas masqué dans le texte.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le site MUST afficher sur **toutes** ses pages, y compris
  l'écran de saisie du code d'accès, l'administration et l'espace bénévoles, un
  pied de page permanent portant trois liens : « Mentions légales »,
  « Confidentialité », « Conditions d'utilisation ».
- **FR-002**: Les trois pages MUST être lisibles sans code d'accès ni
  connexion.
- **FR-003**: Les mentions légales MUST indiquer : l'éditeur (Triathlon Club
  Nantais, association, 2 boulevard René Coty, 44100 Nantes, SIRET
  403 516 347 00016), le directeur de la publication, les hébergeurs (front,
  API, base de production) avec leur raison sociale, leur adresse et leur
  téléphone (LCEN, article 6), et un contact.
- **FR-004**: La politique de confidentialité MUST nommer : le responsable de
  traitement ; chaque catégorie de données traitées (résultats des
  participants, saisies manuelles, comptes du back-office, signalements,
  mesure d'audience, cookies et stockage du navigateur) ; leur provenance (les
  14 chronométreurs nommés, atteints par un lien collé par un adhérent ou une liste de liens importée par un administrateur, et la saisie manuelle).
- **FR-005**: La politique MUST annoncer la finalité et la base légale telles
  que tranchées par la décision #332 (intérêt légitime pour les résultats), et
  exposer en quelques phrases pourquoi les intérêts des personnes ne
  prévalent pas (accès réservé, non-indexation, exclusion des jeunes,
  données déjà publiées).
- **FR-006**: La politique MUST donner, pour chaque catégorie, sa durée de
  conservation, reprise de la décision #332 : résultats tant que le service
  existe sauf opposition, signalements 12 mois, journal d'administration
  12 mois, profils jeunes durée de l'adhésion plus une saison, session de
  connexion 7 jours, cookie du code d'accès 90 jours.
- **FR-007**: La politique MUST lister les destinataires (adhérents via le code
  d'accès, bénévoles et administrateurs habilités) et les sous-traitants
  (hébergeurs, fournisseur d'identité, mesure d'audience, exécution des
  traitements planifiés) avec la localisation des données quand elle est
  connue, et signaler tout transfert hors Union européenne.
- **FR-008**: La politique MUST énoncer les droits (accès, rectification,
  effacement, limitation, opposition) et, pour chacun, comment l'exercer :
  adresse électronique (`president@triathlon-club-nantais.com`) et postale,
  informations à fournir, délai de réponse d'un mois.
- **FR-009**: La politique MUST mentionner le droit d'introduire une
  réclamation auprès de la CNIL, avec ses coordonnées.
- **FR-010**: La politique MUST lister chaque cookie et chaque élément stocké
  dans le navigateur par le site, avec sa finalité et sa durée.
- **FR-011**: Les CGU MUST couvrir : l'objet du site, son accès réservé aux
  adhérents par code, la saisie manuelle et l'engagement de celui qui déclare,
  la validation par un bénévole, les signalements, les limites de
  responsabilité sur les données de tiers, et la manière de demander une
  correction.
- **FR-012**: Chaque page MUST afficher sa date de dernière mise à jour, et
  son texte MUST vivre dans le dépôt, modifié par une contribution relue comme
  le reste du code.
- **FR-013**: Les textes MUST être en français courant, sans jargon juridique
  non expliqué ; tout article de loi cité est accompagné de sa signification.
- **FR-014**: Chaque page MUST porter un titre de document propre (onglet du
  navigateur) et une navigation par sommaire quand elle compte plus de quatre
  rubriques.

### Key Entities

- **Texte légal** : un des trois documents ; porte un titre, une date de
  dernière mise à jour et une suite de rubriques (titre, contenu).
- **Décision #332** : la source des faits juridiques (base légale, durées,
  sous-traitants) ; les textes la publient, ne la contredisent pas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Depuis 100 % des pages du site, les trois textes sont atteints en
  un clic.
- **SC-002**: Un visiteur sans code d'accès lit la politique de
  confidentialité en zéro saisie.
- **SC-003**: Chacune des six rubriques exigées par l'issue pour la politique
  (données et provenance, finalité et base légale, durées, destinataires et
  sous-traitants, droits et contact, réclamation CNIL) est présente.
- **SC-004**: Un adhérent non juriste trouve en moins de deux minutes à qui
  écrire pour faire retirer ses résultats.
- **SC-005**: Chaque modification d'un texte change sa date affichée dans la
  même contribution.

## Assumptions

- Le point de contact est `president@triathlon-club-nantais.com`, adresse du
  représentant légal publiée sur la page contact du site du club, relevée par
  lui.
- Le directeur de la publication est celui des mentions légales du site du
  club (Aurélien Gantier, commission communication).
- Les textes sont de simples pages de contenu, sans formulaire : l'exercice des
  droits passe par courrier électronique ou postal tant que #334 n'outille pas
  l'opposition.
- Les données de l'école de triathlon (profils jeunes) sont mentionnées dans la
  politique, avec leur base légale propre telle que la décision #332 la pose.
- Le bandeau de consentement à la mesure d'audience est hors périmètre ; la
  politique décrit la mesure d'audience telle qu'elle fonctionne aujourd'hui.
- Le site du club (`triathlon-club-nantais.com`) sert d'inspiration pour
  l'identité de l'éditeur ; ses propres textes ne sont pas repris tels quels,
  ils ne décrivent ni ce traitement ni ces hébergeurs.
