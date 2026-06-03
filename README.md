# Triathlon Club — Résultats de compétition

Application web pour centraliser les résultats de compétitions des membres du club.  
Collez une URL de résultat Klikego, Breizh Chrono, TimePulse ou Wiclax — le backend scrape et stocke les données automatiquement.

---

## Fonctionnalités

- **Ajout d'un résultat** : coller une URL de chronométrage → les données sont pré-remplies, vérifiables et éditables avant sauvegarde
- **Import automatique de l'épreuve** : après chaque sauvegarde individuelle, tous les participants de la même épreuve sont importés en arrière-plan (791 participants en ~15 s pour un Ironman)
- **Onglet "Tous les résultats"** : liste complète avec filtres (nom, type d'épreuve, date)
- **Onglet "Club TCN"** : statistiques et résultats filtrés sur le club de l'adhérent — les co-membres présents sur la même épreuve apparaissent automatiquement

---

## Prérequis

- **Python 3.11+**
- **Node.js 18+** (avec npm)
- **PostgreSQL** via [Supabase](https://supabase.com) (gratuit)

---

## Installation locale

### 1. Cloner le projet

```bash
git clone https://github.com/TON_USERNAME/data-triathlon.git
cd data-triathlon
```

### 2. Base de données (Supabase)

1. Créer un projet sur [supabase.com](https://supabase.com)
2. **Connect** → **Direct** → copier l'URI de connexion
3. Créer `backend/.env` :

```env
DATABASE_URL=postgresql://postgres.VOTRE_REF:VOTRE_MDP@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
```

> Les tables sont créées automatiquement au premier démarrage.

### 3. Backend (FastAPI + PostgreSQL)

```bash
cd backend

# Créer et activer un environnement virtuel
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer le serveur (port 8001)
uvicorn main:app --reload --port 8001
```

Le backend est accessible sur `http://localhost:8001`  
Documentation API interactive : `http://localhost:8001/docs`

### 4. Frontend (React + Vite)

Dans un second terminal :

```bash
cd frontend
npm install
npm run dev
```

Le frontend est accessible sur `http://localhost:3000`.

> Les appels `/api/*` sont automatiquement proxifiés vers `http://localhost:8001` via la config Vite.

---

## Fournisseurs supportés

| Site | Import individuel | Import épreuve complète |
|------|:-----------------:|:-----------------------:|
| **Klikego** (`klikego.com`) | ✅ | ✅ |
| **Breizh Chrono** (`resultats.breizhchrono.com`) | ✅ | ✅ |
| **TimePulse** (`timepulse.fr`) | ✅ | ✅ |
| **Wiclax / G-Live** | ✅ | ✅ |

### Types d'épreuves supportés

Triathlon (S/M/L/XL), Duathlon (XS/S/M/L), SwimRun (S/M/L), Aquathlon, Aquarun, Bike & Run.

### Recherche par nom

Pour Klikego et Breizh Chrono, le formulaire affiche automatiquement un champ de saisie du nom si l'URL ne contient pas encore le paramètre `search=`.

### Identification des membres du club (import épreuve)

Lors de l'import en masse d'une épreuve Klikego/Breizh Chrono, les co-membres du club sont identifiés via le filtre `city=nantais` de l'API — plus fiable que le nom de club qui varie selon les fournisseurs ("TCN", "TRIATHLON CLUB NANTAIS", etc.). Leur page de détail est ensuite récupérée pour obtenir les splits et le nom de club complet.

---

## Tests

Depuis le répertoire `backend/` avec le virtualenv activé :

### Tests unitaires (sans réseau)

```bash
# Installer les dépendances de test (une seule fois)
pip install -r requirements-test.txt

# Lancer tous les tests unitaires
pytest

# Avec détail verbose
pytest -v
```

Couverture : ~51 tests unitaires Klikego + TimePulse, tous sans appel réseau.

Les tests Klikego couvrent notamment :
- `_parse_detail` : splits, temps cumulés vs delta, classements, méta-ligne (genre/catégorie/club)
- `_detect_event_type` : 30 variantes de heat/slug
- `_parse_search_row` : extraction des lignes paginées (bulk import)

### Tests d'intégration (réseau réel)

```bash
pytest -m integration
```

Ces tests appellent les APIs Klikego, Breizh Chrono et TimePulse en conditions réelles.
Ils nécessitent une connexion internet et peuvent être plus lents (~30 s).

```bash
# Exclure les tests d'intégration (comportement par défaut sans -m)
pytest -m "not integration"
```

---

## Structure du projet

```
data-triathlon/
├── backend/
│   ├── main.py                  # App FastAPI, CORS, montage des routers
│   ├── database.py              # Engine SQLAlchemy + session (PostgreSQL)
│   ├── models.py                # Modèle Result
│   ├── requirements.txt         # Dépendances de production
│   ├── requirements-test.txt    # + pytest, respx
│   ├── pytest.ini               # testpaths, markers, pythonpath
│   ├── .env                     # Variables locales (DATABASE_URL) — non versionné
│   ├── routers/
│   │   ├── scrape.py            # POST /api/scrape  +  POST /api/scrape/event
│   │   └── results.py           # GET / POST / DELETE /api/results
│   ├── scrapers/
│   │   ├── __init__.py          # detect_provider() + scrape() + scrape_event_all()
│   │   ├── base.py              # Dataclass ScrapedResult
│   │   ├── klikego.py           # Scraper Klikego (+ logique partagée avec BC)
│   │   ├── breizhchrono.py      # Scraper Breizh Chrono (réutilise klikego._parse_detail)
│   │   ├── timepulse.py         # Scraper TimePulse (XML API)
│   │   ├── wiclax.py            # Scraper Wiclax / G-Live
│   │   └── utils.py             # normalize_time, normalize_rank
│   └── tests/
│       ├── conftest.py
│       ├── test_klikego.py      # Tests unitaires Klikego (~51 tests)
│       ├── test_timepulse.py    # Tests unitaires TimePulse
│       └── test_integration.py  # Tests réseau Klikego, Breizh Chrono, TimePulse
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Onglets + import épreuve en arrière-plan
│   │   ├── api/client.js
│   │   └── components/
│   │       ├── ScrapeForm.jsx   # Formulaire de scraping + édition + sauvegarde
│   │       ├── ResultsList.jsx  # Liste + filtres
│   │       ├── ResultCard.jsx   # Carte résultat (splits adaptatifs par sport)
│   │       └── ClubView.jsx     # Statistiques et résultats filtrés par club
│   ├── vite.config.js           # Proxy /api → localhost:8001
│   ├── vercel.json              # Rewrites SPA pour Vercel
│   └── package.json
└── render.yaml                  # Config déploiement Render (backend)
```

---

## Déploiement

### Base de données → Supabase

1. Créer un projet sur [supabase.com](https://supabase.com)
2. Récupérer l'URL de connexion : **Connect** → **Direct** → URI
3. Utiliser cette URL comme variable `DATABASE_URL` sur Render

### Backend → Render.com

1. Connecter le repo GitHub sur [render.com](https://render.com)
2. Le fichier `render.yaml` configure automatiquement le service Python
3. Dans **Environment** → ajouter :
   - `DATABASE_URL` = URL Supabase (Session Pooler pour compatibilité IPv4)

### Frontend → Vercel

1. Importer le repo sur [vercel.com](https://vercel.com)
2. **Root Directory** : `frontend`
3. Variable d'environnement : `VITE_API_URL` = URL de votre service Render
