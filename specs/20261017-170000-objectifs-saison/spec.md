# Feature Specification: Objectifs de saison de l'athlète rattaché

**Feature Branch**: `feat/1373-season-goals` (empilée sur `feat/1371-result-card`)

**Created**: 2026-10-17

**Status**: Draft

**Input**: Issue #1373, epic #1360. Rien ne relie un compte à une intention pour la saison ; les meilleurs temps (#1361) donnent la référence chiffrée. Demande : un objectif = (discipline, format, temps cible ou nombre d'épreuves), créé, modifié et supprimé par son seul propriétaire ; progression calculée et affichée sur l'Accueil ; mention dans la politique de confidentialité, suppression avec le compte (#1326) ; tests d'accès refusé à un autre utilisateur. Hors périmètre : partage, objectifs de club, jeunes.

## Clarifications

### Session 2026-10-17

Tranchées par l'option la plus simple et la plus sûre (autonomie accordée par le mainteneur).

- Q: Qui peut poser un objectif ? → A: un compte **rattaché** à sa fiche (#1325) : la progression se lit sur ses résultats. Un compte sans fiche reçoit un refus explicite.
- Q: Deux sortes ? → A: **temps cible** sur une discipline et un format (`event_type`, ex. « Triathlon M ») : atteint quand le meilleur temps validé de la saison est inférieur ou égal ; **nombre d'épreuves** sur une discipline et un format, ou toutes disciplines : atteint quand le nombre de résultats validés de la saison l'atteint.
- Q: Quels résultats comptent ? → A: ceux de la fiche rattachée, validés, de la saison de l'objectif (1er septembre au 31 août). Pour le temps, mêmes exclusions que la carte des meilleurs temps (#1361) : ni relais, ni épreuve non fiable, ni non classé. Pour le nombre, les épreuves courues : résultats validés hors non-partants (un abandon ou une disqualification comptent), relais compris.
- Q: Combien ? → A: 10 objectifs au plus par compte et par saison.
- Q: Visibilité ? → A: privée : seul le propriétaire les lit, par sa session ; un objectif d'un autre compte répond 404, jamais 403 (ne pas confirmer son existence).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'adhérent se fixe un objectif et suit sa progression (Priority: P1)

Sur l'Accueil, un adhérent rattaché ajoute « Triathlon M en moins de 2:30:00 » ou « 6 épreuves cette saison », et voit où il en est.

**Independent Test**: compte rattaché à une fiche avec un Triathlon M validé en 2:35:10 cette saison ; objectif temps 2:30:00 : progression « meilleur 2:35:10, non atteint » ; objectif 1 épreuve : atteint.

**Acceptance Scenarios**:

1. **Given** un compte rattaché, **When** il crée un objectif temps ou nombre, **Then** il est enregistré pour la saison en cours et affiché avec sa progression.
2. **Given** un objectif, **When** son propriétaire le modifie ou le supprime, **Then** la modification s'applique.
3. **Given** un objectif d'un autre compte, **When** un utilisateur tente de le lire, modifier ou supprimer, **Then** 404.
4. **Given** un compte sans fiche rattachée, **When** il crée un objectif, **Then** refus (conflit) avec un message français.
5. **Given** 10 objectifs sur la saison, **When** il en crée un onzième, **Then** refus.
6. **Given** un compte supprimé, **Then** ses objectifs disparaissent avec lui.

## Requirements *(mandatory)*

- **FR-001**: Un objectif MUST porter : saison, sorte (`time` ou `count`), discipline et format (`event_type`, requis pour `time`, facultatif pour `count`), cible (secondes ou nombre, strictement positive).
- **FR-002**: Seul son propriétaire MUST pouvoir le lire, le modifier ou le supprimer ; un autre compte reçoit 404.
- **FR-003**: Créer un objectif MUST exiger un compte rattaché à sa fiche ; 10 objectifs au plus par compte et saison.
- **FR-004**: La progression MUST être calculée à la lecture, jamais stockée : meilleur temps (secondes et libellé) ou nombre d'épreuves, et « atteint ».
- **FR-005**: Les objectifs MUST disparaître avec le compte (table possédée, #1326).
- **FR-006**: La politique de confidentialité MUST les mentionner (donnée personnelle, privée, durée : celle du compte).
- **FR-007**: L'Accueil MUST les afficher au compte rattaché, avec ajout, modification et suppression ; rien pour un autre visiteur.

## Success Criteria *(mandatory)*

- **SC-001**: Un objectif se crée en un formulaire depuis l'Accueil.
- **SC-002**: Aucun objectif n'est lisible par un autre compte.

## Assumptions

- La saison suit `core/season` (bascule au 1er septembre) ; l'objectif reste attaché à sa saison et n'est pas reconduit.
- Pas de notification à l'atteinte d'un objectif.
