# Statuts DNS/DNF/DSQ — extension multi-provider — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fiabiliser le statut sportif (finisher / DNF / DNS / DSQ) des 5 providers restants de `backend-v2` (Klikego, Breizh Chrono, TimePulse, Wiclax, Sport Innovation), en conservant les non-finishers et en ne posant un statut précis que si le provider l'expose explicitement.

**Architecture :** Un helper partagé `derive_status_from_label` dans `app/scrapers/utils.py` traduit un label brut en constante `STATUS_*`. Chaque scraper l'appelle à son point d'extraction naturel ; à défaut de marqueur explicite il laisse `status=""` et l'infra (`services/mapping.derive_status`, **inchangée**) retombe sur son heuristique actuelle. Fix structurel TimePulse : ne plus jeter les athlètes sans balise `<R>`.

**Tech Stack :** Python 3.11+, pytest, httpx + BeautifulSoup/lxml + `xml.etree.ElementTree`, ruff. Tests unitaires sans réseau (fixtures synthétiques + `monkeypatch`) ; réseau réel isolé sous le marker `integration`.

---

## Contexte indispensable (lire avant de coder)

- **Cible exclusive : `backend-v2/`.** Toutes les commandes s'exécutent depuis `backend-v2/`, venv activé. `backend/` (v1) est déprécié — n'y toucher à rien.
- **Constantes de statut** déjà définies dans `app/scrapers/base.py` :
  `STATUS_FINISHER = "finisher"`, `STATUS_DNF = "DNF"`, `STATUS_DNS = "DNS"`,
  `STATUS_DSQ = "DSQ"`. Champ `ScrapedResult.status` (défaut `""`).
- **`services/mapping.derive_status` reste inchangé.** Sa logique : si
  `scraped.status` non vide → on le respecte ; sinon heuristique
  (`finisher` si `total_time`, sinon `DNF`). Donc poser `status=""` = comportement
  identique à aujourd'hui (zéro régression).
- **Hygiène non-finisher** (calquée sur prolivesport, déjà implémenté) : dès qu'un
  statut **non-finisher explicite** (`DNF`/`DNS`/`DSQ`) est posé, on vide
  `total_time` et on met les rangs à `None` (éviter des temps/rangs bidons).
- **Pas de migration Alembic** (colonne `Participation.status` déjà présente).
- **Référence (déjà fait) :** `app/scrapers/prolivesport.py:231-244` (`_derive_status`)
  et `app/scrapers/prolivesport.py:89-96` (hygiène non-finisher). Le présent plan
  reproduit le même contrat pour les autres providers.
- **Étape de découverte :** le nom exact de l'attribut/colonne portant le statut
  dans chaque payload réel est *inconnu*. Chaque tâche provider commence par une
  étape de découverte (réseau réel) ; le code d'extraction écrit ici lit un
  **emplacement candidat** précis (encodé dans les fixtures de test) qu'il faudra
  **confirmer/corriger** à la lumière du payload réel. Les tests synthétiques
  passent de façon déterministe quoi qu'il arrive ; seul l'emplacement réel lu en
  prod dépend de la découverte.

Commandes de référence :

```bash
cd backend-v2                       # toujours
pytest -m "not integration" -q      # suite unitaire (défaut CI)
pytest -m integration -q            # réseau réel (scrapers)
ruff check .                        # lint
python scripts/audit_scrapers.py --provider <nom>   # inspecter un provider réel
```

---

## File Structure

| Fichier | Responsabilité | Action |
|---------|----------------|--------|
| `app/scrapers/utils.py` | Helper partagé `derive_status_from_label` + table de jetons | Modifier |
| `app/scrapers/timepulse.py` | Fix structurel (conserver non-finishers) + extraction statut | Modifier |
| `app/scrapers/wiclax.py` | Extraction statut explicite + hygiène | Modifier |
| `app/scrapers/klikego.py` | Extraction statut dans la ligne de listing | Modifier |
| `app/scrapers/breizhchrono.py` | Hérite de klikego (vérifier, ne pas dupliquer) | Vérifier |
| `app/scrapers/sportinnovation.py` | Extraction statut (HTML + API JSON) | Modifier |
| `tests/test_scrapers_utils.py` | Tests du helper partagé | Créer |
| `tests/test_timepulse.py` | Test « non-finisher conservé » + statut explicite | Modifier |
| `tests/test_wiclax.py` | Test statut explicite / vide | Modifier |
| `tests/test_klikego.py` | Test statut dans la ligne de listing | Modifier |
| `tests/test_breizhchrono.py` | Test héritage du parseur klikego | Modifier |
| `tests/test_sportinnovation.py` | Test statut HTML + API | Modifier |
| `tests/test_integration_scrapers.py` | Conservation non-finishers (best-effort) | Modifier |

---

## Task 1 : Helper partagé `derive_status_from_label`

**Files:**
- Modify: `app/scrapers/utils.py`
- Test: `tests/test_scrapers_utils.py` (créer)

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_scrapers_utils.py` :

```python
"""Tests unitaires pour le helper de reconnaissance de statut (sans réseau)."""
import pytest

