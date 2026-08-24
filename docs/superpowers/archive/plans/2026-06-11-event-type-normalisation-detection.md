# Normalisation `event_type` & détection mono-sport — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centraliser la classification des disciplines dans un classifieur unique, normaliser tous les `event_type` en slugs canoniques, détecter course à pied / trail / cyclisme, ajouter un champ `distance_km`, et corriger l'existant en base via migration.

**Architecture:** Un module `app/scrapers/classify.py` devient la seule source de vérité (détection + normalisation + extraction km). Les 5 `_detect_event_type` par scraper délèguent vers lui. Un champ `Course.distance_km` est ajouté. Une migration Alembic ajoute la colonne et re-classe les données existantes via une fonction de service testable.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, pytest, ruff (backend-v2) ; Next.js 16 + TypeScript + Vitest (frontend-v2).

**Spec de référence :** `docs/superpowers/specs/2026-06-11-event-type-normalisation-detection-design.md`

**Convention de travail :** toutes les commandes backend s'exécutent depuis `backend-v2/` avec le venv activé ; front depuis `frontend-v2/`. Langue du code/commentaires : **français**.

---

## Fichiers touchés

**Backend (`backend-v2/`)**
- Créer : `app/scrapers/classify.py` — classifieur unique (source de vérité).
- Créer : `tests/test_classify.py` — tests du classifieur.
- Créer : `app/services/reclassify.py` — fonction de re-classement de l'existant.
- Créer : `tests/test_services/test_reclassify.py` — tests du re-classement.
- Créer : `alembic/versions/<hash>_distance_km_et_reclassement.py` — migration.
- Modifier : `app/scrapers/base.py` — champ `distance_km` sur `ScrapedResult`.
- Modifier : `app/services/mapping.py` — splits nouveaux sports, `_sport_base`, `distance_km`.
- Modifier : `app/models/course.py` — colonne `distance_km`.
- Modifier : `app/schemas/course.py` — champ `distance_km` dans `CourseBrief`.
- Modifier : `app/scrapers/klikego.py`, `timepulse.py`, `wiclax.py`, `prolivesport.py`, `sportinnovation.py` — délégation vers `classify`.
- Modifier : `tests/test_services/test_mapping.py` — cas nouveaux sports.

**Frontend (`frontend-v2/`)**
- Modifier : `lib/constants.ts` — libellés + helper `disciplineLabel`.
- Modifier : `lib/sport-colors.ts` — couleurs nouveaux sports.
- Modifier : `lib/types.ts` — `distance_km` sur `CourseBrief`.
- Créer : `lib/__tests__/disciplines.test.ts` — tests labels + `disciplineLabel`.

---

## Task 1 : Classifieur unique `classify.py`

**Files:**
- Create: `backend-v2/app/scrapers/classify.py`
- Test: `backend-v2/tests/test_classify.py`

- [ ] **Step 1 : Écrire les tests du classifieur (échec attendu)**

Créer `backend-v2/tests/test_classify.py` :

