# Plan — Simplifier, vérifier et améliorer les scrapers (backend-v2)

> Doc persistant à committer (convention projet) :
> `docs/superpowers/specs/2026-06-08-scrapers-simplif-audit.md`.
> Ce fichier `.claude/plans/...` n'est qu'un brouillon de travail (plan mode).

## Contexte

PR #6 (`feat/refactor-backend-architecture`) refond le backend en `backend-v2/`.
Dans les commentaires de la PR, @tjarrier (1) dresse une analyse par chronométreur,
(2) veut **simplifier le process en supprimant le scraping d'un athlète unique**,
(3) puis **vérifier que les scrapers marchent** avant de décider des améliorations.

Diagnostic de l'existant (`backend-v2/app/scrapers/`) :

| Provider | Détection (`registry.py`) | Technique actuelle | Tests |
|---|---|---|---|
| klikego | `klikego.com` | scraping HTML | ✅ |
| timepulse | `timepulse.fr` | **API XML** | ✅ |
| breizhchrono | `breizhchrono.com` | HTML (réutilise `klikego._parse_detail`) | ❌ |
| wiclax (+chronosmetron) | `wiclax-results.com`, `wiclax.com&G-Live`, `chronosmetron.com` | HTML/JSON | ❌ |
| prolivesport | `prolivesport.fr` | **API JSON** (token `AUTH_PLSWS_V2`) | ❌ |
| sportinnovation | `sportinnovation.fr` | HTML table **+** API JSON | ❌ |
| playwright | fallback | navigateur headless | ❌ |

**Constats :** aucun moyen automatisé de vérifier le scraping sur le vrai site
(marker `integration` défini mais inutilisé) ; 4 providers sur 6 ont 0 test ;
plusieurs « améliorations » demandées sont déjà faites (prolivesport/timepulse =
API). D'où l'ordre **simplifier → vérifier → améliorer**.

---

## Phase 0 — Simplifier : retirer le scraping « athlète unique »

But : il ne reste qu'**une seule voie de scraping**, l'import d'épreuve complète
(`scrape_event_all`). On supprime le chemin URL→athlète unique.

**Point clé à préserver :** `_parse_detail` (klikego.py:159 ; réutilisé par
breizhchrono.py:209) et `_parse_athlete` (prolivesport.py:71) sont appelés *dans*
`scrape_event_all` pour enrichir les splits par athlète. **Ces helpers restent.**
On ne retire que les *points d'entrée* athlète-unique.

### À supprimer
- `app/scrapers/registry.py` : la méthode `scrape()` de `ScraperProtocol` et de
  chaque `*Provider`, ainsi que la fonction module `scrape(url, bib)`.
- Chaque module provider : la fonction publique `def scrape(url, bib=...)`
  (klikego:50, breizhchrono:214, wiclax:308, timepulse:249, prolivesport:185,
  sportinnovation:351). **Garder** tous les `_parse_*` internes.
