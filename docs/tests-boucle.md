# Boucle de tests

Quoi lancer, et quand, pour ne pas payer une suite complète à chaque édition.

## Pendant l'itération

Tests ciblés uniquement, depuis `backend/` ou `frontend/`.

```bash
# Backend
uv run pytest tests/<chemin> -n 0     # un fichier ou un dossier
uv run pytest tests/<chemin> -k <expr> -n 0
uv run pytest --lf -n 0               # rejoue les derniers échecs
uv run pytest --sw -n 0               # s'arrête au premier échec, reprend là

# Frontend
npx vitest run <fichier>
npx vitest related --run <fichiers source>
npx vitest --changed origin/main
```

## Une suite complète par branche

Avant `finishing-a-development-branch`, lancer la suite complète de
l'application touchée seulement (backend ou frontend, pas les deux par défaut).

Les deux suites sont lancées ensemble quand la branche change :

- le contrat API consommé par le front ;
- les dépendances ;
- la configuration de test ;
- les workflows CI ;
- `backend/alembic/` ou `backend/app/models/` : la suite backend se lance alors
  avec `--migrations` (voir ci-dessous).

Une suite complète n'est jamais relancée tant qu'aucun fichier n'a été modifié
depuis le dernier vert.

## Migrations

Les tests marqués `migrations` (`backend/tests/test_migrations.py`) sont
désélectionnés par défaut, quel que soit `-m`. Seul le test fumée
`test_upgrade_head_sur_base_vierge` (`test_migrations_smoke.py`) reste dans la
boucle. `--migrations` les réintègre :

```bash
uv run pytest -m "not integration" --migrations
uv run pytest tests/test_migrations.py --migrations -n 0
```

La CI passe toujours `--migrations`.

## Précédence

Cette règle du projet prime sur les consignes de suite complète des skills pour les étapes intermédiaires. `verification-before-completion` est satisfait par la commande ciblée pour une affirmation sur une tâche, et par la suite complète pour une affirmation sur la branche.

## La porte

La CI et la merge queue exécutent tout : suite complète backend et frontend,
`ci-ok` étant le seul check requis. La boucle locale allège l'itération, jamais
la porte.
