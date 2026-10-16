# Documentation data-triathlon

Application web qui centralise les résultats de compétition des membres du
Triathlon Club Nantais : on colle une URL de chronométrage, le backend scrape,
stocke, et importe tous les participants de l'épreuve.

## Sommaire

- [Workflow IA](WORKFLOW-IA.md) — Speckit et Superpowers : deux voies complètes,
  laquelle lancer, et pourquoi jamais les deux sur la même feature.
- [CI/CD](ci-cd.md) — pipelines GitHub Actions, déploiements Render et Vercel.
- [Analytics PostHog](analytics-posthog.md) — SDK frontend, cycle de vie de la
  session, catalogue des événements suivis.
- [Modèle de données](modele-donnees.md) — schéma normalisé (athlète, course,
  participation) et migrations Alembic.
- [Infrastructure Azure](infra-azure.md) — base de production PostgreSQL,
  pare-feu, contrainte budget zéro.
- [Gestion de projet](gestion-de-projet.md) — Definition of Ready, epics,
  priorité, workflow git des epics.
- API (`api/`) — une page par epic : sources et fusion d'épreuves, données
  d'administration, retours utilisateurs et statistiques.
- Authentification (`auth/`) — liste d'autorisation et groupes d'appartenance.
- [Dev multi-worktree](dev-multi-worktree.md) — plusieurs worktrees en
  parallèle : découverte de port, `.worktreeinclude`, codes de sortie.
- [RTK](rtk.md) — compresser la sortie des commandes pour les sessions d'agent :
  ce que ça rapporte vraiment, et les cas où c'est interdit.
- Frontend (`frontend/`) : une page par sujet, renvoyée depuis
  `frontend/AGENTS.md` : [accès et routes](frontend/acces-et-routes.md),
  [écrans de panne](frontend/ecrans-erreur.md),
  [back-office](frontend/back-office.md),
  [navigation](frontend/navigation.md),
  [athlète retenu](frontend/athlete-retenu.md),
  [données et cache](frontend/donnees-serveur.md),
  [import](frontend/import.md), [tableaux](frontend/tableaux.md),
  [graphiques](frontend/graphiques.md),
  [en-têtes et CSP](frontend/securite-entetes.md).
- Fournisseurs de chronométrage (`scrapers/`) — un fichier par chronométreur :
  formes d'URL acceptées, pièges mesurés et vérités d'API.

Le code source et les instructions d'installation sont sur
[le dépôt GitHub](https://github.com/Triathlon-Club-Nantais/data-triathlon).

Les specs, plans et notes de test (`docs/superpowers/`, `docs/test/`) sont des
documents de travail : ils se lisent dans le dépôt, pas sur ce site.
