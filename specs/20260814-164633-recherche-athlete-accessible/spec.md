# Feature Specification: Recherche d'athlète toujours accessible et sélection explicite

**Feature Branch**: `feat-ui-garder-la-recherche-dathl-te-accessible`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Issue #323 — feat(ui): garder la recherche d'athlète accessible et rendre la sélection explicite. La navigation propose deux états : sans athlète sélectionné (bouton « Rechercher »), ou avec athlète (tuile + chevron). La sélection se mémorise via localStorage. Constats : une fois l'athlète retenu, la recherche n'est plus annoncée ; avec le rail replié, aucun accès sauf raccourci clavier ; la sélection n'est exploitée nulle part ; impossible de se sélectionner depuis son propre profil. Attendu : l'entrée « Rechercher un athlète » reste toujours accessible quel que soit le format, un athlète retenu s'affiche en complément et non à la place de cette entrée, bouton explicite sur la page profil pour se sélectionner/relâcher, raccourci clavier conservé, tests couvrant les deux états et formats. Hors périmètre : les usages fonctionnels (filtrage, classements) sont reportés à l'issue #325."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Garder la recherche accessible en toutes circonstances (Priority: P1)

Un membre du club navigue dans l'application. Qu'il ait déjà retenu un athlète ou non, et que le rail de navigation soit déplié ou replié, il doit pouvoir ouvrir la recherche d'athlète d'un geste visible — pas seulement via un raccourci clavier qu'il ne connaît pas forcément.

**Why this priority**: C'est le problème le plus bloquant relevé dans l'issue : en rail replié avec un athlète déjà retenu, l'entrée de recherche disparaît entièrement de l'écran et seul le raccourci clavier y donne accès. Un utilisateur qui ne connaît pas ce raccourci n'a plus aucun moyen de changer d'athlète.

**Independent Test**: Retenir un athlète, puis parcourir chaque combinaison d'état de la navigation (rail déplié/replié, desktop/mobile) et vérifier que l'entrée "Rechercher un athlète" reste visible et actionnable à la souris/au tactile dans chacune, sans dépendre du raccourci clavier.

**Acceptance Scenarios**:

1. **Given** aucun athlète retenu et le rail déplié, **When** l'utilisateur regarde la navigation, **Then** il voit l'entrée "Rechercher un athlète" et peut l'activer.
2. **Given** un athlète retenu et le rail déplié, **When** l'utilisateur regarde la navigation, **Then** il voit à la fois l'entrée "Rechercher un athlète" et la tuile de l'athlète retenu, l'une n'effaçant pas l'autre.
3. **Given** un athlète retenu et le rail replié, **When** l'utilisateur regarde la navigation, **Then** une icône de recherche reste visible et cliquable, indépendamment de la tuile de l'athlète.
4. **Given** n'importe quel état de la navigation, **When** l'utilisateur active le raccourci clavier existant, **Then** la recherche s'ouvre.

---

### User Story 2 - Se sélectionner ou se relâcher depuis une page profil (Priority: P2)

Un membre consulte la page profil d'un athlète (y compris potentiellement la sienne). Il veut pouvoir le retenir comme son athlète sans repasser par la recherche, et pouvoir relâcher la sélection tout aussi facilement si cet athlète est déjà celui retenu.

