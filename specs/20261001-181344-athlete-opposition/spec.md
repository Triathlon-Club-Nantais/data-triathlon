# Feature Specification: Droit d'opposition effectif d'un athlète

**Feature Branch**: `feat/334-athlete-opposition`

**Created**: 2026-10-01

**Status**: Draft

**Input**: Issue #334 (epic #313). Rendre effectif le droit d'opposition qu'annonce la politique de confidentialité. La base légale (intérêt légitime) et ses obligations sont tranchées par `docs/superpowers/specs/2026-10-01-base-legale-decision.md` (#332), qui prime.

## Clarifications

### Session 2026-10-01

- Q: Que deviennent les résultats d'une personne qui s'oppose ? → A: anonymisés (ligne « Anonyme » gardant dossard, temps, rangs et statut), jamais supprimés.
- Q: Comment traiter un homonyme ? → A: l'empreinte porte sur nom et prénom normalisés ; les homonymes sont couverts, et l'administrateur est averti du nombre de résultats concernés avant de confirmer.
- Q: Faut-il un écran listant les oppositions ? → A: oui, un écran d'administration dédié, qui liste chaque opposition (date de la demande, date d'application, délai, auteur, nombre de résultats anonymisés) et porte l'enregistrement d'une opposition par nom.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un administrateur applique une opposition, et elle tient (Priority: P1)

Une personne, adhérente ou non, a demandé le retrait de ses résultats. Un administrateur ouvre sa fiche athlète et applique l'opposition en indiquant la date de la demande. Ses résultats cessent immédiatement d'être nominatifs, sa fiche disparaît, et aucun import ultérieur ne la fait revenir.

**Why this priority**: c'est l'obligation que l'intérêt légitime impose. Aujourd'hui, une suppression à la main est défaite au prochain re-scrape de l'épreuve : le droit annoncé n'est pas tenu.

**Independent Test**: appliquer une opposition sur un athlète présent dans une épreuve, relancer l'import de cette épreuve, et constater que son nom n'apparaît nulle part et que les rangs des autres n'ont pas bougé.

**Acceptance Scenarios**:

1. **Given** un athlète classé 12ᵉ d'une épreuve, **When** un administrateur applique son opposition, **Then** la 12ᵉ ligne du classement s'affiche « Anonyme », avec son dossard, son temps et son rang, et le 13ᵉ reste 13ᵉ.
2. **Given** une opposition appliquée, **When** l'épreuve est réimportée (import web, re-scrape, batch, bascule de source), **Then** la ligne revient anonyme, jamais nominative, et aucune fiche athlète n'est recréée à son nom.
3. **Given** une opposition appliquée, **When** on cherche la personne par son nom, **Then** aucun résultat ni aucune fiche ne la désigne.
4. **Given** une opposition appliquée, **When** on consulte le journal d'administration, **Then** on y lit qui l'a appliquée, la date de la demande et la date d'application, sans le nom de la personne.

---

### User Story 2 - Une personne demande le retrait depuis le site (Priority: P2)

Une personne veut faire retirer ses résultats. Depuis le bouton de signalement présent sur chaque page, elle choisit « Retrait de mes données », indique son nom et l'épreuve, et envoie. La demande arrive dans la file des retours utilisateurs, reconnaissable, avec sa date.

**Why this priority**: un canal identifiable rend le droit exerçable sans chercher une adresse, et date la demande, ce qui fait courir le délai d'un mois.

**Independent Test**: envoyer une demande de retrait depuis le formulaire et la retrouver, typée et datée, dans l'écran des retours utilisateurs.

**Acceptance Scenarios**:

1. **Given** le formulaire de signalement, **When** la personne choisit « Retrait de mes données », **Then** le formulaire lui dit quoi indiquer (nom, prénom, épreuve) et qu'une réponse lui est due sous un mois.
2. **Given** une demande envoyée, **When** un administrateur ouvre les retours utilisateurs, **Then** elle porte un type distinct des bugs et des suggestions, et sa date de dépôt.

---

### User Story 3 - Le club prouve qu'il a tenu le délai (Priority: P3)

En cas de réclamation, un responsable retrouve, pour chaque opposition, la date de la demande et celle de l'application.

**Why this priority**: preuve de conformité ; utile sans être bloquant pour l'exercice du droit.

**Independent Test**: ouvrir l'écran des oppositions et lire, pour chacune, l'écart entre demande et application.

**Acceptance Scenarios**:

1. **Given** plusieurs oppositions appliquées, **When** un administrateur ouvre l'écran des oppositions, **Then** chacune y figure avec la date de la demande, la date d'application, le délai en jours, l'auteur et le nombre de résultats anonymisés, sans aucun nom.
2. **Given** une opposition appliquée plus d'un mois après la demande, **When** l'écran l'affiche, **Then** le dépassement du délai légal est signalé.
3. **Given** l'écran des oppositions, **When** un administrateur saisit un nom, un prénom et une date de demande, **Then** l'opposition est enregistrée (et appliquée aux résultats existants s'il y en a), après confirmation.

### Edge Cases

- **Homonyme** : deux personnes portent le même nom et le même prénom. L'opposition de l'une rend anonymes aussi les résultats de l'autre ; l'administrateur en est averti avant de confirmer, avec le nombre de résultats concernés.
- **Variante d'écriture** : la source publie « Jean-Pierre DUPONT » une fois, « Jean Pierre Dupont » une autre. L'empreinte se calcule sur une forme normalisée (casse, accents, espaces, ponctuation), pour que les deux soient couvertes.
- **Relais** : la personne figure comme équipière d'un relais. Son nom disparaît de la composition ; le résultat de l'équipe reste.
- **Saisie manuelle** : quelqu'un saisit à la main un résultat au nom d'une personne opposée. La saisie est refusée, avec un message qui dit pourquoi : un résultat manuel anonyme n'aurait ni source ni dossard pour le relier à un classement.
- **Fiche référencée ailleurs** (compte du back-office lié, déclaration de bénévolat, validation de saison) : ces liens sont rompus, et la fiche nominative disparaît quand même.
- **Opposition sans résultat en base** : la personne n'apparaît encore dans aucune épreuve. L'opposition peut être enregistrée par nom pour bloquer les imports futurs.
- **Erreur d'application** : un administrateur se trompe de fiche. Le geste est destructif et sans retour : il est confirmé, avec le nom et le nombre de résultats, avant d'agir.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Un administrateur porteur d'un pouvoir dédié MUST pouvoir appliquer une opposition depuis la fiche d'un athlète, en indiquant la date de la demande (par défaut, le jour même).
- **FR-002**: Un administrateur porteur de ce pouvoir MUST pouvoir enregistrer une opposition par nom et prénom depuis l'écran des oppositions (FR-013), qu'une fiche existe ou non.
- **FR-003**: À l'application, chaque résultat de la personne MUST devenir anonyme : affiché « Anonyme », avec dossard, temps, rangs et statut conservés, sans nom, prénom, club, catégorie ni ligne brute de la source qui la désignent.
- **FR-004**: Les rangs, effectifs et classements des autres participants MUST rester identiques avant et après l'application.
- **FR-005**: La fiche nominative de la personne MUST être supprimée, et les liens qui la référencent ailleurs rompus.
- **FR-006**: L'opposition MUST être conservée sous la seule forme d'une empreinte de l'identité normalisée (nom et prénom), un pseudonyme qui ne stocke jamais le nom en clair.
- **FR-007**: Tout résultat importé dont l'identité normalisée correspond à une opposition MUST être enregistré anonyme (import web, re-scrape, batch par liste de liens, bascule de source) ; un équipier de relais opposé MUST être retiré de la composition ; une saisie manuelle ou une composition d'équipe à son nom MUST être refusée avec un message explicite. La fusion d'épreuves ne réimporte rien et conserve les lignes déjà anonymes.
- **FR-008**: Chaque application MUST être consignée au journal d'administration avec son auteur, la date de la demande et la date d'application, sans le nom de la personne.
- **FR-009**: Avant de confirmer, l'administrateur MUST voir le nombre de résultats concernés, homonymes compris, et confirmer un geste présenté comme définitif.
- **FR-010**: Le formulaire de signalement MUST proposer un type « Retrait de mes données », avec les informations à fournir et le délai de réponse, et l'écran des retours utilisateurs MUST le distinguer.
- **FR-011**: La politique de confidentialité MUST annoncer ce canal et l'anonymisation, et sa date de mise à jour changer.
- **FR-012**: Aucune opposition ne s'annule depuis l'application.
- **FR-013**: Un écran d'administration, sous le même pouvoir, MUST lister les oppositions (date de la demande, date d'application, délai en jours, auteur, nombre de résultats anonymisés), signaler celles appliquées au-delà d'un mois, et porter l'enregistrement par nom de FR-002. Il n'affiche aucun nom.

### Key Entities

- **Opposition** : l'empreinte de l'identité normalisée, la date de la demande, la date d'application, l'administrateur qui l'a appliquée, le nombre de résultats anonymisés à l'application. Ne porte aucun nom.
- **Résultat anonyme** : un résultat d'épreuve sans identité nominative, qui garde dossard, temps, rangs et statut.
- **Demande de retrait** : un retour utilisateur d'un type dédié, daté à son dépôt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Après application, une recherche par le nom de la personne rend zéro résultat et zéro fiche.
- **SC-002**: Après application puis réimport complet de chaque épreuve concernée, zéro résultat nominatif de la personne en base.
- **SC-003**: Le rang affiché de chaque autre participant d'une épreuve concernée est identique avant et après.
- **SC-004**: Pour 100 % des oppositions, la date de la demande et celle de l'application se lisent au journal.
- **SC-005**: Une demande de retrait se dépose depuis n'importe quelle page en moins de deux minutes.

## Assumptions

- L'identité utilisée par les imports est le couple nom et prénom ; la date de naissance n'est jamais publiée par les sources, elle n'entre pas dans l'empreinte.
- L'anonymisation est préférée au retrait de la ligne : elle tient FR-004 sans recalcul, et le classement officiel de l'organisateur reste cohérent avec celui du site.
- Les homonymes sont couverts par l'opposition ; le risque est assumé (perte d'affichage pour un tiers, sans perte de donnée de classement) et signalé avant confirmation.
- Le pouvoir est attribué aux administrateurs ; un superutilisateur le porte d'office.
- Les données déjà transmises à la mesure d'audience ne relèvent pas de cette fonctionnalité (décision #332, #1159).