from app.scrapers.utils import derive_status_from_label


@pytest.mark.parametrize("label,expected", [
    # Disqualification (FR/EN, casse/ponctuation/accents)
    ("DSQ", "DSQ"),
    ("Disqualifié", "DSQ"),
    ("disqualified", "DSQ"),
    ("Disq.", "DSQ"),
    # Abandon
    ("DNF", "DNF"),
    ("Abandon", "DNF"),
    ("ABD", "DNF"),
    ("Ab.", "DNF"),
    # Non-partant
    ("DNS", "DNS"),
    ("Non partant", "DNS"),
    ("NON PARTANT", "DNS"),
    ("Forfait", "DNS"),
    ("NP", "DNS"),
    # Finisher (label positif explicite)
    ("Finisher", "finisher"),
    ("Classé", "finisher"),
])
def test_derive_status_from_label_recognized(label, expected):
    assert derive_status_from_label(label) == expected


@pytest.mark.parametrize("label", ["", "   ", "12e", "SEH", "blah", "01:23:45"])
def test_derive_status_from_label_unknown_returns_empty(label):
    assert derive_status_from_label(label) == ""
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `pytest tests/test_scrapers_utils.py -q`
Expected: FAIL avec `ImportError: cannot import name 'derive_status_from_label'`.

- [ ] **Step 3 : Implémenter le helper**

Dans `app/scrapers/utils.py`, ajouter l'import en tête (après `import re` / `from datetime import date as date_t`) :

```python
from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER
```

Puis, à la fin du fichier, ajouter :

```python
# Jetons de statut bruts (FR/EN) → constante STATUS_*. Comparés sur le label
# normalisé (minuscule, sans accents ni ponctuation). Table volontairement
# conservatrice : à compléter à la lumière des payloads réels (cf. découverte
# par provider). Un label non listé → "" → l'infra applique son heuristique.
_STATUS_TOKENS: dict[str, str] = {
    # Disqualification
    "dsq": STATUS_DSQ,
    "disq": STATUS_DSQ,
    "disqualifie": STATUS_DSQ,
    "disqualified": STATUS_DSQ,
    # Abandon (Did Not Finish)
    "dnf": STATUS_DNF,
    "abd": STATUS_DNF,
    "abandon": STATUS_DNF,
    "ab": STATUS_DNF,
    # Non-partant (Did Not Start)
    "dns": STATUS_DNS,
    "nonpartant": STATUS_DNS,
    "np": STATUS_DNS,
    "forfait": STATUS_DNS,
    "ff": STATUS_DNS,
    # Finisher — label positif explicite, utilisé seulement si un provider le pose
    "finisher": STATUS_FINISHER,
    "classe": STATUS_FINISHER,
    "fin": STATUS_FINISHER,
    "ok": STATUS_FINISHER,
}

_STATUS_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _normalize_label(label: str) -> str:
    """Minuscule, sans accents, ne garde que les caractères alphanumériques.

    'Non partant' → 'nonpartant' ; 'Disqualifié' → 'disqualifie'.
    """
    s = label.strip().lower().translate(_STATUS_ACCENTS)
    return re.sub(r"[^a-z0-9]", "", s)


def derive_status_from_label(label: str) -> str:
    """Traduit un label de statut brut en constante STATUS_* (ou "" si inconnu).

    "" (vide / non reconnu) est le défaut sûr : services/mapping.derive_status
    retombe alors sur son heuristique (finisher si temps total, sinon DNF),
    comportement identique à aujourd'hui. Comparaison sur le label normalisé →
    insensible à la casse, aux accents et à la ponctuation.
    """
    if not label:
        return ""
    return _STATUS_TOKENS.get(_normalize_label(label), "")
```

> Note : `base.py` n'importe pas `utils.py` (il ne dépend que de la stdlib) →
> pas de cycle d'import.

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `pytest tests/test_scrapers_utils.py -q`
Expected: PASS (tous les cas).

- [ ] **Step 5 : Lint + commit**

```bash
ruff check app/scrapers/utils.py tests/test_scrapers_utils.py
git add app/scrapers/utils.py tests/test_scrapers_utils.py
git commit -m "feat(scrapers): helper partagé derive_status_from_label (FR/EN)"
```

---

## Task 2 : TimePulse — conserver les non-finishers + statut explicite

**Files:**
- Modify: `app/scrapers/timepulse.py` (imports ; `scrape_event_all` ~270-310 ; nouveau helper `_extract_status`)
- Test: `tests/test_timepulse.py`

- [ ] **Step 0 : Découverte (réseau réel)**

Identifier comment TimePulse encode un non-finisher dans le XML. Confirmé par
l'audit : les athlètes sans `<R>` sont aujourd'hui *jetés* (seuls les finishers
remontent). Vérifier si un attribut de statut existe sur `<E>`/`<R>`.

```bash
python scripts/audit_scrapers.py --provider timepulse --out /tmp/tp.md
# Puis inspecter le XML brut d'une épreuve avec abandons :
python -c "from app.scrapers.timepulse import _fetch_xml; print(_fetch_xml('3232')[:4000])"
```

