# Import exhaustif Klikego / Breizh Chrono — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** Importer **tous** les participants d'une épreuve Klikego / Breizh Chrono (finishers **et** DNF/DNS/DSQ), avec les temps totaux et les splits intermédiaires pour chacun, en remplaçant l'endpoint de liste incomplet par le data block authentique du fournisseur.

**Architecture :** Klikego et Breizh Chrono partagent la même plateforme. Leur page de résultats charge les données dans une iframe `/bc/resultats/course-result.jsp` qui embarque **toute** la liste (statuts compris) dans un `<script id="data">` encodé base64 + XOR. On crée un moteur partagé `klikego_platform.py` qui décode ce bloc, pagine, et collecte les splits via le paramètre `inter`. `klikego.py` et `breizhchrono.py` deviennent de fines couches au-dessus de ce moteur. La détection TCN et les splits détaillés TCN (page `resultat-participant.jsp`) restent inchangés.

**Tech Stack :** Python 3.11, httpx, BeautifulSoup/lxml, pytest. Aucune nouvelle dépendance.

## Global Constraints

- UI, commentaires et messages en **français** (avec accents).
- Tests unitaires **sans réseau** : tout test touchant le réseau réel porte le marker `integration` (`pytest.ini`). Les tests unitaires utilisent des fixtures HTML capturées.
- Conventional Commits (`fix:`, `feat:`, `refactor:`, `test:`).
- Les temps restent des **strings** `"HH:MM:SS"`, normalisés via `app/scrapers/utils.normalize_time`.
- Ne pas dupliquer la logique Klikego dans Breizh Chrono (cf. AGENTS.md) — la factoriser dans le moteur partagé.
- Le flux ne traverse qu'une direction : `registry → scraper → ScrapedResult`. Le scraper ne touche pas la DB.

---

## Contexte technique vérifié (source de vérité)

Toutes les valeurs ci-dessous ont été observées en interrogeant les fournisseurs en réel (28/06/2026).

**Endpoint data block (identique Klikego & Breizh Chrono) :**
```
{BASE}/bc/resultats/course-result.jsp?ref={event_id}&heat={heat}&query=&category=&sex=&inter={inter}&page={page}
```
- `BASE` = `https://www.klikego.com` (Klikego) ou `https://resultats.breizhchrono.com` (Breizh Chrono).
- `page` commence à **0**, 50 lignes par page.
- `inter` vide = temps d'arrivée (officiel). Une valeur (`Natation___T1`, `Vélo`, `Course`…) = temps du checkpoint correspondant.

**Décodage du bloc :** élément `<script type="text/plain" id="data">`, contenu base64 → décoder → XOR chaque octet avec `ord('K')` (= 75) → décoder UTF-8.

**Format d'une ligne (séparateur `|`), 12 champs :**
```
dossard | diploma | classement | classementCat | nom | cat | sexe | club_ou_ville | inter | officiel | reel | endurance
```
- `classement` / `classementCat` : un entier **ou** un statut `"DNF"` / `"DNS"` / `"DSQ"`.
- `nom` : `"DE POORTER Axel"` → nom de famille = tokens initiaux en MAJUSCULES, prénom = le reste.
- `club_ou_ville` : nom de club **ou** `"ST ETIENNE DE MONTLUC (44360)"` (ville + code postal). Vide pour les DNS.
- `officiel` : temps total (rempli si `inter` vide). `inter` (champ idx 8) : temps du checkpoint (rempli si `inter` non vide).

