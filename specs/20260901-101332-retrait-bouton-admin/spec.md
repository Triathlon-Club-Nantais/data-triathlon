# Feature Specification: Retrait du bouton admin de déclaration de bénévolat

**Feature Branch**: `780-retrait-bouton-admin`

**Created**: 2026-09-01

**Status**: Draft

**Input**: Issue GitHub #780 (sous-issue de l'epic #776) — « feat(athletes):
remove admin-only volunteer declaration button ». `SeasonValidationPanel`
affiche un bouton « Déclarer une action de bénévolat » réservé aux admins
détenant `athletes:volunteer_manage` — un geste en un clic, sans titre ni
description, qui crédite immédiatement le quota de saison. Ce chemin est
redondant depuis #778 (formulaire public, tout adhérent connecté) et #779
(workflow de validation) : le retirer était explicitement conditionné à leur
fusion, désormais faite.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Le geste admin en un clic disparaît de la fiche athlète (Priority: P1)

Un admin qui ouvrait autrefois la fiche d'un athlète pour lui déclarer un
bénévolat en un clic ne voit plus ce bouton — le seul chemin restant est le
formulaire public (#778), quel que soit son rôle.

**Why this priority**: C'est la demande explicite de l'issue — sans ce
retrait, deux chemins concurrents subsistent pour le même geste, l'un sans
trace (titre/description), l'autre avec.

**Independent Test**: Un admin détenant `athletes:volunteer_manage` (et
seulement ce pouvoir) ouvre la fiche d'un athlète ; la section validation de
saison n'affiche plus de bouton de déclaration de bénévolat. Le bouton
« Valider la saison » (pouvoir distinct, #709), lui, reste inchangé pour un
titulaire de `athletes:season_validate`.

**Acceptance Scenarios**:

1. **Given** un admin détenant uniquement `athletes:volunteer_manage`,
   **When** il ouvre la fiche d'un athlète, **Then** aucune section ni
   bouton de déclaration de bénévolat n'apparaît (la section entière
   disparaît si c'était son seul pouvoir sur ce panneau).
2. **Given** un admin détenant `athletes:season_validate`, **When** il ouvre
   la fiche d'un athlète, **Then** le bouton « Valider la saison » et
   l'indicateur de quota restent affichés, inchangés.
3. **Given** un athlète ayant des actions de bénévolat créées par ce chemin
   avant son retrait (titre/description absents), **When** un admin
   consulte la file d'attente (#779) ou la liste des actions validées
   (#781), **Then** ces lignes historiques restent visibles avec leur
   repli d'affichage existant — rien ne casse sur les données déjà en
   base.

---

### Edge Cases

- Un rôle qui ne détenait *que* `athletes:volunteer_manage` perd tout accès
  à ce panneau — attendu, ce pouvoir n'existe plus (voir Assumptions).
- Aucune migration de schéma : les colonnes `title`/`description` de
  `VolunteerAction` restent nullables, pour les lignes historiques créées
  par ce chemin avant son retrait.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système NE DOIT PLUS proposer, sur la fiche athlète, de
  geste admin permettant de créer une déclaration de bénévolat sans titre
  ni description.
- **FR-002**: Le système DOIT continuer à proposer le bouton « Valider la
  saison » (et son indicateur de quota) à un titulaire de
  `athletes:season_validate`, sans aucun changement de comportement.
- **FR-003**: Le système NE DOIT PLUS exposer aucune ressource (API,
  pouvoir, fonction) devenue inatteignable par la suppression de ce
  geste — un pouvoir sans ressource qu'il garde, ou une fonction sans
  appelant, est un chemin mort (Principe VI, YAGNI).
- **FR-004**: Le système DOIT continuer à représenter correctement, en
  lecture, les déclarations de bénévolat déjà créées par ce chemin avant
  son retrait (titre/description absents) — sur la file d'attente (#779)
  et la liste des actions validées (#781).

### Key Entities *(include if feature involves data)*

- **VolunteerAction** (existant) : aucun changement de schéma. Le seul
  chemin de création restant est le formulaire public self-service (#778,
  `create_pending`) — le chemin admin (`create`, sans titre/description) est
  retiré, pas seulement débranché de l'interface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des admins, quel que soit leur pouvoir, ne voient plus
  de geste de déclaration de bénévolat sans titre ni description sur la
  fiche athlète.
- **SC-002**: 100 % des lignes `VolunteerAction` déjà créées par l'ancien
  chemin admin restent lisibles et correctement affichées (repli
  d'affichage) dans les écrans existants (#779, #781) après le retrait.
- **SC-003**: Aucune ressource du dépôt (route, pouvoir, fonction) ne reste
  sans appelant ni garde après ce retrait.

## Assumptions

- **Retrait complet du chemin, pas seulement du bouton** : le pouvoir
  `athletes:volunteer_manage` ne garde qu'une seule ressource dans tout le
  dépôt (`POST /admin/athletes/{athlete_id}/volunteer-actions`) ; le retrait
  du seul bouton qui l'utilisait laisserait ce pouvoir sans aucune garde,
  ce que le dépôt vérifie déjà par un test dédié
  (`test_permissions_catalogue.py::
  test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource`,
  « un pouvoir que rien ne vérifie est un mensonge d'écran »). Conforme au
  principe du projet de ne pas garder de chemin mort, le retrait couvre
  donc la route, le pouvoir, la fonction de service et la fonction
  repository associées — pas seulement l'affichage.
- **Pas de migration de schéma** : `title`/`description` de `VolunteerAction`
  restent nullables — des lignes historiques créées par le chemin retiré
  peuvent légitimement porter ces champs à `NULL` en production, et rien
  n'exige de les réécrire.
- **La fiche athlète reste hors périmètre pour tout le reste** : aucun
  changement à `AthleteAdminPanel`, aux autres pouvoirs de la page, ni au
  workflow de validation (#779) ou à la liste des actions validées (#781).
