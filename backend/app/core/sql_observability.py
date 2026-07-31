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