**Comptes de référence (validation) :**
- Audencia La Baule, heat `triathlon-s-light` : **591** participants = 483 finishers + 108 DNF/DNS/DSQ. (L'ancien endpoint `resultats-search.jsp` n'en renvoyait que 433.)
- Duathlon Nozeen (issue #11), heat `duathlon-s---open` : **166** = 139 finishers + 27 DNF.

**Options `inter`** lues dans `<select name="inter">` de la page heat :
- Triathlon (Audencia) : `[("", "Arrivée"), ("Natation___T1", "Natation + T1"), ("Vélo", "Vélo"), ("Course", "Course")]`.
- Duathlon Nozeen : **aucun select `inter`** → seuls les temps totaux sont disponibles pour les non-TCN (les splits détaillés restent réservés aux athlètes TCN via la page détail).

---

## File Structure

- **Create `backend/app/scrapers/klikego_platform.py`** — moteur partagé : décodage du data block, pagination, parsing des lignes en `ScrapedResult` (statuts compris), collecte des splits via `inter`, mapping label→slot. Une seule responsabilité : extraire la liste complète d'un heat de la plateforme Klikego/BC.
- **Modify `backend/app/scrapers/klikego.py`** — `scrape_event_all` réécrit pour déléguer la liste au moteur ; conserve la détection TCN (`city=nantais`) + splits détaillés TCN.
- **Modify `backend/app/scrapers/breizhchrono.py`** — `scrape_event_all` / `_import_one_heat` réécrits pour déléguer au moteur ; conserve la découverte multi-heats et les splits détaillés TCN.
- **Create `backend/tests/fixtures/klikego_datablock_page0.html`** — capture réelle d'une page `course-result.jsp` (heat triathlon avec DNF/DNS, ≥1 page).
- **Create `backend/tests/fixtures/klikego_datablock_inter_velo.html`** — même page avec `inter=Vélo`.
- **Modify `backend/tests/test_klikego.py`** — tests du moteur sur fixtures.
- **Modify `backend/tests/test_breizhchrono.py`** — test d'intégration du parsing BC.
- **Modify `backend/tests/test_integration_scrapers.py`** — assertions de comptes réels (marker `integration`).

---

## Task 1 : Décodage du data block

**Files :**
- Create : `backend/app/scrapers/klikego_platform.py`
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Produces : `decode_data_block(html: str) -> list[list[str]]` — retourne la liste des lignes, chaque ligne étant la liste de ses 12 champs (str). Lignes vides ignorées. Retourne `[]` si pas de bloc `id="data"` ou bloc vide.

- [ ] **Step 1 : Écrire le test qui échoue**

```python
# backend/tests/test_klikego.py (ajout)
from app.scrapers.klikego_platform import decode_data_block
import base64


def _encode_block(lines: list[str]) -> str:
    """Encode des lignes comme le fait le fournisseur : XOR 'K' puis base64."""
    payload = "\n".join(lines).encode("utf-8")
    xored = bytes(b ^ ord("K") for b in payload)
    b64 = base64.b64encode(xored).decode("ascii")
    return f'<script type="text/plain" id="data">{b64}</script>'


def test_decode_data_block_returns_split_rows():
    html = _encode_block([
        "358|true|1|1|DE POORTER Axel|S3|M|LE MANS TRIATHLON||00:38:05||",
        "282|false|DNF|DNF|DELAUNAY Juliette|S2|F|||||",
    ])
    rows = decode_data_block(html)
    assert len(rows) == 2
    assert rows[0][0] == "358"
    assert rows[0][4] == "DE POORTER Axel"
    assert rows[0][9] == "00:38:05"
    assert rows[1][2] == "DNF"


def test_decode_data_block_empty_when_no_element():
    assert decode_data_block("<html><body>rien</body></html>") == []
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py::test_decode_data_block_returns_split_rows -v`
Expected : FAIL — `ModuleNotFoundError: No module named 'app.scrapers.klikego_platform'`.

- [ ] **Step 3 : Implémentation minimale**

```python
# backend/app/scrapers/klikego_platform.py
"""
Moteur partagé pour la plateforme Klikego / Breizh Chrono.

Les deux fournisseurs utilisent le même back-office. Leur page de résultats
charge l'intégralité de la liste (finishers + DNF/DNS/DSQ) dans une iframe
`/bc/resultats/course-result.jsp` qui embarque les données dans un
`<script id="data">` encodé base64 + XOR (clé 'K'). C'est la source de vérité,
contrairement à `/v8/evenement/resultats-search.jsp` qui n'expose que les
classés et sous-pagine.

Format d'une ligne (séparateur `|`), 12 champs :
  dossard|diploma|classement|classementCat|nom|cat|sexe|club_ou_ville|inter|officiel|reel|endurance
"""
import base64

from bs4 import BeautifulSoup

_XOR_KEY = ord("K")


def decode_data_block(html: str) -> list[list[str]]:
    """Décode le `<script id="data">` d'une page course-result.jsp.

    Retourne une liste de lignes, chaque ligne = liste de ses champs (str).
    `[]` si le bloc est absent ou vide.
    """
    el = BeautifulSoup(html, "lxml").find(id="data")
    if not el:
        return []
    raw_b64 = el.get_text().strip()
    if not raw_b64:
        return []
    raw = base64.b64decode(raw_b64)
    text = bytes(b ^ _XOR_KEY for b in raw).decode("utf-8")
    return [line.split("|") for line in text.split("\n") if line.strip()]
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run : `cd backend && pytest tests/test_klikego.py -k decode_data_block -v`
Expected : 2 passed.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/klikego_platform.py backend/tests/test_klikego.py
git commit -m "feat(scrapers): décode le data block course-result.jsp (Klikego/BC)"
```

---

## Task 2 : Parsing d'une ligne en ScrapedResult (statuts compris)

**Files :**
- Modify : `backend/app/scrapers/klikego_platform.py`
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Consumes : `decode_data_block` (Task 1).
- Produces : `parse_data_row(fields: list[str]) -> dict` — transforme une ligne (12 champs) en dict avec les clés : `bib_number, athlete_name, athlete_firstname, category, gender, club, rank_overall (int|None), rank_category (int|None), total_time (str), status (str)`. `status` ∈ `{"", "DNF", "DNS", "DSQ"}` ; pour un statut non vide, `rank_overall`/`rank_category`/`total_time` sont neutralisés (`None`/`""`).

- [ ] **Step 1 : Écrire le test qui échoue**

```python
# backend/tests/test_klikego.py (ajout)
from app.scrapers.klikego_platform import parse_data_row


def test_parse_data_row_finisher():
    fields = "358|true|1|1|DE POORTER Axel|S3|M|LE MANS TRIATHLON||00:38:05||".split("|")
    r = parse_data_row(fields)
    assert r["bib_number"] == "358"
    assert r["athlete_name"] == "DE POORTER"
    assert r["athlete_firstname"] == "Axel"
    assert r["category"] == "S3"
    assert r["gender"] == "M"
    assert r["club"] == "LE MANS TRIATHLON"
    assert r["rank_overall"] == 1
    assert r["rank_category"] == 1
    assert r["total_time"] == "00:38:05"
    assert r["status"] == ""


def test_parse_data_row_dnf_neutralises_rank_and_time():
    fields = "282|false|DNF|DNF|DELAUNAY Juliette|S2|F|||||".split("|")
    r = parse_data_row(fields)
    assert r["status"] == "DNF"
    assert r["rank_overall"] is None
    assert r["rank_category"] is None
    assert r["total_time"] == ""
    assert r["athlete_name"] == "DELAUNAY"
    assert r["athlete_firstname"] == "Juliette"


def test_parse_data_row_dns_and_dsq():
    assert parse_data_row("476|false|DNS|DNS|AVENARD Benedicte|S2|F|||||".split("|"))["status"] == "DNS"
    assert parse_data_row("375|false|DSQ|DSQ|MOTTAY Aude|V3|F|||||".split("|"))["status"] == "DSQ"
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py::test_parse_data_row_finisher -v`
Expected : FAIL — `ImportError: cannot import name 'parse_data_row'`.

- [ ] **Step 3 : Implémentation minimale**

```python
# backend/app/scrapers/klikego_platform.py (ajout)
import re

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ
from .utils import normalize_time

_STATUS_BY_TOKEN = {
    "DNF": STATUS_DNF,
    "AB": STATUS_DNF,
    "ABANDON": STATUS_DNF,
    "DNS": STATUS_DNS,
    "NP": STATUS_DNS,
    "DSQ": STATUS_DSQ,
    "DQ": STATUS_DSQ,
    "DISQ": STATUS_DSQ,
}


def _split_name(full: str) -> tuple[str, str]:
    """`"DE POORTER Axel"` -> ("DE POORTER", "Axel"). Nom = tokens MAJUSCULES de tête."""
    parts = full.split()
    i = 0
    while i < len(parts) and parts[i].isupper():
        i += 1
    return " ".join(parts[:i]), " ".join(parts[i:])


def _parse_rank(value: str) -> int | None:
    m = re.match(r"\d+", value.strip())
    return int(m.group(0)) if m else None


def parse_data_row(fields: list[str]) -> dict:
    """Transforme une ligne du data block (12 champs) en dict de champs ScrapedResult."""
    f = (fields + [""] * 12)[:12]
    dossard, _diploma, clt, cltcat, nom, cat, sexe, club, inter, officiel, reel, _end = f

    status = _STATUS_BY_TOKEN.get(clt.strip().upper(), "")
    nom_fam, prenom = _split_name(nom.strip())
    gender = sexe.strip().upper()
    if gender == "H":  # alias utilisé par certains systèmes
        gender = "M"

    return {
        "bib_number": dossard.strip(),
        "athlete_name": nom_fam,
        "athlete_firstname": prenom,
        "category": cat.strip(),
        "gender": gender if gender in ("M", "F") else "",
        "club": club.strip(),
        "rank_overall": None if status else _parse_rank(clt),
        "rank_category": None if status else _parse_rank(cltcat),
        "total_time": "" if status else normalize_time(officiel.strip()),
        "status": status,
    }
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run : `cd backend && pytest tests/test_klikego.py -k parse_data_row -v`
Expected : 4 passed.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/klikego_platform.py backend/tests/test_klikego.py
git commit -m "feat(scrapers): parse une ligne du data block (statuts DNF/DNS/DSQ)"
```

---

## Task 3 : Pagination complète d'un heat

**Files :**
- Modify : `backend/app/scrapers/klikego_platform.py`
- Create : `backend/tests/fixtures/klikego_datablock_page0.html`
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Consumes : `decode_data_block`, `parse_data_row`.
- Produces : `fetch_heat_rows(base: str, event_id: str, heat: str, client: httpx.Client, inter: str = "") -> list[list[str]]` — pagine `course-result.jsp` (page 0..N), concatène les lignes brutes (12 champs) de toutes les pages. Arrêt quand une page renvoie <50 lignes **ou** quand le 1er dossard d'une page répète celui de la page précédente. Dédoublonne par dossard (1ère occurrence gagne).

- [ ] **Step 1 : Capturer la fixture réelle (une seule fois, hors test)**

Run :
```bash
cd backend && source .venv/bin/activate && python - <<'PY'
import httpx
H={"User-Agent":"Mozilla/5.0 Chrome/124.0","Referer":"https://resultats.breizhchrono.com/","Accept":"text/html,*/*"}
u="https://resultats.breizhchrono.com/bc/resultats/course-result.jsp?ref=1488071608761-572&heat=triathlon-s-light&query=&category=&sex=&inter=&page=0"
open("tests/fixtures/klikego_datablock_page0.html","w").write(httpx.get(u,headers=H,follow_redirects=True,timeout=30).text)
print("ok")
PY
```
Expected : `ok`, fichier créé (~46 Ko, contient `id="data"` et des lignes `DNF`/`DNS`).

- [ ] **Step 2 : Écrire le test qui échoue**

```python
# backend/tests/test_klikego.py (ajout)
from pathlib import Path
from app.scrapers.klikego_platform import decode_data_block, parse_data_row

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_page0_contains_dnf_and_finishers():
    html = (FIXTURES / "klikego_datablock_page0.html").read_text()
    rows = [parse_data_row(r) for r in decode_data_block(html)]
    assert len(rows) == 50  # page pleine
    statuses = {r["status"] for r in rows}
    assert "" in statuses  # des finishers
    # au moins un finisher a un temps total non vide
    assert any(r["total_time"] for r in rows if not r["status"])
```

- [ ] **Step 3 : Lancer le test, vérifier le succès** (valide fixture + Tasks 1-2)

Run : `cd backend && pytest tests/test_klikego.py::test_fixture_page0_contains_dnf_and_finishers -v`
Expected : PASS.

- [ ] **Step 4 : Implémenter `fetch_heat_rows`**

```python
# backend/app/scrapers/klikego_platform.py (ajout)
import httpx

_PAGE_SIZE = 50

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,*/*",
}


def _course_result_url(base: str, event_id: str, heat: str, inter: str, page: int) -> str:
    return (
        f"{base}/bc/resultats/course-result.jsp"
        f"?ref={event_id}&heat={heat}&query=&category=&sex=&inter={inter}&page={page}"
    )


def fetch_heat_rows(
    base: str, event_id: str, heat: str, client: httpx.Client, inter: str = ""
) -> list[list[str]]:
    """Pagine course-result.jsp et retourne toutes les lignes brutes (dédoublonnées)."""
    out: dict[str, list[str]] = {}
    page = 0
    prev_first: str | None = None
    while True:
        resp = client.get(_course_result_url(base, event_id, heat, inter, page))
        if resp.status_code != 200:
            break
        rows = decode_data_block(resp.text)
        if not rows:
            break
        first_bib = rows[0][0] if rows[0] else ""
        if first_bib and first_bib == prev_first:
            break  # la plateforme répète la dernière page
        prev_first = first_bib
        for r in rows:
            bib = r[0] if r else ""
            if bib and bib not in out:
                out[bib] = r
        if len(rows) < _PAGE_SIZE:
            break
        page += 1
    return list(out.values())
```

- [ ] **Step 5 : Test de pagination sur monkeypatch (sans réseau)**

```python
# backend/tests/test_klikego.py (ajout)
import app.scrapers.klikego_platform as plat


def test_fetch_heat_rows_paginates_and_stops(monkeypatch):
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()
    # page 1 : moins de 50 lignes -> doit arrêter après
    short = plat.decode_data_block  # sanity import
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        def __init__(self, text): self.text = text

    # Construit une page courte (2 lignes) encodée comme le fournisseur
    import base64
    short_lines = "\n".join([
        "999|true|51|1|TEST Alpha|S1|M|CLUB X||01:00:00||",
        "998|true|52|2|TEST Beta|S1|M|CLUB Y||01:01:00||",
    ]).encode()
    short_b64 = base64.b64encode(bytes(b ^ ord("K") for b in short_lines)).decode()
    page1 = f'<script id="data">{short_b64}</script>'

    def fake_get(url):
        calls["n"] += 1
        return FakeResp(page0 if "page=0" in url else page1)

    class FakeClient:
        def get(self, url): return fake_get(url)

    rows = plat.fetch_heat_rows("https://x", "evt", "heat", FakeClient())
    assert calls["n"] == 2          # page 0 (pleine) + page 1 (courte) puis stop
    assert len(rows) == 52          # 50 + 2, dédoublonnés
```

- [ ] **Step 6 : Lancer les tests, vérifier le succès**

Run : `cd backend && pytest tests/test_klikego.py -k "fetch_heat_rows or fixture_page0" -v`
Expected : 2 passed.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/scrapers/klikego_platform.py backend/tests/test_klikego.py backend/tests/fixtures/klikego_datablock_page0.html
git commit -m "feat(scrapers): pagination complète d'un heat via le data block"
```

---

## Task 4 : Découverte des checkpoints `inter` et mapping vers slots de splits

**Files :**
- Modify : `backend/app/scrapers/klikego_platform.py`
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Produces :
  - `discover_inter_options(heat_page_html: str) -> list[tuple[str, str]]` — extrait les `(value, label)` non vides du `<select name="inter">` de la page heat. `[]` si absent.
  - `inter_label_to_slot(label: str) -> str | None` — mappe un label de checkpoint vers un slot positionnel de `ScrapedResult` (`"swim" | "t1" | "bike" | "t2" | "run"`), ou `None` si non reconnu.

- [ ] **Step 1 : Écrire le test qui échoue**

```python
# backend/tests/test_klikego.py (ajout)
from app.scrapers.klikego_platform import discover_inter_options, inter_label_to_slot


def test_discover_inter_options_triathlon():
    html = '''
    <select name="inter" id="inter">
      <option value="">Arrivée</option>
      <option value="Natation___T1">Natation + T1</option>
      <option value="Vélo">Vélo</option>
      <option value="Course">Course</option>
    </select>'''
    assert discover_inter_options(html) == [
        ("Natation___T1", "Natation + T1"),
        ("Vélo", "Vélo"),
        ("Course", "Course"),
    ]


def test_discover_inter_options_absent():
    assert discover_inter_options("<html>pas de select</html>") == []


def test_inter_label_to_slot():
    assert inter_label_to_slot("Natation + T1") == "swim"
    assert inter_label_to_slot("Vélo") == "bike"
    assert inter_label_to_slot("Course") == "run"
    assert inter_label_to_slot("Course à pied 1") == "swim"   # duathlon CAP1 -> slot swim
    assert inter_label_to_slot("Course à pied 2") == "run"    # duathlon CAP2 -> slot run
    assert inter_label_to_slot("Truc inconnu") is None
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py -k "inter_options or label_to_slot" -v`
Expected : FAIL — `ImportError`.

- [ ] **Step 3 : Implémentation minimale**

```python
# backend/app/scrapers/klikego_platform.py (ajout)

def discover_inter_options(heat_page_html: str) -> list[tuple[str, str]]:
    """Retourne les checkpoints (value, label) du <select name="inter">, sauf 'Arrivée'."""
    sel = BeautifulSoup(heat_page_html, "lxml").find("select", {"name": "inter"})
    if not sel:
        return []
    out = []
    for opt in sel.find_all("option"):
        value = (opt.get("value") or "").strip()
        if value:
            out.append((value, opt.get_text(strip=True)))
    return out


# Mapping label de checkpoint -> slot positionnel ScrapedResult.
# Ordre : motifs spécifiques (numérotés) avant génériques.
_INTER_SLOT_RULES = [
    ("course à pied 1", "swim"),
    ("course a pied 1", "swim"),
    ("cap 1", "swim"),
    ("course à pied 2", "run"),
    ("course a pied 2", "run"),
    ("cap 2", "run"),
    ("natation", "swim"),
    ("nat", "swim"),
    ("t1", "t1"),
    ("vélo", "bike"),
    ("velo", "bike"),
    ("bike", "bike"),
    ("t2", "t2"),
    ("course", "run"),
    ("cap", "run"),
    ("run", "run"),
]


def inter_label_to_slot(label: str) -> str | None:
    """Mappe un label de checkpoint (`"Natation + T1"`, `"Vélo"`…) vers un slot."""
    low = label.lower()
    for key, slot in _INTER_SLOT_RULES:
        if key in low:
            return slot
    return None
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run : `cd backend && pytest tests/test_klikego.py -k "inter_options or label_to_slot" -v`
Expected : 3 passed.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/klikego_platform.py backend/tests/test_klikego.py
git commit -m "feat(scrapers): découvre les checkpoints inter et les mappe aux slots"
```

---

## Task 5 : Collecte des splits `inter` pour tous les participants

**Files :**
- Modify : `backend/app/scrapers/klikego_platform.py`
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Consumes : `fetch_heat_rows`, `discover_inter_options`, `inter_label_to_slot`.
- Produces : `fetch_inter_splits(base, event_id, heat, inter_options, client) -> dict[str, dict[str, str]]` — pour chaque checkpoint, pagine `course-result.jsp?inter=...` et lit le champ idx 8 (`inter`) par dossard. Retourne `{bib: {slot: "HH:MM:SS"}}`. Les checkpoints dont le label ne mappe sur aucun slot sont ignorés.

- [ ] **Step 1 : Écrire le test qui échoue (monkeypatch, sans réseau)**

```python
# backend/tests/test_klikego.py (ajout)
import base64
import app.scrapers.klikego_platform as plat
from app.scrapers.klikego_platform import fetch_inter_splits


def _block(lines):
    payload = "\n".join(lines).encode()
    return f'<script id="data">{base64.b64encode(bytes(b ^ ord("K") for b in payload)).decode()}</script>'


def test_fetch_inter_splits_collects_per_slot(monkeypatch):
    # inter=Vélo : le temps du checkpoint est dans le champ idx 8
    velo = _block(["358|true|1|1|DE POORTER Axel|S3|M|CLUB|00:19:28|||"])
    nat = _block(["358|true|1|1|DE POORTER Axel|S3|M|CLUB|00:06:24|||"])

    class FakeResp:
        status_code = 200
        def __init__(self, t): self.text = t

    class FakeClient:
        def get(self, url):
            if "inter=Vélo" in url:
                return FakeResp(velo)
            if "inter=Natation___T1" in url:
                return FakeResp(nat)
            return FakeResp(_block([]))

    options = [("Natation___T1", "Natation + T1"), ("Vélo", "Vélo")]
    splits = fetch_inter_splits("https://x", "evt", "heat", options, FakeClient())
    assert splits["358"] == {"swim": "00:06:24", "bike": "00:19:28"}
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py::test_fetch_inter_splits_collects_per_slot -v`
Expected : FAIL — `ImportError`.

- [ ] **Step 3 : Implémentation minimale**

```python
# backend/app/scrapers/klikego_platform.py (ajout)

def fetch_inter_splits(
    base: str,
    event_id: str,
    heat: str,
    inter_options: list[tuple[str, str]],
    client: httpx.Client,
) -> dict[str, dict[str, str]]:
    """Collecte les temps de checkpoints pour tous les participants.

    Pour chaque option `inter` mappable sur un slot, pagine le data block et lit
    le champ `inter` (idx 8). Retourne `{bib: {slot: "HH:MM:SS"}}`.
    """
    out: dict[str, dict[str, str]] = {}
    for value, label in inter_options:
        slot = inter_label_to_slot(label)
        if slot is None:
            continue
        for row in fetch_heat_rows(base, event_id, heat, client, inter=value):
            f = (row + [""] * 12)[:12]
            bib, inter_time = f[0].strip(), normalize_time(f[8].strip())
            if bib and inter_time:
                out.setdefault(bib, {})[slot] = inter_time
    return out
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run : `cd backend && pytest tests/test_klikego.py::test_fetch_inter_splits_collects_per_slot -v`
Expected : PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/klikego_platform.py backend/tests/test_klikego.py
git commit -m "feat(scrapers): collecte les splits inter de tous les participants"
```

---

## Task 6 : Construction des ScrapedResult d'un heat (assemblage moteur)

**Files :**
- Modify : `backend/app/scrapers/klikego_platform.py`
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Consumes : tout ce qui précède.
- Produces :
  `build_heat_results(base, provider, event_id, heat, heat_page_html, event_name, slug, event_type, source_url, event_date, client) -> list[ScrapedResult]`
  — pagine la liste complète, parse chaque ligne, applique les splits `inter` (si checkpoints publiés), et retourne les `ScrapedResult` complets (avec `status`, `event_type`, `event_date`, `source_url`, `provider`). `is_relay` n'est PAS posé ici (laissé à l'appelant qui connaît le label du heat).

- [ ] **Step 1 : Écrire le test qui échoue (sur la fixture réelle + monkeypatch des splits)**

```python
# backend/tests/test_klikego.py (ajout)
from datetime import date
import app.scrapers.klikego_platform as plat
from app.scrapers.klikego_platform import build_heat_results


def test_build_heat_results_includes_dnf_and_total_times(monkeypatch):
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        status_code = 200
        def __init__(self, t): self.text = t

    class FakeClient:
        def get(self, url):
            # Liste : page 0 pleine puis page vide pour arrêter
            if "inter=&page=0" in url:
                return FakeResp(page0)
            return FakeResp("<html></html>")

    # Pas de checkpoints inter dans ce test -> heat_page_html sans select
    results = build_heat_results(
        base="https://resultats.breizhchrono.com",
        provider="breizhchrono",
        event_id="1488071608761-572",
        heat="triathlon-s-light",
        heat_page_html="<html>pas de inter</html>",
        event_name="Triathlon Audencia La Baule 2024",
        slug="triathlon-audencia-la-baule-2024",
        event_type="triathlon_s",
        source_url="https://resultats.breizhchrono.com/x",
        event_date=date(2024, 9, 28),
        client=FakeClient(),
    )
    assert len(results) == 50
    assert any(r.status == "DNF" for r in results)
    assert any(r.status == "" and r.total_time for r in results)
    assert all(r.provider == "breizhchrono" for r in results)
    assert all(r.event_type == "triathlon_s" for r in results)
    assert all(r.event_date == date(2024, 9, 28) for r in results)
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py::test_build_heat_results_includes_dnf_and_total_times -v`
Expected : FAIL — `ImportError`.

- [ ] **Step 3 : Implémentation minimale**

```python
# backend/app/scrapers/klikego_platform.py (ajout)
from datetime import date as _date

from .base import ScrapedResult


def build_heat_results(
    *,
    base: str,
    provider: str,
    event_id: str,
    heat: str,
    heat_page_html: str,
    event_name: str,
    slug: str,
    event_type: str,
    source_url: str,
    event_date: _date | None,
    client: httpx.Client,
) -> list[ScrapedResult]:
    """Assemble la liste complète d'un heat (finishers + DNF/DNS/DSQ) avec splits inter."""
    rows = fetch_heat_rows(base, event_id, heat, client)
    inter_options = discover_inter_options(heat_page_html)
    splits = fetch_inter_splits(base, event_id, heat, inter_options, client) if inter_options else {}

    results: list[ScrapedResult] = []
    for raw in rows:
        d = parse_data_row(raw)
        r = ScrapedResult(source_url=source_url, provider=provider)
        r.event_name = event_name
        r.event_type = event_type
        r.event_date = event_date
        r.bib_number = d["bib_number"]
        r.athlete_name = d["athlete_name"]
        r.athlete_firstname = d["athlete_firstname"]
        r.category = d["category"]
        r.gender = d["gender"]
        r.club = d["club"]
        r.rank_overall = d["rank_overall"]
        r.rank_category = d["rank_category"]
        r.total_time = d["total_time"]
        r.status = d["status"]
        r.raw_data["heat_slug"] = heat
        for slot, t in splits.get(d["bib_number"], {}).items():
            setattr(r, f"{slot}_time", t)
        results.append(r)
    return results
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run : `cd backend && pytest tests/test_klikego.py::test_build_heat_results_includes_dnf_and_total_times -v`
Expected : PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/klikego_platform.py backend/tests/test_klikego.py
git commit -m "feat(scrapers): assemble les ScrapedResult complets d'un heat"
```

---

## Task 7 : Réécriture du scraper Klikego sur le moteur

**Files :**
- Modify : `backend/app/scrapers/klikego.py:297-396` (`scrape_event_all`)
- Test : `backend/tests/test_klikego.py`

**Interfaces :**
- Consumes : `klikego_platform.build_heat_results`, et les helpers existants `_fetch_event_meta`, `_parse_detail`.
- Produces : `klikego.scrape_event_all(event_id, heat, event_name, slug) -> list[ScrapedResult]` (signature inchangée).

**Détails de conception :**
- Phase A — récupérer `event_date` (réutiliser `_fetch_event_meta`) et le HTML de la page heat (pour les options `inter`).
- Phase B — `build_heat_results(base=BASE, provider="klikego", ...)` pour la liste complète + splits inter.
- Phase C (TCN, **inchangée**) — collecter les dossards Nantais via `resultats-search.jsp?city=nantais` + mots-clés sur le club, puis enrichir ces athlètes via la page détail `resultat-participant.jsp` (`_parse_detail`) pour les splits fins (transitions incluses) qui priment sur les splits `inter`.
- `event_type` via `_detect_event_type(heat, slug)`.

- [ ] **Step 1 : Écrire le test qui échoue (monkeypatch httpx.Client)**

```python
# backend/tests/test_klikego.py (ajout)
from app.scrapers import klikego


def test_klikego_scrape_event_all_returns_dnf(monkeypatch):
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        def __init__(self, t, code=200): self.text, self.status_code = t, code

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url):
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            if "course-result.jsp" in url:
                return FakeResp("<html></html>")
            if "resultats-search.jsp" in url:  # phase TCN city=nantais -> vide
                return FakeResp("<html></html>")
            return FakeResp("<html></html>")

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("triathlon-s-light", None))

    results = klikego.scrape_event_all(
        "1488071608761-572", "triathlon-s-light",
        "Triathlon Audencia La Baule 2024", "triathlon-audencia-la-baule-2024",
    )
    assert len(results) == 50
    assert any(r.status == "DNF" for r in results)
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py::test_klikego_scrape_event_all_returns_dnf -v`
Expected : FAIL — l'ancien code renvoie des finishers sans DNF (longueur ≠ 50 / pas de DNF).

- [ ] **Step 3 : Réécrire `scrape_event_all`**

```python
# backend/app/scrapers/klikego.py — remplace le corps de scrape_event_all (l.297-396)
def scrape_event_all(
    event_id: str, heat: str, event_name: str, slug: str
) -> list["ScrapedResult"]:
    """Tous les participants d'un heat Klikego (finishers + DNF/DNS/DSQ) via le data block.

    Phase A — meta (date) + HTML de la page heat (options inter).
    Phase B — liste complète + splits inter pour tous (moteur partagé).
    Phase C — splits fins via page détail pour les athlètes TCN/Nantais (priment).
    """
    from app.scrapers import klikego_platform as plat

    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        _, event_date = _fetch_event_meta(event_id, slug, client)
        heat_page = client.get(
            f"{BASE}/resultats/{slug}/{event_id}?heat={heat}" if slug
            else f"{BASE}/resultats/{event_id}?heat={heat}"
        )
        heat_page_html = heat_page.text if heat_page.status_code == 200 else ""

        source_url = f"{BASE}/resultats/{slug}/{event_id}?heat={heat}"
        results = plat.build_heat_results(
            base=BASE,
            provider="klikego",
            event_id=event_id,
            heat=heat,
            heat_page_html=heat_page_html,
            event_name=event_name,
            slug=slug,
            event_type=_detect_event_type(heat, slug),
            source_url=source_url,
            event_date=event_date,
            client=client,
        )
        bib_to_result = {r.bib_number: r for r in results}

        # Phase C — détection TCN (city=nantais + mots-clés club) puis splits fins
        nantais_bibs = _collect_nantais_bibs(event_id, heat, client, bib_to_result)
        for bib in nantais_bibs:
            r = bib_to_result.get(bib)
            if not r:
                continue
            dr = client.get(
                f"{BASE}/v8/evenement/resultat-participant.jsp"
                f"?embedded=1&e={event_id}&heat={heat}&dossard={bib}"
            )
            if dr.status_code == 200:
                _parse_detail(dr.text, r, {})

    return results
