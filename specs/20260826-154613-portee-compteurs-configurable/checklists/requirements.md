# Specification Quality Checklist: Portée des compteurs configurable depuis le panel admin

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-26
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

- Passage 1 : deux formulations trop techniques corrigées avant écriture finale — « cache invalidé »
  et « miroir SQL / prédicat Python » remplacés par leur effet observable (FR-005 « le badge affiché
  et les compteurs coïncident », FR-006 « sans coût d'accès à la base par résultat », FR-008 « effet
  immédiat sans redéploiement »). Les noms de modules et de tests restent dans l'en-tête *Input* et
  dans l'issue, pas dans les exigences.
- Aucun [NEEDS CLARIFICATION] posé : les trois zones grises (portée mono-club, propagation entre
  processus, appartenance de la nomenclature des disciplines) ont un défaut raisonnable, documenté
  en *Assumptions*. La propagation notamment : le service tourne en un seul processus uvicorn
  (`render.yaml`, aucun `--workers`), l'invalidation en mémoire suffit donc.
- Reste ouvert au *plan*, pas à la spec : la forme de stockage (une table ou deux), et le sort de
  l'index fonctionnel sur les libellés normalisés — la normalisation ne changeant pas (Assumptions),
  l'index reste valide, à confirmer en conception.
