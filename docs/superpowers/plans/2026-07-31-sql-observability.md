# Observabilité des requêtes SQL — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner au backend de quoi mesurer ce que coûtent ses requêtes SQL — durée, volume, N+1 — sur l'API web comme sur les batches CLI, sans rien coûter tant que la mesure est éteinte.

**Architecture:** Deux étages indépendants, aucun lien de code entre eux. (1) `app/core/sql_observability.py` pose des listeners SQLAlchemy sur l'engine : seuil de lenteur toujours actif en WARNING, plus un bilan agrégé par unité de travail (requête HTTP, épreuve importée) ouvert par un context manager. (2) `app/core/tracing.py` pose un socle OpenTelemetry éteint par défaut, dont les imports sont paresseux, prêt à recevoir un collecteur le jour venu.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 (listeners `before_cursor_execute` / `after_cursor_execute`), FastAPI (middleware ASGI pur), pydantic-settings, OpenTelemetry SDK + instrumentations FastAPI/SQLAlchemy, pytest.

**Spec :** `docs/superpowers/specs/2026-07-31-sql-observability-design.md` — elle fait foi. **Issue :** #89.

## Global Constraints

- **Langue** (constitution, Principe I) : français pour ce qui est visible utilisateur ou métier (docstrings de règle métier, messages, docs) ; anglais pour la couche technique invisible (identifiants, noms de tests… — mais **ce dépôt nomme ses tests en français**, cf. `tests/test_core/test_session_scope.py` : suivre l'existant).
- **TDD** (constitution, Principe III) : le test est écrit et **vu échouer** avant l'implémentation. Non négociable.
- **`ruff check .` doit passer** — `line-length = 100`, règles `E, F, I, W, UP, B`.
- **Aucun paramètre lié SQL ne doit apparaître dans un log.** C'est la garde de données personnelles ; le test 5 de la tâche 2 la verrouille.
- **Aucun enregistrement de log ne doit contenir de retour à la ligne** : le formateur JSON d'`app/core/logging.py` construit son objet à la main (`"message":"%(message)s"`).
- **stdout de la CLI reste parsable** : logs et spans sur **stderr**, jamais stdout.
- **Tests sans réseau** : rien de ce plan n'est marqué `integration`.
- Commandes depuis `backend/` : `uv run pytest -m "not integration"`, `uv run ruff check .`.
- Conventional Commits, en français après le préfixe.

---

## Structure des fichiers

| Fichier | Responsabilité |
| --- | --- |
| `backend/app/core/sql_observability.py` | **Créé.** Listeners, seuil de lenteur, accumulateur, `measure_queries`, middleware ASGI. Tout l'étage maison. |
| `backend/app/core/tracing.py` | **Créé.** Socle OTel : construction du provider, instrumentations, arrêt. |
| `backend/app/core/config.py` | **Modifié.** Trois réglages. |
| `backend/app/core/database.py` | **Modifié.** Appelle `install()` sur l'engine applicatif. |
| `backend/app/main.py` | **Modifié.** Monte le middleware, appelle `setup_tracing()`. |
| `backend/app/services/batch.py` | **Modifié.** Une épreuve = une unité de travail. |
| `backend/app/cli/__init__.py` | **Modifié.** Démarrage et arrêt du traçage CLI. |
| `backend/app/cli/__main__.py` | **Modifié.** Appelle les deux. |
| `backend/tests/test_core/test_sql_observability.py` | **Créé.** Étage maison. |
| `backend/tests/test_core/test_tracing.py` | **Créé.** Étage OTel. |
| `backend/pyproject.toml` | **Modifié.** Quatre dépendances OTel. |
| `backend/.env.example`, `AGENTS.md` | **Modifiés.** Documentation. |

Le middleware ASGI vit dans `sql_observability.py` et non dans `app/api/` : un middleware ASGI pur n'importe ni FastAPI ni Starlette (il ne manipule que des dicts et des callables), il n'introduit donc aucun couplage web dans `core/`, et il est indissociable de `measure_queries` qu'il enveloppe.

---

## Task 1: Réglages de configuration

**Files:**
- Modify: `backend/app/core/config.py:45-49` (après le bloc « Cache TTL », avant « Géocodage »)
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: rien.
- Produces: `Settings.sql_slow_query_ms: int` (défaut `100`), `Settings.sql_query_stats: bool` (défaut `False`), `Settings.otel_enabled: bool` (défaut `False`). Variables d'environnement correspondantes : `SQL_SLOW_QUERY_MS`, `SQL_QUERY_STATS`, `OTEL_ENABLED`.

- [ ] **Step 1: Write the failing tests**

Ajouter à la fin de `backend/tests/test_config.py` :

```python
def test_observabilite_sql_defauts(monkeypatch):
    """Défauts : seuil à 100 ms, bilan et OTel éteints.

    Le bilan et OTel sont éteints par défaut parce qu'ils coûtent ; le seuil,
    lui, est le garde-fou permanent.
    """
    for var in ("SQL_SLOW_QUERY_MS", "SQL_QUERY_STATS", "OTEL_ENABLED"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings()
    assert settings.sql_slow_query_ms == 100
    assert settings.sql_query_stats is False
    assert settings.otel_enabled is False


def test_observabilite_sql_depuis_env(monkeypatch):
    monkeypatch.setenv("SQL_SLOW_QUERY_MS", "250")
    monkeypatch.setenv("SQL_QUERY_STATS", "true")
    monkeypatch.setenv("OTEL_ENABLED", "true")
    settings = Settings()
    assert settings.sql_slow_query_ms == 250
    assert settings.sql_query_stats is True
    assert settings.otel_enabled is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'sql_slow_query_ms'`

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/core/config.py`, insérer après le bloc « Cache TTL dynamique » et avant « Géocodage » :

```python
    # ── Observabilité SQL (issue #89) ─────────────────────────────────────────
    # Garde-fou permanent : toute requête au-delà du seuil sort en WARNING.
    # 0 désactive ce log ; avec `sql_query_stats` à False, plus aucun listener
    # n'est posé — coût strictement nul.
    sql_slow_query_ms: int = 100
    # Bilan agrégé par unité de travail (requête HTTP, épreuve importée) : c'est
    # lui qui rend un N+1 visible. Verbeux, donc éteint par défaut.
    sql_query_stats: bool = False
    # Socle OpenTelemetry. Éteint = aucun paquet OTel n'est même chargé.
    # L'exporter se règle par la variable standard OTEL_TRACES_EXPORTER.
    otel_enabled: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v && uv run ruff check .`
Expected: PASS, lint clean

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_config.py
git commit -m "feat(core): ajoute les réglages d'observabilité SQL (#89)"
```

---

## Task 2: Seuil de lenteur — listeners SQLAlchemy

**Files:**
- Create: `backend/app/core/sql_observability.py`
- Test: `backend/tests/test_core/test_sql_observability.py` (créé)

**Interfaces:**
- Consumes: rien (les valeurs de réglage sont **passées en arguments**, le module ne lit jamais `get_settings()` — c'est ce qui le rend testable sans toucher au cache `lru_cache`).
- Produces:
  - `normalize_sql(statement: str) -> str`
  - `install(engine: Engine, *, slow_query_ms: float, collect_stats: bool) -> None`
  - `is_installed(engine: Engine) -> bool`
  - constantes de module `_SQL_MAX_CHARS = 200`, `_TOP_N = 5`
  - logger nommé `app.sql`

`slow_query_ms` est un `float` et non un `int` : le réglage est entier, mais les
tests passent des valeurs sous la milliseconde pour forcer le déclenchement.

- [ ] **Step 1: Write the failing tests**

Créer `backend/tests/test_core/test_sql_observability.py` :

```python
"""Tests de l'observabilité SQL (issue #89)."""
import logging

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def engine():
    """Engine SQLite jetable — `install()` prend l'engine en argument, donc
    instrumenter celui-ci n'affecte aucun autre test."""
    eng = create_engine("sqlite://")
    yield eng
    eng.dispose()


def test_requete_au_dessus_du_seuil_sort_en_warning(engine, caplog):
    """Seuil à 0 ms : toute requête est « lente », donc journalisée."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)

    with caplog.at_level(logging.WARNING, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    assert any("SELECT 1" in r.message for r in caplog.records)
    assert all(r.levelno == logging.WARNING for r in caplog.records)


def test_requete_sous_le_seuil_ne_journalise_rien(engine, caplog):
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=60_000, collect_stats=False)

    with caplog.at_level(logging.DEBUG, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    assert caplog.records == []


def test_seuil_nul_et_bilan_eteint_ne_pose_aucun_listener(engine, caplog):
    """L'échappatoire « coût strictement nul » : rien n'est posé du tout."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=False)

    assert sql_observability.is_installed(engine) is False
    with caplog.at_level(logging.DEBUG, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    assert caplog.records == []


def test_install_est_idempotent(engine, caplog):
    """Deux appels ne doivent pas doubler les listeners — sinon chaque requête
    serait comptée et journalisée deux fois."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)
    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)

    assert sql_observability.is_installed(engine) is True
    with caplog.at_level(logging.WARNING, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    lentes = [r for r in caplog.records if "SELECT 1" in r.getMessage()]
    assert len(lentes) == 1


def test_aucun_parametre_lie_ne_fuit_dans_les_logs(engine, caplog):
    """Garde de données personnelles : les valeurs liées portent des noms
    d'athlètes et des libellés de club. Seule la forme paramétrée est journalisée.

    Test de non-régression à part entière : c'est la seule chose qui empêche des
    noms de membres du club de partir dans les logs Render.
    """
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)

    with caplog.at_level(logging.WARNING, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT :valeur"), {"valeur": "LEMÉE"})

    assert caplog.records, "la requête aurait dû être journalisée"
    assert all("LEMÉE" not in r.getMessage() for r in caplog.records)


def test_aucun_message_ne_contient_de_retour_a_la_ligne(engine, caplog):
    """Le formateur JSON d'app.core.logging construit son objet à la main :
    un retour à la ligne dans le message casserait le JSON."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0.0001, collect_stats=False)

    with caplog.at_level(logging.WARNING, logger="app.sql"):
        with engine.connect() as conn:
            conn.execute(text("SELECT 1\n  UNION SELECT 2"))

    assert caplog.records
    assert all("\n" not in r.getMessage() for r in caplog.records)


def test_normalize_sql_compacte_et_tronque():
    from app.core.sql_observability import normalize_sql

    assert normalize_sql("SELECT   1\n  FROM t") == "SELECT 1 FROM t"
    long = "SELECT " + "x" * 500
    assert len(normalize_sql(long)) == 201  # 200 caractères + l'ellipse
    assert normalize_sql(long).endswith("…")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_core/test_sql_observability.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.sql_observability'`

- [ ] **Step 3: Write minimal implementation**

Créer `backend/app/core/sql_observability.py` :

```python
"""Observabilité des requêtes SQL : durée, volume, N+1 (issue #89).

Deux niveaux indépendants, tous deux posés par `install()` :

- **seuil de lenteur** — toute requête au-delà de `slow_query_ms` sort en
  WARNING sur le logger dédié `app.sql` ;
- **bilan par unité de travail** — `measure_queries(label)` compte les requêtes
  d'une requête HTTP ou d'une épreuve importée et rend un bilan agrégé, où un
  N+1 se lit d'un coup d'œil (« x1810 » sur la même requête).

Deux règles structurantes, à ne pas relâcher :

1. **Le SQL est journalisé paramétré**, jamais avec ses valeurs liées : elles
   portent des noms d'athlètes et des libellés de club, qui n'ont rien à faire
   dans les logs Render. La forme paramétrée est aussi la clé d'agrégation.
2. **Un enregistrement ne contient jamais de retour à la ligne** : le formateur
   JSON d'`app.core.logging` construit son objet à la main, un saut de ligne
   brut y casserait le JSON. Le bilan sort donc en plusieurs enregistrements.

Les réglages sont **passés en arguments** plutôt que lus ici : le module reste
testable sans toucher au cache de `get_settings()`.
"""
import logging
from time import perf_counter
from weakref import WeakSet

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("app.sql")

_SQL_MAX_CHARS = 200
_TOP_N = 5
_INFO_KEY = "tcn_query_start"

# Engines déjà instrumentés : rend `install()` idempotent (deux appels
# doubleraient sinon comptes et journaux) et se vérifie depuis les tests.
# `WeakSet` pour ne pas retenir en vie un engine jetable.
_installed: WeakSet = WeakSet()


def is_installed(engine: Engine) -> bool:
    """L'engine porte-t-il les listeners de mesure ?"""
    return engine in _installed


def normalize_sql(statement: str) -> str:
    """Requête sur une seule ligne, tronquée.

    Sert à la fois de forme journalisée et de **clé d'agrégation** du bilan :
    c'est elle qui fait apparaître le « x1810 » d'un N+1.
    """
    compact = " ".join(statement.split())
    if len(compact) > _SQL_MAX_CHARS:
        return compact[:_SQL_MAX_CHARS] + "…"
    return compact


def install(engine: Engine, *, slow_query_ms: float, collect_stats: bool) -> None:
    """Pose les listeners de mesure sur `engine`.

    L'engine est passé en argument — et non écouté sur la classe `Engine`, comme
    l'est le listener SQLite de `database.py` — pour que les tests instrumentent
    un engine jetable sans instrumenter la suite entière.

    Seuil nul **et** bilan éteint : aucun listener n'est posé, coût strictement
    nul. C'est l'échappatoire pour tout éteindre.

    Idempotent : un second appel sur le même engine ne repose rien.
    """
    if slow_query_ms <= 0 and not collect_stats:
        return
    if engine in _installed:
        return
    _installed.add(engine)

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        # Une pile, pas une valeur simple : elle tient la réentrance. `conn.info`
        # est propre à la Connection, donc au thread qui l'utilise.
        conn.info.setdefault(_INFO_KEY, []).append(perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        starts = conn.info.get(_INFO_KEY)
        if not starts:
            return
        elapsed_ms = (perf_counter() - starts.pop()) * 1000
        sql = normalize_sql(statement)

        if 0 < slow_query_ms <= elapsed_ms:
            logger.warning("Requête lente | %.1f ms | %s", elapsed_ms, sql)
```

Note d'implémentation : `after_cursor_execute` n'est pas appelé quand la requête lève — c'est assumé (l'échec remonte déjà en exception) et sans fuite d'état, la pile vivant sur la `Connection` jetée avec elle. Les listeners ne font aucune I/O et ne sont volontairement pas gardés par un `try`/`except` : un `except` silencieux ici masquerait ses propres bugs.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_core/test_sql_observability.py -v && uv run ruff check .`
Expected: PASS (7 tests), lint clean

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/sql_observability.py backend/tests/test_core/test_sql_observability.py
git commit -m "feat(core): journalise les requêtes SQL au-delà d'un seuil (#89)"
```

---

## Task 3: Bilan agrégé par unité de travail

**Files:**
- Modify: `backend/app/core/sql_observability.py`
- Test: `backend/tests/test_core/test_sql_observability.py`

**Interfaces:**
- Consumes: `install(engine, *, slow_query_ms, collect_stats)`, `normalize_sql(statement)` de la tâche 2.
- Produces:
  - `QueryStats` — dataclass : `label: str`, `count: int`, `total_ms: float`, `by_sql: Counter[str]`
  - `measure_queries(label: str)` — context manager, rend le `QueryStats` courant ou `None` si le bilan est éteint
  - `reset_for_tests() -> None` — remet le drapeau de bilan et le `ContextVar` à zéro. **Ne vide pas `_installed`** : l'engine applicatif y est inscrit une fois pour toutes au chargement de `database.py`, et l'en retirer ferait échouer le test de la tâche 4 selon l'ordre d'exécution.

`install()` gagne un effet : il mémorise `collect_stats` dans un drapeau de module. Sans cela `measure_queries` ouvrirait un accumulateur que rien n'alimente, et rendrait un bilan « 0 requête » trompeur.

- [ ] **Step 1: Write the failing tests**

Ajouter à `backend/tests/test_core/test_sql_observability.py`. **Ajouter aussi cette fixture `autouse` en tête de fichier** (le drapeau est un état de module : sans remise à zéro, un test hériterait du réglage du précédent) :

```python
@pytest.fixture(autouse=True)
def _etat_propre():
    """Le drapeau de bilan est un état de module : on le remet à zéro entre
    deux tests, sinon l'ordre d'exécution devient significatif."""
    from app.core import sql_observability

    sql_observability.reset_for_tests()
    yield
    sql_observability.reset_for_tests()
```

Puis les tests :

```python
def test_bilan_agrege_rend_un_n_plus_un_visible(engine, caplog):
    """Le test qui vaut la feature : trois exécutions de la même requête
    ressortent en une seule entrée « x3 »."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with sql_observability.measure_queries("import epreuve=Test"):
            with engine.connect() as conn:
                for _ in range(3):
                    conn.execute(text("SELECT 1"))

    messages = [r.getMessage() for r in caplog.records]
    assert any("import epreuve=Test" in m and "3 requêtes" in m for m in messages)
    assert any("x3" in m and "SELECT 1" in m for m in messages)


def test_bilan_emis_meme_si_le_bloc_leve(engine, caplog):
    """Une épreuve qui plante est justement celle qu'on veut mesurer."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with pytest.raises(RuntimeError):
            with sql_observability.measure_queries("import epreuve=Boom"):
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                raise RuntimeError("boom")

    assert any("import epreuve=Boom" in r.getMessage() for r in caplog.records)


def test_bilan_eteint_est_un_no_op(engine, caplog):
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=False)

    with caplog.at_level(logging.DEBUG, logger="app.sql"):
        with sql_observability.measure_queries("rien") as stats:
            assert stats is None
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

    assert caplog.records == []


