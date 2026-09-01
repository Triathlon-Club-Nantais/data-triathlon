# Quickstart: Workflow de validation admin des actions de bénévolat (#779)

## Prérequis

```bash
cd backend && uv sync && uv run alembic upgrade head
```

Aucune migration nouvelle — `status` existe déjà (#778). Backend démarré
(`uv run python scripts/dev_server.py`).

## Scénario 1 — File d'attente (US1)

```bash
curl -s http://localhost:<port>/api/v1/admin/volunteer-actions/pending \
  -H "Cookie: <cookie d'un compte athletes:volunteer_validate>"
```

**Attendu** : uniquement les déclarations `status="en_attente"`.

## Scénario 2 — Accepter (US2)

```bash
curl -s -X POST http://localhost:<port>/api/v1/admin/volunteer-actions/1/accept \
  -H "Cookie: <cookie>"
```

**Attendu** : `status="validee"` en réponse ; `GET .../season-quota`
(`admin_data.py`) rend `has_volunteer_action: true` pour l'athlète/saison
concernés.

## Scénario 3 — Refuser (US3)

```bash
curl -s -X POST http://localhost:<port>/api/v1/admin/volunteer-actions/1/reject \
  -H "Cookie: <cookie>"
```

**Attendu** : `status="refusee"` ; `has_volunteer_action` redevient `false`
si c'était la seule ligne validée de l'athlète/saison.

## Scénario 4 — Accès refusé sans le pouvoir dédié

```bash
curl -i http://localhost:<port>/api/v1/admin/volunteer-actions/pending \
  -H "Cookie: <cookie d'un compte sans athletes:volunteer_validate>"
```

**Attendu** : `403`.

## Vérifications automatisées

```bash
cd backend && uv run pytest -m "not integration"
cd backend && uv run ruff check .
```
