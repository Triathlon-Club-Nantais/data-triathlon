# Research: Droit d'opposition effectif

Faits relevés dans le code le 2026-10-01 (cartographie des chemins d'écriture).

## R1. Où filtrer les imports

- **Decision**: dans `import_service._Persister.add`, au même endroit que le traitement des noms masqués (`is_masked_name`), et dans `_resolve_pending` pour les équipiers d'un relais découpé.
- **Rationale**: tout import scrapé (web, SSE, `rescrape-db`, `import-sheet`, bascule de source, re-scrape admin) passe par `persist_steps` → `_Persister.add`. Le motif « Anonyme {course.id}-{dossard} » y existe déjà pour les noms masqués : l'identité est stable au re-scrape, le dossard restant unique sur l'épreuve. Filtrer **après** la renumérotation des rangs (`_renumber_*`) garde les rangs sources intacts.
- **Alternatives considered**: un filtre dans `athlete_repository` (ne couvre pas la mise à jour par dossard d'une ligne existante) ; un filtre avant la renumérotation (décalerait les rangs).

## R2. Chemins hors `_Persister`

- `scrape_service.save_one` (`POST /participations`, saisie manuelle) et `admin_actions.set_teammates` créent ou résolvent un athlète sans passer par `_Persister`. **Decision**: refus explicite (`DomainError`, message français) si l'identité est opposée. Un résultat manuel anonyme n'aurait ni source ni dossard pour être rattaché.
- `course_merge` ne réimporte rien (`AbsorbedCourse` évite les réimports) : rien à faire.

## R3. L'empreinte

- **Decision**: SHA-256 hexadécimal de la clé normalisée : nom et prénom concaténés, passés en minuscules, sans accents (`core/text.deaccent`), découpés sur tout ce qui n'est pas lettre ou chiffre, mots **triés** puis joints par une espace.
- **Rationale**: couvre « Jean-Pierre DUPONT » / « Jean Pierre Dupont » / « DUPONT Jean-Pierre » (inversion nom/prénom fréquente chez les chronométreurs). L'import n'a jamais de date de naissance (`birth_date IS NULL` codé en dur dans `get_by_identities_batch`), elle n'y entre donc pas.
- **Limite assumée**: une empreinte non salée d'un nom se retrouve par dictionnaire ; c'est une pseudonymisation, pas une anonymisation. Un sel secret ajouterait une variable d'environnement dont la perte rendrait toutes les oppositions inopérantes ; écarté. La politique parle d'« empreinte », pas d'anonymat.
- **Alternatives considered**: HMAC avec secret (risque opérationnel ci-dessus) ; nom en clair (contraire à la minimisation).

## R4. Rangs et compteurs

- Les rangs sont des valeurs sources stockées (`participations.rank_*`) : anonymiser une ligne ne décale rien.
- `Course.participation_count` inchangé ; `Course.tcn_count` baisse si la personne était au TCN, son club étant effacé : `course_repository.adjust_counts`, comme `delete_participation`.

## R5. Références vers la fiche

- `users.athlete_id` : nullable, mis à `NULL`.
- `volunteer_actions.athlete_id`, `season_validations.athlete_id` : `NOT NULL`, lignes supprimées (elles portent sur la personne).
- `participation_teammates` : liaison retirée pour la personne.

## R6. Canal et suivi

- `user_feedback.type` : `FEEDBACK_TYPES = ("bug", "feedback")`, `Literal` côté schéma, aucune contrainte en base. Ajout de `"retrait"`, sans migration.
- Pouvoir : nouveau `oppositions:manage` dans `core/permissions.py` (`P`, `ALL`), à ajouter à `CODES_ATTENDUS` (`tests/test_core/test_permissions.py`) ; il garde des routes, donc pas de `GARDE_A_VENIR`.
- Écran : `/admin/oppositions`, entrée de `nav.config.ts` sous ce pouvoir.
