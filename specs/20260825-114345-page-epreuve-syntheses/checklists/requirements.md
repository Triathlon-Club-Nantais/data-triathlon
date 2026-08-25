# Specification Quality Checklist: la page épreuve — répartitions honnêtes, synthèses navigables, temps douteux signalés

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-25
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

- **Itération 1** — trois écarts relevés et corrigés :
  1. *Implementation details* : la première rédaction nommait `CategoryBars`,
     `RaceFinishers` et `frontend/lib/quality.ts` dans les exigences. Les noms de fichiers
     ont été retirés des `FR-*` et déplacés vers le contexte, où ils servent de preuve et
     non de prescription.
  2. *Testable et non ambigu* : « un marqueur discret » ne disait pas quand il se pose.
     `FR-005` porte désormais le seuil (au-delà de 2 % du temps total) et `FR-008` les cas
     où le contrôle est omis, avec le cas limite « juste au seuil » en Edge Cases.
  3. *Scope clairement borné* : l'audit note que le détail de participation ne lit pas non
     plus la fiabilité. Le périmètre le dit maintenant explicitement — la liste des
     épreuves est dedans (`RES-10` la nomme), le détail de participation est dehors (repris
     par le lot #462), les deux décisions sont motivées en Assumptions.

- Deux points ont été tranchés par défaut plutôt que marqués `[NEEDS CLARIFICATION]`, et
  restent à confirmer en `/speckit-plan` s'ils coûtent plus que prévu :
  - **Accès au libellé de catégorie** (`FR-024`, `FR-025`) : l'audit proposait une
    infobulle, qui n'existe ni au doigt ni au clavier. La spec exige l'accès sans imposer
    la forme — c'est au plan de choisir entre popover, légende dépliable ou libellé inline.
  - **Cumul des sélections** (`FR-019`, Edge Cases) : club, catégorie, recherche et portée
    club sont déclarés cumulables. L'alternative — un filtre exclusif — aurait été plus
    simple mais aurait fait disparaître silencieusement une sélection au profit d'une
    autre, ce que l'entrée `RES-9` reproche déjà à l'écran.

- Le point de vérité des constats reste
  `docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md` § 6. Toute divergence entre
  ce document et lui se tranche en re-sondant, pas en arbitrant sur pièces.
