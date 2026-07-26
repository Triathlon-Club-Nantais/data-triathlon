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

Préfixes : `b:*` (backend), `f:*` (frontend), `docker:*` (docker-compose). Ex. :
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
uv run python scripts/dev_server.py    # API + /docs, premier port libre à partir de 8001
```

Aucun venv à activer : `uv run` synchronise l'environnement avant d'exécuter.

> Les endpoints sont versionnés sous **`/api/v1`** et le schéma DB est géré par
> **Alembic**. Voir [`backend/README.md`](backend/README.md) pour le détail.

Le port retenu s'affiche au démarrage — `http://localhost:8001` tant qu'il est libre,
`/docs` pour la documentation interactive.

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

Le mécanisme tient en un fichier. `backend/scripts/dev_server.py` prend le premier
port libre à partir de 8001 et le publie dans `.dev-backend.json` à la racine du
worktree (gitignoré) ; `npm run dev` lit ce fichier — en vérifiant que le port
répond, pour ignorer un fichier laissé par un backend tué — puis lance `next dev`
avec `BACKEND_URL` et `API_URL` renseignés.

L'ordre de démarrage est libre : lancé en premier, le frontend attend le backend
(60 s au plus, puis repli sur `:8001` avec un avertissement).

| Variable | Effet |
|---|---|
| `DEV_BACKEND_PORT` | force le port du backend et court-circuite le scan |
| `DEV_BACKEND_PORT_BASE` | change le point de départ du scan (défaut : 8001) |
| `BACKEND_URL` | impose la cible du frontend : aucune attente, aucune découverte |
| `API_URL` | impose la seule cible des pages serveur (RSC), sans toucher aux rewrites |

Le lanceur du frontend ne fait que **combler** ces deux dernières : une valeur déjà
posée gagne, qu'elle vienne du shell ou de `frontend/.env.local` (lu avec le loader
de Next). Dissocier `API_URL` de `BACKEND_URL` reste donc possible en dev, comme en
prod.

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
├── docker-compose.yml           # pile full-stack locale (backend :8000 + frontend :3000)
├── Taskfile.yml                 # raccourcis go-task (b:* / f:* / docker:*)
└── render.yaml                  # config déploiement Render (backend)
```

---

## Déploiement

### Backend → Render.com

1. Connecter le repo GitHub sur [render.com](https://render.com)
2. `render.yaml` configure automatiquement le service Python (`rootDir: backend`)
3. Ajouter la variable d'environnement `DATABASE_URL` (Supabase Session Pooler)

> Au démarrage, Render exécute `alembic upgrade head && uvicorn app.main:app …`
> (migrations appliquées avant le lancement de l'API).

### Frontend → Vercel

1. Importer le repo sur [vercel.com](https://vercel.com)
2. **Root Directory** : `frontend`
3. Variables d'environnement :
   - `BACKEND_URL` — URL interne du backend Render (rewrites client)
   - `API_URL` — URL du backend pour les Server Components

---

## Contribuer avec les outils IA (Superpowers + Speckit)

Ce projet embarque deux outils d'assistance IA préconfigurés pour le vibe coding.
Pour savoir quel outil utiliser (bugfix vs vraie feature, quand lancer les
sous-agents…) : voir [`docs/WORKFLOW-IA.md`](docs/WORKFLOW-IA.md).