def test_unite_sans_requete_n_emet_pas_de_bilan(engine, caplog):
    """Une requête HTTP qui ne touche pas la base ne doit pas polluer les logs."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.DEBUG, logger="app.sql"):
        with sql_observability.measure_queries("GET /health"):
            pass

    assert caplog.records == []


def test_imbrication_la_plus_proche_gagne(engine, caplog):
    """Règle écrite plutôt que découverte : aucune sommation vers l'englobante."""
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with sql_observability.measure_queries("externe") as dehors:
            with sql_observability.measure_queries("interne"):
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            assert dehors.count == 0


def test_bilan_ne_contient_ni_valeur_liee_ni_retour_a_la_ligne(engine, caplog):
    from app.core import sql_observability

    sql_observability.install(engine, slow_query_ms=0, collect_stats=True)

    with caplog.at_level(logging.INFO, logger="app.sql"):
        with sql_observability.measure_queries("fuite"):
            with engine.connect() as conn:
                conn.execute(text("SELECT :valeur"), {"valeur": "LEMÉE"})

    assert caplog.records
    assert all("LEMÉE" not in r.getMessage() for r in caplog.records)
    assert all("\n" not in r.getMessage() for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_core/test_sql_observability.py -v`
Expected: FAIL — `AttributeError: module 'app.core.sql_observability' has no attribute 'reset_for_tests'`

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/core/sql_observability.py`, compléter les imports :

```python
import logging
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.engine import Engine
```

Ajouter après les constantes :

```python
@dataclass
class QueryStats:
    """Compteurs d'une unité de travail — une requête HTTP, une épreuve importée."""

    label: str
    count: int = 0
    total_ms: float = 0.0
    by_sql: Counter = field(default_factory=Counter)


# Propre à la tâche asyncio ou au thread : deux requêtes HTTP simultanées ont
# deux accumulateurs distincts.
_current: ContextVar[QueryStats | None] = ContextVar("tcn_query_stats", default=None)

# Drapeau de module posé par `install()` : sans lui, `measure_queries` ouvrirait
# un accumulateur que rien n'alimente et rendrait un bilan « 0 requête ».
_stats_enabled = False


def reset_for_tests() -> None:
    """Remet le drapeau de bilan et le `ContextVar` à zéro.

    Les tests, et eux seuls, en ont besoin : sans cela l'ordre d'exécution
    devient significatif. `_installed` n'est **pas** vidé — l'engine applicatif
    y est inscrit une fois pour toutes au chargement de `database.py`.
    """
    global _stats_enabled
    _stats_enabled = False
    _current.set(None)
```

Dans `install()`, poser le drapeau **avant** le court-circuit :

```python
def install(engine: Engine, *, slow_query_ms: float, collect_stats: bool) -> None:
    """(docstring inchangée)"""
    global _stats_enabled
    _stats_enabled = collect_stats

    if slow_query_ms <= 0 and not collect_stats:
        return
```

Dans `_after`, alimenter l'accumulateur après le log de lenteur :

```python
        if 0 < slow_query_ms <= elapsed_ms:
            logger.warning("Requête lente | %.1f ms | %s", elapsed_ms, sql)

        stats = _current.get()
        if stats is not None:
            stats.count += 1
            stats.total_ms += elapsed_ms
            stats.by_sql[sql] += 1
```

Et ajouter en fin de module :

```python
@contextmanager
def measure_queries(label: str) -> Iterator[QueryStats | None]:
    """Borne une unité de travail et journalise son bilan à la sortie.

    No-op quand le bilan est éteint (rend `None`). En cas d'imbrication, la plus
    proche unité gagne : les requêtes ne sont pas sommées vers l'englobante.
    Le bilan est émis dans un `finally` — une épreuve qui plante est justement
    celle qu'on veut mesurer.
    """
    if not _stats_enabled:
        yield None
        return

    stats = QueryStats(label=label)
    token = _current.set(stats)
    try:
        yield stats
    finally:
        _current.reset(token)
        _emit(stats)


def _emit(stats: QueryStats) -> None:
    """Bilan en **plusieurs** enregistrements — jamais un message multi-ligne,
    qui casserait le format JSON d'`app.core.logging`.

    Une unité sans aucune requête n'émet rien : une page qui ne touche pas la
    base n'a pas à polluer les logs.
    """
    if stats.count == 0:
        return
    logger.info(
        "Bilan SQL | %s | %d requêtes | %.0f ms",
        stats.label,
        stats.count,
        stats.total_ms,
    )
    for sql, occurrences in stats.by_sql.most_common(_TOP_N):
        logger.info("Bilan SQL | %s | x%d | %s", stats.label, occurrences, sql)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_core/test_sql_observability.py -v && uv run ruff check .`
Expected: PASS (13 tests), lint clean

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/sql_observability.py backend/tests/test_core/test_sql_observability.py
git commit -m "feat(core): agrège les requêtes SQL par unité de travail (#89)"
```

---

## Task 4: Brancher les listeners sur l'engine applicatif

**Files:**
- Modify: `backend/app/core/database.py:41-47`
- Test: `backend/tests/test_core/test_sql_observability.py`

**Interfaces:**
- Consumes: `install()`, `is_installed()` (tâche 2), `Settings.sql_slow_query_ms` / `sql_query_stats` (tâche 1).
- Produces: l'engine applicatif `app.core.database.engine` est instrumenté au démarrage du process.

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_core/test_sql_observability.py` :

```python
def test_engine_applicatif_est_instrumente():
    """`database.py` doit appeler `install()` sur son engine : sans ce
    branchement, tout le reste ne mesure rien en production.

    On interroge `is_installed` et non le registre d'événements de SQLAlchemy :
    `event.contains()` réclame la fonction écoutante exacte, qu'on n'expose pas,
    et inspecter son registre interne serait se lier à un détail privé.

    Le seuil par défaut étant de 100 ms, on ne peut pas vérifier le branchement
    par un `SELECT 1` sur SQLite : il ne le franchira jamais. Et recharger
    `database` avec un seuil forcé bas reconstruirait `Base`, laissant les
    modèles liés à l'ancienne — ce qui casserait la suite entière.
    """
    from app.core.database import engine
    from app.core.sql_observability import is_installed

    assert is_installed(engine) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core/test_sql_observability.py::test_engine_applicatif_est_instrumente -v`
Expected: FAIL — `assert False is True` (aucun `install()` dans `database.py`)

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/core/database.py`, après la création de l'engine (ligne 45) et avant `SessionLocal` :

```python
from app.core import sql_observability

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.is_sqlite else {},
    pool_pre_ping=True,
)