Noter les attributs présents sur `<E ...>` et `<R ...>`. Si un attribut de statut
existe (ex. `etat=`, `st=`), l'ajouter à `_STATUS_ATTRS` (Step 3). Sinon : le fix
structurel suffit (non-finisher conservé → statut heuristique `DNF`).

- [ ] **Step 1 : Écrire les tests qui échouent**

Dans `tests/test_timepulse.py`, ajouter à l'import existant `scrape_event_all` :

```python
from app.scrapers.timepulse import (
    _attrs,
    _compute_ranks,
    _detect_event_type,
    _find_tag,
    _parse_event_date,
    _parse_series,
    scrape_event_all,
)
```

Puis ajouter ces tests (le helper `make_xml` existe déjà dans le fichier) :

```python
def test_scrape_event_all_keeps_non_finisher(monkeypatch):
    """Un <E> sans <R> est désormais CONSERVÉ (régression du drop historique)."""
    xml = make_xml(
        athletes=[
            ("10", "ALPHA Jean", "SEH", "M", "p1"),   # finisher (a un <R>)
            ("20", "BETA Marie", "SEF", "F", "p1"),   # non-finisher (pas de <R>)
        ],
        results=[("10", "01:00:00", {"s0": "00:20:00"})],
    )
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    results = scrape_event_all("https://www.timepulse.fr/resultats/3090")
    by_bib = {r.bib_number: r for r in results}

    assert set(by_bib) == {"10", "20"}          # le non-finisher n'est plus jeté
    assert by_bib["10"].total_time == "01:00:00"
    assert by_bib["20"].total_time == ""        # pas de <R> → pas de temps
    assert by_bib["20"].rank_overall is None
    assert by_bib["20"].status == ""            # aucun marqueur → heuristique infra
    assert by_bib["20"].athlete_name == "BETA"
    assert by_bib["20"].athlete_firstname == "Marie"


def test_scrape_event_all_reads_explicit_status(monkeypatch):
    """Statut explicite sur <E> (attribut candidat etat=) → DNF + hygiène."""
    xml = make_xml(
        athletes=[("30", "GAMMA Paul", "SEH", "M", "p1")],
        results=[],
    ).replace('<E d="30"', '<E etat="Abandon" d="30"')
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    results = scrape_event_all("https://www.timepulse.fr/resultats/3090")
    assert results[0].status == "DNF"
    assert results[0].total_time == ""
    assert results[0].rank_overall is None
```

- [ ] **Step 2 : Lancer les tests, vérifier qu'ils échouent**

Run: `pytest tests/test_timepulse.py -k "non_finisher or explicit_status" -q`
Expected: FAIL — `test_scrape_event_all_keeps_non_finisher` ne renvoie que le bib `10` (le `20` est jeté par le `continue`).

- [ ] **Step 3 : Implémenter le fix structurel + extraction**

Dans `app/scrapers/timepulse.py` :

a) Élargir l'import `base` (ligne 22) :

```python
from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
```

b) Élargir l'import `utils` (ligne 23) :

```python
from .utils import (
    derive_status_from_label,
    normalize_time,
    parse_fr_date,
    split_athlete_name,
)
```

c) Ajouter, juste après les `_HEADERS`/`_DATA_API_URLS` (vers la ligne 35), la
liste des attributs candidats + le helper d'extraction :

```python
# Attributs susceptibles de porter un statut explicite (DNF/DNS/DSQ) dans le XML
# TimePulse. À confirmer/compléter à la découverte d'une épreuve réelle (§Step 0).
_STATUS_ATTRS = ("etat", "st", "status", "statut")


def _extract_status(ea: dict[str, str], ra: dict[str, str]) -> str:
    """Lit un statut explicite depuis les attributs E puis R ; "" sinon.

    Cherche l'un des attributs candidats (_STATUS_ATTRS) et le traduit via
    derive_status_from_label. Découverte : compléter _STATUS_ATTRS si le XML réel
    encode le statut sous un autre nom.
    """
    for attrs in (ra, ea):
        for name in _STATUS_ATTRS:
            val = attrs.get(name, "")
            if val:
                status = derive_status_from_label(val)
                if status:
                    return status
    return ""
```

d) Remplacer le cœur de la boucle dans `scrape_event_all`. Le bloc actuel
(lignes ~269-310) :

```python
        r_tag = _find_tag(xml, "R", "d", bib)
        if not r_tag:
            continue  # no result for this athlete (DNS/DNF)

        result = ScrapedResult(source_url=url, provider="timepulse", bib_number=bib)
        result.event_name = event_name
        result.event_date = event_date_val
        result.event_type = event_type

        full_name = ea.get("n", "")
        surname, firstname = split_athlete_name(full_name)
        result.athlete_name = surname
        result.athlete_firstname = firstname
        result.club = ea.get("c", "")
        result.gender = ea.get("x", "")
        result.category = ea.get("ca", "")

        ra = _attrs(r_tag)
        result.total_time = normalize_time(ra.get("t", ""))
        for key, field in series_map.items():
            t = normalize_time(ra.get(key, ""))
            if not t:
                continue
            if field == "swim" and not result.swim_time:
                result.swim_time = t
            elif field == "t1" and not result.t1_time:
                result.t1_time = t
            elif field == "bike" and not result.bike_time:
                result.bike_time = t
            elif field == "t2" and not result.t2_time:
                result.t2_time = t
            elif field == "run" and not result.run_time:
                result.run_time = t

        parcours = ea.get("p", "")
        if parcours and result.gender and result.category:
            ro, rg, rc = _compute_ranks(xml, bib, parcours, result.gender, result.category)
            result.rank_overall = ro
            result.rank_gender = rg
            result.rank_category = rc

        results.append(result)
```