```

- [ ] **Step 4 : Extraire la détection TCN dans un helper réutilisable**

```python
# backend/app/scrapers/klikego.py (nouveau helper, au-dessus de scrape_event_all)
_TCN_KEYWORDS = ("nantais", "tcn", "tri club nant", "triathlon club nant")


def _collect_nantais_bibs(
    event_id: str, heat: str, client: httpx.Client,
    bib_to_result: dict[str, "ScrapedResult"],
) -> set[str]:
    """Dossards des athlètes nantais : filtre API city=nantais + mots-clés club."""
    nantais: set[str] = set()
    page = 1
    prev_first: str | None = None
    while True:
        url = (
            f"{BASE}/v8/evenement/resultats-search.jsp"
            f"?event={event_id}&heat={heat}&search=&city=nantais&category=&sexe=&page={page}"
        )
        resp = client.get(url)
        if resp.status_code != 200:
            break
        rows = BeautifulSoup(resp.text, "lxml").select("tr.result-row[data-dossard]")
        if not rows:
            break
        first_bib = rows[0].get("data-dossard", "")
        if first_bib and first_bib == prev_first:
            break
        prev_first = first_bib
        for row in rows:
            bib = row.get("data-dossard", "")
            if bib:
                nantais.add(bib)
        page += 1
    for bib, r in bib_to_result.items():
        if r.club and any(k in r.club.lower() for k in _TCN_KEYWORDS):
            nantais.add(bib)
    return nantais
