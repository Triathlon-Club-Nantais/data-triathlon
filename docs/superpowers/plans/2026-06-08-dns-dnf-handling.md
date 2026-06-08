# Gestion des statuts DNS / DNF / DSQ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conserver les non-finishers (DNF/DNS/DSQ) à l'import d'épreuve avec un statut sportif explicite, au lieu de les jeter silencieusement.

**Architecture :** Deux niveaux. (1) Infra commune : `ScrapedResult` gagne un champ `status`, et `mapping.derive_status` respecte un statut explicite posé par un scraper, sinon retombe sur l'heuristique actuelle (donc les 5 autres providers ne changent pas). (2) prolivesport : un helper `_derive_status` lit les champs `dsq`/`dnf`/`time` de l'API, `_parse_athlete` pose le statut (et purge temps/rangs des non-finishers), et `scrape_event_all` ne filtre plus les non-finishers.

**Tech Stack :** Python 3.11+, pytest, ruff. Pas de migration Alembic (la colonne `Participation.status` existe déjà).

---

## File Structure

| Fichier | Rôle | Action |
|---------|------|--------|
| `backend-v2/app/scrapers/base.py` | dataclass `ScrapedResult` + constantes de statut partagées | Modifier |
| `backend-v2/app/services/mapping.py` | `derive_status` respecte le statut explicite | Modifier |
| `backend-v2/app/scrapers/prolivesport.py` | `_derive_status`, `_parse_athlete`, `scrape_event_all` | Modifier |
| `backend-v2/tests/test_prolivesport.py` | tests unitaires prolivesport | Modifier |
| `backend-v2/tests/test_services/test_mapping.py` | tests unitaires mapping | Modifier |
| `backend-v2/tests/test_integration_scrapers.py` | test réseau réel prolivesport | Modifier |

**Choix de l'emplacement des constantes :** elles vivent dans `app/scrapers/base.py`. C'est la couche la plus basse, déjà importée à la fois par `prolivesport.py` (`from .base import ...`) et par `mapping.py` (`from app.scrapers.base import ScrapedResult`). Y placer les constantes évite toute violation de couches (un scraper ne doit pas importer depuis `app/models`).

**Toutes les commandes ci-dessous s'exécutent depuis `backend-v2/`, venv activé.**

---

### Task 1 : Constantes de statut + champ `ScrapedResult.status`

**Files:**
- Modify: `backend-v2/app/scrapers/base.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à la fin de `backend-v2/tests/test_prolivesport.py` :

```python
# ---------------------------------------------------------------------------
# Constantes de statut + champ ScrapedResult.status
# ---------------------------------------------------------------------------

def test_status_constants_values():
    from app.scrapers.base import (
        STATUS_DNF,
        STATUS_DNS,
        STATUS_DSQ,
        STATUS_FINISHER,
    )
    assert STATUS_FINISHER == "finisher"
    assert STATUS_DNF == "DNF"
    assert STATUS_DNS == "DNS"
    assert STATUS_DSQ == "DSQ"


def test_scraped_result_status_defaults_empty():
    from app.scrapers.base import ScrapedResult
    r = ScrapedResult(source_url="http://x", provider="prolivesport")
    assert r.status == ""
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `pytest tests/test_prolivesport.py::test_status_constants_values tests/test_prolivesport.py::test_scraped_result_status_defaults_empty -v`
Expected : FAIL avec `ImportError: cannot import name 'STATUS_FINISHER'`.

- [ ] **Step 3 : Implémenter**

Dans `backend-v2/app/scrapers/base.py`, ajouter les constantes avant la dataclass et le champ `status` dans la dataclass.

Après les imports (avant `@dataclass`) :

```python
# Statuts sportifs d'une participation. Centralisés ici (couche la plus basse,
# importée par les scrapers ET par services/mapping) pour éviter les chaînes
# magiques disséminées.
STATUS_FINISHER = "finisher"
STATUS_DNF = "DNF"  # abandon (Did Not Finish)
STATUS_DNS = "DNS"  # non-partant (Did Not Start)
STATUS_DSQ = "DSQ"  # disqualifié
```

Dans la dataclass `ScrapedResult`, ajouter le champ juste après `is_relay` (avant `raw_data`) :

```python
    is_relay: bool = False
    # "" = le scraper ne se prononce pas → l'infra retombe sur l'heuristique.
    # Un scraper qui sait (prolivesport) le renseigne explicitement.
    status: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run : `pytest tests/test_prolivesport.py::test_status_constants_values tests/test_prolivesport.py::test_scraped_result_status_defaults_empty -v`
Expected : PASS (2 passed).

- [ ] **Step 5 : Commit**

```bash
git add app/scrapers/base.py tests/test_prolivesport.py
git commit -m "feat(scrapers): ajoute le champ status à ScrapedResult + constantes de statut"
```

---

### Task 2 : `mapping.derive_status` respecte le statut explicite

**Files:**
- Modify: `backend-v2/app/services/mapping.py`
- Modify: `backend-v2/tests/test_services/test_mapping.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Dans `backend-v2/tests/test_services/test_mapping.py`, remplacer la fonction existante `test_derive_status` (lignes 43-45) par :

