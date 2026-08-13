# Quickstart : valider le re-scrape à la demande

## Prérequis

- Backend dev lancé (`uv run python scripts/dev_server.py`), migrations à
  jour (`uv run alembic upgrade head`) — aucune migration n'est ajoutée par
  cette feature, mais la base doit déjà porter au moins une course avec une
  source active.
- Une session admin valide (cookie de session), portant le pouvoir
  `courses:sources` — cf. `backend/app/services/auth/AGENTS.md` pour créer un
  compte de test.
- Une course de dev dont la source active pointe vers un provider réel
  (`uv run python scripts/reset_db.py` avec le jeu de données de démo en
  fournit au moins une).

## Scénario 1 — succès (User Story 1)

1. Récupérer l'`id` d'une course en base : `GET /api/v1/courses?limit=1`.
2. Déclencher le re-scrape, cookie de session inclus :
   ```bash
   curl -N -X POST http://localhost:<port>/api/v1/admin/courses/<id>/rescrape \
     -H "Cookie: <cookie de session admin>"
   ```
3. **Attendu** : un flux `text/event-stream` — au moins un événement
   `scraping`, puis un ou plusieurs `saving` avec `progress` croissant, puis
   un `done` portant `imported`/`updated`/`total` cohérents avec le nombre de
   participants de la course.
4. Recharger `GET /api/v1/courses/{id}` : les temps/classements reflètent la
   dernière réponse du chronométreur (SC-003).

## Scénario 2 — refus, épreuve divergente ou zéro résultat (Edge case)

1. Choisir une course dont la source active répond aujourd'hui par une page
   vide ou une épreuve différente (ou simuler via un mock en test).
2. Déclencher le re-scrape comme ci-dessus.
3. **Attendu** : un événement `{"phase": "error", "message": "..."}` (une des
   deux formes du contrat), et `GET /api/v1/courses/{id}` inchangé par
   rapport à avant le geste (SC-004).

## Scénario 3 — concurrence (User Story 3)

1. Démarrer un re-scrape sur une course `A` (connexion SSE tenue ouverte).
2. Avant sa fin, démarrer un second re-scrape sur la **même** course `A`.
3. **Attendu** : le second appel répond `409` immédiatement, sans ouvrir de
   flux.
4. Démarrer, en parallèle du premier (toujours en cours), un re-scrape sur une
   course `B` différente.
5. **Attendu** : le re-scrape de `B` se déroule normalement (SC-005).

## Vérification automatisée

```bash
cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_course_rescrape.py tests/test_services/test_admin_actions.py -v
cd frontend && npm test -- CourseSourcesPanel useRescrapeStream
```

Réfèrence contractuelle complète des événements SSE :
[contracts/admin-rescrape-sse.md](./contracts/admin-rescrape-sse.md).