```python
"""Tests du classifieur unique de disciplines (source de vérité)."""
import pytest

from app.scrapers.classify import (
    classify_event_type,
    extract_distance_km,
    normalize_event_type,
)


# --- Triathlon (porté de klikego/timepulse/wiclax, non-régression) ---
@pytest.mark.parametrize("text,expected", [
    ("triathlon-s", "triathlon-s"),
    ("triathlon-s-individuel", "triathlon-s"),
    ("format-s-en-individuel", "triathlon-s"),
    ("triathlon-m---individuel", "triathlon-m"),
    ("triathlon-l", "triathlon-l"),
    ("triathlon-xl", "triathlon-xl"),
    ("medoc-atlantique-frenchman-xxl", "triathlon-xl"),
    ("triathlon-xs-jeunes", "triathlon-s"),            # XS triathlon → S (collapse)
    ("Triathlon de Noirmoutier Sprint 2025", "triathlon-s"),
    ("Triathlon Olympique de Paris 2025", "triathlon-m"),
    ("Triathlon L de Bordeaux", "triathlon-l"),
    ("Ironman France 2025", "triathlon-xl"),
    ("Triathlon XXL Embrunman", "triathlon-xl"),
    ("Triathlon 70.3 Aix-en-Provence", "triathlon-l"),
    ("Triathlon de Lacanau 2025", "triathlon"),
    ("Sprint de la Roche", "triathlon-s"),             # pas de sport explicite → triathlon + taille
    ("", "triathlon"),
])
def test_classify_triathlon(text, expected):
    assert classify_event_type(text) == expected


# --- Duathlon ---
@pytest.mark.parametrize("text,expected", [
    ("duathlon-classique", "duathlon"),
    ("duathlon-s-individuel", "duathlon-s"),
    ("duathlon-liffre-cormier-open--xs-court", "duathlon-xs"),
    ("duathlon-liffre-cormier-open--sprint-court", "duathlon-s"),
    ("duathlon-m-individuel", "duathlon-m"),
    ("duathlon-l-individuel", "duathlon-l"),
    ("duathlon-liffre-cormier-clm-par-equipe", "duathlon"),   # "clm" ne doit PAS → cyclisme
    ("Duathlon de Rennes", "duathlon"),
    ("Duathlon Sprint de Couëron 2025", "duathlon-s"),
])
def test_classify_duathlon(text, expected):
    assert classify_event_type(text) == expected


# --- Autres multisports ---
@pytest.mark.parametrize("text,expected", [
    ("swimrun-classique", "swimrun"),
    ("format-s---en-binome re-swimrun-2025", "swimrun-s"),
    ("format-m---en-solo swimrun-cote-beaute-2025", "swimrun-m"),
    ("format-l---championnat re-swimrun-2025", "swimrun-l"),
    ("SwimRun des Îles", "swimrun"),
    ("aquathlon-s-champnat aquathlon-des-2-amants", "aquathlon"),
    ("Aquathlon du RC Doué", "aquathlon"),
    ("Planète Racing Aquarun 2026", "aquarun"),
    ("bikerun-sprint", "bike-run"),
    ("BIKE & RUN d'Halloween", "bike-run"),
    ("Run & Bike du Bignon", "bike-run"),
])
def test_classify_multisport(text, expected):
    assert classify_event_type(text) == expected


# --- Nouveaux mono-sports ---
@pytest.mark.parametrize("text,expected", [
    ("Trail des Forts 23 km", "trail"),
    ("Trail du Mont Blanc L", "trail"),                # ne doit PAS → triathlon-l
    ("Marathon de Nantes 2025", "course-a-pied-marathon"),
    ("Semi-Marathon de Vannes", "course-a-pied-semi"),
    ("Les 10 km de Carquefou", "course-a-pied-10k"),
    ("Foulées du 5 km", "course-a-pied-5k"),
    ("Course sur route de Rezé", "course-a-pied"),
    ("Cyclosportive des Vignes 120 km", "cyclisme-route"),
    ("Cyclisme contre-la-montre", "cyclisme-clm"),
    ("CLM par équipe cyclisme", "cyclisme-clm"),
    ("Cyclisme route 90 km", "cyclisme-route"),
    ("Cyclo de printemps", "cyclisme"),
])
def test_classify_mono_sport(text, expected):
    assert classify_event_type(text) == expected


# --- Normalisation (idempotence + reprise de l'existant) ---
@pytest.mark.parametrize("value,expected", [
    ("Triathlon M", "triathlon-m"),
    ("triathlon-m", "triathlon-m"),       # déjà propre → inchangé
    ("triathlon-l", "triathlon-l"),
    ("duathlon-xs", "duathlon-xs"),
    ("bike-run", "bike-run"),
    ("aquathlon", "aquathlon"),
    ("trail", "trail"),
])
def test_normalize_idempotent(value, expected):
    assert normalize_event_type(value) == expected
    # idempotence stricte : normaliser deux fois = normaliser une fois
    assert normalize_event_type(normalize_event_type(value)) == expected


# --- Extraction du kilométrage ---
@pytest.mark.parametrize("text,expected", [
    ("Trail des Forts 23 km", 23.0),
    ("Cyclo 120km", 120.0),
    ("Trail 42,2 km", 42.2),
    ("Marathon 42.195 km", 42.195),
    ("Triathlon M", None),
    ("", None),
])
def test_extract_distance_km(text, expected):
    assert extract_distance_km(text) == expected
```

- [ ] **Step 2 : Lancer les tests pour vérifier l'échec**

Run: `pytest tests/test_classify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.scrapers.classify'`

- [ ] **Step 3 : Écrire `classify.py`**

Créer `backend-v2/app/scrapers/classify.py` :

