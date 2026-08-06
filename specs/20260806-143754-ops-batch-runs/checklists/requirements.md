# Specification Quality Checklist: Lancer les batches de production depuis l'interface d'administration

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-06
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

Trois points relevés à la relecture, tranchés plutôt que laissés en suspens :

- **FR-005 nomme deux codes de pouvoir** (`batch:run`, `batch:read`). Ce ne sont
  pas des détails d'implémentation ici : l'inventaire des pouvoirs est un objet
  produit, affiché tel quel dans l'écran de composition des rôles (#115). Les
  nommer rend l'exigence testable.
- **FR-013 énonce une contrainte d'exécution** sans nommer de plateforme :
  « pas dans le processus qui sert les visiteurs ». Le choix de la plateforme
  est arrêté dans #47 et sera porté par `plan.md`, pas par la spec.
- **Les bornes chiffrées** (2 Mo, 500 URL, 20 lancements consultables et 50 au
  plus) sont des hypothèses assumées, pas des mesures — elles sont regroupées
  dans *Assumptions* pour être révisables sans toucher aux exigences.

### Révision du 2026-08-06, après `/speckit-analyze`

Quatre corrections apportées à la spec, toutes issues de l'analyse :

- **SC-005 était invérifiable** (« 0 fichier ne subsiste sur le serveur ») depuis
  une plateforme sans accès shell. Reformulé en critère vérifiable par test :
  aucune écriture de fichier applicative dans le chemin de téléversement.
- **SC-007 est sorti des critères de fusion** : quatre échéances hebdomadaires
  demandent un mois. Il devient un point de suivi daté.
- **Un edge case manquait** : le porteur de `batch:run` sans `batch:read`.
- **L'hypothèse de notification** dit désormais que le destinataire réel reste à
  constater, et ce qu'il advient si ce n'est pas la bonne personne.