…doit devenir (on construit toujours le résultat depuis `<E>`, et on ne remplit
temps/splits/rangs que pour un finisher avec `<R>`) :

```python
        result = ScrapedResult(source_url=url, provider="timepulse", bib_number=bib)
        result.event_name = event_name
        result.event_date = event_date_val
        result.event_type = event_type

        full_name = ea.get("n", "")
        surname, firstname = split_athlete_name(full_name)
        result.athlete_name = surname
        result.athlete_firstname = firstname
        result.club = ea.get("c", "")
        result.gender = ea.get("x", "")
        result.category = ea.get("ca", "")

        r_tag = _find_tag(xml, "R", "d", bib)
        ra = _attrs(r_tag) if r_tag else {}

        # Statut explicite éventuel (E puis R) ; "" → heuristique de l'infra.
        result.status = _extract_status(ea, ra)
        is_non_finisher = result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ)

        # Sans <R> (non-partant/abandon) OU statut non-finisher explicite : on
        # conserve l'athlète mais on laisse total_time="", splits vides, rangs None.
        if r_tag and not is_non_finisher:
            result.total_time = normalize_time(ra.get("t", ""))
            for key, field in series_map.items():
                t = normalize_time(ra.get(key, ""))
                if not t:
                    continue
                if field == "swim" and not result.swim_time:
                    result.swim_time = t
                elif field == "t1" and not result.t1_time:
                    result.t1_time = t
                elif field == "bike" and not result.bike_time:
                    result.bike_time = t
                elif field == "t2" and not result.t2_time:
                    result.t2_time = t
                elif field == "run" and not result.run_time:
                    result.run_time = t

            parcours = ea.get("p", "")
            if parcours and result.gender and result.category:
                ro, rg, rc = _compute_ranks(xml, bib, parcours, result.gender, result.category)
                result.rank_overall = ro
                result.rank_gender = rg
                result.rank_category = rc

        results.append(result)
```

- [ ] **Step 4 : Lancer les tests, vérifier qu'ils passent**

Run: `pytest tests/test_timepulse.py -q`
Expected: PASS (anciens + nouveaux). Le bib `20` est conservé, le `30` est DNF.

- [ ] **Step 5 : Lint + commit**

```bash
ruff check app/scrapers/timepulse.py tests/test_timepulse.py
git add app/scrapers/timepulse.py tests/test_timepulse.py
git commit -m "fix(timepulse): conserve les non-finishers (plus de drop sans <R>) + statut explicite"
```

---

## Task 3 : Wiclax — statut explicite + hygiène

**Files:**
- Modify: `app/scrapers/wiclax.py` (imports ; `_parse_competitor` ; branche E/R de `scrape_event_all`)
- Test: `tests/test_wiclax.py`

- [ ] **Step 0 : Découverte (réseau réel)**

Wiclax *conserve* déjà ses non-finishers (audit : 12 % sans temps), mais sans
statut explicite. Identifier un éventuel attribut de statut sur
`Competitor`/`Runner` ou sur l'élément `E`/`R`.

```bash
python scripts/audit_scrapers.py --provider wiclax --out /tmp/wx.md
python -c "from app.scrapers.wiclax import _fetch_clax; root,*_=_fetch_clax('https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/'); import xml.etree.ElementTree as ET; print(ET.tostring(list(root.iter('E'))[0]).decode()[:600] if list(root.iter('E')) else 'no E')"
```

Si un attribut de statut existe, l'ajouter à `_STATUS_ATTRS` (Step 3). Sinon :
les sans-temps restent `DNF` par heuristique (pas de régression).

- [ ] **Step 1 : Écrire les tests qui échouent**

Dans `tests/test_wiclax.py`, ajouter en tête (ou compléter les imports) :

```python
import xml.etree.ElementTree as ET

from app.scrapers.wiclax import _parse_competitor
```

Puis :

```python
def test_parse_competitor_explicit_status_dnf():
    """Attribut Status="Abandon" → DNF + hygiène (temps/rangs purgés)."""
    comp = ET.fromstring(
        '<Competitor Bib="5" Name="DUPONT" FirstName="Jean" '
        'Status="Abandon" Time="01:00:00" Rank="3"/>'
    )
    r = _parse_competitor(comp, "http://x", "Triathlon", "triathlon-s")
    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None


def test_parse_competitor_no_status_is_empty():
    """Sans marqueur → status="" et temps conservé (heuristique infra)."""
    comp = ET.fromstring(
        '<Competitor Bib="5" Name="DUPONT" FirstName="Jean" Time="01:00:00" Rank="3"/>'
    )
    r = _parse_competitor(comp, "http://x", "Triathlon", "triathlon-s")
    assert r.status == ""
    assert r.total_time == "01:00:00"
    assert r.rank_overall == 3
```