```python
"""
Classifieur unique de disciplines — **seule source de vérité**.

Remplace les `_detect_event_type` jadis dupliqués dans chaque scraper. Les
scrapers délèguent ici ; la migration de re-classement réutilise les mêmes
fonctions. Voir la note `registry.py` sur la factorisation.

Forme canonique d'un `event_type` : minuscules, tirets, sport en base +
suffixe de taille optionnel. Le kilométrage exact n'entre jamais dans le slug
(il vit dans `Course.distance_km`).
"""
import re

# Bases de sport « nues » (sans taille). Sert au re-classement à savoir si une
# valeur peut être raffinée. `trail` est volontairement nu (distance via km).
BARE_TYPES = frozenset({
    "triathlon", "duathlon", "swimrun", "cyclisme", "course-a-pied", "trail",
})


def _norm(text: str) -> str:
    return (text or "").lower().strip()


def _detect_size(t: str) -> str:
    """Renvoie la taille détectée : "", "xs", "s", "m", "l", "xl".

    Gère à la fois les slugs (`-m-`, fin `-l`, `format-m`) et les noms humains
    (`olympique`, `sprint`, `longue`, `70.3`, `ironman`…). Ordre : du plus
    grand au plus petit, XL avant L, XS testé après S (un slug `-xs-` ne
    déclenche pas la frontière `-s-`).
    """
    def seg(tag: str) -> bool:
        return (
            f"-{tag}-" in t or t.endswith(f"-{tag}")
            or f" {tag} " in t or t.endswith(f" {tag}")
            or f"format-{tag}" in t
        )

    if "xxl" in t or "ironman" in t or "embrunman" in t or seg("xl"):
        return "xl"
    if "longue" in t or "half" in t or "70.3" in t or seg("l"):
        return "l"
    if "olymp" in t or seg("m"):
        return "m"
    if "sprint" in t or "decouverte" in t or "découverte" in t or seg("s"):
        return "s"
    if "extra" in t or seg("xs"):
        return "xs"
    return ""


def _triathlon(t: str) -> str:
    size = _detect_size(t)
    if not size:
        return "triathlon"
    if size == "xs":  # le triathlon n'a pas de XS canonique → collapse vers S
        size = "s"
    return f"triathlon-{size}"


def _course_a_pied(t: str) -> str | None:
    """Course à pied (route) avec format nommé, ou None si non reconnu."""
    is_cap = (
        "marathon" in t or "semi" in t
        or re.search(r"\b\d+\s*k(m)?\b", t)
        or "course à pied" in t or "course a pied" in t
        or "course sur route" in t or "course pédestre" in t
        or "course pedestre" in t or "foulées" in t or "foulees" in t
        or "corrida" in t or "running" in t
    )
    if not is_cap:
        return None
    if "semi" in t or "half" in t:
        return "course-a-pied-semi"
    if "marathon" in t:
        return "course-a-pied-marathon"
    if re.search(r"\b10\s*k(m)?\b", t):
        return "course-a-pied-10k"
    if re.search(r"\b5\s*k(m)?\b", t):
        return "course-a-pied-5k"
    return "course-a-pied"


def _cyclisme(t: str) -> str | None:
    """Cyclisme route / CLM, ou None si non reconnu."""
    is_velo = (
        "cyclisme" in t or "cyclo" in t or "cyclosport" in t
        or "gran fondo" in t or "granfondo" in t
        or "vélo" in t or "velo" in t
    )
    if not is_velo:
        return None
    if "contre-la-montre" in t or "contre la montre" in t or re.search(r"\bclm\b", t):
        return "cyclisme-clm"
    if "route" in t:
        return "cyclisme-route"
    return "cyclisme"


def classify_event_type(text: str) -> str:
    """Texte libre (nom d'épreuve, heat+slug, parcours…) → slug canonique."""
    t = _norm(text)

    # 1. Multisports composites d'abord (sous-mots piégeux).
    if "swimrun" in t or "swim-run" in t or "swim run" in t or "swim&run" in t:
        size = _detect_size(t)
        return f"swimrun-{size}" if size in ("s", "m", "l") else "swimrun"
    if ("bike" in t and "run" in t) or "bikerun" in t or "bike-run" in t:
        return "bike-run"
    if "aquathlon" in t:
        return "aquathlon"
    if "aquarun" in t:
        return "aquarun"
    if "duathlon" in t:
        size = _detect_size(t)
        return f"duathlon-{size}" if size else "duathlon"

    # 2. Triathlon explicite : logique de distance (avant les mono-sports, car
    #    "half" est ambigu — half-marathon vs half-ironman).
    if "triathlon" in t:
        return _triathlon(t)

    # 3. Mono-sports nouveaux.
    if "trail" in t:
        return "trail"
    cap = _course_a_pied(t)
    if cap:
        return cap
    cyc = _cyclisme(t)
    if cyc:
        return cyc

    # 4. Repli : triathlon nu (+ taille si déductible : « Sprint … », « Ironman … »).
    return _triathlon(t)


def normalize_event_type(value: str) -> str:
    """Canonicalise une valeur existante (`Triathlon M` → `triathlon-m`).

    Idempotent : un slug déjà canonique se renvoie lui-même.
    """
    return classify_event_type(value)


def extract_distance_km(text: str) -> float | None:
    """Extrait un kilométrage explicite (`23 km`, `42,2 km`, `120km`)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*km\b", _norm(text))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run: `pytest tests/test_classify.py -q`
Expected: PASS (tous les cas verts).

- [ ] **Step 5 : Lint + commit**

```bash
ruff check app/scrapers/classify.py tests/test_classify.py
git add app/scrapers/classify.py tests/test_classify.py
git commit -m "feat(backend-v2): classifieur unique de disciplines (classify.py)"
```

---

## Task 2 : `distance_km` sur `ScrapedResult` + mapping nouveaux sports

**Files:**
- Modify: `backend-v2/app/scrapers/base.py` (après `run_time`, vers ligne 33)
- Modify: `backend-v2/app/services/mapping.py:19-44` et `65-75`
- Test: `backend-v2/tests/test_services/test_mapping.py`

- [ ] **Step 1 : Écrire les tests mapping (échec attendu)**

Ajouter à la fin de `backend-v2/tests/test_services/test_mapping.py` :

```python
def test_build_splits_trail_single_run():
    s = _scraped(event_type="trail", run_time="01:45:00")
    assert mapping.build_splits(s) == {"run": "01:45:00"}


def test_build_splits_course_a_pied_named_size():
    # _sport_base doit gérer la base multi-mots "course-a-pied" (pas "course").
    s = _scraped(event_type="course-a-pied-10k", run_time="00:38:00")
    assert mapping.build_splits(s) == {"run": "00:38:00"}


