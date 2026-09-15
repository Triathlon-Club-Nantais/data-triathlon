# Feature Specification: Profil individuel jeune

**Feature Branch**: `867-profil-jeune`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Issue GitHub #867, sous-issue de l'epic #863 : modèle de données (migration Alembic) et écran de consultation d'un profil individuel jeune — informations personnelles et journal de bord (entrées texte datées). Tables génériques (pas de préfixe 'jeune' figé) en anticipation d'une future extension aux adultes, non implémentée. Routes backend + écran frontend mobile-first, protégés par les pouvoirs jeunes:read / jeunes:write."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consulter la liste des jeunes (Priority: P1)

Un encadrant porteur du pouvoir `jeunes:read` ouvre l'écran des jeunes depuis son téléphone et voit la liste des profils déjà créés (nom, prénom, âge).

**Why this priority**: C'est le point d'entrée de toute la fonctionnalité — sans liste, aucun profil n'est atteignable. C'est aussi la première chose qu'audite #863 : un référencement de tous les jeunes.

**Independent Test**: Se connecter avec un compte porteur de `jeunes:read`, ouvrir l'écran, constater que la liste des profils créés s'affiche.

**Acceptance Scenarios**:

1. **Given** deux profils existent en base, **When** l'encadrant ouvre l'écran des jeunes, **Then** les deux profils apparaissent, triés par nom.
2. **Given** aucun profil n'existe, **When** l'encadrant ouvre l'écran, **Then** un message clair indique qu'aucun jeune n'est encore référencé.
3. **Given** un visiteur sans le pouvoir `jeunes:read` (session ouverte ou non), **When** il appelle la route de liste, **Then** l'accès est refusé (401 sans session, 403 avec session mais sans le pouvoir).

---

### User Story 2 - Consulter le détail d'un profil et son journal de bord (Priority: P1)

