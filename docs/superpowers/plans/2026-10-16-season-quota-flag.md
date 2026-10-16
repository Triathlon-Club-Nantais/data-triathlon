# Season quota flag in the club season list (#1542)

## Brainstorming (answered by the agent, voie Superpowers)

- **Où vit la règle ?** `app/core/season.py` : `SEASON_QUOTA_EVENTS = 3` et
  `season_quota_met(validated_count, has_volunteer_action)`. Pure, sans DB,
  appelée par `admin_actions.season_quota` et par la route de liste.
- **Compteur fédéral indépendant de `federal_only`** : un quatrième agrégat
  `federal_validated_count` dans la requête groupée existante
  `athlete_repository.list_with_season_participation_count` (même jointure,
  zéro requête de plus). Il compte `validated_clause` + `finisher` +
  `federal_clause`, quel que soit le filtre de la requête.
- **Bénévolat** : `volunteer_action_repository.athlete_ids_with_validated_action(athlete_ids, season)`,
  une requête groupée, sur le patron de `season_validation_repository.map_by_athlete`.
- **`season_quota`** gagne un champ additif `quota_met` (Principe IV) : c'est
  ainsi qu'il partage la constante.
- **Front** : option radio « Quota atteint, à valider » (`quota_met && !season_validated`)
  dans le filtre existant, visible sur saison unique seulement, plus une
  pastille neutre « Quota atteint » sur les lignes concernées non validées.
- **Requêtes** : la route reste à 3 requêtes (liste, validations, bénévolat),
  quel que soit le nombre d'athlètes.

## Tasks (TDD)

1. Repo : test `federal_validated_count` (trail, DNS, en attente exclus), puis agrégat.
2. Repo : test `athlete_ids_with_validated_action` (en attente et autre saison exclus), puis fonction.
3. Core + service : test `season_quota` rend `quota_met`, puis constante et règle.
4. API : tests `quota_met` (atteint, sans bénévolat, bénévolat en attente, multi-saison `null`, nombre de requêtes constant), puis route + schéma.
5. Front : vitest option de filtre et pastille, puis type + composant.
6. Docs : `backend/app/api/AGENTS.md` si nécessaire ; lint, tests, build.
