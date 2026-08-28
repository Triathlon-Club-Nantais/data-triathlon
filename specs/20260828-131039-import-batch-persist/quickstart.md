# Quickstart: valider la persistance par lot

## Prérequis

- `backend/.env` avec `DATABASE_URL` (voir `docs/infra-azure.md` pour la
  variante production Supabase, utilisée seulement pour la mesure réelle de
  SC-001 — le reste de la validation tourne en local/SQLite).
- `uv sync` déjà fait dans `backend/`.

## 1. Non-régression comportementale (unitaire, sans réseau)

```bash
cd backend
uv run pytest -m "not integration" tests/test_services/test_import_service.py -v
```

Aucune assertion de résultat métier (compteurs `imported`/`updated`/`skipped`/
`reconciled`, rapport qualité, réconciliation d'identité) ne doit changer par
rapport à `main` — seuls des tests **nouveaux** sur le nombre de requêtes et
les cas de tranche sont ajoutés (cf. `research.md`).

## 2. Le nombre de requêtes ne croît plus avec le volume

Nouveau test, même patron que
`tests/test_services/test_course_merge.py::test_the_query_count_does_not_grow_with_the_number_of_results`
(instrumentation `before_cursor_execute` sur l'engine, comparaison entre un
petit scrape et un scrape 50-100× plus gros sur la même course) :

```bash
uv run pytest -m "not integration" tests/test_services/test_import_service.py -k query_count -v
```

Attendu : le nombre de requêtes émises par `_Persister.add`/`finalize()` sur
un scrape de N lignes croît par paliers de taille de tranche (≈500), pas
linéairement avec N.

## 3. Mesure du temps réel en production (SC-001)

Suit le protocole de mesure déjà utilisé pour diagnostiquer #706 : ré-importer
une épreuve de volume comparable à Trégastel 2026 (1147 lignes) sur
l'environnement Render/Supabase, chronométrer la phase de persistance.

```bash
# Depuis backend/, avec DATABASE_URL pointant vers la prod (lecture documentée
# dans reference_prod_db_access — usage exceptionnel, mesure seulement)
uv run python -m app.cli rescrape-db --course-id <id_tregastel_2026> --json
```

Lire le temps entre le début de la phase de sauvegarde et la fin (`finalize`
+ `commit`) dans les logs applicatifs (`app/core/logging.py`). Avant le
correctif : ~89 s. Attendu après : quelques secondes, pas de dégradation
proportionnelle au nombre de lignes.

## 4. Suivi qualitatif des symptômes en cascade (SC-004)

Pas un test automatisé — un suivi manuel après déploiement : sur les
prochains imports de volume comparable, vérifier dans les logs/Sentry que la
fréquence des faux messages « Erreur » après commit réussi et des connexions
SSE sans phase `done`/`error` diminue. Si elle persiste, ouvrir un suivi sur
les issues dédiées #704/#705 plutôt que de réouvrir cette feature.