# Observabilité SQL (#89) : seuil de lenteur toujours actif, bilan agrégé
# activable. Les deux réglages à zéro/False → aucun listener posé.
sql_observability.install(
    engine,
    slow_query_ms=settings.sql_slow_query_ms,
    collect_stats=settings.sql_query_stats,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

L'import se place en tête de fichier avec les autres imports `app.core` (ruff `I` trie).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: PASS — toute la suite, lint clean

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/database.py backend/tests/test_core/test_sql_observability.py
git commit -m "feat(core): instrumente l'engine applicatif (#89)"
```

---

## Task 5: Middleware ASGI — une requête HTTP = une unité de travail

**Files:**
- Modify: `backend/app/core/sql_observability.py` (ajout du middleware)
- Modify: `backend/app/main.py:24-31`
- Test: `backend/tests/test_core/test_sql_observability.py`

**Interfaces:**
- Consumes: `measure_queries(label)` (tâche 3).
- Produces: `SqlStatsMiddleware` — classe ASGI, `__init__(self, app)`, `async __call__(self, scope, receive, send)`. Montée dans `create_app()` **uniquement** si `settings.sql_query_stats`.

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_core/test_sql_observability.py` :

```python
def test_middleware_compte_les_requetes_d_un_appel_http(monkeypatch, caplog):
    """Le seul point du design qui ne se tranche pas au raisonnement : le
    `ContextVar` doit traverser le middleware ASGI jusqu'à l'endpoint, que
    FastAPI exécute dans un threadpool quand il est déclaré `def`.

    On instrumente ici l'engine **de test** : `install()` prend son engine en
    argument précisément pour ça.
    """
    import app.models  # noqa: F401 — enregistre les tables sur Base.metadata
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core import sql_observability
    from app.core.config import get_settings
    from app.core.database import Base, get_db

    # `create_app()` lit `sql_query_stats` pour décider de monter le middleware,
    # et `get_settings()` est en lru_cache : forcer le réglage *avant* l'appel,
    # et vider le cache en sortie pour ne pas le laisser pollué.
    monkeypatch.setenv("SQL_QUERY_STATS", "true")
    get_settings.cache_clear()

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    try:
        Base.metadata.create_all(bind=eng)
        sql_observability.install(eng, slow_query_ms=0, collect_stats=True)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=eng)

        from app.main import create_app

        application = create_app()

        def _override_get_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        application.dependency_overrides[get_db] = _override_get_db

        with caplog.at_level(logging.INFO, logger="app.sql"):
            with TestClient(application) as client:
                reponse = client.get("/api/v1/athletes?page_size=1")

        assert reponse.status_code == 200
        messages = [r.getMessage() for r in caplog.records]
        assert any("GET /api/v1/athletes" in m and "Bilan SQL" in m for m in messages)
    finally:
        Base.metadata.drop_all(bind=eng)
        eng.dispose()
        get_settings.cache_clear()
```

La route `/api/v1/athletes` existe bien (`backend/app/api/v1/athletes.py:15`) et pagine par `page` / `page_size` — **pas** par `limit`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core/test_sql_observability.py::test_middleware_compte_les_requetes_d_un_appel_http -v`
Expected: FAIL — aucun enregistrement « Bilan SQL » (le middleware n'existe pas)

- [ ] **Step 3: Write minimal implementation**

Ajouter en fin de `backend/app/core/sql_observability.py` :

```python
class SqlStatsMiddleware:
    """Borne une unité de travail sur chaque requête HTTP.

    Middleware **ASGI pur**, et non `BaseHTTPMiddleware` : ce dernier exécute la
    suite dans une tâche anyio distincte, ce qui rend la propagation du
    `ContextVar` subtile. Une classe ASGI n'importe ni FastAPI ni Starlette —
    elle ne manipule que des dicts et des callables — donc elle n'introduit
    aucun couplage web dans `app/core/`.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with measure_queries(f"{scope['method']} {scope['path']}"):
            await self.app(scope, receive, send)
```

Dans `backend/app/main.py`, après `register_exception_handlers(app)` :

```python
    # Bilan SQL par requête HTTP (#89). Monté seulement si le bilan est activé :
    # éteint, l'application n'a pas même un middleware de plus dans sa pile.
    if settings.sql_query_stats:
        from app.core.sql_observability import SqlStatsMiddleware

        app.add_middleware(SqlStatsMiddleware)
```

Starlette applique les middlewares dans l'ordre inverse d'ajout : ajouté après CORS, celui-ci est le plus externe et mesure donc toute la requête.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: PASS, lint clean

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/sql_observability.py backend/app/main.py backend/tests/test_core/test_sql_observability.py
git commit -m "feat(api): borne le bilan SQL sur chaque requête HTTP (#89)"
```

---

## Task 6: Une épreuve importée = une unité de travail (CLI)

**Files:**
- Modify: `backend/app/services/batch.py:203-212`
- Test: `backend/tests/test_services/test_batch.py`

**Interfaces:**
- Consumes: `measure_queries(label)` (tâche 3).
- Produces: aucune nouvelle interface — `run_batch` enveloppe chaque épreuve.

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_services/test_batch.py`. Le fichier fournit déjà `_settings()` et `_phases_ok` au niveau module, et la fixture `db_session` vient de `tests/conftest.py` — les réutiliser tels quels. Ajouter `from contextlib import contextmanager` en tête du fichier.

Le double espion vérifie la **structure** — une unité par épreuve, dans l'ordre — sans dépendre du contenu des logs, déjà couvert par la tâche 3.

```python
def test_run_batch_borne_une_unite_de_travail_par_epreuve(db_session, monkeypatch):
    """C'est le branchement qui rend un N+1 d'import visible : « 1812 requêtes
    pour 1810 participants » ne se lit que si l'unité de mesure est l'épreuve."""
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    unites: list[str] = []

    @contextmanager
    def _espion(label):
        unites.append(label)
        yield None

    monkeypatch.setattr(batch, "measure_queries", _espion)

    batch.run_batch(
        db_session,
        [
            BatchItem(url="https://k/1", label="klikego · A"),
            BatchItem(url="https://k/2", label="klikego · B"),
        ],
        _settings(),
        force=False,
        delay=0.0,
    )

    assert unites == ["klikego · A", "klikego · B"]


def test_unite_de_travail_ouverte_meme_sur_une_epreuve_en_echec(db_session, monkeypatch):
    """Le filet `try`/`except` vit *dans* l'unité de mesure : une épreuve qui
    plante est justement celle qu'on veut mesurer."""
    def _phases(db, url, settings, force=False, persist=True):
        raise RuntimeError("bug inattendu")
        yield  # inatteignable, mais fait de la fonction un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    unites: list[str] = []

    @contextmanager
    def _espion(label):
        unites.append(label)
        yield None

    monkeypatch.setattr(batch, "measure_queries", _espion)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/crash", label="A")],
        _settings(),
        force=False,
        delay=0.0,
    )

    assert totals.errors == 1
    assert unites == ["A"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_batch.py -k unite_de_travail -v`
Expected: FAIL — `AttributeError: module 'app.services.batch' has no attribute 'measure_queries'`

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/services/batch.py`, ajouter l'import :

```python
from app.core.sql_observability import measure_queries
```

Puis envelopper l'import d'une épreuve dans `run_batch` (le `try`/`except` reste **à l'intérieur** : `measure_queries` émet dans un `finally`, donc une épreuve qui plante rend quand même son bilan) :

```python
            _notify(partial(reporter.item_start, i, item.label))
            with measure_queries(item.label):
                try:
                    result = _import_one(
                        db, item.url, settings, force=force, persist=persist, reporter=reporter
                    )
                except Exception as exc:  # filet : un bug ne doit pas tuer le batch
                    logger.warning("Échec import %s : %s", item.url, exc)
                    result = _ItemResult(error=str(exc))
```

Le reste de la boucle (comptage, `_notify`, `_liberer_session`, pause) reste **hors** du `with` : le rollback de libération de session n'appartient pas à l'épreuve mesurée.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: PASS, lint clean

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/batch.py backend/tests/test_services/test_batch.py
git commit -m "feat(cli): borne le bilan SQL sur chaque épreuve importée (#89)"
```

---

## Task 7: Socle OpenTelemetry

**Files:**
- Create: `backend/app/core/tracing.py`
- Modify: `backend/pyproject.toml:6-20`
- Test: `backend/tests/test_core/test_tracing.py` (créé)

**Interfaces:**
- Consumes: rien (l'interrupteur est passé en argument).
- Produces:
  - `setup_tracing(*, enabled: bool, app=None, engine=None) -> None`
  - `shutdown_tracing() -> None`
  - `current_provider()` — rend le `TracerProvider` du module, ou `None`

- [ ] **Step 1: Déclarer les dépendances**

```bash
cd backend
uv add opentelemetry-sdk opentelemetry-instrumentation-fastapi \
       opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp-proto-http
uv sync
```

Les paquets `instrumentation-*` s'épinglent sur des plages de versions de FastAPI et SQLAlchemy : **si la résolution échoue ou dégrade une version en place, s'arrêter et le signaler** plutôt que de contourner. Vérifier ensuite que la suite passe toujours : `uv run pytest -m "not integration" -q`.

- [ ] **Step 2: Write the failing tests**

Créer `backend/tests/test_core/test_tracing.py` :

```python
"""Tests du socle OpenTelemetry (issue #89)."""
import builtins

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(autouse=True)
def _etat_propre():
    from app.core import tracing

    tracing.shutdown_tracing()
    yield
    tracing.shutdown_tracing()


def test_eteint_ne_charge_aucun_paquet_otel(monkeypatch):
    """Éteint, le coût doit être strictement nul — pas même un import.

    On rend l'import fatal plutôt que d'inspecter `sys.modules`, qu'un autre
    test aurait déjà peuplé.
    """
    from app.core import tracing

    vrai_import = builtins.__import__

    def _interdit(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise AssertionError(f"import OTel interdit quand éteint : {name}")
        return vrai_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _interdit)

    tracing.setup_tracing(enabled=False, engine=None)

    assert tracing.current_provider() is None


def test_allume_produit_un_span_sql(monkeypatch):
    """Allumé, une requête doit produire un span. On lit le provider du module,
    jamais le provider global : `trace.set_tracer_provider()` n'accepte qu'un
    seul appel par process, ce qui rendrait le test dépendant de son ordre.
    """
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from app.core import tracing

    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    eng = create_engine("sqlite://")
    tracing.setup_tracing(enabled=True, engine=eng)
    try:
        exporter = InMemorySpanExporter()
        tracing.current_provider().add_span_processor(SimpleSpanProcessor(exporter))

        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))

        assert exporter.get_finished_spans(), "aucun span SQL produit"
    finally:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        # Les instrumentations OTel sont globales et rémanentes : sans ce
        # désarmement, ce test contamine toute la suite.
        SQLAlchemyInstrumentor().uninstrument()
        eng.dispose()