- [ ] **Step 2 : Lancer les tests, vérifier qu'ils échouent**

Run: `pytest tests/test_wiclax.py -k "status" -q`
Expected: FAIL — `r.status` vaut `""` au lieu de `"DNF"` et le temps n'est pas purgé.

- [ ] **Step 3 : Implémenter l'extraction + hygiène**

Dans `app/scrapers/wiclax.py` :

a) Élargir l'import `base` (ligne 16) :

```python
from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
```

b) Élargir l'import `utils` (ligne 17) :

```python
from .utils import (
    derive_status_from_label,
    normalize_rank,
    normalize_time,
    split_athlete_name,
)
```

c) Ajouter, juste avant `_parse_competitor` (vers la ligne 28), la liste candidate
et le helper :

```python
# Attributs susceptibles de porter un statut explicite. À confirmer/compléter à
# la découverte d'une épreuve réelle (cf. Step 0).
_STATUS_ATTRS = ("Status", "status", "State", "state", "Etat", "etat", "st")


def _competitor_status(comp) -> str:
    """Statut explicite lu des attributs d'un élément (Competitor ou E/R) ; "" sinon."""
    for name in _STATUS_ATTRS:
        val = comp.get(name)
        if val:
            status = derive_status_from_label(val)
            if status:
                return status
    return ""
```

d) À la fin de `_parse_competitor`, juste avant `result.raw_data = raw` /
`return result` (lignes ~94-95), insérer :

```python
    result.status = _competitor_status(comp)
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.total_time = ""
        result.rank_overall = None
        result.rank_category = None
        result.rank_gender = None
```

e) Dans `scrape_event_all`, branche format E/R (lignes ~324-328), remplacer :

```python
            # Timing from sibling R element
            result_elem = r_by_bib.get(bib)
            if result_elem is not None and not r.total_time:
                r.total_time = normalize_time(result_elem.get("t", ""))
                _fill_er_splits(result_elem, r, split_idx)
```

par (lecture du statut aussi depuis `<R>`, puis temps/splits seulement si finisher) :

```python
            # Timing from sibling R element
            result_elem = r_by_bib.get(bib)
            if result_elem is not None:
                if not r.status:
                    r.status = _competitor_status(result_elem)
                is_non_finisher = r.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ)
                if is_non_finisher:
                    r.total_time = ""
                    r.rank_overall = r.rank_category = r.rank_gender = None
                elif not r.total_time:
                    r.total_time = normalize_time(result_elem.get("t", ""))
                    _fill_er_splits(result_elem, r, split_idx)
```

- [ ] **Step 4 : Lancer les tests, vérifier qu'ils passent**

Run: `pytest tests/test_wiclax.py -q`
Expected: PASS (anciens + nouveaux).

- [ ] **Step 5 : Lint + commit**

```bash
ruff check app/scrapers/wiclax.py tests/test_wiclax.py
git add app/scrapers/wiclax.py tests/test_wiclax.py
git commit -m "feat(wiclax): lit le statut explicite (DNF/DNS/DSQ) + hygiène non-finisher"
```

---

## Task 4 : Klikego — statut dans la ligne de listing (Breizh hérite)

**Files:**
- Modify: `app/scrapers/klikego.py` (import ; `_parse_search_row`)
- Test: `tests/test_klikego.py`

- [ ] **Step 0 : Découverte (réseau réel)**

Klikego affiche les résultats en HTML. Sur la ligne de listing
(`tr.result-row`), la cellule temps `td.font-mono` peut contenir un label de
statut (`Abandon`, `Ab.`, `DNF`, `NC`) au lieu d'un temps. Vérifier :

```bash
python scripts/audit_scrapers.py --provider klikego --out /tmp/kg.md
# Inspecter les cellules temps d'un listing réel :
python - <<'PY'
import httpx
from bs4 import BeautifulSoup
from app.scrapers.klikego import BASE, HEADERS
url = (f"{BASE}/v8/evenement/resultats-search.jsp"
       "?event=1674523163798-4&heat=&search=&city=&category=&sexe=&page=1")
html = httpx.get(url, headers=HEADERS, timeout=20).text
for row in BeautifulSoup(html, "lxml").select("tr.result-row[data-dossard]"):
    c = row.select_one("td.font-mono")
    print(repr(c.get_text(strip=True)) if c else None)
PY
```

Noter les libellés non-temps observés. Les ajouter à `_STATUS_TOKENS` (Task 1) si
nécessaire. Si Klikego encode le statut ailleurs (page détail), documenter et
adapter le point d'extraction.

- [ ] **Step 1 : Écrire les tests qui échouent**

Dans `tests/test_klikego.py`, ajouter (compléter les imports existants) :

