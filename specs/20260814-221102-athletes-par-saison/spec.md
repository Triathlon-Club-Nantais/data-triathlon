# Feature Specification: Page de visualisation des athlètes par saison

**Feature Branch**: `feature-page-visualisation-des-preuves-par-athl`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Page de visualisation des épreuves par athlète (issue #274) : en tant que secrétaire général, je peux accéder à une page dédiée où je vois tous les membres du club ayant au moins une participation, avec le nombre d'épreuves qu'ils ont fait, filtrable par saison (saison = 1er septembre au 31 août). Athlètes triables par nombre d'épreuves et par nom de famille. Accès public, pas de restriction RBAC. Nouvelle page dédiée, distincte de /club existant."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consulter la liste des athlètes actifs d'une saison (Priority: P1)

En tant que visiteur du site (secrétaire général ou tout autre membre), j'accède à une page dédiée qui liste les athlètes du club ayant participé à au moins une épreuve durant la saison en cours, avec pour chacun le nombre d'épreuves faites.

**Why this priority**: C'est la demande centrale de l'issue — sans cette liste, la page n'a pas de raison d'être. Elle seule livre déjà de la valeur (photographie de l'activité du club sur la saison en cours).

**Independent Test**: Charger la page sans filtre : elle affiche uniquement les athlètes ayant ≥1 participation sur la saison en cours, chacun avec son nombre d'épreuves.

**Acceptance Scenarios**:

1. **Given** la saison en cours compte des athlètes avec des participations, **When** j'ouvre la page, **Then** je vois la liste de ces athlètes, chacun avec son nom et son nombre d'épreuves sur la saison.
2. **Given** un athlète du club n'a aucune participation sur la saison en cours, **When** j'ouvre la page, **Then** cet athlète n'apparaît pas dans la liste.

---

### User Story 2 - Filtrer par saison (Priority: P2)

En tant que visiteur, je change la saison sélectionnée pour voir l'activité d'une saison passée (une saison va du 1er septembre au 31 août).

**Why this priority**: Complète la P1 en donnant une profondeur historique, explicitement demandée dans l'issue, mais la page reste utile sans ce filtre (saison en cours par défaut).

**Independent Test**: Sélectionner une saison antérieure : la liste et les compteurs se recalculent pour cette seule saison, sans rechargement de page complet.

**Acceptance Scenarios**:

1. **Given** je suis sur la page avec la saison en cours affichée, **When** je sélectionne une saison antérieure, **Then** la liste ne montre que les athlètes ayant ≥1 participation sur cette saison, avec leur nombre d'épreuves recalculé pour cette saison.
2. **Given** une saison sélectionnée ne compte aucune participation d'aucun athlète du club, **When** j'ouvre la page sur cette saison, **Then** la page affiche un état vide explicite plutôt qu'une liste vide silencieuse.

---

### User Story 3 - Trier la liste (Priority: P3)

En tant que visiteur, je trie la liste par nombre d'épreuves ou par nom de famille pour retrouver rapidement un athlète ou identifier les plus actifs.

**Why this priority**: Confort d'usage sur une liste qui peut compter plusieurs dizaines d'athlètes ; la P1 reste consultable sans tri (ordre par défaut).

**Independent Test**: Sur une liste déjà affichée, activer chaque tri : l'ordre des lignes change en conséquence, sans changer les données affichées.

**Acceptance Scenarios**:

1. **Given** la liste est affichée, **When** je choisis le tri par nombre d'épreuves, **Then** les athlètes s'affichent du plus grand au plus petit nombre d'épreuves.
2. **Given** la liste est affichée, **When** je choisis le tri par nom de famille, **Then** les athlètes s'affichent par ordre alphabétique de nom de famille.

---

### Edge Cases

- Deux athlètes à égalité sur le nombre d'épreuves : le tri par nombre d'épreuves les départage par nom de famille (ordre secondaire stable).
- Une participation dont la date de course tombe exactement le 1er septembre ou le 31 août : elle compte dans la saison dont cette date est la borne (définition déjà en vigueur ailleurs sur le site, réutilisée telle quelle).
- Athlète dont le nom de famille est absent ou mal renseigné en base : il apparaît en fin de tri alphabétique plutôt que de faire échouer le tri.
- Saison sélectionnée sans aucune participation pour aucun athlète du club : état vide explicite (cf. US2, scénario 2), pas une liste techniquement vide sans explication.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT exposer une page dédiée, distincte de `/club`, listant les athlètes du club.
- **FR-002**: Le système DOIT n'afficher, pour la saison sélectionnée, que les athlètes ayant au moins une participation à une épreuve sur cette saison.
- **FR-003**: Le système DOIT afficher pour chaque athlète listé son nom complet et son nombre d'épreuves sur la saison sélectionnée.
- **FR-004**: Le système DOIT permettre de sélectionner la saison affichée, une saison courant du 1er septembre au 31 août, avec la saison en cours sélectionnée par défaut à l'ouverture de la page.
- **FR-005**: Le système DOIT permettre de trier la liste par nombre d'épreuves (décroissant) et par nom de famille (alphabétique croissant).
- **FR-006**: La page DOIT être accessible sans authentification ni restriction de rôle.
- **FR-007**: Le système DOIT afficher un état vide explicite lorsque la saison sélectionnée ne compte aucun athlète avec participation.

### Key Entities

- **Athlète** : membre reconnu du club, identifié par son nom complet (dont nom de famille, utilisé pour le tri).
- **Participation** : rattachement d'un athlète à une épreuve, dont la date détermine la saison d'appartenance.
- **Saison** : période du 1er septembre au 31 août, unité de filtrage de la page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Un visiteur identifie, en une seule page et sans navigation supplémentaire, le nombre d'épreuves fait par chaque athlète actif du club sur une saison donnée.
- **SC-002** : Un visiteur retrouve un athlète précis dans la liste en moins de 10 secondes grâce au tri par nom de famille, sur une liste de plusieurs dizaines d'athlètes.
- **SC-003** : Changer de saison affichée met à jour la liste et les compteurs sans quitter la page.

## Assumptions

- « Tous les membres du club » se limite, comme précisé en commentaire de l'issue, aux athlètes ayant au moins une participation sur la saison sélectionnée — les athlètes du club sans participation sur cette saison ne sont pas affichés (potentiellement plus au club).
- La définition de saison, le calcul de la saison en cours et le composant de sélection de saison déjà en place ailleurs sur le site (`app/core/season.py`, `SeasonSelector`) sont réutilisés tels quels, sans nouvelle règle métier.
- Le nom cliquable d'un athlète peut renvoyer vers sa page de détail déjà existante (`/athletes/[id]`) : comportement cohérent avec le reste du site, mais non bloquant pour la valeur livrée par cette page si reporté.
- Le tri par défaut à l'ouverture de la page est le tri par nombre d'épreuves décroissant (met en avant les athlètes les plus actifs), l'issue ne précisant pas d'ordre par défaut.
- Pagination : hors scope explicite de cette spec si le volume d'athlètes actifs par saison reste dans les dizaines ; à réévaluer si la volumétrie constatée le justifie (non chiffré dans l'issue).