def test_exporter_console_ecrit_sur_stderr():
    """Contrainte dure de la CLI : stdout ne porte que le rapport et la ligne
    `--json`. `ConsoleSpanExporter` écrit sur **stdout** par défaut — le socle
    doit donc le construire avec `out=sys.stderr`, faute de quoi un span imprimé
    casserait `… --json | jq`.
    """
    import sys

    from app.core import tracing

    exporter = tracing._build_exporter("console")
    assert exporter.out is sys.stderr


def test_exporter_none_ne_rend_rien():
    from app.core import tracing

    assert tracing._build_exporter("none") is None
```

> Si la version installée de `ConsoleSpanExporter` ne conserve pas le flux sous
> l'attribut `out`, en trouver le nom réel (`inspect.signature(ConsoleSpanExporter)`)
> et adapter l'assertion. L'intention à vérifier ne change pas : **l'exporter
> console ne doit pas écrire sur stdout.**

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_core/test_tracing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.tracing'`

- [ ] **Step 4: Write minimal implementation**

Créer `backend/app/core/tracing.py` :

```python
"""Socle OpenTelemetry — traces seules, éteint par défaut (issue #89).

Aucun collecteur n'est hébergé à ce jour : ce module est posé pour que le
branchement futur tienne en deux variables d'environnement et zéro code. Il ne
remplace pas `sql_observability` — OTel exporte, il n'alerte pas ; le seuil de
lenteur reste l'affaire des listeners.

Les imports `opentelemetry.*` vivent **dans** les fonctions : éteint, aucun
paquet OTel n'est chargé.

Configuration par les variables standard. `OTEL_SERVICE_NAME` est lu par
`Resource.create()` et `OTEL_EXPORTER_OTLP_ENDPOINT` par l'exporter OTLP :
rien à écrire pour elles. `OTEL_TRACES_EXPORTER`, en revanche, n'est interprété
que par le lanceur `opentelemetry-instrument`, que nous n'utilisons pas — c'est
donc `_build_exporter` qui la lit, en respectant la sémantique standard.
"""
import logging
import os
import sys

logger = logging.getLogger(__name__)

_provider = None


def current_provider():
    """Le `TracerProvider` du module, ou `None` s'il n'est pas allumé.

    Les instrumentations le reçoivent explicitement : les spans ne dépendent
    donc jamais du provider global, dont `set_tracer_provider()` n'accepte
    qu'un seul réglage par process.
    """
    return _provider


def _build_exporter(name: str):
    """Exporter correspondant à `OTEL_TRACES_EXPORTER` — `None` pour « none »."""
    if name == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        # Sur stderr, jamais stdout : la CLI y réserve le rapport et la ligne
        # `--json`, qu'un span imprimé casserait (`… --json | jq`).
        return ConsoleSpanExporter(out=sys.stderr)
    if name == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        # Lit OTEL_EXPORTER_OTLP_ENDPOINT lui-même.
        return OTLPSpanExporter()
    return None


def setup_tracing(*, enabled: bool, app=None, engine=None) -> None:
    """Construit le provider et pose les instrumentations demandées.

    No-op si `enabled` est faux, et idempotent : un second appel ne reconstruit
    rien. `app` et `engine` sont facultatifs — la CLI n'a pas d'app.
    """
    global _provider
    if not enabled or _provider is not None:
        return

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create())
    exporter = _build_exporter(os.getenv("OTEL_TRACES_EXPORTER", "none").strip().lower())
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    _provider = provider

    if engine is not None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    logger.info("Traçage OpenTelemetry actif (exporter=%s)", exporter or "none")


def shutdown_tracing() -> None:
    """Vide les spans en attente.

    Indispensable en CLI : un batch est un process court et le
    `BatchSpanProcessor` exporte de façon différée — sans cet appel, les spans
    du dernier import sont perdus.
    """
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_core/test_tracing.py -v && uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: PASS — la suite **entière** doit rester verte : c'est elle qui révélerait une instrumentation rémanente.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/tracing.py backend/tests/test_core/test_tracing.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(core): pose le socle OpenTelemetry, éteint par défaut (#89)"
```

