# Feature Specification: Carte résultat à télécharger

**Feature Branch**: `feat/1371-result-card` (empilée sur `feat/1374-posthog-member`, elle-même sur `feat/1325-claim-athlete`)

**Created**: 2026-10-17

**Status**: Draft

**Input**: Issue #1371, epic #1360. Les adhérents partagent leurs résultats par capture d'écran. Une image OG publique est exclue (code d'accès, `noindex`, base légale de réutilisation interne). Demande : un bouton « Télécharger l'image » sur la page détail d'un résultat, PNG 1080×1350 à l'identité TCN, avec la seule ligne de l'adhérent, refusé pour une ligne en attente ou un athlète qui n'est pas celui du compte. Hors périmètre : URL publique, balises OG, partage direct vers un réseau.

## Clarifications

### Session 2026-10-17

- Q: Où générer l'image ? → A (mainteneur) : **dans le navigateur** (canvas), sans route serveur ; le moteur de rendu est isolé pour pouvoir passer côté serveur (`next/og`) si les appareils des adhérents s'avèrent trop lents. L'issue citait `next/og` ; ce choix la remplace.
- Q: Un relais ? → A: exclu : sa ligne nomme des équipiers (tiers), que l'issue écarte.
- Q: Un abandon ou une disqualification ? → A: permis, l'image dit le statut à la place du temps et des rangs.
- Q: Le refus côté serveur ? → A: sans route, rien à refuser au serveur : le bouton n'apparaît pas, et l'image ne contient que ce que la page affiche déjà à l'utilisateur.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'adhérent télécharge l'image de son résultat (Priority: P1)

Sur la page détail de l'un de ses résultats, un adhérent rattaché à sa fiche (#1325) choisit « Télécharger l'image » et reçoit un PNG à partager.

**Independent Test**: session rattachée à la fiche 42, résultat validé de la fiche 42 : le bouton est là, le rendu écrit le nom de l'épreuve, la date, le nom, le temps et les rangs, et rien d'autre.

**Acceptance Scenarios**:

1. **Given** un compte rattaché à la fiche du résultat, résultat validé et individuel, **When** il clique, **Then** un PNG 1080×1350 se télécharge, nommé d'après l'épreuve.
2. **Given** un visiteur anonyme, un compte non rattaché ou rattaché à une autre fiche, **When** la page s'affiche, **Then** aucun bouton.
3. **Given** un résultat en attente ou refusé, ou un relais, **When** la page s'affiche, **Then** aucun bouton.
4. **Given** un abandon, **When** il télécharge, **Then** l'image dit « Abandon » sans temps ni rang.

## Requirements *(mandatory)*

- **FR-001**: Le bouton MUST n'apparaître que pour un compte dont la fiche rattachée est celle du résultat, sur un résultat validé et non relais.
- **FR-002**: L'image MUST mesurer 1080×1350, à l'identité TCN (dégradé orange, Anton et Barlow), et porter : club, épreuve, date, discipline, nom de l'athlète, temps (ou statut), rang au scratch, rang et libellé de catégorie s'ils existent.
- **FR-003**: L'image MUST NOT nommer de tiers ni montrer de classement.
- **FR-004**: Le rendu MUST vivre dans un module isolé (modèle de données puis dessin), sans dépendance au composant, pour pouvoir être déplacé côté serveur.
- **FR-005**: Aucune dépendance nouvelle, aucune route serveur.

## Success Criteria *(mandatory)*

- **SC-001**: L'image se télécharge en un geste depuis la page du résultat.
- **SC-002**: Aucune information au-delà de la ligne de l'adhérent n'y figure.

## Assumptions

- Les polices sont celles déjà chargées par la page (variables `--font-anton`, `--font-barlow`) ; à défaut, le repli système.
- Le validation du principe par le bureau (#1342 citée par l'issue) relève du mainteneur ; la fonction ne publie rien d'elle-même.