```python
def test_derive_status_heuristic_finisher():
    # Pas de status explicite + temps total → finisher (heuristique).
    assert mapping.derive_status(_scraped(total_time="01:59:00")) == "finisher"


def test_derive_status_heuristic_dnf():
    # Pas de status explicite + pas de temps → DNF (heuristique).
    assert mapping.derive_status(_scraped()) == "DNF"


def test_derive_status_respects_explicit_status():
    # Un status posé par le scraper prime sur l'heuristique, même contre le temps.
    assert mapping.derive_status(_scraped(status="DSQ", total_time="01:59:00")) == "DSQ"
    assert mapping.derive_status(_scraped(status="DNS")) == "DNS"
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `pytest tests/test_services/test_mapping.py -k derive_status -v`
Expected : `test_derive_status_respects_explicit_status` FAIL (renvoie `"finisher"` au lieu de `"DSQ"`).

- [ ] **Step 3 : Implémenter**

Dans `backend-v2/app/services/mapping.py`, modifier l'import en tête de fichier :

```python
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER, ScrapedResult
```

Puis remplacer `derive_status` (lignes 57-59) par :

```python
def derive_status(scraped: ScrapedResult) -> str:
    """Statut sportif. Respecte le statut explicite du scraper s'il existe,
    sinon retombe sur l'heuristique (finisher si temps total, sinon DNF)."""
    if scraped.status:
        return scraped.status
    return STATUS_FINISHER if scraped.total_time else STATUS_DNF
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run : `pytest tests/test_services/test_mapping.py -v`
Expected : PASS (tous les tests du fichier passent).

- [ ] **Step 5 : Commit**

```bash
git add app/services/mapping.py tests/test_services/test_mapping.py
git commit -m "feat(mapping): derive_status respecte le statut explicite d'un scraper"
```

---

### Task 3 : Helper `_derive_status` dans prolivesport

**Files:**
- Modify: `backend-v2/app/scrapers/prolivesport.py`
- Modify: `backend-v2/tests/test_prolivesport.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Dans `backend-v2/tests/test_prolivesport.py`, remplacer le bloc `_is_finisher` (lignes 144-163, des commentaires de section jusqu'à la fin du fichier) par :

```python
# ---------------------------------------------------------------------------
# _derive_status — lit dsq / dnf / time (le champ dns de l'API n'est pas fiable)
# ---------------------------------------------------------------------------

def test_derive_status_dsq():
    assert _derive_status({"dsq": "O", "time": "01:59:00"}) == "DSQ"


def test_derive_status_dnf():
    assert _derive_status({"dnf": "O", "time": ""}) == "DNF"


def test_derive_status_finisher_with_time():
    # Cas réel : dns="O" alors que l'athlète a fini → finisher (pas DNS).
    assert _derive_status({"time": "01:59:00", "dns": "O"}) == "finisher"


def test_derive_status_dns_no_time():
    assert _derive_status({"time": "", "dns": "O"}) == "DNS"


def test_derive_status_dns_zero_time():
    assert _derive_status({"time": "00:00:00"}) == "DNS"


def test_derive_status_dsq_takes_precedence_over_dnf():
    assert _derive_status({"dsq": "O", "dnf": "O", "time": ""}) == "DSQ"
```

Et mettre à jour le bloc d'import en tête du fichier (lignes 9-16) pour remplacer `_is_finisher` par `_derive_status` :

```python
from app.scrapers.prolivesport import (
    _build_split_map,
    _derive_status,
    _detect_event_type,
    _parse_athlete,
    _parse_url,
    _resolve_race,
)
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `pytest tests/test_prolivesport.py -k derive_status -v`
Expected : FAIL avec `ImportError: cannot import name '_derive_status'`.

- [ ] **Step 3 : Implémenter**

Dans `backend-v2/app/scrapers/prolivesport.py`, modifier l'import (ligne 25) :

```python
from .base import (
    STATUS_DNF,
    STATUS_DNS,
    STATUS_DSQ,
    STATUS_FINISHER,
    ScrapedResult,
)
```

Puis remplacer la fonction `_is_finisher` (lignes 221-227) par :

