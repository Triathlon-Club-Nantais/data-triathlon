# Feature Specification: Fin du statut adhérent par rattachement, détachement par le club

**Feature Branch**: `epic/1312-member-accounts` (commits directs, revue sur #1379)

**Created**: 2026-10-19

**Status**: Draft

**Input**: Issue #1633. Depuis #1325, un compte rattaché à sa fiche est adhérent sans limite : un ancien adhérent garde la dispense du code d'accès tant qu'il ne se détache pas. Aucun geste du back-office ne détache un compte.

## Clarifications

### Session 2026-10-19

- Q: Quand le rattachement cesse-t-il de valoir adhésion ? → A (mainteneur) : **borné à la saison**. Un compte rattaché est adhérent si sa fiche est un licencié TCN **rattaché** de la saison en cours (`club_members`, statut `auto` ou `manual`), ou si son adresse compte dans la liste d'adhérents (#1334). Le rattachement lui-même reste : il continue de servir l'espace personnel (#1360), il ne vaut plus adhésion hors saison.
- Q: Le geste du club ? → A: « Détacher » un compte de sa fiche depuis `/admin/rattachements`, sous `athlete_claims:review`, confirmé, journalisé (`athlete_claim.detach`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'adhésion par rattachement suit la saison (Priority: P1)

**Independent Test**: compte rattaché à une fiche ; fiche licenciée TCN de la saison en cours → adhérent ; licence de la saison précédente seule → non adhérent ; adresse sur la liste → adhérent quoi qu'il en soit.

**Acceptance Scenarios**:

1. **Given** un compte rattaché dont la fiche est licenciée TCN pour la saison en cours, **Then** il est adhérent.
2. **Given** un compte rattaché sans licence de la saison en cours, adresse hors liste, **Then** il n'est pas adhérent, et garde sa fiche.
3. **Given** une licence en statut non rattaché ou ambigu, **Then** elle ne compte pas.

### User Story 2 - Le club détache un compte (Priority: P1)

**Independent Test**: un porteur d'`athlete_claims:review` liste les comptes rattachés (compte, fiche, adhérent ou non cette saison), détache l'un d'eux : le compte n'a plus de fiche, le journal trace le geste.

**Acceptance Scenarios**:

1. **Given** des comptes rattachés, **When** le responsable ouvre `/admin/rattachements`, **Then** il voit, à part des demandes, la liste des comptes rattachés avec leur statut d'adhérent de la saison.
2. **When** il détache un compte après confirmation, **Then** le compte perd sa fiche, le geste est journalisé, la liste se met à jour.
3. **Given** un compte sans fiche, **When** on le détache, **Then** 404.
4. **Given** un connecté sans le pouvoir, **Then** 403 sur la liste et le geste.

## Requirements *(mandatory)*

- **FR-001**: `is_member` MUST valoir vrai pour un compte rattaché seulement si sa fiche est un licencié TCN rattaché de la saison en cours, ou si son adresse compte dans la liste d'adhérents.
- **FR-002**: Le back-office MUST lister les comptes rattachés (identité, fiche, adhérent cette saison) et permettre de détacher l'un d'eux, sous `athlete_claims:review`, après confirmation.
- **FR-003**: Le détachement MUST être journalisé (`athlete_claim.detach`, fiche dans la charge).
- **FR-004**: La politique de confidentialité et `docs/auth/membres.md` MUST dire la règle.

## Success Criteria *(mandatory)*

- **SC-001**: Au réimport de septembre, un ancien adhérent non relicencié perd la dispense du code sans geste du club.

## Assumptions

- La saison qui compte suit la règle de la liste d'adhérents : la saison en cours dès qu'elle a un licencié, sinon la précédente (`club_member_repository.counting_season`), ce qui évite une coupure au 1er septembre. Les rattachements faits à la main (homonymes tranchés) suivent la personne à la saison suivante, sans quoi la première synchro les rendait ambigus (revue).