```

- [ ] **Step 5 : Lancer le test ciblé puis toute la suite Klikego**

Run : `cd backend && pytest tests/test_klikego.py -v`
Expected : tous verts (anciens tests adaptés si besoin — voir Self-Review).

- [ ] **Step 6 : Commit**

```bash
git add backend/app/scrapers/klikego.py backend/tests/test_klikego.py
git commit -m "fix(scrapers): import Klikego exhaustif via data block (issue #11)"
```

---

## Task 8 : Réécriture du scraper Breizh Chrono sur le moteur

**Files :**
- Modify : `backend/app/scrapers/breizhchrono.py:114-209` (`_import_one_heat`, `scrape_event_all`)
- Test : `backend/tests/test_breizhchrono.py`

**Interfaces :**
- Consumes : `klikego_platform.build_heat_results`, helpers BC existants `_parse_bc_url`, `_fetch_all_heats`, `_parse_bc_date`, et `klikego._parse_detail`, `klikego._collect_nantais_bibs`.
- Produces : `breizhchrono.scrape_event_all(event_id, heat, event_name, slug) -> list[ScrapedResult]` (signature inchangée).

**Détails de conception :**
- `BASE = "https://resultats.breizhchrono.com"`, provider `"breizhchrono"`.
- Conserver la découverte multi-heats (`_fetch_all_heats`) quand aucun heat n'est fourni, avec `is_relay` déduit du label (`"relais"` dans le nom) — posé sur les résultats après `build_heat_results`.
- Pour chaque heat : récupérer le HTML de la page heat (`/resultats-courses/{slug}-{event_id}/{heat}`) pour les options `inter`, puis `build_heat_results`.
- `event_type` par heat via `klikego._detect_event_type(heat_slug, slug)` (au lieu d'un type unique) — corrige le mélange tri/duathlon/relais d'un même événement.
- Splits fins TCN via `_parse_detail` (inchangé).

- [ ] **Step 1 : Écrire le test qui échoue**

```python
# backend/tests/test_breizhchrono.py (ajout)
from datetime import date
from app.scrapers import breizhchrono