---

## Task 8: Brancher le traçage sur l'API et la CLI

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/cli/__init__.py`
- Modify: `backend/app/cli/__main__.py`
- Test: `backend/tests/test_core/test_tracing.py`

**Interfaces:**
- Consumes: `setup_tracing()`, `shutdown_tracing()` (tâche 7), `Settings.otel_enabled` (tâche 1).
- Produces: `app.cli.configure_cli_tracing() -> None`, `app.cli.shutdown_cli_tracing() -> None`.

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_core/test_tracing.py` :

```python
def test_cli_expose_demarrage_et_arret_du_tracage():
    """Un batch est un process court : sans arrêt explicite, les spans du
    dernier import ne sont jamais exportés."""
    from app import cli

    assert callable(cli.configure_cli_tracing)
    assert callable(cli.shutdown_cli_tracing)


def test_cli_eteint_ne_pose_rien(monkeypatch):
    from app import cli
    from app.core import tracing
    from app.core.config import get_settings

    monkeypatch.setenv("OTEL_ENABLED", "false")
    get_settings.cache_clear()
    try:
        cli.configure_cli_tracing()
        assert tracing.current_provider() is None
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_core/test_tracing.py -v`
Expected: FAIL — `AttributeError: module 'app.cli' has no attribute 'configure_cli_tracing'`

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/main.py`, à la fin de `create_app()` avant `return app` :

```python
    # Socle OpenTelemetry (#89) : éteint par défaut, aucun paquet OTel chargé.
    from app.core.database import engine
    from app.core.tracing import setup_tracing

    setup_tracing(enabled=settings.otel_enabled, app=app, engine=engine)
