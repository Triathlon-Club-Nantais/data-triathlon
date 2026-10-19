# Feature Specification: Marquer les adhérents dans PostHog

**Feature Branch**: `feat/1374-posthog-member` (empilée sur `feat/1325-claim-athlete`)

**Created**: 2026-10-17

**Status**: Draft

**Input**: Issue #1374, epic #1360. `identify()` sous consentement est livré (#1159) ; seule la propriété `is_staff` est posée côté serveur. Avec les comptes membres (#1312) et le rattachement (#1325), il faut distinguer membres et visiteurs dans PostHog, pour les seuls utilisateurs qui ont accepté la mesure détaillée. Hors périmètre : comptes jeunes, construction des cohortes dans l'interface PostHog.

## Clarifications

### Session 2026-10-17

- Q: Quelles propriétés ? → A: les deux, `is_member` (statut dérivé, #1322) et `has_claimed_athlete` (fiche rattachée, #1325) : la seconde distingue l'adhérent qui a fait le geste du rattachement, utile pour la rétention de l'espace personnel (#1360).
- Q: Où les poser ? → A: à l'`identify()` du front, déjà sous consentement et rejoué à chaque changement de session : la valeur suit le statut sans écriture serveur supplémentaire.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'analyste distingue les adhérents (Priority: P1)

Dans PostHog, une personne identifiée porte `is_member` et `has_claimed_athlete`, à jour de sa dernière session.

**Independent Test**: une session adhérente rattachée avec accord : `identify` reçoit `is_member: true`, `has_claimed_athlete: true` ; sans accord, aucun `identify`.

**Acceptance Scenarios**:

1. **Given** un connecté qui a accepté la mesure détaillée, **When** sa session se charge, **Then** `identify` porte `is_member` et `has_claimed_athlete` à leurs valeurs courantes.
2. **Given** un connecté sans accord, **When** sa session se charge, **Then** aucune propriété ne part.
3. **Given** un rattachement validé ou un détachement, **When** la session se relit, **Then** `identify` repart avec la nouvelle valeur.

## Requirements *(mandatory)*

- **FR-001**: `identify()` MUST porter `is_member` et `has_claimed_athlete`, booléens.
- **FR-002**: Ces propriétés MUST NOT partir sans l'accord à la mesure détaillée.
- **FR-003**: `docs/analytics-posthog.md` MUST décrire les propriétés et la construction des cohortes et de la rétention dans l'interface PostHog.

## Success Criteria *(mandatory)*

- **SC-001**: Une cohorte « adhérents » se construit dans PostHog sans autre donnée que ces propriétés.

## Assumptions

- Aucune propriété ne nomme la fiche (pas d'identifiant d'athlète dans PostHog) : un booléen suffit aux cohortes.
