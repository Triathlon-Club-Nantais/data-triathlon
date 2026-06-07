# Data Triathlon — Claude Code Guide

> **⚠️ Backend v1 — déprécié.** Ce dossier reste en production mais la refonte
> vit dans `../backend-v2/` (archi en couches, modèle normalisé, Alembic, API
> `/api/v1`). Tout nouveau développement va dans `backend-v2/`. Voir
> [`../AGENTS.md`](../AGENTS.md) et [`../backend-v2/README.md`](../backend-v2/README.md).

Application de suivi des résultats de course pour le **Tri Club Nantais (TCN)**.
Agrège les résultats de 6 providers de chronométrage, avec filtrage par club et stats.

---

## Contexte métier

**Qui utilise l'app :**
- **Membres TCN** : importent leurs propres résultats après chaque course. Ce sont eux qui connaissent les épreuves — le club ne tient pas de calendrier centralisé.
- **Admins** : gèrent la qualité des données (corrections, suppressions, providers en attente).

**Parcours typique d'un membre :**
1. Il court un triathlon
2. Le lendemain, le chronométreur publie les résultats sur son site
3. Le membre trouve son URL de résultat et la colle dans ScrapeForm
4. Il vérifie les données extraites et sauvegarde

**Friction principale :** trouver la bonne URL sur le site du chronométreur (chaque provider a une interface différente). Les membres ne sont pas des devs.

**Règles métier :**
- Un athlète peut apparaître sous "Triathlon Club Nantais", "TCN", "TRI CLUB NANTAIS" → tous équivalents
- Les relais (`is_relay=True`) sont exclus des stats individuelles
- Un résultat sans `total_time` est valide (DNF, DNS)
- Les formats "Découverte" et "XS" sont traités comme `triathlon-s`

**Authentification / rôles :**
- Actuellement : aucune restriction, tous les résultats sont visibles et modifiables par tout le monde
- Pas de système de compte membre pour l'instant
- Backlog : profils membres, droits (un membre ne supprime que ses propres résultats)

**Comportement attendu lors de l'ajout d'un lien provider :**
- Quand un membre colle une URL d'un provider supporté → importer **toute la compétition** automatiquement (pas seulement son propre résultat)
- Logique : si un membre trouve l'URL, tous les autres membres TCN qui ont couru ce jour-là bénéficient aussi de l'import
- L'import individuel (un seul athlète) reste disponible en fallback pour les providers non supportés (saisie manuelle)

**Features manquantes prioritaires (backlog PM) :**
1. Guidage par provider dans ScrapeForm : montrer à un membre non-technique où trouver son URL selon le chronométreur
2. Import automatique de toute la compétition dès qu'un lien provider est soumis (SSE progress)
3. Profil membre : retrouver facilement ses propres résultats
4. Droits : un membre ne devrait supprimer que ses propres résultats

---

## Stack

| Couche | Techno |
|--------|--------|
| Backend | FastAPI + SQLAlchemy + Python 3.11 |
| Frontend | React 18 + Vite 6 (pas de TypeScript) |
| Base de données | PostgreSQL via Supabase (prod) / SQLite (tests) |
| Tests E2E | Playwright (`tests/e2e/`) |
| Déploiement backend | Render.com (`render.yaml`) |
| Déploiement frontend | Vercel (`frontend/vercel.json`) |

---

## Lancer en local (Windows / PowerShell)

```powershell
# Backend (port 8000)
cd backend
.venv\Scripts\uvicorn.exe main:app --reload --port 8000

# Frontend (port 3000+)
cd frontend
npm run dev
```

La base de données est dans `backend/.env` :
```
DATABASE_URL=postgresql://...supabase...
```

Pour les tests, SQLite est utilisé automatiquement (pas de `.env` requis).

---

## Architecture backend

