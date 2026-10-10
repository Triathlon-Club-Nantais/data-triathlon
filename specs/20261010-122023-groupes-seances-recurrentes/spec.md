# Feature Specification: Groupes d'entraînement, inscription d'office et séances récurrentes

**Feature Branch**: `feat/1291-training-groups`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "#1291 : groupes d'entraînement avec inscription d'office et séances récurrentes, catégorie FFTri calculée. Voir le corps de l'issue 1291. Modèle générique (jeunes puis adultes), mobile-first, pouvoirs jeunes:read / jeunes:write."

## Contexte

Les écrans jeunes livrés par l'epic #863 (profils, calendrier, appel) fonctionnent, mais chaque séance part **vide** : l'encadrant y ajoute les jeunes un par un depuis une liste de tous les profils, séance après séance (recette de la preview du 2026-10-10, #870). Cette feature retire cette saisie répétée : un jeune appartient à des groupes, une séance vise des groupes, et une règle de récurrence crée les séances de la saison d'un seul geste.

## Clarifications

### Session 2026-10-10

Tranchées en autonomie (mandat de l'utilisateur : « Spec Kit en autonomie »), sur recommandation.

- Q: Où l'encadrant gère-t-il les groupes ? → A: un quatrième écran « Groupes » dans la section « Jeunes » du rail, et la liste des groupes d'un profil sur sa fiche (avec ajout et retrait depuis la fiche).
- Q: L'appel du jour (« Créer la séance du jour ») propose-t-il de choisir des groupes ? → A: oui, la création rapide de la séance du jour propose les groupes, et une séance générée par une récurrence apparaît directement dans l'appel du jour.
- Q: Supprimer un groupe ou une récurrence demande-t-il une confirmation ? → A: oui, confirmation destructive (règle « Gestes destructifs » du front), avec le nombre de séances à venir concernées pour une récurrence.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Constituer des groupes (Priority: P1)

Un encadrant porteur de `jeunes:write` crée un groupe (« Benjamins mercredi »), le renomme, y ajoute et en retire des profils. Un profil peut appartenir à plusieurs groupes. Un porteur de `jeunes:read` consulte les groupes et leurs membres.

**Why this priority**: les groupes sont le support de tout le reste ; seuls, ils servent déjà de liste de référence de l'encadrant.

**Independent Test**: créer un groupe, y ajouter trois profils, en retirer un, vérifier la liste des membres et, sur chaque profil, la liste de ses groupes.

**Acceptance Scenarios**:

1. **Given** trois profils et aucun groupe, **When** l'encadrant crée « Benjamins mercredi » et y ajoute deux profils, **Then** le groupe affiche ces deux membres et chacun de ces profils affiche le groupe.
2. **Given** un profil déjà membre d'un groupe, **When** l'encadrant l'ajoute à nouveau, **Then** rien n'est dupliqué et l'écran le signale sans erreur.
3. **Given** un groupe, **When** l'encadrant le renomme avec le nom d'un autre groupe existant, **Then** le renommage est refusé avec un message clair.
4. **Given** un visiteur sans `jeunes:read`, **When** il tente d'atteindre les groupes (écran ou API), **Then** l'accès est refusé (401 sans session, 403 sans le pouvoir) ; avec `jeunes:read` seul, les formulaires d'édition ne sont pas proposés.

---

### User Story 2 - Inscription d'office des membres d'un groupe à une séance (Priority: P1)

À la création ou la modification d'une séance, l'encadrant choisit un ou plusieurs groupes : leurs membres sont inscrits à la séance. L'appel de début présente alors directement la liste, et l'encadrant n'a plus qu'à pointer.

**Why this priority**: c'est le gain de saisie principal, celui qui rend l'appel praticable avec 30 ou 40 jeunes.

**Independent Test**: créer une séance visant un groupe de trois membres et vérifier que l'appel de début liste ces trois jeunes sans aucun ajout manuel.

**Acceptance Scenarios**:

1. **Given** un groupe de trois membres, **When** l'encadrant crée une séance visant ce groupe, **Then** les trois sont inscrits à la séance.
2. **Given** deux groupes qui partagent un membre, **When** une séance vise les deux, **Then** ce membre n'est inscrit qu'une fois.
3. **Given** une séance déjà inscrite depuis un groupe, **When** l'encadrant ajoute ou retire un jeune à la main, **Then** l'ajout ou le retrait individuel reste possible, comme aujourd'hui.
4. **Given** une séance passée ou dont l'appel a commencé, **When** un membre est ajouté au groupe après coup, **Then** il n'est **pas** inscrit rétroactivement à cette séance ; seules les séances à venir dont l'appel n'a pas commencé suivent les changements de composition du groupe.
5. **Given** une séance à venir visant un groupe, **When** un membre est retiré du groupe, **Then** il est désinscrit de cette séance seulement s'il n'y a aucun statut de présence et qu'il n'y était pas inscrit à la main ou par un autre groupe visé.

---

### User Story 3 - Séances récurrentes (Priority: P2)

L'encadrant définit une récurrence : jour de la semaine, heure, lieu, type, groupes visés, date de début et date de fin. Les séances correspondantes sont créées d'un seul geste et apparaissent au calendrier. Chacune reste modifiable ou supprimable seule (créneau annulé, changement de lieu).

**Why this priority**: évite de recréer chaque mercredi la même séance, mais la valeur de US1 et US2 existe sans elle.

**Independent Test**: créer une récurrence « mercredi 14 h, du 1er octobre au 30 novembre » et vérifier que les séances de chaque mercredi de cette période existent, avec les membres des groupes visés inscrits.

**Acceptance Scenarios**:

1. **Given** une récurrence hebdomadaire sur deux mois, **When** l'encadrant la valide, **Then** une séance est créée pour chaque occurrence de la période, et l'écran annonce le nombre de séances créées avant et après validation.
2. **Given** une séance générée par une récurrence, **When** l'encadrant en change le lieu ou la supprime, **Then** seule cette séance change ; les autres séances de la récurrence ne bougent pas.
3. **Given** une récurrence existante, **When** l'encadrant modifie l'heure ou les groupes visés de la récurrence, **Then** la modification s'applique aux séances à venir dont l'appel n'a pas commencé, et jamais aux séances passées ni à celles déjà modifiées une par une.
4. **Given** une récurrence dont la période produirait un nombre de séances supérieur à la borne fixée (FR-012), **When** l'encadrant la valide, **Then** la création est refusée avec un message qui donne la borne.
5. **Given** une récurrence, **When** l'encadrant la supprime, **Then** les séances à venir sans appel commencé sont supprimées, les séances passées ou déjà pointées sont conservées.

---

### User Story 4 - Catégorie FFTri affichée et filtrable (Priority: P3)

La catégorie d'âge fédérale (Mini-poussin à Junior, puis Senior) est calculée depuis la date de naissance et affichée sur chaque profil, dans la liste des profils et dans l'appel. La liste des profils se filtre par catégorie, ce qui aide à constituer un groupe.

**Why this priority**: confort de lecture et d'organisation ; ne change aucun flux.

**Independent Test**: un profil né une année donnée affiche la catégorie attendue pour la saison en cours ; un profil sans date de naissance affiche « Catégorie inconnue ».

**Acceptance Scenarios**:

1. **Given** un profil dont la date de naissance le place en Benjamin pour la saison en cours, **When** l'encadrant ouvre la liste, **Then** le profil affiche « Benjamin ».
2. **Given** un profil sans date de naissance, **When** il s'affiche, **Then** la catégorie est « inconnue », sans erreur.
3. **Given** la liste des profils, **When** l'encadrant filtre sur « Pupille », **Then** seuls les profils de cette catégorie restent.

### Edge Cases

- Un groupe supprimé : ses membres restent inscrits aux séances existantes (l'inscription est une donnée de la séance) ; les récurrences qui le visaient le perdent de leur liste de groupes.
- Un profil dont l'adhésion est terminée (`fin d'adhésion` renseignée et passée) n'est plus inscrit d'office aux nouvelles séances, mais reste visible dans ses groupes, signalé comme tel.
- Une récurrence dont la date de fin précède la date de début, ou sans aucune occurrence dans la période : refusée avec un message clair.
- Deux encadrants modifient la même séance ou le même groupe en même temps : le dernier enregistrement l'emporte, sans perte des statuts de présence déjà saisis.
- Changement d'heure (heure d'été) : l'heure saisie d'une récurrence reste l'heure locale affichée pour chaque occurrence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un porteur de `jeunes:write` de créer, renommer et supprimer un groupe ; le nom d'un groupe est obligatoire et unique.
- **FR-002**: Le système DOIT permettre à un porteur de `jeunes:write` d'ajouter un profil à un groupe et de l'en retirer ; un profil peut appartenir à plusieurs groupes, sans doublon dans un même groupe.
- **FR-003**: Le système DOIT permettre à un porteur de `jeunes:read` de lister les groupes avec leur nombre de membres, de consulter les membres d'un groupe, et de voir les groupes d'un profil sur sa fiche.
- **FR-004**: Une séance DOIT pouvoir viser zéro, un ou plusieurs groupes ; à la création, les membres actifs des groupes visés DOIVENT être inscrits, chacun une seule fois.
- **FR-005**: Le système DOIT conserver l'origine de chaque inscription (manuelle ou par groupe) pour que le retrait d'un membre d'un groupe ne désinscrive pas un jeune inscrit à la main ou par un autre groupe.
- **FR-006**: Un changement de composition d'un groupe DOIT se répercuter sur les séances **à venir dont l'appel n'a pas commencé** qui visent ce groupe, et jamais sur les autres.
- **FR-007**: L'inscription et la désinscription individuelles existantes DOIVENT rester disponibles sur toute séance.
- **FR-008**: Le système DOIT permettre à un porteur de `jeunes:write` de créer une récurrence hebdomadaire (jour de semaine, heure optionnelle, lieu, type, groupes visés, date de début, date de fin) qui crée une séance par occurrence de la période.
- **FR-009**: Chaque séance générée DOIT rester modifiable et supprimable seule ; une séance modifiée seule n'est plus touchée par les modifications ultérieures de sa récurrence.
- **FR-010**: La modification ou la suppression d'une récurrence DOIT ne s'appliquer qu'aux séances à venir, non modifiées seules et sans appel commencé.
- **FR-011**: L'écran de création d'une récurrence DOIT annoncer le nombre de séances qui seront créées avant validation.
- **FR-012**: Une récurrence DOIT être bornée à une saison sportive (au plus 53 occurrences) ; au-delà, la création est refusée avec la borne dans le message.
- **FR-013**: Le système DOIT calculer la catégorie d'âge FFTri d'un profil depuis sa date de naissance pour la saison sportive en cours, l'afficher sur la fiche, dans la liste et dans l'appel, et permettre de filtrer la liste des profils par catégorie.
- **FR-014**: Toute route de consultation exige `jeunes:read`, toute route d'écriture `jeunes:write`, comme les routes jeunes existantes ; aucune n'est accessible sans session.
- **FR-015**: Les noms des données (groupes, appartenances, récurrences) DOIVENT rester génériques, sans référence au public jeune, pour servir plus tard aux adultes (FR-008 de la spec profil).
- **FR-016**: Les écrans groupes, récurrence et le choix des groupes d'une séance DOIVENT être pleinement utilisables sur un téléphone (usage principal de l'epic #863).
- **FR-017**: Un profil dont l'adhésion est terminée à la date de la séance NE DOIT PAS être inscrit d'office.
- **FR-018**: Les groupes DOIVENT se gérer depuis un écran « Groupes » de la section « Jeunes » et depuis la fiche d'un profil (ses groupes, ajout et retrait).
- **FR-019**: La création rapide de la séance du jour, depuis l'appel, DOIT proposer le choix des groupes visés.
- **FR-020**: La suppression d'un groupe ou d'une récurrence DOIT être confirmée comme un geste destructif ; pour une récurrence, la confirmation donne le nombre de séances à venir qui seront supprimées.

### Key Entities

- **Groupe**: ensemble nommé de profils, propre à l'organisation ; nom unique.
- **Appartenance**: lien profil ↔ groupe ; un profil a zéro ou plusieurs groupes.
- **Récurrence**: règle hebdomadaire (jour, heure, lieu, type, période, groupes visés) qui a engendré des séances.
- **Séance** (existante): gagne les groupes qu'elle vise, sa récurrence d'origine éventuelle, et l'indication qu'elle a été modifiée seule.
- **Inscription** (existante, participant d'une séance): gagne son origine (manuelle, ou le groupe qui l'a produite).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Préparer l'appel d'une séance d'un groupe de 30 jeunes demande au plus 3 gestes (choisir le groupe, valider), contre 30 ajouts un par un aujourd'hui.
- **SC-002**: Créer les séances hebdomadaires d'un trimestre pour un groupe prend moins d'une minute.
- **SC-003**: Aucun statut de présence déjà saisi n'est perdu ou modifié par une modification de groupe ou de récurrence (vérifié par les scénarios US2.4, US3.3, US3.5).
- **SC-004**: Les trois parcours (groupes, séance visant un groupe, récurrence) se réalisent en entier sur un écran de téléphone de 375 px de large sans défilement horizontal.

## Assumptions

- Seuls les encadrants (`jeunes:read`, `jeunes:write`) utilisent ces écrans ; pas de compte jeune ni parent (décision du 2026-10-10).
- Récurrence **hebdomadaire uniquement** (le rythme des entraînements du club) ; une séance ponctuelle reste créée comme aujourd'hui.
- Catégories FFTri : âge = année de la saison sportive moins année de naissance ; Mini-poussin 6-7 ans, Poussin 8-9, Pupille 10-11, Benjamin 12-13, Minime 14-15, Cadet 16-17, Junior 18-19, Senior au-delà, « Moins de 6 ans » en dessous. La date de bascule de la saison sportive FFTri est à vérifier à la phase de recherche du plan.
- « Appel commencé » = au moins un statut présent ou absent saisi sur la séance.
- Pas de suppression de profil dans cette feature (la fin d'adhésion existante en tient lieu).
- Pas de notification ni d'envoi de message lié aux séances (hors périmètre, #870).