```python
def _derive_status(athlete: dict) -> str:
    """Statut sportif d'un athlète prolivesport, lu des champs distincts de l'API.

    Le champ `dns` est ignoré car non fiable (`dns="O"` est posé sur des
    finishers) ; on déduit DNS de l'absence de temps réel.
    """
    if (athlete.get("dsq") or "").strip().upper() == "O":
        return STATUS_DSQ
    if (athlete.get("dnf") or "").strip().upper() == "O":
        return STATUS_DNF
    t = (athlete.get("time") or "").strip()
    if t and t != "00:00:00":
        return STATUS_FINISHER
    return STATUS_DNS
```

> Note : `scrape_event_all` appelle encore `_is_finisher` à ce stade (ligne 251). Cet appel sera supprimé en Task 5. Pour garder le code exécutable entre-temps, **ne pas** retirer la ligne `if _is_finisher(a)` ici — mais `_is_finisher` n'existe plus. Donc, **dans cette même Task, à l'étape 3**, remplacer aussi temporairement le filtre de `scrape_event_all` pour qu'il n'appelle plus `_is_finisher` : voir le bloc ci-dessous (il sera finalisé en Task 5).

Remplacer la list-comprehension finale de `scrape_event_all` (lignes 248-252) par une version provisoire qui conserve seulement les finishers via le nouveau helper (comportement identique à avant, sans `_is_finisher`) :

```python
    return [
        _parse_athlete(a, split_map, url, event_name, event_type, event_date)
        for a in athletes
        if _derive_status(a) == STATUS_FINISHER
    ]
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run : `pytest tests/test_prolivesport.py -v`
Expected : PASS. Vérifier qu'aucun test ne référence encore `_is_finisher` (sinon ImportError).

- [ ] **Step 5 : Commit**

```bash
git add app/scrapers/prolivesport.py tests/test_prolivesport.py
git commit -m "refactor(prolivesport): remplace _is_finisher par _derive_status (DSQ/DNF/DNS/finisher)"
```

---

### Task 4 : `_parse_athlete` pose le statut et purge les non-finishers

**Files:**
- Modify: `backend-v2/app/scrapers/prolivesport.py`
- Modify: `backend-v2/tests/test_prolivesport.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Dans `backend-v2/tests/test_prolivesport.py`, ajouter après `test_parse_athlete_skips_zero_splits` :

```python
def test_parse_athlete_finisher_keeps_time_and_ranks_and_status():
    athlete = {
        "lastname": "Dupont", "firstname": "Jean", "number": "42",
        "rank": "5", "rankSex": "4", "rankCat": "1", "time": "01:59:00",
    }
    r = _parse_athlete(athlete, {}, "http://x", "E", "triathlon-s", None)
    assert r.status == "finisher"
    assert r.total_time == "01:59:00"
    assert r.rank_overall == 5
    assert r.rank_gender == 4
    assert r.rank_category == 1


def test_parse_athlete_dns_clears_time_and_ranks():
    # Non-partant : pas de temps. L'API renvoie des rangs sentinelles (99991/99992).
    athlete = {
        "lastname": "Martin", "number": "7",
        "rank": "99991", "rankSex": "99992", "rankCat": "99991", "time": "",
    }
    r = _parse_athlete(athlete, {}, "http://x", "E", "triathlon-s", None)
    assert r.status == "DNS"
    assert r.total_time == ""
    assert r.rank_overall is None
    assert r.rank_gender is None
    assert r.rank_category is None


def test_parse_athlete_dnf_clears_time_and_ranks():
    athlete = {
        "lastname": "Durand", "number": "8",
        "dnf": "O", "rank": "99991", "time": "00:00:00",
    }
    r = _parse_athlete(athlete, {}, "http://x", "E", "triathlon-s", None)
    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `pytest tests/test_prolivesport.py -k "parse_athlete and (finisher or clears)" -v`
Expected : FAIL — `r.status` est vide (le champ n'est pas posé) et les rangs sentinelles ne sont pas annulés.

- [ ] **Step 3 : Implémenter**

Dans `backend-v2/app/scrapers/prolivesport.py`, dans `_parse_athlete`, remplacer le bloc rangs + temps (lignes 83-86) :

```python
    result.rank_overall = normalize_rank(athlete.get("rank"))
    result.rank_gender = normalize_rank(athlete.get("rankSex"))
    result.rank_category = normalize_rank(athlete.get("rankCat"))
    result.total_time = normalize_time(athlete.get("time", ""))
```

par :

```python
    result.status = _derive_status(athlete)
    if result.status == STATUS_FINISHER:
        result.rank_overall = normalize_rank(athlete.get("rank"))
        result.rank_gender = normalize_rank(athlete.get("rankSex"))
        result.rank_category = normalize_rank(athlete.get("rankCat"))
        result.total_time = normalize_time(athlete.get("time", ""))
    # Non-finisher : on laisse total_time="" et les rangs à None (défauts de la
    # dataclass) — l'API renvoie des sentinelles (99991/99992) pour les non-classés.
