# Quickstart: Compteurs de saison distincts + validation humaine du quota club

Valide les trois user stories de `spec.md` de bout en bout, sur la base de
dev SQLite. Prérequis : `backend/.env` configuré, `uv sync` fait (voir
`AGENTS.md`).

## Préparation

```bash
cd backend
uv run alembic upgrade head          # applique la migration de cette feature
uv run python scripts/dev_server.py  # API + /docs
```

Dans un autre terminal :

```bash
cd frontend
npm run dev
```

## Scénario 1 — Compteurs distincts (User Story 1, FR-001 à FR-004)

1. Identifier en base un athlète du club ayant une participation sur un
   fournisseur sans affiliation club publiée (Audencia La Baule ou Ironman
   70.3 Les Sables d'Olonne dans les fixtures/données de dev), avec d'autres
   participations club-affiliées la même saison.
2. `GET /api/v1/athletes/{id}` — noter le nombre réel de participations de la
   saison sur sa fiche.
3. `GET /api/v1/athletes/season-activity?scope=club&seasons=<saison>` —
   vérifier que `total_count` pour cet athlète égale le nombre noté à
   l'étape 2, et que `club_affiliated_count` est strictement inférieur.
4. Sur `/club/athletes` (front), vérifier que les trois compteurs sont
   visibles et distincts pour cet athlète.

**Attendu** : `total_count` = total réel (SC-001) ; les trois compteurs sont
distinguables sans quitter la page (SC-002).

## Scénario 2 — Déclarer une action de bénévolat (User Story 2, FR-006 à FR-008)

```bash
curl -X POST http://localhost:<port>/api/v1/admin/athletes/<athlete_id>/volunteer-actions \
  -H "Content-Type: application/json" -H "Cookie: <session>" \
  -d '{"season": <saison>}'
```

1. Avec un utilisateur **sans** `P.ATHLETES_VOLUNTEER_MANAGE` : attendu `403`.
2. Avec un titulaire du pouvoir : attendu `201`, réponse portant `athlete_id`,
   `season`, `declared_by_user_id`, `created_at`.
3. Répéter l'appel (même athlète, même saison) : attendu un **second** `201`
   (journal, pas d'indicateur unique — D4).
4. `GET /api/v1/admin/action-log?entity_type=athlete&entity_id=<athlete_id>` —
   vérifier une entrée `athlete.volunteer_action.create` par appel (SC-004).

## Scénario 3 — Valider puis dévalider une saison (User Story 3, FR-009 à FR-014)

1. S'assurer que l'athlète a ≥3 `validated_count` et ≥1 action de bénévolat
   pour la saison (scénario 2).
2. `GET /api/v1/athletes/season-activity?scope=club&seasons=<saison>` —
   vérifier `season_validated: false` (ou absent) avant validation.
3. `POST /api/v1/admin/athletes/<athlete_id>/season-validations` avec un
   titulaire de `P.ATHLETES_SEASON_VALIDATE`, `{"season": <saison>}` —
   attendu `201`.
4. Re-`GET /athletes/season-activity` — `season_validated: true` pour cet
   athlète.
5. Sur `/club/athletes`, trier/filtrer par statut de validation — vérifier
   que seuls les athlètes validés apparaissent avec le filtre actif (SC-005).
6. `DELETE /api/v1/admin/athletes/<athlete_id>/season-validations/<saison>` —
   attendu `204`. Re-`GET season-activity` — `season_validated: false`.
7. `GET /admin/action-log` — deux entrées (`...create` puis `...delete`) pour
   cet athlète et cette saison (SC-004).
8. Sélectionner **deux** saisons à la fois sur `/club/athletes` — vérifier
   que le tri/filtre par validation est désactivé et que `season_validated`
   n'est pas exposé comme trompeur (D9).

## Vérification finale

```bash
cd backend && uv run pytest -m "not integration"
cd frontend && npm test
```