```
backend/
├── main.py              # FastAPI app, CORS, routers montés sur /api
├── database.py          # Engine SQLAlchemy, SessionLocal, get_db
├── models.py            # ORM : Result, PendingProvider
├── routers/
│   ├── scrape.py        # POST /api/scrape, /api/scrape/event, /api/scrape/event/stream (SSE)
│   ├── results.py       # GET/POST/DELETE /api/results, /api/results/events
│   ├── stats.py         # GET /api/stats, /api/stats/events-geo
│   └── admin.py         # GET/POST /api/admin/pending-providers
└── scrapers/
    ├── __init__.py      # scrape(url), scrape_event_all(url), detect_provider(url)
    ├── base.py          # ScrapedResult dataclass, MultipleMatchesError
    ├── utils.py         # normalize_time, normalize_rank, split_athlete_name
    ├── klikego.py       # klikego.com — _detect_event_type(heat, slug)
    ├── breizhchrono.py  # resultats.breizhchrono.com — multi-heat auto-discovery
    ├── wiclax.py        # wiclax-results.com / chronosmetron.com — lit attribut p= par athlète
    ├── timepulse.py     # timepulse.fr
    ├── prolivesport.py  # prolivesport.fr
    ├── sportinnovation.py
    └── playwright_fallback.py
```

---

## Architecture frontend

```
frontend/src/
├── api/client.js        # api.scrape(), api.saveResult(), api.listResults(), api.importEventStream()
├── constants.js         # EVENT_TYPE_LABELS, EVENT_TYPE_OPTIONS
└── components/
    ├── ScrapeForm.jsx   # Formulaire d'ajout (scraping + saisie manuelle)
    ├── ResultsList.jsx  # Liste paginée avec filtres
    ├── ResultCard.jsx   # Carte résultat individuel
    ├── ClubView.jsx     # Vue club TCN (stats, meilleurs temps, filtres)
    ├── DashboardView.jsx
    ├── EventGroupList.jsx
    ├── EventHeatmap.jsx # Carte Leaflet des épreuves
    ├── ResultsFeed.jsx
    └── AdminView.jsx
```

---

## Modèle de données — table `results`

```
id, source_url, provider, athlete_name, athlete_firstname,
club, category, gender, bib_number,
event_name, event_date, event_type,
rank_overall, rank_category, rank_gender,
total_time, swim_time, t1_time, bike_time, t2_time, run_time,
is_relay, raw_data, scraped_at
```

**Clé de déduplication :** `(bib_number, event_name, event_type)`
Les dossards ne sont uniques que par discipline — un même dossard peut exister dans deux heats différents du même événement.

---

## Types d'épreuves (`event_type`)

```
triathlon-s / triathlon-m / triathlon-l / triathlon-xl / triathlon
duathlon-xs / duathlon-s / duathlon-m / duathlon-l / duathlon
swimrun-s / swimrun-m / swimrun-l / swimrun
aquathlon / aquarun / bike-run
```

---

## Comportement des scrapers

### Wiclax / ChronoSmetron
- Format XML `.clax` contenant tous les participants
- Attribut `p=` sur chaque élément `E` donne la discipline (`"Triathlon M"`, `"Relais S"`, etc.)
- `scrape_event_all` : strip le paramètre `B=` de la source URL (B = sélecteur athlète, pas le dossard)

### Breizh Chrono / Klikego
- URL format : `/resultats-courses/{slug}-{event_id}/{heat}`
- `scrape_event_all` sans heat → découverte automatique de tous les heats depuis la page racine
- `scrape_event_all` avec heat → import uniquement ce heat
- Paramètre de recherche : `search=` (API) ou `query=` (URL frontend BC)
- Le `heat` détermine le type d'épreuve — le `slug` est ignoré pour la détection sport (évite les faux positifs ex: "triathlon-swimrun-dinard" → swimrun)

---

## Filtrage TCN

Le filtre club reconnaît : `nantais`, `TCN`, `tri club nant`, `triathlon club nant` (insensible à la casse).

---

## Tests

```powershell
# Tests unitaires (rapides, pas de réseau)
cd backend
.venv\Scripts\pytest.exe -m "not integration"

# Tests avec réseau
.venv\Scripts\pytest.exe -m integration

# E2E Playwright (long ~20-30 min)
cd tests/e2e
npm test
```

