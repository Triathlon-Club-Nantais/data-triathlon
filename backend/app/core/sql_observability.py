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
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
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


@dataclass
class QueryStats:
    """Compteurs d'une unité de travail — une requête HTTP, une épreuve importée."""

    label: str
    count: int = 0
    total_ms: float = 0.0
    by_sql: Counter[str] = field(default_factory=Counter)


# Propre à la tâche asyncio ou au thread : deux requêtes HTTP simultanées ont
# deux accumulateurs distincts.
_current: ContextVar[QueryStats | None] = ContextVar("tcn_query_stats", default=None)

# Drapeau de module posé par `install()` : sans lui, `measure_queries` ouvrirait
# un accumulateur que rien n'alimente et rendrait un bilan « 0 requête ».
_stats_enabled = False


def is_installed(engine: Engine) -> bool:
    """L'engine porte-t-il les listeners de mesure ?"""
    return engine in _installed


def reset_for_tests() -> None:
    """Remet le drapeau de bilan et le `ContextVar` à zéro.

    Les tests, et eux seuls, en ont besoin : sans cela l'ordre d'exécution
    devient significatif. `_installed` n'est **pas** vidé — l'engine applicatif
    y est inscrit une fois pour toutes au chargement de `database.py`.
    """
    global _stats_enabled
    _stats_enabled = False
    _current.set(None)


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
    # Drapeau global bien que l'idempotence ci-dessous soit par engine : posé
    # *avant* la garde, délibérément — sinon un second appel sur un engine déjà
    # instrumenté ne pourrait jamais éteindre le bilan. Contrepartie assumée
    # (aucun chemin actuel ne la déclenche, un seul engine applicatif) : avec
    # deux engines, le dernier appel à `install()` fixe le bilan pour tous.
    global _stats_enabled
    _stats_enabled = collect_stats

    if slow_query_ms <= 0 and not collect_stats:
        return
    if engine in _installed:
        return
    _installed.add(engine)

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        # Une pile, pas une valeur simple : elle tient la réentrance. `conn.info`
        # survit au cycle connect()/close() via son `_ConnectionRecord` du pool,
        # donc les requêtes qui lèvent laissent un `float` orphelin jusqu'au
        # recyclage de la connexion — pattern nominal du Profiling cookbook.
        conn.info.setdefault(_INFO_KEY, []).append(perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        starts = conn.info.get(_INFO_KEY)
        if not starts:
            return
        elapsed_ms = (perf_counter() - starts.pop()) * 1000

        is_slow = 0 < slow_query_ms <= elapsed_ms
        stats = _current.get()
        # `normalize_sql` coûte un `split()`/`join()` sur tout le statement : ne
        # la calculer que si une des deux branches ci-dessous la consomme
        # réellement, et une seule fois si les deux sont actives.
        if is_slow or stats is not None:
            sql = normalize_sql(statement)

        if is_slow:
            logger.warning("Requête lente | %.1f ms | %s", elapsed_ms, sql)

        if stats is not None:
            stats.count += 1
            stats.total_ms += elapsed_ms
            stats.by_sql[sql] += 1


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
    # Normalise le label : remplace les retours à la ligne par des espaces.
    # `stats.label` vient de l'appelant et peut contenir des données de la base
    # (nom d'épreuve, libellé de club). La garde s'applique une fois ici.
    normalized_label = " ".join(stats.label.split())
    logger.info(
        "Bilan SQL | %s | %d requêtes | %.0f ms",
        normalized_label,
        stats.count,
        stats.total_ms,
    )
    for sql, occurrences in stats.by_sql.most_common(_TOP_N):
        logger.info("Bilan SQL | %s | x%d | %s", normalized_label, occurrences, sql)


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
