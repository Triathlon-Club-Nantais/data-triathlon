# Quickstart: Page de résultats détaillée d'une participation

Guide de validation bout en bout, une fois l'implémentation faite (issue
#272). Ne remplace pas `tasks.md` — décrit comment vérifier que la feature
marche, pas comment l'écrire.

## Prérequis

- Backend et frontend démarrés en local (`docs/dev-multi-worktree.md` si
  plusieurs worktrees) :
  ```bash
  cd backend && uv run python scripts/dev_server.py
  cd frontend && npm run dev
  ```
- Une base de dev avec au moins une course scrapée par un fournisseur
  **éligible** (ex. `raceresult`, `oktime`, `klikego` — cf. research.md §1) et
  une par un fournisseur **non éligible** (`t2area`, `breizhchrono`, ou une
  entrée `manuel`), toutes deux avec des finishers ayant des splits. Le seed
  de démo (`uv run python scripts/reset_db.py`) peut ne pas couvrir les deux
  cas — au besoin, `uv run python -m app.cli rescrape-db --url <url>` sur une
  course réelle de chacun des deux types.

## Scénario 1 — Course éligible (US1, US2, US3)

1. Ouvrir `/courses/{id}` pour une course d'un fournisseur éligible.
2. Cliquer sur une ligne de finisher.
3. **Attendu** : navigation vers `/courses/{id}/participations/{participationId}`
   (FR-001), page affichant :
   - le bloc ligne de résultat (rang, identité, temps total, 5 splits —
     FR-006) ;
   - le tableau de comparaison avec 1er/10e/25e/50e/100e, une ligne omise si
     l'effectif ne l'atteint pas (FR-008, FR-014) ;
   - le graphique d'évolution du classement, infobulle au survol d'un point
     ou d'une barre (FR-009, FR-010) ;
   - le tableau de simulation de gains par amélioration (FR-011).
4. Vérifier un split manquant (si la course en a un) : la cellule affiche un
   tiret, jamais `0:00:00` ni vide (FR-007).
5. Depuis la page athlète (`/athletes/{athleteId}`), cliquer sur une ligne
   d'épreuve correspondant à la même course : même page atteinte (FR-002).

## Scénario 2 — Course non éligible (FR-005)

1. Ouvrir `/courses/{id}` pour une course dont le fournisseur est `manuel`,
   `t2area` ou `breizhchrono`.
2. Cliquer sur une ligne de finisher.
3. **Attendu** : la page affiche l'état "statistiques indisponibles" (message
   explicatif + lien de retour), aucun tableau ni graphique.

## Scénario 3 — Relais (FR-012)

1. Ouvrir une course comportant une participation `is_relay = true`.
2. Cliquer sur cette ligne.
3. **Attendu** : état "statistiques indisponibles", même si le fournisseur de
   la course est par ailleurs éligible.

## Validation automatisée

```bash
cd backend
uv run pytest -m "not integration" tests/test_services/test_participation_stats_service.py -v
uv run pytest -m "not integration" tests/test_api/test_participations_api.py -v
uv run pytest -m "not integration"   # suite complète, doit rester verte

cd ../frontend
npm test
npm run build   # TS strict + RSC, doit compiler sans erreur
```

## Vérification manuelle du contrat API

```bash
curl -s http://localhost:<port>/api/v1/participations/<id_eligible> | jq '.stats.comparison'
curl -s http://localhost:<port>/api/v1/participations/<id_non_eligible> | jq '.stats'
# → null pour la seconde commande
```

Référence complète du contrat : `contracts/get-participation-stats.md`.
Référence des value objects calculés : `data-model.md`.
