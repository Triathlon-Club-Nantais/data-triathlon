# Specification Quality Checklist: RBAC — rôles composables

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-04 · **Révisé**: 2026-08-04 (v2)
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
- [x] Success criteria are technology-agnostic
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

### Écarts assumés

1. **Les codes HTTP 401 et 403 figurent dans la spec.** Détail
   d'implémentation au sens du template, mais **cœur du besoin** : l'AC2 de
   l'issue #115 est formulé sur cette distinction précise, et `/api/v1` est un
   contrat public au sens du Principe IV. Les effacer rendrait la spec plus pure
   et moins vérifiable.

2. **Des routes existantes sont nommées.** Ce n'est pas de la conception, c'est
   le périmètre réel : qu'une route préfixée `/admin/` soit appelée par le
   formulaire public interdit de protéger par préfixe, et deux routes de
   participations sont ouvertes à Internet. Le taire ferait planifier une garde
   fausse.

### Ce que la v2 change, et pourquoi la v1 est caduque

La v1 reposait sur l'arbitrage du 2026-08-02 (association `(user, role)` **sans
organisation**, deux rôles figés, organisation hors périmètre). Trois arbitrages
produit du 2026-08-04 l'annulent : multi-club, plus de trois rôles, et **rôles
éditables à chaud**.

Cette spec **contredit donc explicitement** un arbitrage antérieur consigné dans
sa propre v1. C'est délibéré et daté, pas un oubli — laisser cohabiter les deux
aurait produit exactement la divergence documentation/code que ce dépôt combat.

### Deux points instruits par confrontation, pas par déduction

- **L'exigence « éditable à chaud » a d'abord été refusée**, par trois
  instructions indépendantes, au motif qu'« on ne peut pas créer un point de
  contrôle à l'exécution ». C'est vrai — et cela ne couvre que la moitié de la
  demande. Créer un rôle et composer ses pouvoirs est parfaitement faisable à
  chaud. FR-002 conserve la partie vraie de l'objection ; FR-004 satisfait le
  reste.
- **Une anomalie de sécurité a été découverte** en instruisant le filet :
  `POST /participations` et `DELETE /participations/{id}` sont ouvertes sans
  authentification, et le filet de #114 imposait qu'elles le restent. FR-023 les
  ferme. C'est hors du périmètre littéral de l'issue #115, et intégré sur
  arbitrage du 2026-08-04.

### Une limite que le filet ne couvre plus, et qui doit être écrite

Avec la politique en données, le filet automatique prouve qu'une ressource exige
*un* pouvoir — jamais *qui* le porte. C'est le prix assumé de l'édition à chaud.
La docstring du filet doit le dire, sous peine de laisser croire à une garantie
qui n'existe plus.

Rien ne bloque `/speckit-tasks`.
