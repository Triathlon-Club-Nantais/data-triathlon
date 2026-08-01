# Specification Quality Checklist: Socle d'authentification SSO pour le back-office admin

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-01
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

Deux itérations de correction ont été nécessaires.

**Itération 1 — fuite d'implémentation.** La première rédaction nommait la bibliothèque retenue,
l'algorithme d'empreinte, les noms de tables, les chemins d'URL, les noms de cookies et les codes
de statut HTTP. Tout cela a été reformulé en propriétés observables : « valeur opaque et
imprévisible » plutôt que le générateur employé, « ne doit pas être conservée en clair » plutôt que
l'algorithme, « moyen de connexion » plutôt que le nom d'un endpoint. Ces choix techniques sont
arbitrés et **mesurés**, mais leur place est dans `plan.md` et dans le sondage, pas ici.

**Itération 2 — exigences non testables.** Trois exigences disaient « le système devrait » sans
critère d'observation. Elles ont été soit rendues vérifiables (FR-013 énonce désormais un invariant
à trois conditions, adossé à SC-006 et SC-007), soit versées aux hypothèses quand elles décrivaient
un contexte plutôt qu'un comportement.

**Deux références au dépôt sont conservées délibérément** et ne sont pas considérées comme des
fuites d'implémentation : FR-039 et SC-009 renvoient au contrôle de destination de l'issue #101, et
FR-019 au fait que le dépôt n'a aucun ordonnanceur. Ce sont des **contraintes de l'existant**, non
des choix de technologie : les taire produirait une spec qui autorise une régression de sécurité
déjà payée, et une commande que personne ne lancerait jamais.

**Périmètre élargi, acté.** L'issue #114 borne son périmètre au backend et renvoie l'interface de
connexion à l'issue #116. Cette spec couvre les deux, sur décision explicite de l'utilisateur : la
garde des écrans d'administration n'a pas de sens sans interface, et la livraison doit être
testable dans un navigateur. À reporter en commentaire sur #114 et #116 au moment de l'ouverture de
la PR.

**Le sondage prime.** `docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md` fait autorité
sur cette spec comme sur le plan à venir. Il porte notamment deux contraintes d'exécution mesurées
(le plafond de traitements simultanés, et la réémission du corps de requête sur redirection) qui
motivent FR-025 et une partie du plan.
