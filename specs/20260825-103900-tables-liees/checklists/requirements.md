# Specification Quality Checklist: Des tableaux qui se lisent, des lignes qui se partagent

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

Deux passes de validation ont été nécessaires.

**Passe 1 — trois échecs, corrigés :**

1. *No implementation details* — la première rédaction nommait `<table>`,
   `<th scope="col">`, `<Link>`, `useTransition` et `aria-sort`, tous repris de
   l'issue. Ce sont des moyens, et l'issue elle-même laisse ouvertes deux voies
   (balises réelles ou rôles ARIA). Les FR ont été réécrites en termes de ce que
   l'aide technique perçoit et de ce que l'utilisateur peut faire ; l'arbitrage
   est renvoyé au plan, et la raison en est consignée dans les Assumptions.
2. *Requirements are testable* — « les six grilles passent en tableaux » n'est
   pas testable tel quel (rien n'y dit ce qu'on observe). Devenu FR-001 :
   rattachement de chaque cellule à son en-tête, structure annoncée avec ses
   dimensions.
3. *Scope is clearly bounded* — l'issue renvoyait les cibles tactiles au lot
   `CIBLE-1` « à vérifier lors de la clarification ». Vérifié dans le code :
   #479 les a déjà livrées (`padding: 4px 0`, `minHeight: 24` sur
   `EnteteTriable`, commentaire à l'appui). La question est close sans
   clarification, et le hors-périmètre le dit.

**Passe 2 — tous les items passent.** Aucun marqueur `[NEEDS CLARIFICATION]`
n'a été nécessaire : les trois zones d'ombre candidates ont été tranchées par
lecture du code plutôt que par une question au mainteneur.

**Passe 3 — après `/speckit-analyze` et après l'implémentation.** Cinq
corrections, toutes traçables :

- **US1, scénario 4** exigeait « aucune en-tête de tableau orphelin » et
  contredisait donc FR-007 : quatre listes sur six rendent aujourd'hui leur
  en-tête sur une liste vide, et la masquer aurait été un changement
  d'apparence. Le scénario suit désormais le comportement d'origine, liste par
  liste (`contracts/` C1).
- **SC-004** annonçait « moins de 100 ms », qu'aucune tâche ne mesurait. Devenu
  un critère observable à l'œil nu. Un nombre invérifiable ne fait pas un
  critère de succès.
- **C4** dit maintenant que la couverture de FR-003 est **manuelle et
  ponctuelle** — le test jsdom constate le DOM, jamais ce que le serveur écrit.
- **C1** rangeait `EventList` du mauvais côté : elle sort avant sa `Card` sur
  liste vide et ne rend aucun tableau. Corrigé sur lecture du code.
- **`data-model.md`** a gagné deux invariants découverts en écrivant le code :
  aucun `overflow` sur la cellule qui porte la cible (il rogne les voiles
  absolus), et la sous-ligne d'administration qui porte sa `<tr>` elle-même.

**Écart notable relevé, et assumé** : les repères de l'issue (chemins et
numéros de ligne) sont antérieurs à #509, #489 et à la refonte du tableau de
bord. La spec porte un inventaire revérifié le 2026-08-25, et il réduit le
périmètre réel — cinq listes sur six ont déjà une ligne cliquable correcte,
seule celle du classement d'épreuve est encore un `role="button"`.
