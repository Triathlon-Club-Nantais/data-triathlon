# Quickstart : vérifier la feature

## Tests automatisés

```bash
cd backend
uv run pytest tests/test_repositories/test_pending_on_course.py tests/test_api/test_course_pending_rows.py
uv run pytest -m "not integration"
uv run ruff check .

cd ../frontend
npm test
npm run lint
npm run build
```

Attendu : tout vert. `test_course_pending_rows.py` prouve, sur une épreuve à un
résultat validé, un en attente et un refusé, que chaque compte de FR-006 vaut ce qu'il
vaudrait sans la ligne en attente.

## Parcours manuel (SQLite de dev du worktree)

1. `uv run python scripts/reset_db.py`, puis `uv run python scripts/dev_server.py`.
2. Créer un résultat par `POST /api/v1/participations` (formulaire « Ajouter » →
   saisie manuelle) sur une épreuve nouvelle.
3. `/resultats` : l'épreuve figure avec « 1 résultat en attente ».
4. Ouvrir l'épreuve : la ligne figure dans le classement avec « En attente de
   validation », sans rang ; « Participants » vaut 0.
5. Refuser le résultat depuis `/benevoles` : il disparaît de la page et de la liste.