**Why this priority**: C'est une capacité manquante identifiée dans l'issue (constat #4) ; elle complète la première user story mais n'est pas bloquante pour l'accès à la recherche elle-même.

**Independent Test**: Depuis la page profil d'un athlète non retenu, cliquer sur le bouton de sélection et vérifier que la navigation reflète immédiatement ce choix ; revenir sur la même page et vérifier que le bouton propose désormais de relâcher ; cliquer dessus et vérifier que la navigation repasse à l'état "aucun athlète retenu".

**Acceptance Scenarios**:

1. **Given** la page profil d'un athlète qui n'est pas l'athlète retenu, **When** l'utilisateur clique sur le bouton de sélection, **Then** cet athlète devient l'athlète retenu et la navigation l'affiche immédiatement.
2. **Given** la page profil de l'athlète actuellement retenu, **When** l'utilisateur consulte la page, **Then** le bouton propose de relâcher la sélection plutôt que de la créer.
3. **Given** la page profil de l'athlète actuellement retenu, **When** l'utilisateur clique sur le bouton de relâchement, **Then** la sélection est effacée et la navigation repasse à l'état "aucun athlète retenu".

---

### Edge Cases

- Que se passe-t-il si la sélection stockée est corrompue ou dans un format obsolète au chargement de la page profil ou de la navigation ? Le système doit se comporter comme si aucun athlète n'était retenu, sans erreur visible.
- Que se passe-t-il si l'utilisateur relâche l'athlète retenu pendant que la recherche est ouverte ? La recherche doit rester utilisable et refléter l'absence de sélection une fois fermée.
- Le format mobile (barre + tiroir) garde son accès recherche indépendant de l'état de sélection (résolu, cf. Assumptions) : la barre mobile persistante n'affiche pas de tuile complémentaire, seul le tiroir déplié — qui réutilise le même rendu que le rail — l'affiche.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT afficher l'entrée "Rechercher un athlète" dans la navigation à tout moment, quel que soit le format (rail déplié, rail replié, barre mobile, tiroir mobile).
- **FR-002**: Le système DOIT continuer d'afficher l'entrée "Rechercher un athlète" lorsqu'un athlète est retenu — elle ne doit jamais être remplacée par la tuile de l'athlète retenu.
- **FR-003**: Lorsqu'un athlète est retenu, le système DOIT afficher cette sélection comme un élément complémentaire et visuellement distinct de l'entrée recherche (éléments séparés à l'écran, ni fusionnés ni superposés — cf. Acceptance Scenario 2 d'US1).
- **FR-004**: En rail replié, le système DOIT offrir une affordance visuelle actionnable (icône cliquable) pour ouvrir la recherche, sans dépendre exclusivement du raccourci clavier.
- **FR-005**: Le raccourci clavier existant DOIT continuer d'ouvrir la recherche depuis n'importe quel état de la navigation.
- **FR-006**: La page profil d'un athlète DOIT proposer un bouton permettant de retenir cet athlète comme sélection active lorsqu'il ne l'est pas déjà.
- **FR-007**: Lorsque l'athlète affiché sur sa page profil est déjà celui retenu, le système DOIT proposer un bouton pour relâcher la sélection à la place du bouton de sélection.
- **FR-008**: Sélectionner ou relâcher un athlète depuis sa page profil DOIT mettre à jour l'affichage de la navigation immédiatement, sans rechargement de page.
- **FR-009**: Le système DOIT être couvert par des tests automatisés croisant les deux états de sélection (athlète retenu / aucun athlète retenu) avec les formats de navigation (rail déplié, rail replié, mobile).

### Key Entities *(include if feature involves data)*

- **Sélection d'athlète retenue** : référence légère vers un athlète (identifiant, prénom, nom) mémorisée côté utilisateur pour persister son choix d'une visite à l'autre. Ne porte aucune donnée de résultats ni de classement — ces usages restent hors périmètre (issue #325).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dans 100 % des combinaisons état de sélection × format de navigation, l'utilisateur peut ouvrir la recherche d'athlète en une seule action visible (clic ou appui), sans devoir connaître un raccourci clavier.
- **SC-002**: Depuis la page profil d'un athlète, l'utilisateur peut le retenir ou le relâcher en une seule action, sans repasser par la recherche.
- **SC-003**: Un athlète retenu reste visible comme information complémentaire dans 100 % des formats de navigation, sans jamais masquer l'entrée recherche.
- **SC-004**: Les deux états de sélection croisés avec l'ensemble des formats de navigation sont couverts par des tests automatisés qui échouent si l'entrée recherche cesse d'être accessible.

## Assumptions

- Le raccourci clavier existant (⌘K / Ctrl+K) n'est pas modifié, seul l'accès visuel en complément est ajouté.
- Le bouton de la page profil est un simple bascule sélection/relâchement pour l'athlète affiché ; il ne cherche pas à déterminer si cet athlète correspond à l'identité de l'utilisateur connecté — aucune donnée ne relie aujourd'hui un compte utilisateur à un athlète, et établir ce lien est hors périmètre de cette feature.
- Le format et la clé de la sélection mémorisée ne changent pas ; seule sa visibilité et ses points d'entrée évoluent.
- Le format mobile, qui garde déjà un accès recherche indépendant de l'état de sélection, n'est pas régressé par cette feature ; il doit simplement continuer d'afficher l'athlète retenu en complément sans dupliquer cet accès.
- Les usages fonctionnels de la sélection retenue (filtrage, classements) restent hors périmètre, reportés à l'issue #325.
