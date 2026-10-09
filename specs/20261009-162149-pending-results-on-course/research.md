# Research: résultats en attente sur la page de l'épreuve

Aucun `NEEDS CLARIFICATION` dans le contexte technique. Décisions de conception :

## D1. Une liste à part, pas une ligne de plus dans `participations`

- **Decision**: `GET /courses/{id}` rend les lignes en attente dans un champ additif
  `pending_participations`, hors de `participations` et de `total`.
- **Rationale**: `total` donne le nombre de pages et vaut « résultats validés de la
  sélection » ; y glisser des lignes en attente changerait son sens (Principe IV) et
  ferait entrer une ligne en attente dans un compte (FR-006). Le front place la liste
  à la fin du classement (dernière page), ce que la clarification demande.
- **Alternatives considered**: (a) les intégrer à la requête paginée, ordonnées après
  les validées : change `total`, rejeté ; (b) une route `/courses/{id}/pending` :
  un second appel pour quelques lignes, rejeté (VI).

## D2. Mêmes filtres que le classement, triées par nom, non paginées

- **Decision**: `list_pending_for_course` partage la construction de requête de
  `list_page_for_course` (`q`, `club_only`, `club`, `category`) et trie par nom,
  prénom, id ; pas de pagination.
- **Rationale**: une recherche doit trouver ou masquer la ligne en attente comme une
  ligne validée (FR-005). Le rang déclaré n'est pas affiché (FR-003), il ne doit donc
  pas non plus ordonner. Volume : 17 lignes en production.
- **Alternatives considered**: `_ordre_affichage` (trierait par rang déclaré, invisible
  à l'écran) ; pagination propre (YAGNI).

## D3. `awaiting_validation_clause` dans `core/validation.py`

- **Decision**: une clause `pending is True AND rejected is False`, à côté de
  `validated_clause`, utilisée par les deux nouvelles lectures.
- **Rationale**: le point unique de la règle de validation reste `core/validation.py`
  (patron `club.py`/`discipline.py`). Les filtres inline existants (`list_pending`,
  `count_pending`, `has_pending_for_course`…) restent tels quels (VI : pas de refacto
  dans une feature).

## D4. Listes d'épreuves : `events_page` seulement

- **Decision**: `events_page` (route `/courses/events`, consommée par `/resultats`,
  le tableau de bord et `/ajouter`) liste aussi les épreuves qui n'ont que des
  résultats en attente et rend `pending_count`. `events_with_counts` (carte,
  statistiques) ne change pas.
  - Chemin rapide (#623) : condition `participation_count > 0 OR EXISTS(en attente)`
    et `pending_count` en sous-requête corrélée.
  - Chemin groupé (`name`, `scope=club`) : la jointure garde validées **et** en
    attente non refusées ; `total`/`tcn_count` deviennent des `SUM(CASE validated)`,
    `pending_count` un `SUM(CASE awaiting)`. `total_participations` suit le même
    `SUM(CASE validated)` ; `total_events` compte les épreuves listées.
- **Rationale**: c'est là que l'épreuve « paraît vide » ou absente. La carte et les
  statistiques sont des agrégats : elles n'en ont pas besoin.
- **Alternatives considered**: colonne dénormalisée `Course.pending_count` : sept
  chemins d'écriture à tenir (saisie, validation, refus, dé-refus, suppression,
  réassignation, fusion) pour 17 lignes, rejeté.

## D5. Front : fin de dernière page, `PendingBadge`, sans rang ni écart

- **Decision**: `RaceFinishers` reçoit `pending` et l'ajoute après les lignes de la
  page quand `page === nbPages` ; la ligne porte `PendingBadge`, un tiret dans la
  colonne rang, ni rang de catégorie ni marqueur d'écart, et ne participe pas au tri
  client. Les listes affichent « N résultat(s) en attente » à la place du compte
  quand `total === 0 && pending_count > 0`.
- **Rationale**: réutilise le marqueur déjà présent sur la fiche d'athlète (contrastes
  déjà vérifiés, #270) ; la ligne garde le lien vers son détail, que
  `GET /participations/{id}` sert déjà pour une ligne en attente (FR-019, #938).
