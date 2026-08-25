# backend — Triathlon Club Results

Backend en **architecture en couches** avec un **modèle de données
normalisé** (Athlete / Course / Participation). Construit avec FastAPI +
SQLAlchemy 2.0, migrations Alembic, configuration typée et tests par couche.

> Design d'origine :
> `../docs/superpowers/specs/2026-06-07-refactoring-backend-architecture-design.md`.

## Architecture

```
app/
  main.py          # usine create_app() : CORS, handlers d'erreurs, montage des routers
  core/            # config (pydantic-settings), logging, database, exceptions, time, club
  models/          # SQLAlchemy : Athlete, Course, Participation, PendingProvider
  schemas/         # DTO Pydantic (entrée/sortie)
  repositories/    # accès données — seule couche qui touche la Session
  services/        # logique métier : mapping, cache TTL, scrape, import, stats, geocode
  api/
    deps.py        # dépendances partagées (version-agnostiques)
    v1/            # routers FastAPI fins de la v1 — montés sous /api/v1
      router.py    # agrège tous les routers v1
  scrapers/        # registre Protocol + un module par provider
alembic/           # migrations (révision initiale = schéma complet)
tests/             # test_repositories / test_services / test_api / test_scrapers
```

Flux d'un import épreuve :
`api/scrape` → `services/import_service` → (cache TTL) → `scrapers/registry`
→ `services/mapping` (ScrapedResult → entités) → `repositories` → DB.

## Prérequis

