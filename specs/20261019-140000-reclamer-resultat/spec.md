# Feature Specification: Réclamer un résultat rangé sur une autre fiche

**Feature Branch**: `epic/1360-personal-space` (commits directs, revue sur #1632)

**Created**: 2026-10-19

**Status**: Draft

**Input**: Issue #1637. Le rattachement (#1325) porte sur une fiche entière. Quand un homonyme partage la fiche d'un adhérent, ou qu'un de ses résultats est rangé sur la fiche d'un autre, seul le back-office peut le déplacer (`reassign_participation`, #1209). L'adhérent passe par un message hors du site.

## Clarifications

### Session 2026-10-19

- Q: Qui ? → A: un compte rattaché à sa fiche ; le résultat doit être sur une autre fiche, validé, individuel.
- Q: Quelle file ? → A (mainteneur) : **commune** avec les rattachements de fiche (`/admin/rattachements`), avec un **effort important d'interface** pour distinguer les deux sortes : sections séparées, titres, pastille de sorte (« Fiche entière » / « Un résultat »), phrase d'explication par section, verbes d'action distincts (« Rattacher la fiche » / « Déplacer le résultat »).
- Q: Fiche d'origine vidée ? → A: le geste existant (`reassign_participation`) la purge déjà quand elle devient orpheline ; rien de plus.
- Q: Combien ? → A: 5 demandes en attente au plus par compte ; une seule par résultat et par compte (une nouvelle demande d'un résultat refusé la remet en attente).
- Q: Jamais d'office ? → A: jamais : un responsable valide, comme #1325.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'adhérent demande « ce résultat est à moi » (Priority: P1)

**Independent Test**: compte rattaché à la fiche A ; résultat validé sur la fiche B ; la demande crée une réclamation en attente ; la page du résultat dit « Demande en attente ».

**Acceptance Scenarios**:

1. **Given** un compte rattaché et un résultat validé, individuel, d'une autre fiche, **When** il demande, **Then** une réclamation en attente est enregistrée.
2. **Given** un résultat de sa propre fiche, en attente de validation, ou un relais, **Then** le bouton n'apparaît pas, l'API refuse.
3. **Given** 5 réclamations en attente, **Then** la sixième est refusée.
4. **Given** une réclamation en attente, **When** il l'annule, **Then** elle disparaît.
5. **Given** un compte sans fiche, **Then** refus explicite.

### User Story 2 - Le club valide ou refuse, sans confondre les deux files (Priority: P1)

**Independent Test**: `/admin/rattachements` montre deux sections distinctes ; valider une réclamation de résultat déplace le résultat vers la fiche du compte (journal `participation.reassign` et `result_claim.approve`) ; la pastille compte les deux sortes.

**Acceptance Scenarios**:

1. **Given** des réclamations de résultat, **Then** elles apparaissent dans leur section « Résultats réclamés », distincte des « Fiches demandées », avec : épreuve, date, dossard, temps, fiche actuelle et son nombre de résultats, compte et sa fiche, licencié de la saison.
2. **When** le responsable valide, **Then** le résultat passe sur la fiche du compte, figé contre l'import, la fiche d'origine vidée est purgée, la réclamation disparaît, le geste est journalisé.
3. **When** il refuse, **Then** la réclamation est marquée refusée, le résultat ne bouge pas.
4. **Given** la fiche du compte porte déjà un résultat sur cette épreuve, **Then** refus (conflit), rien ne bouge.

## Requirements *(mandatory)*

- **FR-001**: Un compte rattaché MUST pouvoir réclamer un résultat validé, individuel, d'une autre fiche ; 5 en attente au plus ; une par résultat.
- **FR-002**: Aucune réclamation MUST NOT être validée d'office.
- **FR-003**: Valider MUST passer par `admin_actions.reassign_participation` vers la fiche du compte, et journaliser `result_claim.approve` ; refuser MUST journaliser `result_claim.reject`.
- **FR-004**: La file MUST rester commune (`/admin/rattachements`, pouvoir `athlete_claims:review`) en distinguant nettement les deux sortes (FR UX ci-dessus) ; la pastille `claims` MUST compter les deux.
- **FR-005**: Les réclamations MUST appartenir au compte (supprimées avec lui) et suivre leur résultat (supprimées avec lui).
- **FR-006**: La page détail du résultat MUST offrir « Ce résultat est à moi » au compte concerné, et dire l'état d'une réclamation en cours.

## Success Criteria *(mandatory)*

- **SC-001**: Un adhérent récupère un résultat mal rangé en un geste, sans message hors du site.
- **SC-002**: Un responsable distingue au premier regard une demande de fiche d'une réclamation de résultat.

## Assumptions

- La réclamation ne nomme aucun tiers au delà de ce que la page publique du résultat montre déjà.
