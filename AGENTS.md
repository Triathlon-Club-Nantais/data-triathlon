# AGENTS.md — data-triathlon

App web centralisant les résultats de compétition des membres d'un club de
triathlon (TCN). On colle une URL de chronométrage → le backend scrape, stocke,
et importe en arrière-plan tous les participants de l'épreuve.

Détails install/déploiement : voir `README.md`. Ce fichier cible les agents IA.

## Stack
- **Backend** : Python 3.11, FastAPI 0.115, SQLAlchemy 2.0, PostgreSQL (Supabase).
  Scraping httpx + BeautifulSoup/lxml, fallback Playwright. Tests pytest + respx.
- **Frontend** : React 18 + Vite 6, JSX, pas de TypeScript, pas de lib UI.
- **Déploiement** : backend → Render (`render.yaml`), front → Vercel, DB → Supabase.

## Commandes

```bash
# Backend (depuis backend/, venv activé)
uvicorn main:app --reload --port 8001   # API + /docs
pytest                                   # tests unitaires (sans réseau)
pytest -m integration                    # tests réseau réel (~30 s)
pytest -m "not integration"              # exclut le réseau (défaut)

# Frontend (depuis frontend/)
npm run dev        # Vite sur :3000, proxy /api → :8001
npm run build      # build prod
```

Variable requise : `backend/.env` avec `DATABASE_URL` (voir `backend/.env.example`).
Tables créées automatiquement au démarrage (pas de migrations).

## Architecture backend

- `main.py` — app FastAPI, CORS, montage des routers.
- `database.py` — engine + session SQLAlchemy. `models.py` — `Result`, `PendingProvider`.
- `routers/` — `scrape.py` (`POST /api/scrape`, `/api/scrape/event`),
  `results.py` (CRUD `/api/results`), `admin.py` (providers non supportés signalés).
- `scrapers/` — **registre central dans `__init__.py`** :
  `detect_provider(url)`, `scrape(url, bib)`, `scrape_event_all(url)`.
  Un module par fournisseur : `klikego.py`, `breizhchrono.py`, `timepulse.py`,
  `wiclax.py`, + `playwright_fallback.py` (provider par défaut).
  `base.py` = dataclass `ScrapedResult`. `utils.py` = `normalize_time/rank`.
- `scripts/` — `audit.py`, `seed_demo.py` (utilitaires hors runtime).

### Conventions scrapers

- Tout nouveau fournisseur : créer `scrapers/<nom>.py`, exposer `scrape()` (et
  `scrape_event_all()` si l'import de masse est possible), puis l'enregistrer
  dans les 3 fonctions de `scrapers/__init__.py`. Provider inconnu → `playwright`.
- **Breizh Chrono réutilise la logique Klikego** (`klikego._parse_detail`,
  `_detect_event_type`) — ne pas dupliquer, factoriser dans `klikego.py`.
- Identification club lors d'un import épreuve : filtre `city=nantais` de l'API
  (plus fiable que le nom de club, qui varie : « TCN », « TRIATHLON CLUB NANTAIS »…).
- Les temps restent des **strings** (`"01:23:45"`), normalisés via `utils.py`.
  Splits adaptés au sport, stockés dans les colonnes dédiées + `raw_data` (JSON).

## Architecture frontend

- `App.jsx` — onglets + déclenche l'import épreuve en arrière-plan après save.
- `api/client.js` — appels `/api/*`. `constants.js` — constantes partagées.
- `components/` — `ScrapeForm` (scrape + édition + save, saisie manuelle si
  provider non supporté), `ResultsList` + `ResultCard`, `EventGroupList`,
  `ClubView` (stats club), `AdminView` (providers signalés).

## Conventions générales

- **Langue** : UI, commentaires et messages en **français** (avec accents).
- Commits : Conventional Commits (`feat:`, `fix:`…), déjà en place dans l'historique.
- Pas de couche ORM de migration — modifs de schéma = édition `models.py`
  (recréation auto sur DB vierge ; en prod Supabase, gérer la migration à la main).
- Tests unitaires **sans réseau** (respx mocke httpx) ; le réseau réel est isolé
  derrière le marker `integration` (`pytest.ini`).

## Fournisseurs supportés

Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live (individuel + épreuve complète).
Types : Triathlon S/M/L/XL, Duathlon XS/S/M/L, SwimRun S/M/L, Aquathlon,
Aquarun, Bike & Run.
