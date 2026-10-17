# Météo du jour de course (#1370)

## Brainstorming (tranché par l'agent, voie Superpowers)

- Source : API archive d'Open-Meteo (`archive-api.open-meteo.com/v1/archive`),
  sans clé. Variables journalières `temperature_2m_mean` (°C),
  `wind_speed_10m_mean` (km/h), `precipitation_sum` (mm), fuseau
  `Europe/Paris`. Le cumul de pluie, pas une moyenne : c'est l'unité naturelle
  d'une journée. Sondé le 15/10/2026 sur Nantes.
- Quatre colonnes nullables sur `Course` : `weather_temperature_c`,
  `weather_wind_kmh`, `weather_precipitation_mm`, `weather_fetched_at`.
  Plates, pour que `CourseBrief` les lise telles quelles (`from_attributes`).
- Cible : épreuves géocodées, datées d'au moins 5 jours (l'archive se consolide
  quelques jours après la date), sans `weather_fetched_at`. Idempotent : une
  épreuve servie n'est jamais redemandée.
- Un échec (HTTP, réponse sans température) ne persiste rien : il est retenté
  au prochain lancement. Pas de délai de reprise à la `geocode-courses`, un
  appel Open-Meteo coûte quelques dizaines de millisecondes.
- Un appel par triplet (latitude, longitude, date), propagé aux heats qui le
  partagent, sur le patron de `run_geocode_courses`.
- CLI `weather-courses` : `--limit`, `--dry-run`, `--json`, `--no-progress`,
  codes de sortie de `emit_outcome`. Pas de `--course` (YAGNI).
- API : trois champs additifs sur `CourseBrief` (Principe IV), aucun appel
  réseau dans une route.
- Front : une pastille « Météo » dans l'en-tête de la page épreuve, masquée
  sans température, qui crédite Open-Meteo (lien, licence CC BY 4.0).

## Tâches (TDD)

1. Modèle + migration Alembic (une tête), test de migration.
2. Repository `list_missing_weather`, `save_weather`.
3. Service `weather_service` : `fetch_daily_weather` (httpx bouchonné),
   `run_weather_courses` ; un test `integration` sur la vraie API.
4. CLI `weather-courses` + rapport ; doc `backend/app/cli/AGENTS.md`.
5. `CourseBrief` : trois champs, test API.
6. Front : type, composant `CourseWeather`, test vitest, branchement page.