Un encadrant ouvre un profil depuis la liste et voit les informations personnelles (contact d'urgence, âge, notes) ainsi que l'historique daté du journal de bord.

**Why this priority**: C'est la valeur métier centrale de #867 — un profil qui ne peut être consulté ne sert à rien à l'encadrant sur le terrain.

**Independent Test**: Ouvrir un profil existant portant des entrées de journal, vérifier que les informations personnelles et les entrées apparaissent, les plus récentes en premier.

**Acceptance Scenarios**:

1. **Given** un profil avec trois entrées de journal à des dates différentes, **When** l'encadrant ouvre le profil, **Then** les trois entrées s'affichent, triées de la plus récente à la plus ancienne, chacune avec sa date.
2. **Given** un profil sans aucune entrée de journal, **When** l'encadrant l'ouvre, **Then** le profil s'affiche avec un journal vide et un message l'indiquant.
3. **Given** un identifiant de profil inexistant, **When** l'encadrant tente de l'ouvrir, **Then** un 404 est rendu.

---

### User Story 3 - Créer et modifier un profil (Priority: P2)

Un encadrant porteur du pouvoir `jeunes:write` crée un nouveau profil (nom, prénom, date de naissance, contact d'urgence, notes) ou corrige un profil existant.

**Why this priority**: Nécessaire pour peupler le référencement, mais un référencement peut démarrer avec des profils créés par une autre voie (ex. amorçage manuel en base) — la consultation (P1) reste la valeur livrable minimale.

**Independent Test**: Avec un compte porteur de `jeunes:write`, créer un profil avec les champs obligatoires, vérifier qu'il apparaît ensuite dans la liste et le détail ; modifier un champ, vérifier qu'il est mis à jour.

**Acceptance Scenarios**:

1. **Given** un encadrant porteur de `jeunes:write`, **When** il soumet un nouveau profil avec nom, prénom et date de naissance, **Then** le profil est créé et consultable.
2. **Given** un profil existant, **When** l'encadrant modifie le contact d'urgence ou les notes, **Then** la modification est enregistrée et visible au prochain chargement.
3. **Given** un encadrant porteur seulement de `jeunes:read`, **When** il tente de créer ou modifier un profil, **Then** l'accès est refusé (403).

---

### User Story 4 - Ajouter une entrée au journal de bord (Priority: P2)

Un encadrant porteur du pouvoir `jeunes:write` ajoute une entrée texte datée au journal de bord d'un profil, en dehors de tout appel de présence (le flux d'appel de présence est #869, hors périmètre ici).

**Why this priority**: Le journal de bord est explicitement demandé par #863 et #867 ; il est daté P2 car il dépend de l'existence d'un profil (P2/P1) et n'est pas nécessaire pour livrer la seule consultation.

**Independent Test**: Depuis l'écran de détail d'un profil, ajouter une entrée avec un texte et une date, vérifier qu'elle apparaît dans l'historique.

**Acceptance Scenarios**:

1. **Given** un profil existant, **When** l'encadrant ajoute une entrée avec un texte non vide, **Then** l'entrée apparaît dans le journal, datée du jour par défaut.
2. **Given** un encadrant porteur seulement de `jeunes:read`, **When** il tente d'ajouter une entrée, **Then** l'accès est refusé (403).
3. **Given** un texte vide, **When** l'encadrant tente de soumettre l'entrée, **Then** la soumission est refusée (422) sans créer d'entrée.

### Edge Cases

- Un profil sans date de naissance renseignée (donnée non encore connue) : l'âge n'est pas calculable, l'écran l'indique sans erreur plutôt que d'afficher un âge faux.
- Un profil dont le nom/prénom est modifié : le journal de bord existant reste attaché au même profil, aucune entrée n'est perdue.
- Deux encadrants modifient le même profil presque simultanément : la dernière écriture gagne (pas de verrouillage optimiste demandé pour cette itération).
- Suppression d'un profil ou d'une entrée de journal : hors périmètre de #867 (aucune route de suppression n'est demandée par l'issue) — seules création, modification et consultation le sont.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à un porteur du pouvoir `jeunes:read` de lister tous les profils individuels référencés.
- **FR-002**: Le système DOIT permettre à un porteur du pouvoir `jeunes:read` de consulter le détail d'un profil : nom, prénom, date de naissance, contact d'urgence, notes, et l'historique complet de son journal de bord.
- **FR-003**: Le système DOIT permettre à un porteur du pouvoir `jeunes:write` de créer un profil avec au minimum un nom et un prénom.
- **FR-004**: Le système DOIT permettre à un porteur du pouvoir `jeunes:write` de modifier les champs d'un profil existant (nom, prénom, date de naissance, contact d'urgence, notes).
- **FR-005**: Le système DOIT permettre à un porteur du pouvoir `jeunes:write` d'ajouter une entrée texte datée au journal de bord d'un profil, indépendamment de tout flux d'appel de présence.
- **FR-006**: Le journal de bord DOIT conserver un historique de plusieurs entrées par profil (jamais une valeur unique écrasée à chaque ajout).
- **FR-007**: Toute route de consultation ou d'écriture sur un profil ou son journal DOIT exiger respectivement `jeunes:read` ou `jeunes:write` — aucune n'est accessible sans session, et aucune n'est accessible à un porteur d'un autre pouvoir seul.
- **FR-008**: Le schéma de données DOIT être nommé et structuré de façon générique (aucun préfixe « jeune » dans les noms de tables ou de colonnes), pour ne pas bloquer une future extension à d'autres publics (adultes) — cette extension n'est **pas** implémentée par cette feature.
- **FR-009**: L'écran de consultation d'un profil DOIT rester utilisable sur un écran de téléphone (mobile-first) — c'est l'usage principal décrit par #867.
- **FR-010**: Une tentative de consultation d'un profil inexistant DOIT rendre une erreur 404 explicite plutôt qu'une page vide silencieuse.
- **FR-011**: Une entrée de journal DOIT être horodatée (date de l'entrée) et son texte ne peut pas être vide.

### Key Entities *(include if feature involves data)*

- **Profil individuel** (`PersonalProfile`) : une personne suivie par le club — nom, prénom, date de naissance (optionnelle), contact d'urgence (texte libre), notes (texte libre). Générique : ne porte aucune mention « jeune » dans sa structure, seule la garde d'accès (`jeunes:*`) en réserve l'usage aux jeunes pour cette itération.
- **Entrée de journal** (`ProfileLogEntry`) : une note texte datée, rattachée à un profil individuel. Plusieurs entrées coexistent pour un même profil — c'est un historique, pas un indicateur unique. Porte qui l'a écrite et quand.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un encadrant porteur du pouvoir adéquat peut retrouver le profil d'un jeune et lire son contact d'urgence en moins de 3 étapes depuis l'écran de liste, sur un écran de téléphone.
- **SC-002**: 100 % des tentatives de consultation ou de modification d'un profil par un compte sans le pouvoir requis sont refusées (401 ou 403 selon le cas), vérifié par test automatisé.
- **SC-003**: Un profil créé avec au moins une entrée de journal restitue l'intégralité de son historique daté à la consultation suivante, sans perte d'entrée.
- **SC-004**: Aucune donnée de profil ou de journal n'est visible depuis une route publique non gardée (vérifié par le filet d'inventaire des routes du dépôt).

## Assumptions

- Les pouvoirs `jeunes:read` et `jeunes:write` existent déjà dans le catalogue (`app/core/permissions.py`, livrés par #866) et ne sont pas redéfinis ici.
- Aucune suppression de profil ni d'entrée de journal n'est demandée par #867 ; ce n'est donc pas un objectif de cette feature (une suppression future s'ajoutera sans migration destructive si besoin).
- L'ajout d'une entrée de journal pendant une séance d'entraînement (appel de présence) est le périmètre de #869 et n'est pas construit ici — seule l'édition directe d'un profil et de son journal, hors contexte de séance, l'est.
- Le calendrier des entraînements (table séance + participants, #868) est développé en parallèle par une autre feature et n'est ni lu ni modifié ici.
- Une seule organisation existe actuellement dans le dépôt (le TCN) ; le profil suit le même patron que les autres tables du domaine RBAC sans complexifier pour une multi-organisation non demandée.
- « Âge » à l'écran est dérivé de la date de naissance au moment de l'affichage, jamais stocké — comme le reste du dépôt dérive des valeurs calculées plutôt que de les figer.
