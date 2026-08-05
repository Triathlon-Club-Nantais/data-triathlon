# Specification Quality Checklist: RBAC — rôles composables

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-04 · **Révisé**: 2026-08-05 (v3)
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

### Ce que la v3 change — la revue humaine a trouvé ce que le fan-out n'a pas trouvé

Cinq instructions parallèles avaient instruit cette feature ; une relecture
humaine (PR #193, @MathieuHerrmann, 2026-08-05) a produit deux choses qu'aucune
n'avait produites :

- **un objet manquant** — les groupes d'appartenance. Les cinq instructions
  cherchaient à modéliser des *droits* ; un groupe n'en est pas un, donc aucune
  ne pouvait le voir. Écarté vers **#197**, avec le jalon qui rend le retard
  sûr : « avant qu'un groupe porte un droit » ;
- **une question mal posée** — le patron d'évolution des rôles semés, offert en
  trois voies (organique / GitLab / Kubernetes). Aucune n'est retenue : la
  question qui les précède n'avait pas été posée, et sa réponse (FR-041, une
  migration ne recompose jamais un rôle) les rend sans objet. C'est la seule
  décision de cette révision qui **retire** du travail.

C'est la contre-épreuve exacte de la note « convergence de sous-agents = artefact »
qui ouvre `research.md`. Un lecteur sans le corpus du dépôt en contexte voit ce
que le corpus empêche de voir.

**Six FR ajoutés ou modifiés** : FR-003 (portée de l'inventaire), FR-010
(symétrie du retrait), FR-020 (rôles portés dans la session), FR-040 (convention
de nommage), FR-041 (semis unique), FR-042 (pouvoir périmé en base). Un rôle
système de plus (`moderator`), quatre lignes d'Out of Scope, deux edge cases.

### Ce que `/speckit-analyze` a trouvé, et que ni la revue ni le fan-out n'avaient vu

Deux anomalies **critiques**, même cause, deux sites — dans le contrat, pas dans
le code, donc avant la première ligne écrite.

`PATCH /admin/roles/{id}` remplace l'ensemble des pouvoirs : tout `PATCH` retire
donc implicitement les codes **périmés** qu'un rôle traîne. Le contrat refusait
en 403 le retrait d'un pouvoir que l'appelant ne porte pas — or un code absent du
catalogue n'est porté par **personne**, superutilisateur compris, dont les
pouvoirs effectifs *sont* le catalogue. Le rôle devenait immodifiable ; `is_system`
(FR-006) ou attribué (FR-007), il devenait aussi indélébile. Même mécanisme à
l'attribution : le rôle devenait inattribuable.

Trois documents affirmaient pourtant l'inverse — « purgeable, jamais bloquante ».
Un nettoyage de code ordinaire suffisait à les démentir.

**FR-011 est donc borné à l'inventaire**, à l'octroi comme au retrait. La borne
n'est pas une précaution : c'est la condition de réversibilité. Et la tâche de
test T037, écrite avant l'implémentation, **encodait la règle fautive** — le TDD
protège de l'implémentation fausse, jamais de la spécification fausse.

Trois trous de couverture fermés au passage : FR-005 (renommer sans perdre ses
attributions — la justification même de `role_id`), FR-006 dans sa moitié
« reste modifiable », et FR-012 au niveau de la ressource et non du repository.

### Une limite que le filet ne couvre plus, et qui doit être écrite

Avec la politique en données, le filet automatique prouve qu'une ressource exige
*un* pouvoir — jamais *qui* le porte. C'est le prix assumé de l'édition à chaud.
La docstring du filet doit le dire, sous peine de laisser croire à une garantie
qui n'existe plus.

Rien ne bloque `/speckit-tasks`.