```python
from bs4 import BeautifulSoup

from app.scrapers.klikego import _parse_search_row


def _row(html: str):
    return BeautifulSoup(html, "lxml").select_one("tr")


def test_parse_search_row_explicit_status_dnf():
    """La cellule temps porte 'Abandon' → status DNF, total_time vide, rang purgé."""
    html = (
        '<table><tr class="result-row" data-dossard="42">'
        '<td class="truncate">DUPONT Jean</td>'
        '<td class="font-mono">Abandon</td></tr></table>'
    )
    r = _parse_search_row(_row(html), "evt", "heat", "Tri", "slug", 5)
    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None


def test_parse_search_row_finisher_no_status():
    """Cellule temps = vrai temps → status="" et total_time normalisé."""
    html = (
        '<table><tr class="result-row" data-dossard="42">'
        '<td class="truncate">DUPONT Jean</td>'
        '<td class="font-mono">01:23:45</td></tr></table>'
    )
    r = _parse_search_row(_row(html), "evt", "heat", "Tri", "slug", 5)
    assert r.status == ""
    assert r.total_time == "01:23:45"
    assert r.rank_overall == 5
```

- [ ] **Step 2 : Lancer les tests, vérifier qu'ils échouent**

Run: `pytest tests/test_klikego.py -k "search_row" -q`
Expected: FAIL — `r.status` vaut `""` ; `total_time` vaut `"Abandon"` (renvoyé tel quel par `normalize_time`).

- [ ] **Step 3 : Implémenter l'extraction**

Dans `app/scrapers/klikego.py` :

a) Élargir l'import `utils` (ligne 17) :

```python
from .utils import derive_status_from_label, normalize_time, parse_fr_date
```

b) Dans `_parse_search_row`, remplacer le bloc cellule-temps (lignes ~276-278) :

```python
    time_cell = row.select_one("td.font-mono")
    if time_cell:
        result.total_time = normalize_time(time_cell.get_text(strip=True))
```

par :

```python
    time_cell = row.select_one("td.font-mono")
    if time_cell:
        raw_time = time_cell.get_text(strip=True)
        status = derive_status_from_label(raw_time)
        if status:
            # La colonne temps porte un label de statut (Abandon/DNF…) au lieu
            # d'un temps : on pose le statut et on purge temps/rang positionnel.
            result.status = status
            result.rank_overall = None
        else:
            result.total_time = normalize_time(raw_time)
```

> `breizhchrono.py` réutilise `_parse_search_row` via
> `_klikego_parse_search_row` → il hérite du comportement sans modification
> (cf. Task 5). Ne **pas** dupliquer la logique dans breizhchrono.

- [ ] **Step 4 : Lancer les tests, vérifier qu'ils passent**

Run: `pytest tests/test_klikego.py -q`
Expected: PASS (anciens + nouveaux).

- [ ] **Step 5 : Lint + commit**

```bash
ruff check app/scrapers/klikego.py tests/test_klikego.py
git add app/scrapers/klikego.py tests/test_klikego.py
git commit -m "feat(klikego): lit le statut (Abandon/DNF) dans la ligne de listing"
```

---

## Task 5 : Breizh Chrono — vérifier l'héritage (pas de duplication)

**Files:**
- Modify: `tests/test_breizhchrono.py`
- (Aucune modif de `app/scrapers/breizhchrono.py` attendue — il délègue à klikego)

- [ ] **Step 0 : Découverte (réseau réel, rapide)**

Breizh Chrono utilise la même plateforme que Klikego (HTML identique). Vérifier
que le listing porte le statut au même endroit (`td.font-mono`) :

```bash
python scripts/audit_scrapers.py --provider breizhchrono --out /tmp/bc.md
```

Si l'audit révèle un encodage différent, ouvrir une sous-tâche dédiée. Sinon,
l'héritage suffit.

- [ ] **Step 1 : Écrire le test d'héritage qui échoue (si non vérifié)**

Dans `tests/test_breizhchrono.py`, ajouter :

```python
def test_breizhchrono_reuses_klikego_search_row():
    """Breizh Chrono ne duplique pas la logique : il pointe sur le parseur klikego.

    Garantit que le fix statut de Task 4 s'applique aussi à Breizh Chrono.
    """
    from app.scrapers import breizhchrono, klikego

    assert breizhchrono._klikego_parse_search_row is klikego._parse_search_row
```

- [ ] **Step 2 : Lancer le test**

Run: `pytest tests/test_breizhchrono.py -k reuses_klikego -q`
Expected: PASS immédiatement (l'import existe déjà :
`from .klikego import _parse_search_row as _klikego_parse_search_row`). Ce test
*verrouille* l'héritage contre une régression future.

> Si le test échoue (le code aurait dupliqué la logique), c'est un signal de
> non-conformité à AGENTS.md → corriger en déléguant à klikego, pas en dupliquant.

- [ ] **Step 3 : (aucune implémentation attendue)**

Si Step 0 a révélé un encodage Breizh-spécifique, et seulement dans ce cas,
ajouter un test ciblé `_import_one_heat`/`_parse_detail` + l'extraction dans
`breizhchrono.py`. Sinon, passer.

- [ ] **Step 4 : Lint + commit**