```

> Les splits sont inchangés : la boucle suivante filtre déjà les temps nuls
> (`if not t or t == "00:00:00": continue`), donc un non-finisher (temps vides)
> produit naturellement des splits vides.

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run : `pytest tests/test_prolivesport.py -v`
Expected : PASS (incluant les anciens tests `test_parse_athlete_fields_and_splits` et `test_parse_athlete_skips_zero_splits`, dont les athlètes ont un temps réel → status finisher).

- [ ] **Step 5 : Commit**

```bash
git add app/scrapers/prolivesport.py tests/test_prolivesport.py
git commit -m "feat(prolivesport): _parse_athlete pose le statut et purge temps/rangs des non-finishers"
```

---

### Task 5 : `scrape_event_all` renvoie tous les athlètes

**Files:**
- Modify: `backend-v2/app/scrapers/prolivesport.py`

- [ ] **Step 1 : Vérifier le filtre provisoire actuel**

Run : `grep -n "_derive_status(a) == STATUS_FINISHER" app/scrapers/prolivesport.py`
Expected : une ligne dans `scrape_event_all` (le filtre provisoire posé en Task 3).

- [ ] **Step 2 : Implémenter — supprimer le filtre**

Dans `backend-v2/app/scrapers/prolivesport.py`, remplacer la list-comprehension finale de `scrape_event_all` par (chaque athlète est renvoyé, porteur de son statut) :

```python
    return [
        _parse_athlete(a, split_map, url, event_name, event_type, event_date)
        for a in athletes
    ]
```

- [ ] **Step 3 : Lancer la suite unitaire complète**

Run : `pytest -m "not integration" -v`
Expected : PASS (les 130 tests + nouveaux tests). Aucune référence résiduelle à `_is_finisher`.

- [ ] **Step 4 : Lint**

Run : `ruff check .`
Expected : `All checks passed!` (vérifie notamment qu'aucun import inutilisé ne subsiste, ex. `STATUS_DNS`/`STATUS_DSQ` doivent être utilisés par `_derive_status`).

- [ ] **Step 5 : Commit**

```bash
git add app/scrapers/prolivesport.py
git commit -m "feat(prolivesport): scrape_event_all conserve les non-finishers (DNF/DNS/DSQ)"
```

---

### Task 6 : Test d'intégration — finishers ET non-finishers

**Files:**
- Modify: `backend-v2/tests/test_integration_scrapers.py`

- [ ] **Step 1 : Écrire le test d'intégration**

Dans `backend-v2/tests/test_integration_scrapers.py`, ajouter à la fin du fichier :

```python
@pytest.mark.integration
def test_prolivesport_includes_non_finishers():
    """prolivesport renvoie désormais finishers ET non-finishers, chacun statué."""
    url = LIVE_URLS["prolivesport"]
    results = registry.scrape_event_all(url)
    assert results, "prolivesport : aucun participant renvoyé"
    statuses = {r.status for r in results}
    assert "finisher" in statuses, "prolivesport : aucun finisher"
    assert any(s != "finisher" for s in statuses), (
        f"prolivesport : aucun non-finisher (statuts vus : {statuses})"
    )
    # Un non-finisher n'a ni temps total ni rang.
    for r in results:
        if r.status != "finisher":
            assert not r.total_time, f"{r.status} avec un temps total : {r.total_time}"
            assert r.rank_overall is None, f"{r.status} avec un rang : {r.rank_overall}"
```

- [ ] **Step 2 : Lancer le test d'intégration (réseau réel)**

Run : `pytest tests/test_integration_scrapers.py::test_prolivesport_includes_non_finishers -m integration -v`
Expected : PASS. Si l'épreuve `1082` n'a plus de non-finisher exploitable, ajuster l'URL vers une épreuve documentée dans `docs/superpowers/specs/2026-06-08-scrapers-audit-report.md` ayant des abandons.

- [ ] **Step 3 : Vérifier la non-régression des autres providers**

Run : `pytest tests/test_integration_scrapers.py::test_scrape_event_all_live -m integration -v`
Expected : PASS pour les 6 providers (l'heuristique des 5 autres est préservée car ils ne posent pas `status`).

- [ ] **Step 4 : Commit**

```bash
git add tests/test_integration_scrapers.py
git commit -m "test(prolivesport): vérifie l'inclusion des non-finishers à l'import d'épreuve"
```

---

## Vérification finale

- [ ] `pytest -m "not integration"` → tous verts (suite unitaire CI).
- [ ] `ruff check .` → `All checks passed!`.
- [ ] `grep -rn "_is_finisher" backend-v2/` → aucun résultat (helper entièrement remplacé).
- [ ] `grep -rn '"finisher"\|"DNF"\|"DNS"\|"DSQ"' backend-v2/app/scrapers backend-v2/app/services` → seules occurrences = définitions des constantes dans `base.py` (pas de chaîne magique dispersée).