```

Dans `backend/app/cli/__init__.py`, après `configure_cli_logging()` :

```python
def configure_cli_tracing() -> None:
    """Démarre le traçage OTel pour un batch, s'il est activé.

    Comme pour le logging, c'est le rôle du process (`__main__.py`), pas d'un
    module importé.
    """
    from app.core.config import get_settings
    from app.core.database import engine
    from app.core.tracing import setup_tracing

    setup_tracing(enabled=get_settings().otel_enabled, engine=engine)


def shutdown_cli_tracing() -> None:
    """Vide les spans en attente avant la fin du process.

    Un batch est court et le BatchSpanProcessor exporte de façon différée :
    sans cet appel, les spans du dernier import sont perdus.
    """
    from app.core.tracing import shutdown_tracing

    shutdown_tracing()
```

Et mettre à jour `__all__` :

```python
__all__ = ["app", "configure_cli_logging", "configure_cli_tracing", "shutdown_cli_tracing"]
```

Dans `backend/app/cli/__main__.py` :

```python
"""Point d'entrée `python -m app.cli`."""
from app.cli import (
    app,
    configure_cli_logging,
    configure_cli_tracing,
    shutdown_cli_tracing,
)

if __name__ == "__main__":
    # Le process (et lui seul) configure le logging : sur stderr, pour ne jamais
    # polluer stdout, réservé au rapport et à la ligne `--json`.
    configure_cli_logging()
    configure_cli_tracing()
    try:
        app()
    finally:
        # `app()` sort par SystemExit : sans ce `finally`, les spans du dernier
        # import ne seraient jamais exportés.
        shutdown_cli_tracing()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: PASS, lint clean