def test_build_splits_cyclisme_single_bike():
    s = _scraped(event_type="cyclisme-route", bike_time="03:10:00")
    assert mapping.build_splits(s) == {"bike": "03:10:00"}


def test_get_or_create_course_extracts_distance_km(db_session):
    s = _scraped(event_name="Trail des Forts 23 km", event_type="trail")
    course = mapping.get_or_create_course(db_session, s, event_url="http://x")
    assert course.distance_km == 23.0


def test_get_or_create_course_explicit_distance_km_wins(db_session):
    s = _scraped(event_name="Trail sans km dans le nom", event_type="trail",
                 distance_km=30.0)
    course = mapping.get_or_create_course(db_session, s, event_url="http://x")
    assert course.distance_km == 30.0
```

- [ ] **Step 2 : Lancer les tests pour vérifier l'échec**

Run: `pytest tests/test_services/test_mapping.py -q`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'distance_km'` (sur `_scraped(distance_km=...)`) et `_sport_base("course-a-pied-10k")` renvoie `course`.

- [ ] **Step 3a : Ajouter le champ à `ScrapedResult`**

Dans `backend-v2/app/scrapers/base.py`, après la ligne `run_time: str = ""` :

```python
    run_time: str = ""
    # Kilométrage de l'épreuve si connu/extrait. Sinon mapping l'extrait du nom.
    distance_km: float | None = None
```

- [ ] **Step 3b : Étendre le mapping**

Dans `backend-v2/app/services/mapping.py`, remplacer le bloc `_SPLIT_KEYS_BY_SPORT` (lignes 23-33) par :

```python
_SPLIT_KEYS_BY_SPORT: dict[str, dict[str, str]] = {
    # Duathlon : course à pied 1 → slot swim, course à pied 2 → slot run.
    "duathlon": {
        "swim_time": "course1", "t1_time": "t1", "bike_time": "bike",
        "t2_time": "t2", "run_time": "course2",
    },
    "aquathlon": {"swim_time": "swim", "t1_time": "t1", "run_time": "run"},
    "aquarun": {"swim_time": "swim", "t1_time": "t1", "run_time": "run"},
    "bike-run": {"bike_time": "bike", "run_time": "run"},
    "swimrun": {"swim_time": "swim", "run_time": "run"},
    # Mono-sports : un seul segment pertinent.
    "course-a-pied": {"run_time": "run"},
    "trail": {"run_time": "run"},
    "cyclisme": {"bike_time": "bike"},
}

# Bases de sport dont le nom contient un tiret (le tiret ne sépare pas la taille).
_MULTI_WORD_BASES = ("bike-run", "course-a-pied")
```

Remplacer `_sport_base` (lignes 36-44) par :

```python
def _sport_base(event_type: str) -> str:
    """Préfixe de sport sans suffixe de taille : ``duathlon-m`` → ``duathlon``.

    Les bases multi-mots (``bike-run``, ``course-a-pied``) contiennent un tiret
    qui fait partie du nom, pas un séparateur de taille.
    """
    et = (event_type or "").lower()
    for base in _MULTI_WORD_BASES:
        if et.startswith(base):
            return base
    return et.split("-", 1)[0]
```

Ajouter l'import en haut de `mapping.py` (après les imports existants `from app.scrapers...`) :

```python
from app.scrapers.classify import extract_distance_km
```

Remplacer `get_or_create_course` (lignes 65-75) par :

```python
def get_or_create_course(db: Session, scraped: ScrapedResult, event_url: str) -> Course:
    """Course identifiée par (nom, date, type) ; `source_url` = URL d'import (clé de cache)."""
    distance_km = scraped.distance_km
    if distance_km is None:
        distance_km = extract_distance_km(scraped.event_name)
    return course_repository.get_or_create(
        db,
        name=scraped.event_name,
        event_date=scraped.event_date,
        event_type=scraped.event_type,
        source_url=event_url or scraped.source_url,
        provider=scraped.provider,
        is_relay=scraped.is_relay,
        distance_km=distance_km,
    )
```

> Note : `course_repository.get_or_create` reçoit `distance_km` — le paramètre est ajouté en Task 3, Step 3c. Exécuter Task 3 avant de relancer les tests d'intégration DB de cette task. Les tests `build_splits` (pas de DB) passent dès maintenant.

- [ ] **Step 4 : Lancer les tests `build_splits` (les 3 premiers)**

Run: `pytest tests/test_services/test_mapping.py -k "build_splits" -q`
Expected: PASS (les nouveaux `build_splits` trail/course-a-pied/cyclisme verts).

> Les deux tests `get_or_create_course_*` resteront rouges jusqu'à Task 3 (colonne + param repo). C'est attendu.

- [ ] **Step 5 : Commit partiel**

```bash
ruff check app/scrapers/base.py app/services/mapping.py
git add app/scrapers/base.py app/services/mapping.py tests/test_services/test_mapping.py
git commit -m "feat(backend-v2): mapping splits mono-sport + extraction distance_km"
```

---

## Task 3 : Colonne `Course.distance_km` + schéma + repo

**Files:**
- Modify: `backend-v2/app/models/course.py`
- Modify: `backend-v2/app/repositories/course_repository.py:29-52`
- Modify: `backend-v2/app/schemas/course.py:7-15`
- Test: réutilise les 2 tests `get_or_create_course_*` de Task 2.

