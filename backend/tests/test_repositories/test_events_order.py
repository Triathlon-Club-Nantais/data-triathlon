"""ORDER BY compilé de `_events_order`, épinglé sur les deux dialectes (#567).

La branche PostgreSQL (similarité `pg_trgm`) n'est exercée par AUCUN autre
test de la suite : celle-ci tourne sur SQLite, où `_is_postgres(db)` est faux.
C'est précisément pourquoi le bug — la similarité court-circuitait `sort`, et
aucun tri n'avait de clé de départage unique — a vécu sans être vu.

La technique : une `Session` liée à un moteur `postgresql+psycopg2` jamais
connecté. `ORDER BY` se compile sans exécuter la requête, donc sans jamais
ouvrir de socket — `psycopg2-binary` est une dépendance déjà présente, mais
aucun serveur PostgreSQL n'est requis pour ce test.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.repositories.participation_repository import _events_order

_SORTS = ["date_desc", "date_asc", "name", "imported_desc"]


@pytest.fixture
def pg_session():
    """Session PostgreSQL non connectée — compiler suffit, ne jamais exécuter."""
    engine = create_engine("postgresql+psycopg2://u:p@localhost/x")
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _compiled(db, sort, event_name):
    clauses = _events_order(db, sort, event_name)
    return [str(c.compile(db.bind, compile_kwargs={"literal_binds": True})) for c in clauses]


# --- Point 3 : `Course.id` en dernière clé, sur les quatre tris ------------


@pytest.mark.parametrize("sort", _SORTS)
def test_course_id_derniere_cle_sqlite(db_session, sort):
    """`_grouped_events_query` rend une ligne par `Course.id` ; plusieurs
    `Course` peuvent partager nom et date (heats TimePulse, cas Mesquer,
    `services/course_duplicates`) et sont donc entièrement à égalité sans
    cette clé — la pagination `LIMIT/OFFSET` du défilement infini peut alors
    rendre la même épreuve deux fois, ou aucune."""
    assert _compiled(db_session, sort, None)[-1] == "courses.id"


@pytest.mark.parametrize("sort", _SORTS)
def test_course_id_derniere_cle_postgres(pg_session, sort):
    assert _compiled(pg_session, sort, "mesquer")[-1] == "courses.id"


# --- Sondage complet, épinglé sur les deux dialectes -----------------------


@pytest.mark.parametrize(
    "sort,expected",
    [
        ("date_desc", ["courses.event_date DESC NULLS LAST", "courses.name", "courses.id"]),
        ("date_asc", ["courses.event_date ASC NULLS LAST", "courses.name", "courses.id"]),
        ("name", ["courses.name ASC", "courses.event_date DESC", "courses.id"]),
        ("imported_desc", ["courses.created_at DESC", "courses.name", "courses.id"]),
    ],
)
def test_sqlite_sans_recherche(db_session, sort, expected):
    assert _compiled(db_session, sort, None) == expected


@pytest.mark.parametrize(
    "sort,expected",
    [
        ("date_desc", ["courses.event_date DESC NULLS LAST", "courses.name", "courses.id"]),
        ("name", ["courses.name ASC", "courses.event_date DESC", "courses.id"]),
    ],
)
def test_sqlite_avec_recherche_ignore_la_similarite(db_session, sort, expected):
    """SQLite n'a pas `pg_trgm` : une recherche active ne doit rien changer à
    l'ordre — c'est le tri demandé qui continue de s'appliquer, tel quel."""
    assert _compiled(db_session, sort, "mesquer") == expected


@pytest.mark.parametrize(
    "sort,expected",
    [
        ("date_desc", ["courses.event_date DESC NULLS LAST", "courses.name", "courses.id"]),
        ("date_asc", ["courses.event_date ASC NULLS LAST", "courses.name", "courses.id"]),
        ("name", ["courses.name ASC", "courses.event_date DESC", "courses.id"]),
        ("imported_desc", ["courses.created_at DESC", "courses.name", "courses.id"]),
    ],
)
def test_postgres_sans_recherche(pg_session, sort, expected):
    """Sans recherche, PostgreSQL rend exactement le même ordre que SQLite :
    la similarité n'entre en jeu que si `event_name` est fourni."""
    assert _compiled(pg_session, sort, None) == expected


@pytest.mark.parametrize(
    "sort,expected_tail",
    [
        ("date_desc", ["courses.event_date DESC NULLS LAST", "courses.name"]),
        ("date_asc", ["courses.event_date ASC NULLS LAST", "courses.name"]),
        ("name", ["courses.name ASC", "courses.event_date DESC"]),
        ("imported_desc", ["courses.created_at DESC", "courses.name"]),
    ],
)
def test_postgres_avec_recherche_complete_le_tri_demande(pg_session, sort, expected_tail):
    """#567 points 1 et 2, option 1 retenue : la similarité COMPLÈTE le tri
    choisi, elle ne le remplace pas — `sort` reste consulté (le sélecteur de
    `EventList` cesse de mentir), et `courses.name` reste dans l'ordre (le
    regroupement par compétition du front en dépend, issue #568)."""
    assert _compiled(pg_session, sort, "mesquer") == [
        "similarity(courses.name, 'mesquer') DESC",
        *expected_tail,
        "courses.id",
    ]
