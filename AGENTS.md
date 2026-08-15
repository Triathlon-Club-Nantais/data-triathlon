# AGENTS.md — data-triathlon

App web centralisant les résultats de compétition des membres d'un club de
triathlon (TCN). On colle une URL de chronométrage → le backend scrape, stocke,
et importe en arrière-plan tous les participants de l'épreuve.

Détails install/déploiement : voir `README.md`. Ce fichier cible les agents IA.

## Où lire quoi

Ce fichier ne porte que ce qui vaut pour **toute** session, et reste sous
200 lignes — au-delà, l'adhérence baisse et le contexte se paie à chaque
démarrage. Le reste vit dans des `AGENTS.md` **de dossier**, chacun doublé d'un
`CLAUDE.md` d'une ligne (`@AGENTS.md`) : Claude Code ne lit que `CLAUDE.md`, les
autres agents ne lisent qu'`AGENTS.md`, et les fichiers d'un sous-dossier ne
sont chargés **qu'au moment où un fichier de ce dossier est lu**. Un `docs/` se
lit sur renvoi, sans coût de contexte.

Un ajout de contexte va donc dans le dossier qu'il concerne, jamais ici — ici
n'accueille que ce qu'on voudrait relire à chaque session.

| Sujet | Où |
| --- | --- |
| Workflow IA : les trois voies, garde-fous, artefacts | `docs/WORKFLOW-IA.md` |
| Review UI/UX : grille, seuils chiffrés, faux positifs connus | `.claude/agents/ui-ux-review.md` |
| Architecture backend : inventaire des modules, cache TTL | `backend/AGENTS.md` |
| Conventions scrapers + les 14 fournisseurs supportés | `backend/app/scrapers/AGENTS.md` |
| Un fournisseur en particulier (pièges mesurés, formes d'URL) | `docs/scrapers/<fournisseur>.md` |
| CLI de batch : les 6 commandes, stdout parsable, codes de sortie | `backend/app/cli/AGENTS.md` |
| API de lecture : `scope`, `federal_only`, pagination du classement | `backend/app/api/AGENTS.md` |
| Une epic API en particulier (sources/fusion, admin, feedback, stats) | `docs/api/<sujet>.md` |
| Modèle normalisé et splits | `backend/app/models/AGENTS.md` |
| Observabilité SQL | `backend/app/core/AGENTS.md` |
| Authentification SSO (#114) | `backend/app/services/auth/AGENTS.md` |
| Liste d'autorisation (#170) ou groupes d'appartenance (#197) en détail | `docs/auth/<sujet>.md` |
| Architecture frontend | `frontend/AGENTS.md` |
| Dev multi-worktree : ports, `.worktreeinclude` | `docs/dev-multi-worktree.md` |
| CI/CD, déploiements, variables par environnement | `docs/ci-cd.md` |
| Infrastructure Azure (base de production PostgreSQL) | `docs/infra-azure.md` |

## Workflow IA

Deux outils sont préconfigurés, **Spec Kit** et **Superpowers**. Règle d'or :
**deux voies complètes et parallèles, jamais croisées** — l'exécution suit
l'outil qui a produit le plan. **Le choix de la voie appartient à
l'utilisateur** : l'agent ne le tranche pas seul et ne bascule pas en cours de
route. Détail complet : `docs/WORKFLOW-IA.md`.

- **Voie « sans plan »** — bugfix, typo, ajustement de 1-2 fichiers :
  `systematic-debugging` (bug) ou `test-driven-development` (comportement), puis
  `verification-before-completion`. Ni `specs/`, ni plan.
- **Voie Spec Kit** — `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-analyze` **avant tout code** → `/speckit-implement`. Artefacts dans
  `specs/<id>-feature/`.
- **Voie Superpowers** — `brainstorming` → `writing-plans` → exécution.
  L'exécuteur **n'a pas de défaut** : l'utilisateur nomme `executing-plans` ou
  `subagent-driven-development`. L'agent ne déclenche de lui-même ni le fan-out
  ni les commits par tâche.
- **Fin de branche, commune aux trois voies** : `requesting-code-review` →
  `verification-before-completion` → `finishing-a-development-branch`. Si la
  branche touche `frontend/`, le sous-agent `ui-ux-review` s'insère après la
  revue de code : il juge du **rendu**, en lecture seule, sur déclenchement de
  l'utilisateur, et ne rouvre jamais l'identité visuelle.
- **Le TDD est non-négociable** (Principe III de la constitution) ; seul son
  garant change de place : le skill en voie Superpowers, `tasks.md` en voie Spec
  Kit. Un `tasks.md` sans tâches de test se **régénère**, il ne s'exécute pas.
- **`/speckit-implement`** : ne **pas** dérouler son étape 4 « Project Setup
  Verification » (elle touche aux fichiers d'ignore hors périmètre), ignorer ses
  hooks git, respecter son gate `checklists/`.
- **Un sondage n'est ni une spec ni un plan** : il consigne ce qui a été mesuré
  sur le terrain, vit sous
  `docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md`, et il
  **prime** sur le design, la spec et le plan — toute divergence se tranche en
  re-sondant.
- **Le sur-outillage est le seul piège** : pour un correctif d'une ligne, ne
  rien lancer. Compter ~20-40 % de tokens en plus par feature dès qu'on ouvre un
  cycle complet, quelle que soit la voie.

`docs/superpowers/specs/` mêle deux natures : des **designs de features livrées**
(valeur historique) et des **rapports de terrain encore normatifs** — sondages et
audits, cités là où ils s'appliquent.

## Stack

- **Backend** (`backend/`) : Python 3.13, **uv** (`pyproject.toml` + `uv.lock`), FastAPI,
  SQLAlchemy 2.0 (sync), Pydantic v2 + pydantic-settings, **Alembic** (migrations), PostgreSQL
  (Supabase) / SQLite en dev. Scraping httpx + BeautifulSoup/lxml — **aucun
  navigateur** : le fallback Playwright a été supprimé avec sa dépendance (#102),
  et sa sentinelle attrape-tout avec lui — une URL non reconnue ne matche aucun
  provider. Tests pytest, ruff. API versionnée sous `/api/v1`.
- **Frontend** (`frontend/`) : Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui.
- **Déploiement** : backend → Render (`render.yaml`), front → Vercel, DB → Supabase.

## Commandes

```bash
# Backend (depuis backend/ — aucun venv à activer, uv run s'en charge)
uv sync                                            # installe les dépendances (dev incluses)
uv run python scripts/dev_server.py                # API + /docs, port libre publié (voir « Dev multi-worktree »)
uv run alembic upgrade head                        # applique les migrations
uv run alembic revision --autogenerate -m "..."    # nouvelle migration après modif d'un modèle
uv run python scripts/reset_db.py                  # reset base dev SQLite (vide + migre + seed démo)
uv run python scripts/reset_db.py --no-seed --yes  # schéma vierge seul (refuse si DB non-SQLite)
uv run pytest -m "not integration"                 # tests unitaires (sans réseau) — défaut CI
uv run pytest -m integration                       # tests réseau réel (scrapers)
uv run ruff check .                                # lint

# CLI de batch (depuis backend/) — les invocations : backend/app/cli/AGENTS.md
uv run python -m app.cli --help                    # import-sheet, rescrape-db, club-labels, les 3 d'amorçage

# Frontend (depuis frontend/)
npm run dev        # Next.js sur :3000 (ou suivant libre), branché sur le backend du worktree
npm run build      # build prod (strict TS + RSC)
npm test           # vitest run
npm run lint       # ESLint
```

Variable requise : `backend/.env` avec `DATABASE_URL` (voir `.env.example`). Le
schéma est géré par **Alembic** (`uv run alembic upgrade head`). Les dépendances et la
config des outils vivent dans `backend/pyproject.toml` (lock : `backend/uv.lock`).

Plusieurs worktrees tournent en parallèle sans configuration : le backend prend
le premier port libre à partir de 8001 et le publie, le frontend le lit.
`docs/dev-multi-worktree.md` avant toute intervention sur les lanceurs de dev.

## Architecture

Deux applications, une archi en couches côté backend dont le flux ne traverse
qu'une direction : `api → services → repositories → DB`, les repositories étant
la **seule** couche qui touche la Session SQLAlchemy. L'inventaire module par
module et le cache TTL sont dans `backend/AGENTS.md`, le front dans
`frontend/AGENTS.md` — les deux se chargent d'eux-mêmes dès qu'un fichier du
dossier est lu.

## Principes de conception

Guidelines d'écriture de code, valables dans les trois voies du workflow IA.

- **Ne pas préserver la compatibilité ascendante.** Supprimer les chemins
  obsolètes plutôt qu'ajouter des couches de compatibilité, des replis ou des
  migrations. *Une seule exception, et elle est contractuelle : l'API `/api/v1`
  publiée, que le Principe IV de la constitution interdit de modifier
  silencieusement (cf. `page_size=all`). Le code interne, lui, se supprime.*
- **Choisir l'implémentation la plus simple qui satisfait pleinement le besoin
  actuel.** Pas d'abstraction, de configuration ni d'indirection spéculatives.
- **Faire croître le système par couches.** Partir de la plus petite version qui
  marche de bout en bout, et poser chaque nouvelle capacité sur un produit qui
  fonctionne déjà. Ne jamais échanger un produit qui marche contre une
  complexité inachevée.
- **Garder les composants modulaires et les responsabilités séparées.**
- **Préférer les bibliothèques établies et maintenues** quand elles réduisent la
  complexité globale ou améliorent la fiabilité. Ne pas réimplémenter une
  fonctionnalité courante sans raison explicite.
- **S'appuyer d'abord sur les dépendances déjà présentes** avant d'écrire sa
  propre implémentation ou d'ajouter un paquet. Ne pas supposer qu'une
  bibliothèque n'a pas une capacité sans avoir lu sa documentation et ses types.
- **Décider l'architecture pour le long terme.** Ne pas accepter un pis-aller qui
  ne tient que pour l'instant et qu'on prévoit de remplacer plus tard.

## Conventions générales

- **Langue** : suit le Principe I de la constitution v1.1.0
  (`.specify/memory/constitution.md`) — **français** pour ce qui est
  visible utilisateur ou métier (UI, messages d'erreur affichés, docs
  produit, commentaires de règle métier, messages `DomainError`
  sérialisés vers le front) ; **English** pour la couche technique
  invisible (identifiants, tests, docstrings techniques, logs
  Sentry/Datadog, préfixes Conventional Commits, **titres d'issues
  GitHub** — même jeton machine que les titres de PR). Un identifiant nomme
  ce qu'il porte : les noms d'une ou deux lettres sont réservés aux
  liaisons dont la portée tient sous les yeux (compréhension, boucle,
  lambda, `db`). Règle de transition : on ne réécrit pas l'existant, la
  règle s'applique aux nouveaux ajouts — **à une dérogation près**, la
  campagne de renommage de l'issue #88, bornée aux lots énumérés dans le
  Principe I (plan de découpage, pas définition de la fin : la dérogation
  s'éteint quand `backend/app` ne porte plus d'identifiant français hors de
  la clause « Pas d'exception de vocabulaire métier » du Principe I).
- Commits : Conventional Commits (`feat:`, `fix:`…), déjà en place dans l'historique.
- **Lier une PR à son issue avec un mot-clé GitHub anglais** : `Closes #123`,
  `Fixes #123` ou `Resolves #123`. C'est un **jeton machine**, au même titre que
  les préfixes de commit, donc hors de la règle « français » : GitHub ne
  reconnaît aucune forme française, et « Ferme #123 » n'est que du texte — ni
  lien, ni fermeture à la fusion (constaté sur #162 et #163). Le reste de la
  description reste en français.
- **Assignation GitHub** : s'assigner une issue au moment de commencer à y
  travailler ; assigner toute PR une fois créée ; dès qu'elle n'est plus en
  brouillon (« ready for review »), demander une review (#335).
- Schéma DB : migrations **Alembic** (`uv run alembic revision --autogenerate`
  après modif d'un modèle, puis `uv run alembic upgrade head`).
- Tests unitaires **sans réseau** ; le réseau réel est isolé derrière le marker
  `integration` (déclaré dans `backend/pyproject.toml`).

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/20260814-221102-athletes-par-saison/plan.md
<!-- SPECKIT END -->