```bash
ruff check tests/test_breizhchrono.py
git add tests/test_breizhchrono.py
git commit -m "test(breizhchrono): verrouille l'héritage du parseur de listing klikego (statut)"
```

---

## Task 6 : Sport Innovation — statut HTML + API JSON

**Files:**
- Modify: `app/scrapers/sportinnovation.py` (imports ; `_parse_html_row` ; `_parse_api_athlete`)
- Test: `tests/test_sportinnovation.py`

- [ ] **Step 0 : Découverte (réseau réel)**

Deux formats : HTML tabulaire (`www.sportinnovation.fr/Evenements/Resultats/{id}`)
et API JSON (`results.sportinnovation.fr/race/{slug}`). Identifier où apparaît un
non-finisher : colonne temps contenant `Abandon`/`DNF`/`DSQ` (HTML) ; champ
`status`/`state` (JSON).

```bash
python scripts/audit_scrapers.py --provider sportinnovation --out /tmp/si.md
# JSON : inspecter les clés d'un athlète réel
python - <<'PY'
import httpx
from app.scrapers.sportinnovation import API_BASE, HEADERS
races = httpx.get(f"{API_BASE}/events", headers=HEADERS, timeout=15).json()
print("events sample keys:", list(races[0].keys()) if races else "none")
PY
```

Noter le porteur du statut. Ajuster le candidat lu (Step 3) et les jetons de
`_STATUS_TOKENS` (Task 1) si besoin.

- [ ] **Step 1 : Écrire les tests qui échouent**

Dans `tests/test_sportinnovation.py`, ajouter (compléter les imports) :

```python
from app.scrapers.sportinnovation import _parse_api_athlete, _parse_html_row


def test_parse_html_row_explicit_status():
    """Colonne temps = 'Abandon' → status DNF + temps purgé."""
    col = {"name": 0, "bib": 1, "total_time": 2}
    tds = ["DUPONT JeanH-S3H", "42", "Abandon"]
    r = _parse_html_row(tds, col, "http://x", "Triathlon S")
    assert r.status == "DNF"
    assert r.total_time == ""


def test_parse_html_row_finisher_no_status():
    col = {"name": 0, "bib": 1, "total_time": 2}
    tds = ["DUPONT JeanH-S3H", "42", "01:23:45"]
    r = _parse_html_row(tds, col, "http://x", "Triathlon S")
    assert r.status == ""
    assert r.total_time == "01:23:45"


def test_parse_api_athlete_explicit_status():
    """Champ JSON status='DNS' → DNS + hygiène."""
    a = {
        "lastName": "Dupont", "firstName": "Jean", "bib": 42,
        "status": "DNS", "generalRanking": "5", "officialTime": "",
    }
    r = _parse_api_athlete(a, "http://x", "Triathlon", "triathlon-s", None)
    assert r.status == "DNS"
    assert r.total_time == ""
    assert r.rank_overall is None
```

- [ ] **Step 2 : Lancer les tests, vérifier qu'ils échouent**

Run: `pytest tests/test_sportinnovation.py -k "status" -q`
Expected: FAIL — `status` vaut `""` ; pour le HTML, `total_time` vaut `"Abandon"`.

- [ ] **Step 3 : Implémenter l'extraction (HTML + API)**

Dans `app/scrapers/sportinnovation.py` :

a) Élargir l'import `base` (ligne 23) :

```python
from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
```

b) Élargir l'import `utils` (ligne 24) :

```python
from .utils import derive_status_from_label, normalize_rank, normalize_time
```

c) Dans `_parse_html_row`, remplacer la ligne temps total (ligne ~157) :

```python
    result.total_time = normalize_time(get("total_time"))
```

par :

```python
    raw_total = get("total_time")
    status = derive_status_from_label(raw_total)
    if status:
        result.status = status
    else:
        result.total_time = normalize_time(raw_total)
```

Puis, juste avant `result.raw_data = {"col_map": col}` (ligne ~163), ajouter
l'hygiène rangs :

```python
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.rank_overall = None
        result.rank_category = None
        result.rank_gender = None
```

d) Dans `_parse_api_athlete`, remplacer la ligne temps (ligne ~265) :

```python
    res.total_time = normalize_time(a.get("officialTime") or a.get("realTime") or "")
```

