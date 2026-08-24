# Gestion des statuts DNS / DNF / DSQ — design (2026-06-08)

## Problème

À l'import d'épreuve, les non-finishers (abandons, non-partants, disqualifiés)
sont aujourd'hui **silencieusement perdus** :

- L'infra (`mapping.derive_status`) ne sait dériver que `finisher` / `DNF` par
  heuristique sur la présence d'un temps total.
- prolivesport **filtre** explicitement les non-finishers (`_is_finisher`) →
  ils n'apparaissent jamais dans les résultats importés.

On veut **conserver** ces participants avec un statut sportif explicite plutôt
que de les jeter. Le modèle le permet déjà : `Participation.status`
(`finisher` / DNF / DNS, colonne présente dès la migration initiale
`e4211f35a275_initial_schema.py`).

## Périmètre

**Inclus :** infra commune (`ScrapedResult` + `mapping.derive_status`) et le
provider **prolivesport** (seul à filtrer activement, et qui expose les champs
de statut nécessaires).

**Exclus :**
- Pas de nouvelle migration Alembic — la colonne `status` existe déjà.
- Pas de front (frontend-v2 pas encore codé).
- Pas de saisie manuelle de statut (`ParticipationCreate` inchangé).
- Les 5 autres providers gardent leur comportement actuel (cf. compatibilité).

## Vocabulaire des statuts

Quatre valeurs : `finisher`, `DNF` (abandon), `DNS` (non-partant), `DSQ`
(disqualifié). Centralisées comme constantes pour éviter les chaînes magiques.

## 1. Infra commune

### `ScrapedResult` (`app/scrapers/base.py`)

Nouveau champ : `status: str = ""`. Vide = « le scraper ne se prononce pas » →
l'infra retombe sur l'heuristique. Un scraper qui sait (prolivesport) le
renseigne explicitement.

### `mapping.derive_status` (`app/services/mapping.py`)

```python
def derive_status(scraped: ScrapedResult) -> str:
    """Statut sportif. Respecte le statut explicite du scraper s'il existe,
    sinon retombe sur l'heuristique (finisher si temps total, sinon DNF)."""
    if scraped.status:
        return scraped.status
    return "finisher" if scraped.total_time else "DNF"
```

→ **Comportement des 5 autres providers strictement inchangé** : ils ne posent
pas `status`, donc l'heuristique actuelle s'applique comme avant.

## 2. prolivesport (`app/scrapers/prolivesport.py`)

### Nouveau helper `_derive_status(athlete)`

Remplace `_is_finisher` (qui ne servait qu'à filtrer). Lit les champs distincts
de l'API (`dsq`, `dnf`, `time`) — le champ `dns` est ignoré car non fiable
(`dns="O"` est posé sur des finishers).

```python
def _derive_status(athlete: dict) -> str:
    if (athlete.get("dsq") or "").strip().upper() == "O":
        return "DSQ"
    if (athlete.get("dnf") or "").strip().upper() == "O":
        return "DNF"
    t = (athlete.get("time") or "").strip()
    if t and t != "00:00:00":
        return "finisher"
    return "DNS"
```

### `_parse_athlete`

- Pose `result.status = _derive_status(athlete)`.
- Pour un **non-finisher** (`status != "finisher"`) :
  - **vide `total_time`** (sinon `normalize_time("00:00:00")` → `"00:00:00"`,
    un temps bidon),
  - **annule les rangs** (`rank_overall/rank_gender/rank_category = None`)
    car l'API renvoie des sentinelles (99991/99992) pour les non-classés.
  - Les splits suivent la même logique qu'aujourd'hui (déjà filtrés sur
    temps non nul → naturellement vides pour un non-finisher).

### `scrape_event_all`

Supprime le filtre `if _is_finisher(a)` : **tous** les athlètes sont renvoyés,
chacun porteur de son statut.

## 3. Tests (TDD)

### Unitaires (sans réseau)

`tests/test_prolivesport.py` :
- `_derive_status` : 4 cas (DSQ, DNF, finisher avec temps, DNS sans temps).
- `_parse_athlete` finisher : temps + rangs conservés, `status == "finisher"`.
- `_parse_athlete` DNS/DNF : `total_time == ""`, rangs `None`, statut correct.

`tests/test_services/test_mapping.py` :
- `derive_status` respecte un `status` explicite.
- `derive_status` retombe sur l'heuristique quand `status == ""`.

### Intégration (réseau réel, marker `integration`)

`tests/test_integration_scrapers.py` :
- prolivesport renvoie désormais finishers **+** non-finishers ; au moins un
  résultat avec `status != "finisher"`, et au moins un `finisher`.

## Compatibilité & risques

- **Pas de régression** sur les autres providers (heuristique préservée via
  `status == ""`).
- **Import** : `import_service` écrit déjà `status` via `participation_fields`
  → les non-finishers seront stockés avec leur statut, sans temps ni rang.
- **Doublons** : la contrainte `UNIQUE(course_id, bib_number)` est inchangée ;
  un non-finisher a bien un dossard → pas de collision nouvelle.
- **Stats** : `stats_service` devra à terme distinguer finishers/non-finishers,
  mais c'est **hors périmètre** ici (on se contente de ne plus perdre la donnée).