- [uv](https://docs.astral.sh/uv/) — gère les dépendances et l'interpréteur (Python 3.13)
- `backend/.env` avec au minimum `DATABASE_URL` (voir `.env.example`)

## Installation

```bash
cd backend
uv sync   # crée .venv (Python 3.13) + installe les dépendances depuis uv.lock
```

> `uv sync --frozen --no-dev` écarte le groupe `dev` (pytest, respx, ruff) — c'est ce que font Render et l'image Docker.

## Base de données (Alembic)

Les tables ne sont **plus** créées au démarrage : tout passe par les migrations.

```bash
uv run alembic upgrade head                       # applique les migrations
uv run alembic revision --autogenerate -m "..."   # nouvelle migration après modif d'un modèle
```

### Réinitialiser la base (dev — SQLite uniquement)

`scripts/reset_db.py` vide la base, réapplique les migrations, puis ré-importe
un jeu de données démo réel (toutes disciplines). **Garde-fou** : le script
refuse de s'exécuter si `DATABASE_URL` n'est pas SQLite (jamais sur Supabase).

```bash
uv run python scripts/reset_db.py            # vide + migre + seed démo
uv run python scripts/reset_db.py --no-seed  # schéma vierge seulement (rapide, hors réseau)
uv run python scripts/reset_db.py --yes      # sans confirmation interactive
uv run python scripts/seed_demo.py           # (re)seed seul, sans toucher au schéma
```

## Lancer l'API

```bash
uv run python scripts/dev_server.py  # API + /docs, premier port libre à partir de 8001
```

Le port est choisi au démarrage (8001 s'il est libre, sinon le suivant) et publié
dans `.dev-backend.json` à la racine du worktree : c'est ainsi que `npm run dev`
branche le frontend sur **ce** backend plutôt que sur celui d'un autre worktree.
`DEV_BACKEND_PORT=8005` force un port ; `uvicorn app.main:app --reload --port 8001`
reste utilisable pour un lancement brut, sans publication.

**API versionnée** : tous les endpoints sont sous `/api/v1/*` (une future v2 vivra
dans `app/api/v2/`). `GET /api/v1/health` vérifie l'API **et** la connexion DB.

## Amorcer le premier administrateur

Sur une installation neuve, personne ne porte de rôle et les ressources qui les
distribuent en exigent un. La sortie de boucle est en ligne de commande, sur le
serveur :

```bash
uv run python -m app.cli grant-role --email <adresse> --role admin
```

`--role` prend le **slug** d'un rôle existant — `admin`, `validator`,
`moderator` sont semés par la migration. `--organisation` vaut par défaut le seul
club en base.

Elle **ne crée pas d'utilisateur** : demandez d'abord à la personne de se
connecter une fois, son adresse ayant été autorisée au préalable
(`allow-email`, ci-dessous). Elle **ne crée pas de rôle** non plus : composer un
rôle est un geste d'administration qui passe par l'API.

### Autoriser une adresse (`allow-email`, #170)

```bash
uv run python -m app.cli allow-email --email <adresse>
```

La liste des adresses autorisées à ouvrir une session vit **en base**, éditable
depuis `/admin/acces` sans redéploiement. Cette commande est la voie d'amorçage : sur
une base neuve la liste est vide, donc personne ne peut se connecter, donc
personne ne peut ouvrir l'écran qui inscrirait la première adresse.

Idempotente, elle sort en `0` (inscrite ou déjà présente) et en `2` sur une
adresse mal formée. Elle **ne retire pas** — le retrait vit dans l'écran, où il
est gardé par l'invariant du dernier administrateur.

L'amorçage complet d'une installation tient donc en trois gestes :
`allow-email`, **une connexion par le navigateur** (c'est elle qui crée
l'utilisateur), puis `grant-role --role admin`.

Deux contournements délibérés, écrits pour qu'on ne les prenne pas pour des
oublis : elle **n'applique pas** la règle de non-amplification — sans session, il
n'y a pas d'acteur dont comparer les pouvoirs, et l'accès au serveur *est* le
privilège —, et elle **n'est pas soumise** à l'invariant du dernier
administrateur, puisqu'elle ne fait qu'accorder.

### Révoquer les sessions en urgence (`revoke-sessions`, #169)

```bash
uv run python -m app.cli revoke-sessions --all [--yes]     # tous les comptes
uv run python -m app.cli revoke-sessions --email <adresse> # une adresse
```

Après une fuite de jetons, un poste perdu ou un doute sur la base. Les deux
cibles sont **exclusives** et aucune n'est le défaut (code `2` sinon) ; `--yes`
ne dispense de confirmation que sur `--all`, le seul des deux gestes qui
déconnecte aussi celui qui le lance. Un refus interactif sort en `0`.

**Elle ne désactive aucun compte** : elle coupe des jetons, chacun se reconnecte.
C'est ce qui la distingue du retrait d'une adresse, qui ferme les comptes sans
effacer les sessions — une réinscription dans la fenêtre de TTL ressusciterait
les jetons. Les deux portées existent aussi dans `/admin/acces` (pouvoir
`sessions:revoke`) : « Fermer les sessions » par ligne pour une adresse, une
carte en bas de page pour tout le club. La CLI reste là pour le jour où c'est
justement du back-office qu'on se méfie — et pour fermer les sessions d'une
adresse **déjà retirée** de la liste, que l'écran ne montre plus.

## Tests & qualité

```bash
uv run pytest -m "not integration"   # tests rapides (sans réseau) — défaut CI, 4 workers
uv run pytest -m integration -n 0    # tests réseau réel (scrapers) ; -n 0 : un seul débit sortant
uv run ruff check .                  # lint
```

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `DATABASE_URL` | `sqlite:///./triathlon.db` | Connexion DB (Azure PostgreSQL Flexible Server en production, Supabase en preview — voir `docs/infra-azure.md`) |
| `CORS_ORIGINS` | localhost:3000,5173 | Origines autorisées (CSV, **restreint**) |
| `LOG_LEVEL` | `INFO` | Niveau de log |
| `LOG_JSON` | `false` | Logs JSON (ingestion Render/Datadog) |
| `CACHE_TTL_IN_PROGRESS_SECONDS` | `600` | TTL cache course en cours (10 min) |
| `CACHE_TTL_FINISHED_SECONDS` | `2592000` | TTL cache course terminée (30 j) |
| `DB_POOL_SIZE` | `15` | Connexions permanentes du pool SQLAlchemy (dimensionné sur le plafond Azure B1ms — 35 connexions utilisateur, `docs/infra-azure.md` — #585) |
| `DB_MAX_OVERFLOW` | `10` | Connexions temporaires au-delà de `DB_POOL_SIZE` (25 au total, 10 de marge pour migrations/batch/dev) |
| `DB_POOL_TIMEOUT_SECONDS` | `5` | Attente max d'une connexion avant `TimeoutError` (30 s par défaut chez SQLAlchemy — abaissé pour échouer vite plutôt qu'attendre en silence) |
| `AUTH_SESSION_SECRET_KEY` | *(vide)* | Signe le jeton d'état du parcours. **≥ 32 caractères** ou le démarrage échoue ; vide = authentification non configurée |
| `AUTH_GITHUB_CLIENT_ID` | *(vide)* | Application OAuth GitHub |
| `AUTH_GITHUB_CLIENT_SECRET` | *(vide)* | Application OAuth GitHub |
| `AUTH_REDIRECT_BASE_URL` | *(vide)* | Origine de l'**interface** (jamais celle de l'API) : destination de retour, base de `/login?error=…` et du `redirect_uri` envoyé au fournisseur. **Sans défaut** — un défaut localhost faisait passer pour configuré un déploiement qui l'oubliait, et l'échec tombait alors chez GitHub |
| `AUTH_COOKIE_SECURE` | `true` | `false` en développement sans TLS — retire alors le préfixe `__Host-` du nom des cookies |
| `AUTH_SESSION_TTL_DAYS` | `7` | Durée de session, sans prolongation glissante |
| `AUTH_STATE_TTL_SECONDS` | `600` | Durée de vie du jeton d'état (10 min) |

Une installation **sans** ces variables démarre normalement : le site public est
intact et `GET /api/v1/auth/methods` rend `[]`. Mise en route locale complète
(application OAuth comprise) : `specs/20260801-145428-auth-socle-sso/quickstart.md`.

## Points clés du modèle

- **Course** = (nom, date, type) unique ; `source_url` sert de clé de cache TTL.
- **Participation** unique par (course, dossard) → plus de doublons à l'import.
- **splits** (JSON) remplace les colonnes figées swim/t1/bike/t2/run → couvre tous
  les sports (duathlon course1/course2, swimrun…). Les temps restent des strings.

## Suites (pistes d'amélioration)

- Factorisation des helpers internes des scrapers (`_detect_event_type`, mapping
  des splits) — différée car signatures divergentes et couverture de tests inégale.
