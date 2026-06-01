# Triathlon Club — Résultats de compétition

Application web pour centraliser les résultats de compétitions des membres du club.  
Collez une URL de résultat Klikego, TimePulse, Breizh Chrono ou Wiclax — le backend scrape et stocke les données.

---

## Prérequis

- **Python 3.11+**
- **Node.js 18+** (avec npm)
- Git

---

## Installation locale

### 1. Cloner le projet

```bash
git clone https://github.com/TON_USERNAME/data-triathlon.git
cd data-triathlon
```

### 2. Backend (FastAPI)

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

# Lancer le serveur
uvicorn main:app --reload --port 8001
```

Le backend est accessible sur `http://localhost:8001`  
La documentation API interactive : `http://localhost:8001/docs`

### 3. Frontend (React + Vite)

Dans un second terminal :

```bash
cd frontend
npm install
npm run dev
```

Le frontend est accessible sur `http://localhost:3000`

> Les appels `/api/*` sont automatiquement proxifiés vers `http://localhost:8001` via la config Vite.

---

## Fournisseurs supportés

| Site | Format | Exemple d'URL |
|---|---|---|
| **Klikego** | HTML | `https://www.klikego.com/resultats/event-name/ID?heat=...&search=NOM` |
| **TimePulse** | XML API | `https://www.timepulse.fr/epreuves/resultats/ID?id_event=ID&bib=BIB` |
| **Breizh Chrono** | HTML | `https://www.breizhchrono.com/...?dossard=BIB` |
| **Wiclax** | XML `.clax` | `https://www.wiclax-results.com/...?f=fichier.clax&B=BIB` |

### Recherche par nom

Pour Klikego et TimePulse, si vous n'avez pas le numéro de dossard, ajoutez `&search=NOM PRENOM` à l'URL.  
Le champ de recherche s'affiche aussi automatiquement dans le formulaire.

---

## Structure du projet

```
data-triathlon/
├── backend/
│   ├── main.py              # App FastAPI, CORS, montage des routers
│   ├── database.py          # Engine SQLAlchemy + session
│   ├── models.py            # Modèle Result (SQLite)
│   ├── requirements.txt
│   ├── routers/
│   │   ├── scrape.py        # POST /api/scrape
│   │   └── results.py       # GET / POST / DELETE /api/results
│   └── scrapers/
│       ├── __init__.py      # detect_provider() + scrape()
│       ├── base.py          # Dataclass ScrapedResult
│       ├── klikego.py
│       ├── timepulse.py
│       ├── breizhchrono.py
│       └── wiclax.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/client.js
│   │   └── components/
│   │       ├── ScrapeForm.jsx
│   │       ├── ResultsList.jsx
│   │       └── ResultCard.jsx
│   ├── vite.config.js       # Proxy /api → localhost:8001
│   └── vercel.json          # Réécriture SPA pour Vercel
├── render.yaml              # Config déploiement Render (backend)
└── docker-compose.yml
```

---

## Déploiement

### Backend → Render.com

Le fichier `render.yaml` configure automatiquement :
- Service Python avec `uvicorn`
- Disque persistant pour SQLite (`/data/triathlon.db`)

### Frontend → Vercel

1. Importer le repo sur [vercel.com](https://vercel.com)
2. **Root Directory** : `frontend`
3. Variable d'environnement : `VITE_API_URL` = URL de votre service Render

---

## Lancer avec Docker Compose

```bash
docker compose up --build
```

- Frontend : `http://localhost:3000`
- Backend : `http://localhost:8001`