---

## Tests de fiabilité — Données TCN

### Objectif
Tester toutes les entrées du formulaire d'inscription des dossards TCN pour vérifier la fiabilité
du scraping sur l'ensemble des compétitions réelles soumises par les membres.

### Source de données
- Fichier : `.claude/data/Copie de Enregistrement des Dossards TCN (réponses).xlsx`
- **Ce fichier contient des données personnelles (noms, prénoms) — il ne doit JAMAIS être commité**
- Il est couvert par le `.gitignore` via la règle `.claude/`

### Règles de confidentialité — IMPÉRATIVES
- Ne jamais commiter : le xlsx, `xlsx_urls.json`, `providers.json`, tout fichier contenant des noms ou dossards
- Les tests E2E utilisent **uniquement les URLs d'événements** (données publiques), sans paramètres `search=` ni `query=` ni `B=` (qui révèlent une identité)
- Le rapport de fiabilité ne contient que des statistiques agrégées — aucun nom d'athlète
- Fichiers gitignorés contenant des données sensibles :
  - `backend/xlsx_urls.json`
  - `tests/e2e/fixtures/providers.json`
  - `*.xlsx`, `audit_report.md`

### Pipeline (à exécuter localement uniquement)

```powershell
# Étape 1 — Extraire les URLs du xlsx
cd backend
.venv\Scripts\python.exe extract_xlsx_urls.py
# → backend/xlsx_urls.json (gitignored) — 790 URLs dont 171 utilisables

# Étape 2 — Générer le fixture anonymisé (strip noms, dossards, params personnels)
.venv\Scripts\python.exe generate_test_fixtures.py
# → tests/e2e/fixtures/reliability_urls.json (gitignored) — 171 event URLs

# Étape 3 — Lancer le check de fiabilité (Python direct, pas de navigateur)
.venv\Scripts\python.exe reliability_check.py
# ou avec options :
.venv\Scripts\python.exe reliability_check.py --provider klikego --limit 10
.venv\Scripts\python.exe reliability_check.py --workers 6 --timeout 90
# → backend/reliability_report.md + reliability_report.json (gitignored)
```

### Pourquoi Python direct plutôt que Playwright E2E
Le scraping étant côté backend, tester via `scrape_event_all()` directement est :
- **10× plus rapide** (pas d'overhead navigateur)
- **Plus précis** (erreurs backend détaillées)
- **Parallélisable** (`--workers N`)

Les tests E2E Playwright restent utiles pour valider le parcours UI complet.

### Test de régression pagination BC

BC expose une page `page=` (vide) contenant des athletes absents des pages numérotées.
Le bug : notre import pagine `page=1,2,3...` et rate ces athletes (ex: DUPONT bib 244 sur swimrun-court-solo).
Le fix : `_import_one_heat` commence maintenant par `page=` avant de paginer.

Regression test dédié :
```powershell
# Script Python — vérifie chaque URL BC du fixture
cd backend
.venv\Scripts\python.exe bc_pagination_check.py
# → bc_pagination_report.json (gitignored)

# E2E Playwright — test smoke + toutes URLs BC
cd tests/e2e
npx playwright test bc-pagination.spec.js
```

### Format du rapport (`reliability_report.md`)
- Score global en % (ex: 87.1% — 149/171)
- Tableau par provider : OK / Erreurs / Taux
- Providers à surveiller (taux < 80% signalé ⚠)
- Liste des URLs en erreur avec message d'erreur (pas de noms d'athlètes)

### Données de la fixture (état initial)
- 171 URLs d'événements uniques extraites du xlsx TCN
- Par provider : klikego 67, wiclax 46, prolivesport 13, sportinnovation 14, timepulse 17, breizhchrono 14
- Exclus : breizhchrono_live (48), breizhchrono_dead/detail (87), unknown

---

## Reset base Supabase

```python
# backend/.venv/Scripts/python.exe
from database import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text("DELETE FROM results"))
    conn.commit()
```
