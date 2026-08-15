# Feature Specification: Distinction abandons / non-partants / disqualifiés

**Feature Branch**: `20260815-112430-abandons-dnf-dns-dsq`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "Corriger la pastille « Abandons » de /courses/[id] (issue #331) : elle agrège aujourd'hui trois statuts distincts (DNF, DNS, DSQ) sous un seul libellé trompeur. Option retenue : B — distinguer. `CourseSummary` doit exposer dnf/dns/dsq séparément (champs additifs à l'API existante, compatibles avec le Principe IV — aucun champ retiré), et l'écran /courses/[id] doit afficher séparément ce qui est non nul (pas de pastille vide si une épreuve n'a ni DNS ni DSQ). Le total doit rester cohérent : finishers + non-classés + indéterminés = total (lien avec #322, qui corrige déjà le libellé du total — cette feature doit livrer après #322 pour ne pas toucher les mêmes lignes). Tests attendus : backend sur les trois statuts, test de rendu de l'écran."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un visiteur lit un décompte honnête sur la page d'une épreuve (Priority: P1)

Un visiteur consulte la page publique d'une épreuve (`/courses/[id]`) pour comprendre combien de participants ont terminé, abandonné, ne se sont jamais présentés au départ, ou ont été disqualifiés. Aujourd'hui, une seule pastille « Abandons » agrège les trois derniers cas, ce qui fait passer pour des abandons des personnes qui n'ont jamais couru (non-partants) ou qui ont fini mais ont été disqualifiées.

**Why this priority**: C'est le défaut visible qui motive l'issue — un chiffre affiché est faux pour une partie de la population qu'il prétend décrire, en particulier sur les épreuves qui publient beaucoup de non-partants dès l'inscription.

**Independent Test**: Ouvrir une épreuve connue pour avoir des abandons, des non-partants et des disqualifiés (ou les simuler en base de test), constater trois pastilles distinctes plutôt qu'une pastille unique, chacune avec le bon décompte.

**Acceptance Scenarios**:

1. **Given** une épreuve où des participants ont chacun des statuts abandon, non-partant et disqualifié, **When** un visiteur ouvre la page de l'épreuve, **Then** il voit trois indications séparées (« Abandons », « Non-partants », « Disqualifiés »), chacune portant le bon décompte.
2. **Given** une épreuve sans aucun non-partant ni disqualifié, **When** un visiteur ouvre la page de l'épreuve, **Then** aucune pastille vide n'apparaît pour ces deux catégories — seule celle des abandons s'affiche si elle est non nulle.
3. **Given** une épreuve avec des abandons, des non-partants et des disqualifiés, **When** on additionne finishers + abandons + non-partants + disqualifiés + indéterminés, **Then** le total obtenu est égal au nombre total de participants affiché par ailleurs sur la page.

---

### User Story 2 - Le résumé textuel de l'épreuve reste cohérent avec les pastilles (Priority: P2)

La liste des résultats d'une épreuve (`RaceFinishers`) porte son propre résumé en une ligne (« 120 participants · 110 finishers · 6 abandons · 2 indéterminés »), qui emploie aujourd'hui le même mot générique « abandons » pour désigner le même agrégat à trois statuts que la pastille de la page. Ce résumé doit refléter la même distinction, pour ne pas raconter deux histoires différentes du même chiffre selon l'endroit de la page où on le lit.

**Why this priority**: Moins visible que la pastille principale (US1), mais le même défaut, au même endroit conceptuel — livré juste après pour ne pas laisser un second site incohérent avec le premier.

**Independent Test**: Sur la même épreuve que US1, comparer le résumé textuel de la liste de résultats avec les pastilles de l'en-tête : les deux doivent raconter les mêmes trois catégories, sans qu'aucune ne soit tue par l'autre.

**Acceptance Scenarios**:

1. **Given** une épreuve avec des abandons, des non-partants et des disqualifiés, **When** un visiteur lit le résumé en une ligne de la liste de résultats, **Then** les trois catégories apparaissent séparément si elles sont non nulles, avec le mot juste pour chacune.

---

### Edge Cases

- Une épreuve où tous les non-finishers sont des non-partants (aucun abandon, aucune disqualification) : seule la pastille « Non-partants » doit apparaître, pas les deux autres.
- Une épreuve où un statut est présent en base sous une graphie inattendue (casse différente, espaces) : le classement dans la bonne catégorie doit rester correct, comme c'est déjà le cas aujourd'hui pour l'agrégat unique.
- Une épreuve dont le total affiché ailleurs sur la page (nombre de participants) ne doit jamais diverger de la somme des catégories désormais distinguées — un écart signalerait un participant compté deux fois ou pas du tout.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** : Le système DOIT exposer, pour une épreuve donnée, le décompte des participants en abandon (DNF), le décompte des non-partants (DNS) et le décompte des disqualifiés (DSQ), comme trois informations distinctes plutôt qu'un total unique.
- **FR-002** : Le système DOIT continuer à exposer le total agrégé des trois statuts (la donnée existante consommée aujourd'hui), en plus des trois décomptes distincts — aucune information actuellement disponible ne doit disparaître.
- **FR-003** : La page d'une épreuve DOIT afficher séparément chacune des trois catégories (abandons, non-partants, disqualifiés) lorsqu'elle est non nulle, et ne rien afficher pour une catégorie à zéro.
- **FR-004** : Le résumé textuel de la liste de résultats d'une épreuve DOIT refléter la même distinction à trois catégories que la page de l'épreuve, plutôt que le mot générique actuel.
- **FR-005** : La somme des participants finishers, en abandon, non-partants, disqualifiés et indéterminés DOIT toujours être égale au nombre total de participants de l'épreuve.
- **FR-006** : Cette fonctionnalité ne DOIT retirer, renommer ni changer la sémantique d'aucune donnée actuellement publiée par l'API — les nouveaux décomptes s'ajoutent à ceux qui existent déjà.

### Key Entities

- **Synthèse d'épreuve** : la vue d'ensemble déjà publiée d'une épreuve (nombre de participants, de finishers, répartition par genre, catégories, clubs…) — à qui cette fonctionnalité ajoute trois décomptes (abandons, non-partants, disqualifiés) là où elle n'en portait qu'un seul agrégé.
- **Statut d'un participant** : l'état déclaré d'un participant vis-à-vis de l'épreuve — terminé, abandon, non-partant, disqualifié, ou indéterminé quand le statut n'est ni renseigné ni reconnu.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Sur une épreuve portant les trois statuts, un visiteur distingue en un coup d'œil le nombre d'abandons, de non-partants et de disqualifiés, sans avoir à consulter une source externe pour comprendre la composition du chiffre affiché.
- **SC-002** : Une épreuve sans disqualifié ni non-partant n'affiche aucune indication vide pour ces deux catégories — l'écran ne montre que ce qui a une valeur à raconter.
- **SC-003** : Le total affiché sur la page reste, dans 100 % des cas, égal à la somme de toutes les catégories de statut désormais distinguées.

## Assumptions

- Le statut de chaque participant (terminé / abandon / non-partant / disqualifié / indéterminé) est une donnée déjà collectée et fiable pour les épreuves existantes — cette fonctionnalité ne change pas la façon dont ce statut est déterminé, seulement la façon dont il est agrégé et affiché.
- Cette fonctionnalité livre après #322 (déjà résolue), qui a corrigé le libellé du total de participants — aucune divergence de périmètre entre les deux n'est attendue.
- Aucun changement n'est demandé sur la définition de ce qui compte comme abandon, non-partant ou disqualifié — seule leur agrégation en un chiffre unique est en cause.
