# Quickstart : validation de bout en bout

**Préalable bloquant** : cette feature ne peut pas être vérifiée avant la
fusion de #270 dans `main` (`Participation.is_pending_validation` n'existe pas
avant) — cf. spec § Dépendances. Ce guide suppose #270 déjà fusionnée et
`BENEVOLE_SHARED_PASSWORD` configuré dans `backend/.env`.

## Préparer un résultat en attente

```bash
cd backend
uv run alembic upgrade head
# Créer une participation avec is_pending_validation=true, par exemple via
# le formulaire public de saisie manuelle livré par #270 (POST /participations),
# ou directement en base de dev.
```

## Scénario 1 — validation nominale (US1)

1. `POST /api/v1/benevoles/session` avec le mot de passe partagé → 204,
   cookie posé.
2. `GET /api/v1/benevoles/queue` → le résultat créé apparaît, avec épreuve,
   athlète, temps, splits, `evidence_url` si renseigné.
3. `POST /api/v1/benevoles/participations/{id}/validate` → 200.
4. Vérifier que la fiche de l'athlète (`GET /api/v1/athletes/{id}`) affiche le
   résultat, et qu'un agrégat public qui l'excluait auparavant (ex.
   `GET /api/v1/stats`) le compte désormais.

## Scénario 2 — renommage d'épreuve (US2)

1. Créer deux épreuves de libellés voisins (une avec un résultat en attente).
2. `PATCH /api/v1/benevoles/courses/{course_id}` avec le nom aligné sur
   l'épreuve existante → si les quatre champs d'identité coïncident, 409 —
   sinon 200.

## Scénario 3 — réattribution (US3)

1. `POST /api/v1/benevoles/participations/{id}/reassign` avec l'`athlete_id`
   d'un autre coureur → 200.
2. Vérifier que le résultat, une fois validé, apparaît sur la fiche du
   nouveau coureur et non plus sur l'ancienne.

## Scénario 4 — accès protégé (US4)

1. `GET /api/v1/benevoles/queue` sans cookie de session → 401.
2. `POST /api/v1/benevoles/session` avec un mot de passe erroné → 401.
3. `POST /api/v1/benevoles/session` avec le bon mot de passe puis
   `GET /api/v1/benevoles/queue` → 200.

## Vérification automatisée

```bash
cd backend
uv run pytest -m "not integration"   # suite unitaire, doit rester verte
uv run ruff check .
cd ../frontend
npm test
npm run lint
```