def test_bc_import_one_heat_returns_dnf(monkeypatch):
    from pathlib import Path
    page0 = (Path(__file__).parent / "fixtures" / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        def __init__(self, t, code=200): self.text, self.status_code = t, code

    class FakeClient:
        def get(self, url):
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            return FakeResp("<html></html>")

    results = breizhchrono._import_one_heat(
        "1488071608761-572", "triathlon-s-light", "Triathlon S LIGHT",
        "Triathlon Audencia La Baule 2024", "triathlon-audencia-la-baule-2024",
        date(2024, 9, 28), FakeClient(),
    )
    assert len(results) == 50
    assert any(r.status == "DNF" for r in results)
    assert all(r.provider == "breizhchrono" for r in results)
    assert all(r.is_relay is False for r in results)  # heat non-relais
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_breizhchrono.py::test_bc_import_one_heat_returns_dnf -v`
Expected : FAIL (ancien `_import_one_heat` n'utilise pas le data block).

- [ ] **Step 3 : Réécrire `_import_one_heat`**

```python
# backend/app/scrapers/breizhchrono.py — remplace _import_one_heat (l.114-152)
def _import_one_heat(
    event_id: str, heat_slug: str, heat_label: str,
    event_name: str, slug: str, event_date, client: httpx.Client,
) -> list[ScrapedResult]:
    """Liste complète d'un heat (finishers + DNF/DNS/DSQ) via le moteur partagé."""
    from app.scrapers import klikego_platform as plat
    from app.scrapers.klikego import _detect_event_type

    is_relay = "relais" in heat_label.lower() or heat_slug.endswith("---")
    source_url = f"{BASE}/resultats-courses/{slug}-{event_id}/{heat_slug}"
    heat_page = client.get(source_url)
    heat_page_html = heat_page.text if heat_page.status_code == 200 else ""

    results = plat.build_heat_results(
        base=BASE,
        provider="breizhchrono",
        event_id=event_id,
        heat=heat_slug,
        heat_page_html=heat_page_html,
        event_name=event_name,
        slug=slug,
        event_type=_detect_event_type(heat_slug, slug),
        source_url=source_url,
        event_date=event_date,
        client=client,
    )
    for r in results:
        r.is_relay = is_relay
    return results
```

- [ ] **Step 4 : Adapter la phase TCN de `scrape_event_all`**

Dans `scrape_event_all` (l.196-208), remplacer la boucle de détection TCN ad hoc par l'appel au helper partagé, **par heat** (les dossards sont uniques par heat) :

```python
# backend/app/scrapers/breizhchrono.py — dans scrape_event_all, après la boucle des heats
        # Splits fins pour les athlètes TCN/Nantais (priment sur les splits inter)
        from app.scrapers.klikego import _TCN_KEYWORDS, _parse_detail
        for r in results:
            if r.club and any(k in r.club.lower() for k in _TCN_KEYWORDS):
                h = r.raw_data.get("heat_slug", heat)
                dr = client.get(
                    f"{BASE}/v8/evenement/resultat-participant.jsp"
                    f"?embedded=1&e={event_id}&heat={h}&dossard={r.bib_number}"
                )
                if dr.status_code == 200:
                    _parse_detail(dr.text, r, {})
```

(La détection BC reste par mots-clés sur le club : `resultats-search.jsp?city=nantais` est conservé côté Klikego ; BC s'appuie sur la colonne club/ville du data block, suffisante en pratique. Si nécessaire, factoriser `_collect_nantais_bibs` plus tard.)

- [ ] **Step 5 : Lancer la suite Breizh Chrono**

Run : `cd backend && pytest tests/test_breizhchrono.py -v`
Expected : tous verts.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/scrapers/breizhchrono.py backend/tests/test_breizhchrono.py
git commit -m "fix(scrapers): import Breizh Chrono exhaustif via data block"
```

---

## Task 9 : Tests d'intégration réels (comptes de référence)

**Files :**
- Modify : `backend/tests/test_integration_scrapers.py`

**Interfaces :** aucune (tests réseau, marker `integration`).

- [ ] **Step 1 : Écrire les tests d'intégration**

```python
# backend/tests/test_integration_scrapers.py (ajout)
import pytest
from app.scrapers import breizhchrono, klikego


@pytest.mark.integration
def test_bc_audencia_la_baule_exhaustif():
    results = breizhchrono.scrape_event_all(
        "1488071608761-572", "triathlon-s-light",
        "Triathlon Audencia La Baule 2024", "triathlon-audencia-la-baule-2024",
    )
    assert len(results) == 591
    assert sum(1 for r in results if not r.status) == 483       # finishers
    assert sum(1 for r in results if r.status == "DNF") >= 1
    assert sum(1 for r in results if r.status == "DNS") >= 1
    # splits inter présents pour les finishers (event avec checkpoints)
    assert any(r.bike_time for r in results if not r.status)


@pytest.mark.integration
def test_klikego_nozeen_exhaustif():
    results = klikego.scrape_event_all(
        "1517534975128-8", "duathlon-s---open",
        "6e Duathlon Nozeen 2026", "6e-duathlon-nozeen-2026",
    )
    assert len(results) == 166
    assert sum(1 for r in results if r.status == "DNF") == 27
```

- [ ] **Step 2 : Lancer les tests d'intégration**

Run : `cd backend && pytest -m integration tests/test_integration_scrapers.py -k "audencia or nozeen" -v`
Expected : 2 passed (nécessite le réseau ; les comptes peuvent évoluer si le fournisseur republie — ajuster les constantes le cas échéant).

- [ ] **Step 3 : Commit**

```bash
git add backend/tests/test_integration_scrapers.py
git commit -m "test(scrapers): comptes de référence Audencia (591) et Nozeen (166)"
```

---

## Task 10 : Validation globale (lint + suite complète)

**Files :** aucun (vérification).

- [ ] **Step 1 : Lint**

Run : `cd backend && ruff check app/scrapers/ tests/`
Expected : `All checks passed!` (corriger sinon).

- [ ] **Step 2 : Suite unitaire complète (sans réseau)**

Run : `cd backend && pytest -m "not integration"`
Expected : tous verts. Vérifier en particulier `test_klikego.py`, `test_breizhchrono.py`, `test_services/`, `test_api/`.

- [ ] **Step 3 : Vérifier l'ancien endpoint résiduel**

Run : `cd backend && grep -rn "resultats-search.jsp" app/scrapers/`
Expected : occurrences uniquement dans `_collect_nantais_bibs` (phase TCN volontairement conservée), plus aucune dans la phase de liste principale de klikego/breizhchrono.

- [ ] **Step 4 : Commit final si corrections de lint**

```bash
git add -A && git commit -m "chore(scrapers): lint + nettoyage import exhaustif"
```

---

## Self-Review

**1. Couverture du diagnostic :**
- Participants manquants (433 vs 591) → Tasks 1-3, 6-9 (data block complet, pagination). ✓
- DNF/DNS/DSQ absents → Task 2 (statuts) + assertions Tasks 6-9. ✓
- Issue #11 Nozeen (89 vs 166) → Task 7 + Task 9. ✓
- « Pas de temps » → Task 2 (`total_time` depuis `officiel`) + splits `inter` pour tous (Tasks 4-6). ✓
- Splits pour tous (décision utilisateur) → Tasks 4-6, via `inter` (4 passes/heat) ; fallback : seuls TCN ont les splits fins quand l'event ne publie pas de checkpoints (cas Nozeen). ✓
- Mélange tri/duathlon/relais d'un même event → Task 8 (`event_type` par heat). ✓

**2. Scan placeholders :** aucun TODO/TBD ; tout step de code montre le code complet. ✓

**3. Cohérence des types :** `decode_data_block -> list[list[str]]`, `parse_data_row(list[str]) -> dict`, `fetch_heat_rows -> list[list[str]]`, `fetch_inter_splits -> dict[str, dict[str,str]]`, `build_heat_results -> list[ScrapedResult]`. Noms réutilisés à l'identique entre tasks. ✓

**Risque connu à surveiller pendant l'exécution :** les anciens tests `test_klikego.py` / `test_breizhchrono.py` qui mockaient `resultats-search.jsp` doivent être adaptés au data block (ou supprimés s'ils testaient l'ancien chemin). À traiter dans les Steps de test des Tasks 7-8.

---

## Execution Handoff

Plan complet et sauvegardé dans `docs/superpowers/plans/2026-06-28-fix-scraping-exhaustif.md`. Deux options d'exécution :

1. **Subagent-Driven (recommandé)** — un subagent neuf par task, revue entre les tasks, itération rapide.
2. **Inline Execution** — exécution dans cette session avec checkpoints de revue.

Quelle approche ?