- [ ] **Step 5: Vérification manuelle du bout en bout**

```bash
cd backend
SQL_QUERY_STATS=true SQL_SLOW_QUERY_MS=1 \
  uv run python -m app.cli rescrape-db --limit 1 --dry-run --json | jq .
```

Attendu : la ligne JSON **seule** sur stdout (donc `jq` ne bronche pas), et sur stderr des enregistrements `Bilan SQL | <épreuve> | N requêtes | …` suivis de leurs lignes `x<N>`. C'est la démonstration que l'invariant « stdout parsable » tient et que l'unité de travail est bien l'épreuve.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/cli/__init__.py backend/app/cli/__main__.py backend/tests/test_core/test_tracing.py
git commit -m "feat(ops): branche le traçage OTel sur l'API et la CLI (#89)"
```

---

## Task 9: Documentation

**Files:**
- Modify: `backend/.env.example`
- Modify: `AGENTS.md` (section « Architecture backend », après le paragraphe `app/core/`)

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: rien de code.

- [ ] **Step 1: Compléter `.env.example`**

Ajouter à la fin de `backend/.env.example` :

```bash
# Observabilité SQL (#89)
# Seuil de lenteur en ms : toute requête au-delà sort en WARNING. 0 = désactivé.
# SQL_SLOW_QUERY_MS=100
# Bilan agrégé par unité de travail (requête HTTP, épreuve importée) — verbeux.
# SQL_QUERY_STATS=false

