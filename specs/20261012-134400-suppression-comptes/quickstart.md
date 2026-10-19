# Quickstart: Suppression des comptes

Validation de bout en bout. Commandes backend depuis `backend/`, **toujours** sur une SQLite jetable : `backend/.env` peut viser la production.

```bash
export DATABASE_URL=sqlite:////tmp/<scratch>/accounts.db
uv run python -c "from app.core.database import engine; print(engine.url)"   # doit afficher sqlite
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head && uv run alembic check
```

## US3, activité

- Tests : `uv run pytest tests/test_auth/test_session.py -q` (pose à l'ouverture, une écriture par jour, report le lendemain).
- Migration : après `upgrade head`, `SELECT count(*) FROM users WHERE last_seen_at IS NULL` vaut 0 et `last_seen_at = created_at` pour les comptes antérieurs.

## US1, suppression volontaire

- Tests : `uv run pytest tests/test_auth/test_account_deletion.py tests/test_auth/test_api_delete_me.py -q` (contrat `contracts/auth-delete-me.md`).
- Interface : `npm run dev`, se connecter, menu du compte → « Supprimer mon compte » → la boîte explique ce qui est effacé et ce qui reste → « Supprimer définitivement » → retour sur `/`, anonyme.

## US2, expiration

- Tests : `uv run pytest tests/test_services/test_retention_service.py tests/test_cli/test_purge_retention.py -q`.
- CLI : `uv run python -m app.cli purge-retention --dry-run --json` rend `accounts_deleted` et `accounts_skipped` (contrat `contracts/cli-purge-retention.md`).

## Tout

```bash
uv run pytest -m "not integration" -q && uv run ruff check .
cd ../frontend && npm test && npm run lint && npm run build
```
