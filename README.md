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

```bash
cd backend
pip install -r requirements-test.txt
pytest -m "not integration"
```

91 tests couvrant :
- Klikego : détection du type d'épreuve (30 variantes), parsing des splits, classements, recherche paginée
- TimePulse : parsing XML, normalisation des noms, calcul des rangs, détection du type

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
├── backend/
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
├── frontend/
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

### Frontend → Vercel

1. Importer le repo sur [vercel.com](https://vercel.com)
2. **Root Directory** : `frontend`
3. Variable d'environnement : `VITE_API_URL` = URL du votre service Render

---

## Contribuer avec les outils IA (Superpowers + Speckit)

Ce projet embarque deux outils d'assistance IA préconfigurés pour le vibe coding.
Pour savoir quel outil utiliser (bugfix vs vraie feature, quand lancer les
sous-agents…) : voir [`docs/WORKFLOW-IA.md`](docs/WORKFLOW-IA.md).
3. Variable d'environnement : `VITE_API_URL` = URL du service Render
