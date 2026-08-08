# Triathlon Club — Résultats de compétition

Application web pour centraliser les résultats de compétitions des membres du club TCN.  
Collez une URL de résultat — le backend scrape et stocke les données automatiquement.

---

## Fonctionnalités

- **Ajout d'un résultat** : coller une URL de chronométrage → les données sont pré-remplies, vérifiables et éditables avant sauvegarde
- **Import automatique de l'épreuve** : après chaque sauvegarde individuelle, tous les participants de la même épreuve sont importés en arrière-plan avec une barre de progression en temps réel (SSE)
- **Onglet "Tous les résultats"** : liste complète par épreuve, avec filtres (nom, type, date)
- **Onglet "Club TCN"** : statistiques et résultats filtrés sur le club — les co-membres présents sur la même épreuve apparaissent automatiquement
- **Dashboard** : chiffres clés et répartition par discipline, filtrés sur le club
- **Recherche globale** : barre de recherche dans le header, navigation instantanée vers les résultats
- **Interface responsive** : navigation mobile, formulaire adaptatif

---

## Prérequis

- **[uv](https://docs.astral.sh/uv/)** — gère les dépendances *et* l'interpréteur Python (3.13, téléchargé au besoin)
- **Node.js 20+** (avec npm)
- **PostgreSQL** via [Supabase](https://supabase.com) (gratuit) — ou SQLite en local

---

## Installation locale

### 1. Cloner le projet

```bash
git clone https://github.com/TON_USERNAME/data-triathlon.git
cd data-triathlon
```

### Raccourcis Task (optionnel mais recommandé)

Un `Taskfile.yml` ([go-task](https://taskfile.dev)) regroupe toutes les commandes
courantes. Une fois Task installé (`brew install go-task`, ou voir la
[doc d'installation](https://taskfile.dev/installation/)) :

```bash
task                 # liste toutes les tâches disponibles
task install         # installe les deps (backend + frontend)
task dev             # lance backend + frontend en parallèle (ports libres, cf. « Plusieurs worktrees »)
task test            # tests unitaires backend + frontend
task lint            # lint des deux
```

Préfixes : `b:*` (backend), `f:*` (frontend). Ex. :
`task b:migrate`, `task b:migration -- "mon message"`, `task f:build`.
Les sections ci-dessous documentent les commandes brutes équivalentes.

### 2. Base de données

**Option A — Supabase (recommandé pour la prod)**

1. Créer un projet sur [supabase.com](https://supabase.com)
2. **Connect** → **Direct** → copier l'URI de connexion
3. Créer `backend/.env` :

```env
DATABASE_URL=postgresql://postgres.VOTRE_REF:VOTRE_MDP@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
```

**Option B — SQLite (dev local uniquement)**

```env
DATABASE_URL=sqlite:///./triathlon.db
```

> Le schéma est géré par **Alembic** : appliquer `alembic upgrade head` après
> avoir configuré `DATABASE_URL` (voir ci-dessous).
>
> 📊 **Modèle de données (MCD)** : voir [`docs/modele-donnees.md`](docs/modele-donnees.md)
> — diagramme Mermaid des entités, relations et contraintes d'unicité.

### 3. Backend (FastAPI)

```bash
cd backend

uv sync                                # crée .venv (Python 3.13) et installe depuis uv.lock

uv run alembic upgrade head            # crée / met à jour le schéma
uv run python scripts/dev_server.py    # API + /docs, port libre attribué par l'OS
```

Aucun venv à activer : `uv run` synchronise l'environnement avant d'exécuter.

> Les endpoints sont versionnés sous **`/api/v1`** et le schéma DB est géré par
> **Alembic**. Voir [`backend/README.md`](backend/README.md) pour le détail.

Le port retenu s'affiche au démarrage, avec `/docs` pour la documentation interactive.

L'écoute couvre toutes les interfaces (`0.0.0.0`), comme en production : le seul
loopback rendrait l'API injoignable depuis l'extérieur d'un conteneur, ou depuis un
autre appareil du réseau local. L'URL affichée et publiée reste en `127.0.0.1`, qui
est une cible joignable — ce que `0.0.0.0` n'est pas.

### 4. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Frontend : `http://localhost:3000` (ou le port libre suivant).

> Les appels `/api/*` sont réécrits (rewrites Next.js) vers le backend via
> `BACKEND_URL` (`next.config.ts`), et les pages serveur l'appellent via `API_URL`
> (`lib/api/server.ts`). En dev, `npm run dev` renseigne les deux tout seul.

### 5. Plusieurs worktrees en parallèle

Rien à configurer : chaque worktree prend les ports libres qu'il trouve, et son
frontend parle au backend **de son propre worktree**.

Le mécanisme tient en un fichier. `backend/scripts/dev_server.py` prend un port
libre attribué par l'OS et le publie dans `.dev-backend.json` à la racine du
worktree (gitignoré) ; `npm run dev` lit ce fichier — en vérifiant que le port
répond, pour ignorer un fichier laissé par un backend tué — puis lance `next dev`
avec `BACKEND_URL` et `API_URL` renseignés.

L'ordre de démarrage est libre : lancé en premier, le frontend attend le backend
(60 s au plus, puis repli sur `:8001` avec un avertissement — depuis le passage
au port éphémère, ce repli est un **signal d'échec**, plus une chance de tomber
juste : c'est `DEV_BACKEND_PORT` qui donne une URL stable).

| Variable | Effet |
|---|---|
| `DEV_BACKEND_PORT` | force le port du backend au lieu du port éphémère tiré par l'OS |
| `BACKEND_URL` | impose la cible du frontend : aucune attente, aucune découverte |
| `API_URL` | impose la seule cible des pages serveur (RSC), sans toucher aux rewrites |

Le lanceur du frontend ne fait que **combler** ces deux dernières : une valeur déjà
posée gagne, qu'elle vienne du shell ou de `frontend/.env.local` (lu avec le loader
de Next). Dissocier `API_URL` de `BACKEND_URL` reste donc possible en dev, comme en
prod.

Un worktree est en revanche une copie neuve : les fichiers gitignorés n'y sont pas.
`.worktreeinclude` (racine, syntaxe `.gitignore`) liste ceux que **Claude Code**
recopie à la création d'un worktree — `.env`, `.env.local`, la base de dev
`backend/triathlon.db` et `frontend/node_modules/` (copie : 12,8 s, contre 34,3 s
de `npm ci`). `backend/.venv/` n'y est pas : `uv sync` le reconstruit en 0,21 s
depuis son cache, plus vite que la copie. Avec `git worktree add`, la copie reste à
votre charge.

---

## Providers supportés

| Site | Import individuel | Import épreuve complète |
|------|:-----------------:|:-----------------------:|
| **Klikego** (`klikego.com`) | ✅ | ✅ |
| **Breizh Chrono** (`resultats.breizhchrono.com`) | ✅ | ✅ |
| **TimePulse** (`timepulse.fr`) | ✅ | ✅ |
| **Wiclax / G-Live / ChronoSmetron** | ✅ | ✅ |
| **ProLiveSport** (`prolivesport.fr`) | ✅ | ✅ |
| **Sport Innovation** (`sportinnovation.fr`) | ✅ | ✅ |

### Types d'épreuves supportés

Triathlon (XS/S/M/L/XL), Duathlon (XS/S/M/L), SwimRun (S/M/L), Aquathlon, Aquarun, Bike & Run.

### Identification des membres du club

Lors de l'import d'une épreuve, les co-membres sont identifiés par filtre sur le nom du club (`nantais|TCN`). Les résultats sans club renseigné (certains providers) sont importés sans filtre.

---

## Lancer un batch en production

Les batches (reprise du scraping, import d'une liste d'épreuves) ne tournent **pas** dans le service web : celui-ci est sur une offre gratuite à un seul process, et il sert le site public. Ils s'exécutent sur un runner GitHub Actions, qui lance la même CLI que ci-dessus.

Trois voies, une seule exécution en aval :

| Voie | Où | Pour qui |
|------|----|----------|
| Écran `/admin/batches` | back-office | pouvoir `batch:run` |
| Onglet **Actions** → *Batch* → **Run workflow** | GitHub | droits d'écriture sur le dépôt |
| Planification hebdomadaire (lundi 3 h UTC) | automatique | — |

Depuis l'écran, deux façons de composer la liste d'épreuves : un **filtre** sur la base (fournisseur, ancienneté, nombre maximum), ou le **téléversement d'un fichier** `.csv`/`.xlsx` dont on désigne la colonne portant les liens de résultats — ce qui remplace l'import du Google Sheet. Le fichier n'est jamais stocké côté serveur.

La base écrite n'est jamais choisie dans le formulaire : elle vient du réglage `GITHUB_BATCH_TARGET` de l'instance. L'administration de la preview écrit dans la base de preview, celle de la production dans la sienne.

Détail complet — jeton, environments, secrets, pièges de connexion : [`docs/ci-cd.md`](docs/ci-cd.md).

---

## Tests

### Tests unitaires (sans réseau)

**Backend** (`backend/`)

```bash
cd backend
uv sync
uv run pytest -m "not integration"   # tests par couche (≈130)
uv run ruff check .                  # lint
```

≈130 tests par couche : `test_repositories/`, `test_services/`, `test_api/`,
plus les scrapers Klikego / TimePulse.

**Frontend** (`frontend/`)

```bash
cd frontend
npm test       # Vitest + RTL
npm run lint   # ESLint
```

### Tests d'intégration (réseau réel)

```bash
cd backend
uv run pytest -m integration
```

Tests avec appels aux APIs Klikego, Breizh Chrono et TimePulse en conditions réelles.

---

## Structure du projet

```
data-triathlon/
├── backend/                     # API FastAPI (architecture en couches)
│   ├── app/
│   │   ├── main.py              # create_app() : CORS, handlers d'erreurs, routers
│   │   ├── core/                # config (pydantic-settings), logging, database, exceptions
│   │   ├── models/              # SQLAlchemy normalisé : Athlete, Course, Participation
│   │   ├── schemas/             # DTO Pydantic v2
│   │   ├── repositories/        # accès données (seule couche qui touche la Session)
│   │   ├── services/            # métier : mapping, cache TTL, scrape, import, stats, geocode
│   │   ├── api/v1/              # routers fins montés sous /api/v1
│   │   └── scrapers/            # registre Protocol + un module par provider
│   ├── alembic/                 # migrations (révision initiale = schéma complet)
│   ├── scripts/                 # reset_db.py, seed_demo.py, audit_scrapers.py
│   ├── tests/                   # test_repositories / test_services / test_api (≈130 tests)
│   ├── Dockerfile
│   └── README.md
├── frontend/                    # Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui
│   ├── app/                     # dashboard, resultats, athletes/[id], courses/[id], club, carte, ajouter, admin
│   ├── components/              # scrape/, results/, club/, map/, dashboard/, charts/, ui/ (shadcn)
│   ├── lib/                     # client API (/api/v1), sse.ts, types partagés
│   ├── next.config.ts           # rewrites /api → backend, output standalone (Docker)
│   ├── Dockerfile
│   └── package.json
├── docs/
│   ├── modele-donnees.md       # MCD : diagramme Mermaid + contraintes (entités & migrations)
│   ├── WORKFLOW-IA.md
│   └── superpowers/            # specs & plans de refonte
├── Taskfile.yml                 # raccourcis go-task (b:* / f:*)
└── render.yaml                  # config déploiement Render (backend)
```

---

## Déploiement

### Backend → Render.com

1. Connecter le repo GitHub sur [render.com](https://render.com)
2. Créer un service web Python, **Root Directory = `backend`**, et y reporter le
   `buildCommand` / `startCommand` de `render.yaml`
3. Ajouter la variable d'environnement `DATABASE_URL` (Supabase Session Pooler)

> **`render.yaml` ne configure rien tout seul.** Les services du projet ont été
> créés à la main : Render ne lit ce fichier que pour un service issu d'un
> *Blueprint*. Il sert ici de base de référence, à recopier dans le dashboard —
> détail et conséquences dans [docs/ci-cd.md](docs/ci-cd.md).

> Au démarrage, Render exécute `alembic upgrade head && uvicorn app.main:app …`
> (migrations appliquées avant le lancement de l'API).

### Frontend → Vercel

Deux projets, chacun avec son domaine de production stable :
`data-triathlon` (prod, déployé sur tag `v*`) et `data-triathlon-preview`
(preview, déployé sur merge dans `main`).

1. Importer le repo sur [vercel.com](https://vercel.com)
2. **Root Directory** : `frontend`
3. Variables d'environnement (env **Production** de chaque projet — les deux
   déploiements du pipeline sont des `--prod`, dans leur projet respectif) :
   - `BACKEND_URL` — URL interne du backend Render (rewrites client)
   - `API_URL` — URL du backend pour les Server Components

> La preview vise la production de son propre projet plutôt qu'un *preview
> deployment* : ce dernier change d'URL à chaque exécution, ce qui interdisait
> d'y fixer l'accès SSO. Détail : [`docs/ci-cd.md`](docs/ci-cd.md).

---

## Contribuer avec les outils IA (Superpowers + Speckit)

Ce projet embarque deux outils d'assistance IA préconfigurés. Ils forment **deux
voies complètes qu'on ne croise jamais** : l'exécution suit l'outil qui a produit
le plan. Quelle voie choisir, et quand se passer de plan : voir
[`docs/WORKFLOW-IA.md`](docs/WORKFLOW-IA.md).