- [ ] **Step 1 : Ajouter la colonne au modèle**

Dans `backend-v2/app/models/course.py` :
- Ajouter `Float` à l'import SQLAlchemy : `from sqlalchemy import Boolean, Date, DateTime, Float, String, UniqueConstraint`
- Après la ligne `event_type: Mapped[str] = ...` :

```python
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
```

- [ ] **Step 2 : Étendre le repository**

Dans `backend-v2/app/repositories/course_repository.py`, dans `get_or_create` : ajouter le paramètre `distance_km: float | None = None` dans la signature (après `is_relay`) et le passer au constructeur `Course(...)` :

```python
def get_or_create(
    db: Session,
    *,
    name: str,
    event_date: date | None,
    event_type: str,
    source_url: str = "",
    provider: str = "",
    is_relay: bool = False,
    distance_km: float | None = None,
) -> Course:
    existing = get_by_identity(db, name, event_date, event_type)
    if existing:
        return existing
    course = Course(
        name=name,
        event_date=event_date,
        event_type=event_type,
        source_url=source_url,
        provider=provider,
        is_relay=is_relay,
        distance_km=distance_km,
    )
    db.add(course)
    db.flush()
    return course
```

- [ ] **Step 3 : Exposer dans le schéma API**

Dans `backend-v2/app/schemas/course.py`, dans `CourseBrief`, après `is_relay: bool = False` :

```python
    distance_km: float | None = None
```

- [ ] **Step 4 : Lancer les tests mapping complets**

Run: `pytest tests/test_services/test_mapping.py -q`
Expected: PASS (y compris les 2 `get_or_create_course_*` désormais verts).

- [ ] **Step 5 : Commit**

```bash
ruff check app/models/course.py app/repositories/course_repository.py app/schemas/course.py
git add app/models/course.py app/repositories/course_repository.py app/schemas/course.py
git commit -m "feat(backend-v2): colonne Course.distance_km (modèle, repo, schéma)"
```

---

## Task 4 : Délégation des 5 scrapers vers `classify`

**Files:**
- Modify: `backend-v2/app/scrapers/klikego.py:399-455`
- Modify: `backend-v2/app/scrapers/timepulse.py:357-387`
- Modify: `backend-v2/app/scrapers/wiclax.py:388-405`
- Modify: `backend-v2/app/scrapers/prolivesport.py:151-184`
- Modify: `backend-v2/app/scrapers/sportinnovation.py:80-98`
- Test: suites scrapers existantes (non-régression).

- [ ] **Step 1 : Vérifier l'état vert de départ des scrapers**

Run: `pytest tests/test_klikego.py tests/test_timepulse.py tests/test_wiclax.py tests/test_prolivesport.py tests/test_sportinnovation.py -q`
Expected: PASS (référence avant refactor).

- [ ] **Step 2 : Remplacer chaque `_detect_event_type` par une délégation**

`klikego.py` — remplacer tout le corps de `_detect_event_type` (lignes 399-455) par :

```python
def _detect_event_type(heat: str, slug: str = "") -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(f"{heat} {slug}")
```

`timepulse.py` — remplacer le corps de `_detect_event_type` (lignes 357-387) par :

```python
def _detect_event_type(name: str) -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(name)
```

`wiclax.py` — remplacer le corps de `_detect_event_type` (lignes 388-405) par :

```python
def _detect_event_type(name: str) -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(name)
```

`prolivesport.py` — remplacer le corps de `_detect_event_type` (lignes 151-184) par :

```python
def _detect_event_type(race: str) -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(race)
```

`sportinnovation.py` — remplacer le corps de `_detect_event_type` (lignes 80-98) par :

```python
def _detect_event_type(race_name: str) -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(race_name)
```

> Import local dans chaque fonction pour éviter tout risque de cycle d'import au chargement des modules scrapers. Les fonctions `_detect_event_type` sont conservées (mêmes signatures) car référencées par les tests et les call sites.

- [ ] **Step 3 : Lancer les suites scrapers (non-régression)**

Run: `pytest tests/test_klikego.py tests/test_timepulse.py tests/test_wiclax.py tests/test_prolivesport.py tests/test_sportinnovation.py -q`
Expected: PASS. Si un cas échoue, comparer le résultat de `classify_event_type` au cas attendu : soit ajuster le classifieur (Task 1) si c'est un vrai écart, soit corriger l'assertion du test seulement si l'ancien comportement était erroné (ex. `triathlon-xs` n'existe pas dans la taxonomie). Documenter tout changement d'assertion dans le message de commit.

- [ ] **Step 4 : Suite complète backend**

