# Feature Specification: Pouvoir « jeunes »

**Feature Branch**: `866-permission-scope-jeunes`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Ajouter le scope de pouvoir \"jeunes\" au catalogue RBAC existant (core/permissions.py), pour l'issue GitHub #866, sous-issue de l'epic #863 (encadrement et suivi des jeunes triathlètes)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Composer un rôle avec le pouvoir jeunes (Priority: P1)

Un administrateur, depuis l'écran de composition des rôles déjà en place
(`/admin/roles`), voit apparaître les pouvoirs de consultation et d'encadrement
des jeunes dans la liste des pouvoirs disponibles, au même titre que les
pouvoirs existants (« Coureurs », « Résultats », etc.). Il peut cocher l'un ou
l'autre pour un rôle, sauvegarder, et le rôle porte alors ce pouvoir.

**Why this priority**: C'est la seule capacité livrée par cette issue — sans
elle, aucune sous-issue suivante (profils, calendrier, appel) n'a de pouvoir à
vérifier.

**Independent Test**: Depuis l'écran de composition d'un rôle, cocher
« Consulter les jeunes » ou « Encadrer les jeunes » pour un rôle existant,
enregistrer, recharger l'écran : la case reste cochée. Aucune route jeunes
n'existe encore pour vérifier l'effet du pouvoir — cette issue ne livre que
l'inventaire et son attribution.

**Acceptance Scenarios**:

1. **Given** l'écran de composition d'un rôle, **When** un administrateur
   l'ouvre, **Then** il voit deux nouveaux pouvoirs listés sous une
   fonctionnalité « Jeunes » : consulter, et encadrer.
2. **Given** un rôle sans pouvoir jeunes, **When** un administrateur coche
   « Encadrer les jeunes » et enregistre, **Then** le rôle porte désormais
   `jeunes:write` et l'API `/admin/roles` le reflète.
3. **Given** un rôle qui porte `jeunes:read`, **When** un administrateur
   décoche ce pouvoir et enregistre, **Then** le rôle ne le porte plus.

### Edge Cases

- Un code hors catalogue (ancienne faute de frappe, ou pouvoir retiré plus
  tard) n'accorde rien et ne casse rien — comportement déjà garanti par le
  mécanisme existant (FR-042 de #115), non modifié ici.
- Aucune ressource ne vérifie encore ces deux pouvoirs à l'issue de cette
  PR : voir FR-004 et la section Assumptions pour la façon dont la suite de
  tests reste verte malgré ce fait, en attendant les sous-issues #867/#868/#869.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le catalogue de référence des pouvoirs DOIT gagner deux
  nouveaux codes de la forme `<domaine>:<geste>` : `jeunes:read` (consulter
  le profil des jeunes et le calendrier des entraînements) et `jeunes:write`
  (créer/modifier un profil, tenir le calendrier, faire l'appel, ajouter une
  entrée au journal de bord d'un jeune).
- **FR-002**: Les deux pouvoirs DOIVENT apparaître, avec un libellé et une
  description en français, dans l'écran existant de composition des rôles
  (`GET /admin/permissions`, regroupement par fonctionnalité), sous une
  fonctionnalité dédiée « Jeunes » — sans qu'aucune route ni écran de ce
  regroupement ne soit modifiés pour l'accueillir.
- **FR-003**: Un rôle DOIT pouvoir se voir attribuer ou retirer l'un ou
  l'autre de ces deux pouvoirs via le mécanisme d'attribution déjà en place
  (`PATCH` de composition d'un rôle), sans aucune route ni mécanisme nouveau.
- **FR-004**: La suite de tests DOIT rester verte après l'ajout de ces deux
  codes, alors même qu'aucune ressource ne les vérifie encore
  (`require_permission`) — cette issue ne livre aucune route jeunes. Le test
  de non-régression qui exige qu'un pouvoir du catalogue garde au moins une
  ressource (`tests/test_permissions_catalogue.py`) DOIT documenter cette
  exception de façon explicite, nominative et temporaire (référençant les
  sous-issues #867/#868/#869 qui la lèveront), plutôt que de rester rouge en
  silence ou d'être affaibli pour tous les pouvoirs.
- **FR-005**: Cette issue NE DOIT créer aucune route ni écran spécifique aux
  jeunes (profils, calendrier, appel) — ces ressources sont hors périmètre et
  reviennent aux sous-issues #867 (profils), #868 (calendrier) et #869
  (appel).
- **FR-006**: Cette issue NE DOIT attribuer effectivement aucun de ces deux
  pouvoirs à un rôle particulier en production ou dans les données
  d'amorçage — c'est une décision d'exploitation hors code (cf. semis des
  rôles `admin`/`validator`/`moderator`, qui ne se rejoue jamais).

### Key Entities

- **Pouvoir `jeunes:read`** : autorise la consultation des futures
  ressources jeunes (profils, journal de bord, calendrier des entraînements).
- **Pouvoir `jeunes:write`** : autorise la création et la modification de ces
  mêmes ressources, ainsi que la tenue de l'appel de présence.
- Aucune nouvelle table : la composition et l'attribution passent par les
  tables `roles` / `role_permissions` / `user_roles` déjà existantes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Les deux pouvoirs `jeunes:read` et `jeunes:write` sont visibles
  et sélectionnables depuis l'écran de composition des rôles, sans
  modification de cet écran.
- **SC-002**: La suite de tests backend (unitaire, hors réseau) passe à 100 %
  après l'ajout de ces deux pouvoirs, `ruff check` compris.
- **SC-003**: Aucune ligne de code de routage ou d'écran n'est ajoutée en
  dehors du catalogue de pouvoirs et de son test de non-régression.

## Assumptions

- La granularité retenue est volontairement large : deux pouvoirs
  (`read`/`write`) plutôt qu'un pouvoir par sous-fonctionnalité (profils,
  calendrier, appel), sur le même patron que `athletes:read`/`athletes:write`
  et `groups:read`/`groups:write` déjà dans le catalogue. Les trois
  sous-issues suivantes protègent des ressources étroitement liées (l'appel
  peuple le calendrier et accède aux profils) ; les scinder en pouvoirs
  distincts multiplierait les cases à cocher côté rôle sans bénéfice mesuré
  à ce stade. Rien n'empêche un futur raffinement si un besoin d'exploitation
  le justifie (ce serait un ajout de code, jamais une migration).
- Le test `tests/test_permissions_catalogue.py` est modifié pour documenter
  explicitement, par une liste nominative référençant les sous-issues
  concernées, les pouvoirs dont la garde n'est pas encore posée — plutôt que
  laissé rouge en silence, plutôt que satisfait par une route hors périmètre.
  Cette exception est temporaire : elle doit être retirée dès qu'une
  sous-issue pose la première garde sur l'un des deux codes.
- Aucun rôle existant (`admin`, `validator`, `moderator`) ne reçoit ces
  pouvoirs dans cette issue ; leur attribution à un rôle « encadrant jeunes »
  ou existant est une décision d'exploitation ultérieure, hors code.
