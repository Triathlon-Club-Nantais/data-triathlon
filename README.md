# Triathlon Club — Résultats de compétition

Application web pour centraliser les résultats de compétitions des membres du club TCN.  
Collez une URL de résultat — le backend scrape et stocke les données automatiquement.

> **⚠️ Refonte en cours.** Le dépôt contient deux générations du backend :
> `backend/` (déployé, **déprécié**) et `backend-v2/` (nouvelle architecture en
> couches + modèle normalisé + Alembic, **non encore déployée**). Le frontend
> Next.js `frontend-v2/` est **spécifié mais pas encore codé**. Détails :
> [`docs/superpowers/`](docs/superpowers/) et [`backend-v2/README.md`](backend-v2/README.md).

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

- **Python 3.11+**
- **Node.js 18+** (avec npm)
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
task install         # installe les deps de la pile cible (backend-v2 + frontend-v2)
task dev             # lance backend-v2 (:8001) + frontend-v2 (:3000) en parallèle
task test            # tests unitaires backend-v2 + frontend-v2
task lint            # lint des deux
```

Préfixes : `bv2:*` (backend-v2, cible), `fv2:*` (frontend-v2, cible),
`b1:*`/`f1:*` (v1 dépréciés), `docker:*` (docker-compose). Ex. :
`task bv2:migrate`, `task bv2:migration -- "mon message"`, `task fv2:build`.
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

> Les tables sont créées automatiquement au premier démarrage.

### 3. Backend (FastAPI)

**Backend v1 (`backend/`, déployé en prod — déprécié)**

```bash
cd backend

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

uvicorn main:app --reload --port 8001
```

**Backend v2 (`backend-v2/`, nouvelle architecture — cible)**

```bash
cd backend-v2
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate sous Windows

pip install -r requirements-dev.txt   # requirements.txt seul en prod

alembic upgrade head                   # crée le schéma (plus de create_all auto)
uvicorn app.main:app --reload --port 8001
```

> En v2, les endpoints sont versionnés sous **`/api/v1`** et le schéma DB est géré
> par **Alembic**. Voir [`backend-v2/README.md`](backend-v2/README.md) pour le détail.

Backend : `http://localhost:8001`  
Docs API : `http://localhost:8001/docs`

### 4. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Frontend : `http://localhost:3000`

> Les appels `/api/*` sont proxifiés vers `http://localhost:8001` via Vite.

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

Triathlon (S/M/L/XL), Duathlon (XS/S/M/L), SwimRun (S/M/L), Aquathlon, Aquarun, Bike & Run.

### Identification des membres du club

Lors de l'import d'une épreuve, les co-membres sont identifiés par filtre sur le nom du club (`nantais|TCN`). Les résultats sans club renseigné (certains providers) sont importés sans filtre.

---

## Tests

### Tests unitaires (sans réseau)

**Backend v1 (`backend/`)**

```bash
cd backend
pip install -r requirements-test.txt
pytest -m "not integration"
```

91 tests couvrant :
- Klikego : détection du type d'épreuve (30 variantes), parsing des splits, classements, recherche paginée
- TimePulse : parsing XML, normalisation des noms, calcul des rangs, détection du type

**Backend v2 (`backend-v2/`)**

```bash
cd backend-v2
pip install -r requirements-dev.txt
pytest -m "not integration"   # 130 tests
ruff check .                  # lint
```

130 tests par couche : `test_repositories/`, `test_services/`, `test_api/`,
plus les scrapers Klikego / TimePulse.

### Tests d'intégration (réseau réel)

```bash
pytest -m integration
```

16 tests avec appels aux APIs Klikego, Breizh Chrono et TimePulse en conditions réelles.

### Tests E2E Playwright

```bash
cd tests/e2e
npm install
npx playwright test
```

427 tests E2E couvrant :
- Scrape + save pour chaque provider (klikego, breizhchrono, wiclax, timepulse, prolivesport, sportinnovation)
- Import d'épreuve complète avec vérification des membres TCN
- Gestion des doublons (sélection du bon athlète)
- Saisie manuelle pour providers non supportés
- Bandeaux d'avertissement (liens live/dead Breizh Chrono)
- Fonctionnalités UX : recherche globale, empty state, bannière de progression SSE

> Les tests E2E font de vrais appels HTTP aux scrapers — compter 20-30 min pour la suite complète.  
> Le fichier de fixtures `tests/e2e/fixtures/providers.json` est dans `.gitignore` (données club privées).  
> Pour régénérer les fixtures : `python backend/extract_xlsx_urls.py`

---

## Structure du projet

