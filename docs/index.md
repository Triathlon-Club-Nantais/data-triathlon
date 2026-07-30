# Documentation data-triathlon

Application web qui centralise les résultats de compétition des membres du
Triathlon Club Nantais : on colle une URL de chronométrage, le backend scrape,
stocke, et importe tous les participants de l'épreuve.

## Sommaire

- [Workflow IA](WORKFLOW-IA.md) — Speckit et Superpowers : deux voies complètes,
  laquelle lancer, et pourquoi jamais les deux sur la même feature.
- [CI/CD](ci-cd.md) — pipelines GitHub Actions, déploiements Render et Vercel.
- [Modèle de données](modele-donnees.md) — schéma normalisé (athlète, course,
  participation) et migrations Alembic.

Le code source et les instructions d'installation sont sur
[le dépôt GitHub](https://github.com/Triathlon-Club-Nantais/data-triathlon).

Les specs, plans et notes de test (`docs/superpowers/`, `docs/test/`) sont des
documents de travail : ils se lisent dans le dépôt, pas sur ce site.
