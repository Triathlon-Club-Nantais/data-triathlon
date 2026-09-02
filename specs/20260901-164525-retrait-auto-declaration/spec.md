# Feature Specification: Retrait de l'auto-déclaration de bénévolat

**Feature Branch**: `816-retrait-auto-declaration`

**Created**: 2026-09-01

**Status**: Draft

**Input**: Issue GitHub #816 (sous-issue de l'epic #815) — retire l'auto-déclaration
de bénévolat (#751, `VolunteerDeclaration`) de `/benevolat` et `/admin/benevolat`,
au profit du seul flux de crédit d'un athlète (#778/#779/#781/#809,
`VolunteerAction`). Empilée sur #809 (formulaire de crédit déjà ouvert au mot de
passe du site, non fusionné) : le résultat visé assume que seule la section de
crédit d'un athlète reste sur `/benevolat`.

**Décision produit explicite** : cette sous-issue est livrée **avec** #817
(écran de validation admin) — même branche/fenêtre de livraison — pour que
`/admin/benevolat` ne traverse jamais un état vide en production.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Une seule façon de créditer un athlète (Priority: P1)

Un visiteur ouvrant `/benevolat` ne voit plus qu'une section : « Créditer un
athlète pour le quota de saison ». L'ancienne section d'auto-déclaration
(formulaire + liste de ses propres déclarations + invite « Se connecter ») a
disparu.

**Why this priority**: c'est la demande explicite de l'issue — deux chemins
concurrents pour tracer une activité de bénévolat entretenaient la confusion
que l'epic #815 corrige.

**Independent Test**: ouvrir `/benevolat` sans session SSO et avec une
session SSO — dans les deux cas, une seule section s'affiche, celle du
crédit d'un athlète ; aucune invite de connexion ne s'affiche plus sur cette
page (conséquence du retrait, #809 avait déjà retiré la garde de la section
de crédit).

**Acceptance Scenarios**:

1. **Given** un visiteur sans session SSO, **When** il ouvre `/benevolat`,
   **Then** seule la section de crédit d'un athlète s'affiche — aucune trace
   de l'auto-déclaration ni d'invite « Se connecter ».
2. **Given** un visiteur avec une session SSO, **When** il ouvre
   `/benevolat`, **Then** le résultat est identique au scénario 1 — la
   présence d'une session ne change plus rien sur cette page.
3. **Given** un appel direct à l'ancienne API d'auto-déclaration
   (`POST /volunteer-declarations`), **When** la requête est envoyée,
   **Then** elle rend `404` — la route n'existe plus.

### User Story 2 - Aucune ressource orpheline (Priority: P1)

Le retrait ne laisse aucun chemin mort : pouvoir, route, fonction ou
composant sans appelant.

**Why this priority**: même discipline que #780 pour l'ancien geste admin de
l'epic #776 — un chemin retiré de l'écran mais gardé en base/API est un
chemin mort, et le dépôt vérifie déjà cette propriété par un test dédié au
catalogue de pouvoirs.

**Independent Test**: la suite de tests d'inventaire de routes et de
catalogue de pouvoirs reste verte après le retrait, sans qu'aucun test ne
doive être adapté pour tolérer un pouvoir ou une route orphelins.

**Acceptance Scenarios**:

1. **Given** le retrait effectué, **When** `test_permissions_catalogue.py`
   s'exécute, **Then** aucun pouvoir du catalogue ne garde zéro ressource.
2. **Given** le retrait effectué, **When** l'inventaire de routes
   s'exécute, **Then** aucune route de l'ancienne auto-déclaration n'y
   figure plus, ni comme fermée ni comme publique.

---

### Edge Cases

- `/admin/benevolat` ne doit jamais rendre une page vide ou une 404 sur une
  branche fusionnée — cette sous-issue et #817 (écran de validation) sont
  livrées ensemble, décision produit explicite (voir ci-dessus).
- Les données déjà en base dans la table `VolunteerDeclaration` (déclarations
  historiques) sont perdues à la migration de suppression de table — assumé,
  aucune valeur métier n'est identifiée à en conserver une trace (aucune
  demande de rétention formulée).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système NE DOIT PLUS proposer, sur `/benevolat`, de moyen
  d'auto-déclarer une activité de bénévolat — la page ne porte plus que le
  crédit d'un athlète.
- **FR-002**: Le système NE DOIT PLUS exposer aucune ressource (API,
  pouvoir, fonction, composant) devenue inatteignable par ce retrait — un
  pouvoir sans ressource qu'il garde, ou une fonction sans appelant, est un
  chemin mort (Principe VI, YAGNI).
- **FR-003**: Le système DOIT continuer à proposer, sans changement de
  comportement, le crédit d'un athlète pour le quota de saison (#778/#809)
  et le workflow de validation admin de ce crédit (#779).
- **FR-004**: `/admin/benevolat` DOIT rester une page fonctionnelle à tout
  instant sur une branche fusionnée — jamais vide entre le retrait de
  l'ancien contenu et la livraison du nouveau (#817).

### Key Entities *(include if feature involves data)*

- **VolunteerDeclaration** (existant, #751) : table et tout son code
  applicatif retirés — remplacée fonctionnellement par `VolunteerAction`
  (#778/#779), qui couvre déjà le même besoin (créditer une activité de
  bénévolat) avec un rattachement à un athlète.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des visiteurs de `/benevolat` ne voient plus qu'un seul
  chemin pour tracer une activité de bénévolat.
- **SC-002**: 0 route, pouvoir ou composant de l'ancienne auto-déclaration
  ne subsiste après le retrait (vérifié par grep exhaustif et par la suite
  de tests d'inventaire).
- **SC-003**: `/admin/benevolat` reste utilisable sans interruption pour un
  administrateur, avant et après ce retrait.

## Assumptions

- **Retrait complet, pas seulement de l'affichage** : même principe que
  #780 — les routes, pouvoirs (`benevolat:read`/`benevolat:manage`),
  services et repositories de l'auto-déclaration sont retirés, pas
  seulement débranchés de l'interface.
- **Pas de migration de données** : aucune conservation des déclarations
  historiques de `VolunteerDeclaration` — aucune demande de rétention
  formulée, et leur équivalent fonctionnel (`VolunteerAction`) n'a pas
  vocation à les reprendre automatiquement.
- **`/admin/benevolat` livrée avec #817** : décision produit explicite,
  capturée en Edge Cases — cette sous-issue seule pourrait laisser la page
  vide, ce n'est acceptable que parce que #817 comble l'écart avant toute
  fusion vers une branche de production.
