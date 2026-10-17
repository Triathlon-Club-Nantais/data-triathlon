# Feature Specification: Récap de saison de l'athlète rattaché

**Feature Branch**: `feat/1372-season-recap` (empilée sur `feat/1373-season-goals`)

**Created**: 2026-10-17

**Status**: Draft

**Input**: Issue #1372, epic #1360. Les chiffres d'une saison sont éparpillés entre l'Accueil et la fiche athlète. Demande : une page récapitulative de la saison close pour l'athlète revendiqué (épreuves, podiums, meilleurs temps, challenges) ; les athlètes ayant fait opposition restent anonymisés dans tout classement cité. Hors périmètre : kilométrage, animation façon « Wrapped ».

## Clarifications

### Session 2026-10-17

Tranchées en autonomie, par l'option la plus simple.

- Q: Quelle saison ? → A: par défaut la dernière saison close (celle d'avant la saison en cours) ; on remonte aux saisons précédentes et on revient, sans dépasser la dernière close.
- Q: Quelles données ? → A: celles que la fiche athlète sert déjà (`GET /athletes/{id}` filtré sur la saison) : aucune route nouvelle. Résultats validés seuls.
- Q: Opposition ? → A: la page ne cite que les lignes de l'athlète (ses rangs, ses temps), aucun classement d'autrui : rien à anonymiser au delà de ce que l'import fait déjà.
- Q: Accès ? → A: un compte rattaché (#1325) ; un autre visiteur est invité à rattacher sa fiche.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - L'adhérent relit sa saison (Priority: P1)

Depuis l'Accueil, un adhérent rattaché ouvre « Récap de la saison 2025-2026 » et voit le nombre d'épreuves, ses podiums, ses meilleurs temps, ses challenges et la liste de ses épreuves.

**Independent Test**: compte rattaché, fiche avec trois résultats validés dans la saison 2025 dont un podium et un en attente : la page dit 2 épreuves, 1 podium, liste les deux épreuves, ignore la ligne en attente.

**Acceptance Scenarios**:

1. **Given** un compte rattaché, **When** il ouvre la page, **Then** la dernière saison close s'affiche avec ses chiffres.
2. **Given** la page d'une saison, **When** il choisit la saison précédente, **Then** la page la montre ; la saison suivante n'est offerte que jusqu'à la dernière close.
3. **Given** une saison sans résultat, **Then** la page le dit.
4. **Given** un visiteur sans fiche rattachée, **Then** la page l'invite à rattacher sa fiche.

## Requirements *(mandatory)*

- **FR-001**: La page MUST montrer, pour une saison close de la fiche rattachée : nombre d'épreuves, nombre de podiums (top 3 au scratch, au genre ou en catégorie, règle de « Ma saison »), meilleurs temps (règle #1361), challenges de la saison, liste des épreuves avec temps et rang.
- **FR-002**: Seuls les résultats validés MUST compter.
- **FR-003**: La page MUST NOT citer d'autre athlète.
- **FR-004**: L'Accueil MUST offrir le lien vers la page au compte rattaché.
- **FR-005**: Aucune route serveur nouvelle.

## Success Criteria *(mandatory)*

- **SC-001**: La saison se relit en une page, sans passer par la fiche ni les filtres.

## Assumptions

- La saison suit `lib/utils/season` (bascule au 1er septembre).