- `app/scrapers/base.py` : `MultipleMatchesError` (levée uniquement par la
  recherche par nom de l'athlète unique) + ses imports/usages dans les providers.
- `app/scrapers/__init__.py` : retirer les exports `scrape` et `MultipleMatchesError`.
- API `app/api/v1/scrape.py` : retirer `POST /scrape` (`scrape_athlete`).
  **Garder** `POST /scrape/event`, `POST /scrape/event/stream`, `GET /scrape/detect`.
- `app/services/scrape_service.py` : retirer `preview()` et la gestion
  `ScraperMultipleMatches`. **Garder** `save_one()` (réutilisé par l'import épreuve
  ET la saisie manuelle).
- `app/schemas/scrape.py` : retirer `ScrapedPreview` ; retirer le champ `bib` de
  `ScrapeRequest` (plus utilisé par les endpoints épreuve).

### À conserver explicitement (décisions @tjarrier)
- **Saisie manuelle** d'un résultat unique : `POST /participations` + `_to_scraped`
  + `save_one` → **reste** (ce n'est pas du scraping ; fallback provider non supporté).
- **`GET /scrape/detect`** (détection provider) → **reste**.

### Tests
- Supprimer/ajuster les tests asservis au chemin unique (assertions
  `MultipleMatchesError`, appels au `scrape()` public).
- **Garder** les tests des helpers de parsing (`_parse_detail`, `_parse_search_row`,
  `_detect_event_type`) car ils servent l'import d'épreuve.
- Cible : `pytest -m "not integration"` reste vert.

---

## Phase 1 — Vérifier (harnais de diagnostic + tests integration)

Après simplification, on ne teste plus qu'une voie par provider : `scrape_event_all`.

### 1a. Script `backend-v2/scripts/audit_scrapers.py` (nouveau)
Généralise le patron de `backend/scripts/audit.py` (v1) à **tous** les providers via
`app.scrapers.registry.detect_provider / scrape_event_all`.
- Table `FIXTURE_URLS` : **1 URL d'épreuve réelle par provider** (fournie par
  @tjarrier, événements passés/stables — cf. Prérequis).
- Par entrée : appelle `scrape_event_all`, mesure le temps, capture l'exception,
  et **valide la qualité** (critères repris de `backend/scripts/audit.py`) :
  nb de participants, `athlete_name`/`total_time` peuplés, `event_type` détecté,
  cohérence des splits, rangs.
- Sortie : **rapport Markdown** (tableau provider → OK/KO + champs) + option `--json`.
  CLI : `--provider <nom|all>`, `--out`, `--json`. Sans dépendance pytest.

### 1b. Tests `backend-v2/tests/test_integration_scrapers.py` (nouveau)
- Un test `@pytest.mark.integration` par provider (sauf playwright) tapant l'URL
  réelle de `FIXTURE_URLS` et assertant les champs clés non vides sur ≥1 participant.
- Hors CI par défaut (`pytest -m "not integration"`). Lancement manuel : `pytest -m integration`.

### 1c. Tests unitaires manquants (sans réseau)
Sur le modèle de `test_klikego.py` (fixtures HTML/JSON/XML minimales → on teste les
`_parse_*`), couvrir **wiclax, breizhchrono, prolivesport, sportinnovation** (0 test).

**Livrable Phase 1 :** rapport d'audit (tableau d'état) = base de décision Phase 2.

---

## Phase 2 — Améliorer (décidée après le rapport Phase 1)

Backlog candidat, priorisé selon les faits :
- **prolivesport / timepulse** : valider que l'API (token `AUTH_PLSWS_V2`, XML)
  répond encore. (déjà API)
- **sportinnovation** : mesurer l'impact du **changement d'affichage 2026** sur le
  chemin HTML ; privilégier le chemin **API JSON**.
- **breizhchrono** : évaluer l'**export Excel xlsx** comme source primaire (plus
  robuste que le HTML partagé klikego) → migrer si concluant.
- **chronosmetron** (via `wiclax`) : évaluer l'**export Excel xlsx** ; éventuel
  provider dédié.
- **klikego** : garder le scraping.

> Détail Phase 2 spécifié une fois le rapport Phase 1 connu.

---

## Fichiers concernés
- **Modifiés (Phase 0)** : `app/scrapers/registry.py`, `app/scrapers/base.py`,
  `app/scrapers/__init__.py`, les 6 modules providers (retrait du `def scrape`),
  `app/api/v1/scrape.py`, `app/services/scrape_service.py`, `app/schemas/scrape.py`,
  tests impactés.
- **Nouveaux (Phase 1)** : `scripts/audit_scrapers.py`,
  `tests/test_integration_scrapers.py`, `tests/test_{wiclax,breizhchrono,prolivesport,sportinnovation}.py`.
- **Réutilisé** : patron de `backend/scripts/audit.py` (v1).

## Prérequis
@tjarrier fournit **1 URL d'épreuve réelle par provider** (événements passés/stables)
pour `FIXTURE_URLS`.

## Vérification (end-to-end)
```bash
cd backend-v2 && source <venv>/bin/activate
pytest -m "not integration"        # Phase 0 : suite verte après suppressions
python scripts/audit_scrapers.py --provider all --json   # Phase 1 : rapport d'état
pytest -m integration              # Phase 1 : vérif réseau réel par provider
ruff check .
uvicorn app.main:app --reload --port 8001  # /docs : plus de POST /scrape, /scrape/event* + /scrape/detect OK
```
Succès : (Phase 0) `not integration` vert + plus aucune référence au scraping
athlète-unique ; (Phase 1) rapport classant chaque provider OK/KO.