# Traçage OpenTelemetry — éteint par défaut, aucun collecteur hébergé à ce jour.
# OTEL_ENABLED=false
# OTEL_TRACES_EXPORTER=none          # none | console | otlp
# OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example/v1/traces
# OTEL_SERVICE_NAME=data-triathlon-backend
```

- [ ] **Step 2: Compléter `AGENTS.md`**

Ajouter une sous-section sous « Architecture backend », après la liste des modules `app/core/` :

```markdown
### Observabilité SQL

Deux étages **indépendants**, tous deux éteints ou presque par défaut (#89).

`core/sql_observability.py` — listeners posés sur l'engine par `database.py`.
Deux niveaux : un **seuil de lenteur** (`SQL_SLOW_QUERY_MS`, défaut 100 ms) qui
sort en WARNING sur le logger `app.sql`, et un **bilan agrégé par unité de
travail** (`SQL_QUERY_STATS`, défaut `false`) — une requête HTTP côté web, une
**épreuve** côté CLI. C'est le second qui rend un N+1 visible (« 1812 requêtes
pour 1810 participants ») ; le premier seul ne le montrerait pas.

Trois règles à ne pas relâcher. Le SQL est journalisé **paramétré**, jamais avec
ses valeurs liées : elles portent des noms d'athlètes et des libellés de club, et
partiraient dans les logs Render (test de non-régression dédié). Le bilan sort en
**plusieurs enregistrements**, jamais en message multi-ligne : le formateur JSON
de `core/logging.py` construit son objet à la main. Et seuil à `0` **plus** bilan
éteint = aucun listener posé, coût strictement nul.

`core/tracing.py` — socle OpenTelemetry, `OTEL_ENABLED` à `false` par défaut,
imports paresseux : éteint, aucun paquet OTel n'est chargé. Aucun collecteur
n'est hébergé ; le socle est là pour que le branchement tienne en deux variables
(`OTEL_TRACES_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_ENDPOINT=…`). `OTEL_SERVICE_NAME`
et l'endpoint sont lus par le SDK, mais **`OTEL_TRACES_EXPORTER` est lu par notre
code** — elle n'est interprétée que par le lanceur `opentelemetry-instrument`,
qu'on n'utilise pas. L'exporter `console` écrit sur **stderr** : sur stdout il
casserait `… --json | jq`. La CLI doit appeler `shutdown_cli_tracing()` en fin de
process, faute de quoi le `BatchSpanProcessor` perd les spans du dernier import.

**EXPLAIN et audit d'index restent à faire** : c'est l'analyse à mener *avec* cet
outil, dont le livrable sera un sondage sous `docs/superpowers/specs/`.
Design : `docs/superpowers/specs/2026-07-31-sql-observability-design.md`.
```

- [ ] **Step 3: Vérifier**

Run: `uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: PASS, lint clean

- [ ] **Step 4: Commit**

```bash
git add backend/.env.example AGENTS.md
git commit -m "docs(ops): documente l'observabilité SQL et le socle OTel (#89)"
```

---

## Fin de branche

Une fois les neuf tâches passées :

1. `superpowers:requesting-code-review`
2. `superpowers:verification-before-completion`
3. `superpowers:finishing-a-development-branch`