```
data-triathlon/
├── backend/                     # ⚠️ v1 — déployé en prod, déprécié
│   ├── main.py                  # App FastAPI, CORS, montage des routers
│   ├── database.py              # Engine SQLAlchemy + session
│   ├── models.py                # Modèle Result + PendingProvider
│   ├── requirements.txt
│   ├── requirements-test.txt
│   ├── pytest.ini
│   ├── routers/
│   │   ├── scrape.py            # POST /api/scrape + /api/scrape/event/stream (SSE)
│   │   ├── results.py           # GET/POST/DELETE /api/results + /api/results/events
│   │   ├── admin.py             # GET/POST/DELETE /api/admin/pending-providers
│   │   └── stats.py             # GET /api/stats + /api/stats/events-geo
│   ├── scrapers/
│   │   ├── __init__.py          # detect_provider() + scrape() + scrape_event_all()
│   │   ├── base.py              # ScrapedResult, MultipleMatchesError
│   │   ├── klikego.py
│   │   ├── breizhchrono.py
│   │   ├── timepulse.py
│   │   ├── wiclax.py
│   │   ├── prolivesport.py
│   │   ├── sportinnovation.py
│   │   └── utils.py             # normalize_time, normalize_rank
│   └── tests/
│       ├── test_klikego.py
│       ├── test_timepulse.py
│       └── test_integration.py
├── backend-v2/                  # 🎯 v2 — architecture en couches (cible)
│   ├── app/
│   │   ├── main.py              # create_app() : CORS, handlers d'erreurs, routers
│   │   ├── core/               # config (pydantic-settings), logging, database, exceptions
│   │   ├── models/             # SQLAlchemy normalisé : Athlete, Course, Participation
│   │   ├── schemas/            # DTO Pydantic v2
│   │   ├── repositories/       # accès données (seule couche qui touche la Session)
│   │   ├── services/           # métier : mapping, cache TTL, scrape, import, stats, geocode
│   │   ├── api/v1/             # routers fins montés sous /api/v1
│   │   └── scrapers/           # registre Protocol + un module par provider
│   ├── alembic/                # migrations (révision initiale = schéma complet)
│   ├── tests/                  # test_repositories / test_services / test_api (130 tests)
│   ├── Dockerfile
│   └── README.md
├── docs/
│   ├── WORKFLOW-IA.md
│   └── superpowers/            # specs & plans de refonte (backend-v2, frontend-v2)
├── frontend/                    # ⚠️ v1 React/Vite — déployé en prod
│                                # (frontend-v2 Next.js : spécifié, pas encore codé)
│   ├── src/
│   │   ├── App.jsx              # Onglets, recherche globale, bannière import SSE
│   │   ├── index.css            # Styles globaux, responsive mobile
│   │   ├── api/client.js        # Fetch + importEventStream() (SSE)
│   │   ├── constants.js
│   │   └── components/
│   │       ├── ScrapeForm.jsx   # Formulaire scraping + empty state derniers résultats
│   │       ├── ResultsList.jsx  # Liste par épreuve + filtres
│   │       ├── ClubView.jsx     # Stats et résultats du club TCN
│   │       ├── DashboardView.jsx
│   │       ├── ResultsFeed.jsx  # Feed temps réel (poll 15s, filtre TCN)
│   │       ├── EventGroupList.jsx
│   │       ├── ResultCard.jsx
│   │       └── AdminView.jsx
│   ├── vite.config.js
│   └── package.json
├── tests/
│   └── e2e/
│       ├── playwright.config.js
│       ├── global-setup.js      # Démarre le backend SQLite sur port 8099
│       ├── global-teardown.js
│       ├── fixtures/            # providers.json — gitignore (données privées)
│       └── specs/
│           ├── providers.spec.js
│           ├── event-import.spec.js
│           └── ux-features.spec.js
└── render.yaml                  # Config déploiement Render (backend)
```

---

## Déploiement

### Backend → Render.com

1. Connecter le repo GitHub sur [render.com](https://render.com)
2. `render.yaml` configure automatiquement le service Python
3. Ajouter la variable d'environnement `DATABASE_URL` (Supabase Session Pooler)

> `render.yaml` cible actuellement `backend/` (v1). Lors de la bascule v2, mettre
> à jour `rootDir`, `startCommand` (`uvicorn app.main:app …`) et ajouter
> `alembic upgrade head` au déploiement.

### Frontend → Vercel

1. Importer le repo sur [vercel.com](https://vercel.com)
2. **Root Directory** : `frontend`
3. Variable d'environnement : `VITE_API_URL` = URL de votre service Render

---

## Contribuer avec les outils IA (Superpowers + Speckit)

Ce projet embarque deux outils d'assistance IA préconfigurés pour le vibe coding.
Pour savoir quel outil utiliser (bugfix vs vraie feature, quand lancer les
sous-agents…) : voir [`docs/WORKFLOW-IA.md`](docs/WORKFLOW-IA.md).