par (lecture d'un champ de statut candidat + hygiène) :

```python
    res.status = derive_status_from_label(str(a.get("status") or a.get("state") or ""))
    if res.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        res.total_time = ""
        res.rank_overall = res.rank_gender = res.rank_category = None
    else:
        res.total_time = normalize_time(a.get("officialTime") or a.get("realTime") or "")
```

> Note : dans `_parse_api_athlete`, les rangs sont assignés *avant* cette ligne
> (lignes ~262-264). L'hygiène ci-dessus les remet à `None` pour un non-finisher.

- [ ] **Step 4 : Lancer les tests, vérifier qu'ils passent**

Run: `pytest tests/test_sportinnovation.py -q`
Expected: PASS (anciens + nouveaux).

- [ ] **Step 5 : Lint + commit**

```bash
ruff check app/scrapers/sportinnovation.py tests/test_sportinnovation.py
git add app/scrapers/sportinnovation.py tests/test_sportinnovation.py
git commit -m "feat(sportinnovation): lit le statut (HTML + API JSON) + hygiène non-finisher"
```

---

## Task 7 : Intégration — conservation des non-finishers (best-effort)

**Files:**
- Modify: `tests/test_integration_scrapers.py`

- [ ] **Step 1 : Ajouter le test d'intégration (réseau réel)**

Dans `tests/test_integration_scrapers.py`, ajouter à la fin :

```python
@pytest.mark.integration
def test_timepulse_conserve_non_finishers():
    """Le fix TimePulse conserve les non-finishers s'il y en a (best-effort).

    Données réelles évolutives → pas d'assertion stricte sur le nombre. On vérifie
    que des finishers remontent et on documente le nombre de non-finishers
    conservés (un <E> sans <R> → total_time vide).
    """
    results = registry.scrape_event_all(LIVE_URLS["timepulse"])
    assert results, "timepulse : aucun participant"
    assert any(r.total_time for r in results), "timepulse : aucun finisher"
    non_finishers = [r for r in results if not r.total_time]
    print(
        f"timepulse non-finishers conservés : {len(non_finishers)}/{len(results)}"
    )


@pytest.mark.integration
@pytest.mark.parametrize("provider, url", sorted(LIVE_URLS.items()))
def test_scrape_event_all_status_jamais_incoherent(provider, url):
    """Garde-fou : un résultat avec statut non-finisher n'a pas de temps total.

    Vérifie l'hygiène cross-provider (DNF/DNS/DSQ ⇒ total_time vide).
    """
    results = registry.scrape_event_all(url)
    for r in results:
        if r.status in ("DNF", "DNS", "DSQ"):
            assert not r.total_time, (
                f"{provider} : {r.athlete_name} statut {r.status} mais temps {r.total_time!r}"
            )
```

- [ ] **Step 2 : Lancer l'intégration (réseau réel)**

Run: `pytest -m integration tests/test_integration_scrapers.py -q -s`
Expected: PASS. Noter le compte de non-finishers TimePulse affiché. Si un provider
fait apparaître un statut non-finisher avec un temps, c'est un bug d'hygiène à
corriger dans la tâche du provider concerné.

> Best-effort : si aucune épreuve de référence ne contient de non-finisher
> identifiable, le test reste vert (assertions souples) — documenter le constat
> dans le message de commit.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_integration_scrapers.py
git commit -m "test(integration): conservation des non-finishers + hygiène statut cross-provider"
```

---

## Task 8 : Vérification finale

**Files:** aucun (vérification only)

- [ ] **Step 1 : Suite unitaire complète**

Run: `pytest -m "not integration" -q`
Expected: PASS — les 130 tests existants + les nouveaux (≈ 25 ajoutés). Zéro échec.

- [ ] **Step 2 : Lint global**

Run: `ruff check .`
Expected: aucune erreur.

- [ ] **Step 3 : (optionnel, réseau) intégration complète**

Run: `pytest -m integration -q -s`
Expected: PASS (best-effort, données réelles).

- [ ] **Step 4 : Mettre à jour la doc de design**

Cocher le spec `docs/superpowers/specs/2026-06-08-non-finisher-status-multi-provider-design.md`
comme implémenté (ajouter une ligne « Implémenté : commits … » en tête, à l'image
du spec prolivesport).

```bash
git add docs/superpowers/specs/2026-06-08-non-finisher-status-multi-provider-design.md
git commit -m "docs(scrapers): marque l'extension statut multi-provider comme implémentée"
```

---

## Auto-revue (couverture du spec)

- §1 Helper partagé `derive_status_from_label` → **Task 1** ✅ (table FR/EN, défaut `""`, import depuis `base.py`).
- §2 Fix structurel TimePulse (ne plus `continue` sur absence de `<R>`) → **Task 2** ✅.
- §3 Extraction statut par provider :
  - Klikego → **Task 4** ✅ ; Breizh Chrono par héritage → **Task 5** ✅ (anti-duplication verrouillée par test).
  - Wiclax → **Task 3** ✅ (conserve déjà, ajoute statut + hygiène).
  - Sport Innovation (HTML + `results.sportinnovation.fr`) → **Task 6** ✅.
  - Hygiène non-finisher (`total_time=""`, rangs `None`) appliquée partout ✅.
- §4 Découverte par provider AVANT le code de détection → **Step 0** de chaque tâche provider ✅.
- §5 Tests unitaires (helper, timepulse conserve, statut explicite/vide par provider) → **Tasks 1-6** ✅ ; intégration → **Task 7** ✅.
- Compatibilité : `mapping.derive_status` inchangé, `status=""` par défaut → zéro régression ✅. Pas de migration Alembic ✅.

**Inconnue assumée :** l'emplacement exact du statut dans chaque payload réel
(attribut/colonne/champ JSON) est confirmé par l'étape de découverte. Le code lit
un **candidat nommé** (`_STATUS_ATTRS` / colonne temps / champ `status`) encodé
dans les fixtures ; si la découverte révèle un autre porteur, ajuster le candidat
et la fixture correspondante — les tests synthétiques restent déterministes.
