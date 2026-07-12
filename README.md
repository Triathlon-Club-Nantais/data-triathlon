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
task dev             # lance backend (:8001) + frontend (:3000) en parallèle
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
uv run uvicorn app.main:app --reload --port 8001
```

Aucun venv à activer : `uv run` synchronise l'environnement avant d'exécuter.

> Les endpoints sont versionnés sous **`/api/v1`** et le schéma DB est géré par
> **Alembic**. Voir [`backend/README.md`](backend/README.md) pour le détail.

Backend : `http://localhost:8001`  
Docs API : `http://localhost:8001/docs`

### 4. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Frontend : `http://localhost:3000`

> Les appels `/api/*` sont réécrits (rewrites Next.js) vers `http://localhost:8001`
> via `BACKEND_URL` (`next.config.ts`).

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
