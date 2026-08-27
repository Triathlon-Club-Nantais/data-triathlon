# Quickstart : valider la parallélisation par chronométreur

Depuis `backend/`. Aucun réseau réel requis pour les étapes 1 à 3.

## 1. Suite unitaire (sans réseau)

```bash
uv run pytest -m "not integration" tests/test_services/test_batch.py -v
```

Doit couvrir, en plus des cas déjà existants (1 hôte) :

- deux chronométreurs distincts traités en même temps (preuve par
  synchronisation, pas par minutage) ;
- deux épreuves du **même** chronométreur restent séquentielles, avec le même
  délai de politesse qu'aujourd'hui ;
- deux domaines d'un même chronométreur multi-domaines (cf. Clarifications de
  `spec.md`) ne partent jamais en parallèle l'un de l'autre ;
- le bilan (`BatchTotals`) d'un lot multi-hôtes est équivalent, à l'ordre
  près, à celui d'une exécution avec `--max-concurrent-hosts 1` sur le même
  lot ;
- un Ctrl-C pendant un lot multi-hôtes produit un bilan partiel cohérent et
  se termine en 130 (au niveau CLI, pas seulement du service).

## 2. Suite complète du module CLI

```bash
uv run pytest -m "not integration"
uv run ruff check .
```

Aucune régression attendue ailleurs : la feature ne touche que
`app/services/batch.py`, `app/services/progress.py`, `app/cli/progress.py`,
et les deux commandes `import-sheet`/`rescrape-db`.

## 3. Non-régression volume (mono-hôte)

```bash
uv run python -m app.cli rescrape-db --dry-run --provider klikego --limit 5
```

Un lot mono-chronométreur doit s'exécuter en un temps comparable à avant la
feature (SC-002) — pas de parallélisme possible, donc pas de gain ni de perte
attendue.

## 4. Validation réseau réel (optionnelle, manuelle — hors CI)

Sur un lot couvrant plusieurs dizaines de chronométreurs distincts (le
scénario mesuré par l'issue #690), comparer le temps mur avec
`--max-concurrent-hosts 1` (comportement d'avant la feature) contre la valeur
par défaut :

```bash
time uv run python -m app.cli rescrape-db --dry-run --limit 150 --max-concurrent-hosts 1
time uv run python -m app.cli rescrape-db --dry-run --limit 150
```

Le second doit être significativement plus rapide (SC-001 : au moins 50 % de
réduction), et les deux bilans (`--json`) doivent contenir les mêmes
compteurs, à l'ordre près (SC-003).