Run: `pytest -m "not integration" -q`
Expected: PASS (l'ensemble des tests unitaires verts).

- [ ] **Step 5 : Commit**

```bash
ruff check app/scrapers/
git add app/scrapers/klikego.py app/scrapers/timepulse.py app/scrapers/wiclax.py app/scrapers/prolivesport.py app/scrapers/sportinnovation.py
git commit -m "refactor(backend-v2): scrapers délèguent la détection à classify"
```

---

## Task 5 : Service de re-classement `reclassify_existing`

**Files:**
- Create: `backend-v2/app/services/reclassify.py`
- Test: `backend-v2/tests/test_services/test_reclassify.py`

- [ ] **Step 1 : Écrire les tests (échec attendu)**

Créer `backend-v2/tests/test_services/test_reclassify.py` :

```python
"""Tests du re-classement de l'existant (normalisation + raffinage + km)."""
from app.models.course import Course
from app.services.reclassify import reclassify_existing


def _add(db, **kw):
    c = Course(**kw)
    db.add(c)
    db.flush()
    return c


def test_normalise_casse_et_format(db_session):
    c = _add(db_session, name="Triathlon de Test 2026", event_type="Triathlon M")
    reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.event_type == "triathlon-m"


def test_raffine_nu_meme_famille_depuis_le_nom(db_session):
    # "triathlon" nu + nom révélant la distance → raffiné dans la même famille.
    c = _add(db_session, name="Triathlon Olympique de Nantes", event_type="triathlon")
    reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.event_type == "triathlon-m"


def test_ne_change_pas_de_famille(db_session):
    # "triathlon" nu dont le nom parle d'un marathon → on NE bascule PAS de famille
    # (conservateur ; correction laissée au re-scrape). Reste "triathlon".
    c = _add(db_session, name="Marathon de la Ville", event_type="triathlon")
    reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.event_type == "triathlon"


def test_backfill_distance_km(db_session):
    c = _add(db_session, name="Trail des Forts 23 km", event_type="trail")
    reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.distance_km == 23.0


def test_idempotent(db_session):
    c = _add(db_session, name="Triathlon de Test 2026", event_type="Triathlon M")
    n1 = reclassify_existing(db_session)
    n2 = reclassify_existing(db_session)
    db_session.refresh(c)
    assert c.event_type == "triathlon-m"
    assert n1 == 1  # une course modifiée au 1er passage
    assert n2 == 0  # rien à faire au 2e passage


def test_fusionne_les_doublons_d_identite(db_session):
    # Après normalisation, "Triathlon M" et "triathlon-m" (même nom+date) entrent
    # en collision d'identité → la participation est repointée et le doublon supprimé.
    from app.models.athlete import Athlete
    from app.models.participation import Participation

    canon = _add(db_session, name="Triathlon X", event_date=None, event_type="triathlon-m")
    dup = _add(db_session, name="Triathlon X", event_date=None, event_type="Triathlon M")
    ath = Athlete(nom="Doe", prenom="Jane")
    db_session.add(ath)
    db_session.flush()
    db_session.add(Participation(athlete_id=ath.id, course_id=dup.id, bib_number="42"))
    db_session.flush()

    reclassify_existing(db_session)

    remaining = db_session.query(Course).filter(Course.name == "Triathlon X").all()
    assert len(remaining) == 1
    assert remaining[0].id == canon.id
    parts = db_session.query(Participation).filter(
        Participation.course_id == canon.id
    ).all()
    assert len(parts) == 1
    assert parts[0].bib_number == "42"
```

- [ ] **Step 2 : Lancer les tests pour vérifier l'échec**

Run: `pytest tests/test_services/test_reclassify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.reclassify'`

- [ ] **Step 3 : Écrire `reclassify.py`**

Créer `backend-v2/app/services/reclassify.py` :

```python
"""
Re-classement de l'existant en base : normalise les `event_type` vers la forme
canonique, raffine les valeurs nues à partir du nom d'épreuve (même famille
seulement) et complète `distance_km`. Sans réseau, idempotent.

Réutilisé par la migration Alembic. Isolé ici pour être testable hors Alembic.
"""
from sqlalchemy.orm import Session

from app.models.course import Course
from app.repositories import course_repository
from app.scrapers.classify import (
    BARE_TYPES,
    classify_event_type,
    extract_distance_km,
    normalize_event_type,
)


def _sport_base(event_type: str) -> str:
    for base in ("bike-run", "course-a-pied"):
        if event_type.startswith(base):
            return base
    return event_type.split("-", 1)[0]


def _resolve_event_type(course: Course) -> str:
    """Type canonique cible : normalise, puis raffine depuis le nom si le type
    reste nu (même famille uniquement, conservateur)."""
    new_type = normalize_event_type(course.event_type)
    if new_type in BARE_TYPES:
        candidate = classify_event_type(course.name)
        if candidate not in BARE_TYPES and _sport_base(candidate) == _sport_base(new_type):
            new_type = candidate
    return new_type


def reclassify_existing(db: Session) -> int:
    """Applique le re-classement à toutes les courses. Renvoie le nombre modifié."""
    changed = 0
    for course in db.query(Course).all():
        new_type = _resolve_event_type(course)

        # Backfill distance_km.
        if course.distance_km is None:
            km = extract_distance_km(course.name)
            if km is not None:
                course.distance_km = km
                changed += 1

        if new_type == course.event_type:
            continue

        # Collision d'identité (nom, date, new_type) avec une course existante ?
        target = course_repository.get_by_identity(
            db, course.name, course.event_date, new_type
        )
        if target is not None and target.id != course.id:
            # Fusion : repointer les participations vers la course canonique via
            # la relation (back_populates), pour les retirer de
            # `course.participations` AVANT le delete et éviter le cascade
            # delete-orphan qui les supprimerait. (Limite connue : collision de
            # dossard entre les deux courses non gérée — improbable, événements
            # distincts.)
            for part in list(course.participations):
                part.course = target
            db.delete(course)
        else:
            course.event_type = new_type
        changed += 1

    db.flush()
    return changed
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run: `pytest tests/test_services/test_reclassify.py -q`
Expected: PASS.

- [ ] **Step 5 : Lint + commit**

```bash
ruff check app/services/reclassify.py tests/test_services/test_reclassify.py
git add app/services/reclassify.py tests/test_services/test_reclassify.py
git commit -m "feat(backend-v2): service reclassify_existing (normalisation + raffinage + km)"
```

---

## Task 6 : Migration Alembic (colonne + re-classement)

**Files:**
- Create: `backend-v2/alembic/versions/<hash>_distance_km_et_reclassement.py`

- [ ] **Step 1 : Générer le squelette de migration**

Run: `alembic revision -m "distance_km et reclassement event_type"`
Expected: crée un fichier `alembic/versions/<hash>_distance_km_et_reclassement.py` avec `down_revision = 'e4211f35a275'`.

> Si `down_revision` n'est pas `'e4211f35a275'`, le corriger manuellement (c'est la seule révision existante, la tête actuelle).

- [ ] **Step 2 : Écrire le contenu de la migration**

Remplacer le corps de `upgrade()` / `downgrade()` du fichier généré par :

```python
"""distance_km et reclassement event_type

Revision ID: <hash>
Revises: e4211f35a275
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from app.services.reclassify import reclassify_existing

revision: str = "<hash>"
down_revision: str | None = "e4211f35a275"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Schéma : nouvelle colonne nullable.
    op.add_column("courses", sa.Column("distance_km", sa.Float(), nullable=True))
    # 2. Données : normalisation + raffinage + backfill km (sans réseau, idempotent).
    bind = op.get_bind()
    session = Session(bind=bind)
    reclassify_existing(session)
    session.commit()


def downgrade() -> None:
    op.drop_column("courses", "distance_km")
```

> Conserver l'`<hash>` réel généré (présent dans le nom du fichier et la variable `revision`).

- [ ] **Step 3 : Appliquer la migration sur une base de test jetable**

```bash
DATABASE_URL="sqlite:///_migration_check.db" alembic upgrade head
```
Expected: `Running upgrade e4211f35a275 -> <hash>` sans erreur.

- [ ] **Step 4 : Vérifier le downgrade puis ré-upgrade**

```bash
DATABASE_URL="sqlite:///_migration_check.db" alembic downgrade -1
DATABASE_URL="sqlite:///_migration_check.db" alembic upgrade head
rm -f _migration_check.db
```
Expected: les deux sens s'exécutent sans erreur.

- [ ] **Step 5 : Commit**

```bash
git add alembic/versions/
git commit -m "feat(backend-v2): migration distance_km + reclassement event_type"
```

---

## Task 7 : Frontend — libellés, distance, couleurs

**Files:**
- Modify: `frontend-v2/lib/constants.ts`
- Modify: `frontend-v2/lib/sport-colors.ts:13-22`
- Modify: `frontend-v2/lib/types.ts:11-19`
- Test: `frontend-v2/lib/__tests__/disciplines.test.ts`

- [ ] **Step 1 : Écrire le test Vitest (échec attendu)**

Créer `frontend-v2/lib/__tests__/disciplines.test.ts` :

```ts
import { describe, expect, it } from "vitest";
import { disciplineLabel, eventTypeLabel } from "@/lib/constants";

describe("eventTypeLabel", () => {
  it("libelle les slugs nus", () => {
    expect(eventTypeLabel("triathlon")).toBe("Triathlon");
    expect(eventTypeLabel("duathlon")).toBe("Duathlon");
    expect(eventTypeLabel("swimrun")).toBe("SwimRun");
  });

  it("libelle les nouveaux mono-sports", () => {
    expect(eventTypeLabel("trail")).toBe("Trail");
    expect(eventTypeLabel("course-a-pied-marathon")).toBe("Marathon");
    expect(eventTypeLabel("cyclisme-clm")).toBe("Cyclisme (CLM)");
  });
});

describe("disciplineLabel", () => {
  it("ajoute le kilométrage quand présent", () => {
    expect(disciplineLabel({ event_type: "trail", distance_km: 23 })).toBe(
      "Trail · 23 km",
    );
  });

  it("omet le kilométrage si absent", () => {
    expect(disciplineLabel({ event_type: "trail", distance_km: null })).toBe(
      "Trail",
    );
  });
});
```

- [ ] **Step 2 : Lancer le test pour vérifier l'échec**

Run (depuis `frontend-v2/`): `npm test -- disciplines`
Expected: FAIL — `disciplineLabel` n'existe pas, labels manquants.

- [ ] **Step 3a : Compléter `constants.ts`**

Remplacer le contenu de `frontend-v2/lib/constants.ts` par :

```ts
export const EVENT_TYPE_LABELS: Record<string, string> = {
  triathlon: "Triathlon",
  "triathlon-s": "Triathlon S",
  "triathlon-m": "Triathlon M",
  "triathlon-l": "Triathlon L",
  "triathlon-xl": "Triathlon XL",
  duathlon: "Duathlon",
  "duathlon-xs": "Duathlon XS",
  "duathlon-s": "Duathlon S",
  "duathlon-m": "Duathlon M",
  "duathlon-l": "Duathlon L",
  swimrun: "SwimRun",
  "swimrun-s": "SwimRun S",
  "swimrun-m": "SwimRun M",
  "swimrun-l": "SwimRun L",
  aquathlon: "Aquathlon",
  aquarun: "Aquarun",
  "bike-run": "Bike & Run",
  "course-a-pied": "Course à pied",
  "course-a-pied-5k": "5 km",
  "course-a-pied-10k": "10 km",
  "course-a-pied-semi": "Semi-marathon",
  "course-a-pied-marathon": "Marathon",
  trail: "Trail",
  cyclisme: "Cyclisme",
  "cyclisme-route": "Cyclisme (route)",
  "cyclisme-clm": "Cyclisme (CLM)",
};

export const EVENT_TYPE_OPTIONS: { value: string; label: string }[] =
  Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => ({ value, label }));

export function eventTypeLabel(type: string | null | undefined): string {
  if (!type) return "";
  return EVENT_TYPE_LABELS[type] ?? type;
}

/** Libellé complet d'une discipline : type + kilométrage si disponible. */
export function disciplineLabel(course: {
  event_type: string | null | undefined;
  distance_km?: number | null;
}): string {
  const label = eventTypeLabel(course.event_type);
  if (course.distance_km) {
    return `${label} · ${course.distance_km} km`;
  }
  return label;
}
```

- [ ] **Step 3b : Étendre les couleurs**

Dans `frontend-v2/lib/sport-colors.ts`, remplacer `eventTypeColor` (lignes 13-22) par :

```ts
/** Couleur associée à une famille de type d'épreuve. */
export function eventTypeColor(type: string | null | undefined): string {
  const t = (type ?? "").toLowerCase();
  if (t.startsWith("triathlon")) return DISCIPLINE_COLORS.accent;
  if (t.startsWith("duathlon") || t === "bike-run" || t.startsWith("cyclisme"))
    return DISCIPLINE_COLORS.bike;
  if (t.startsWith("swimrun") || t === "aquathlon" || t === "aquarun")
    return DISCIPLINE_COLORS.swim;
  if (t.startsWith("trail") || t.startsWith("course-a-pied"))
    return DISCIPLINE_COLORS.run;
  return "var(--muted-foreground)";
}
```

- [ ] **Step 3c : Ajouter `distance_km` au type `CourseBrief`**

Dans `frontend-v2/lib/types.ts`, dans `CourseBrief`, après `is_relay: boolean;` :

```ts
  distance_km?: number | null;
```

- [ ] **Step 4 : Lancer le test pour vérifier qu'il passe**

Run: `npm test -- disciplines`
Expected: PASS.

- [ ] **Step 5 : Build + suite front + commit**

```bash
npm run lint
npm test
npm run build
git add lib/constants.ts lib/sport-colors.ts lib/types.ts lib/__tests__/disciplines.test.ts
git commit -m "feat(frontend-v2): libellés disciplines complets, distance_km, couleurs mono-sport"
```

---

## Task 8 : Vérification finale

- [ ] **Step 1 : Suite backend complète (hors réseau)**

Run (depuis `backend-v2/`): `pytest -m "not integration" -q`
Expected: PASS (130 tests d'origine + nouveaux, tous verts).

- [ ] **Step 2 : Lint backend**

Run: `ruff check .`
Expected: aucun problème.

- [ ] **Step 3 : Suite + build front**

Run (depuis `frontend-v2/`): `npm test && npm run build`
Expected: tests verts, build prod OK.

- [ ] **Step 4 : Brancher l'affichage `disciplineLabel` (optionnel, hors périmètre data)**

Si souhaité, remplacer les appels `eventTypeLabel(course.event_type)` par
`disciplineLabel(course)` dans les composants affichant une course avec son
kilométrage (ex. `components/results/ResultCard`, page `courses/[id]`). À faire
seulement si on veut voir le « · 23 km » côté UI ; sinon le helper reste prêt.

---

## Notes & limites

- **Re-classement conservateur** : une valeur nue n'est raffinée que dans la
  **même famille** de sport (un `triathlon` nu dont le nom dit « Marathon » reste
  `triathlon` ; la correction inter-famille passera par un futur re-scrape).
- **Fusion de doublons** : la collision de dossard entre deux courses fusionnées
  n'est pas gérée (improbable car événements distincts) — documentée dans
  `reclassify.py`.
- **`distance_km`** ne reconnaît que les formes explicites « NN km ». Les
  distances canoniques de la route (`course-a-pied-marathon`…) restent portées
  par le slug, sans `distance_km` obligatoire.
- **Déploiement** : backend-v2 n'est pas encore déployé ; la migration s'appliquera
  via `alembic upgrade head` lors de la bascule (cf. AGENTS.md).
