"""Les trois recherches par URL passent par `course_sources` (#281).

`get_latest_by_source_url`, `list_by_source_url` et `list_by_source_urls`
alimentent le cache TTL (`import_service._cached_result`), sa sonde par heat
(`_make_cache_probe`) et le lot du fan-out (`_merge_cached_courses`). Depuis #279
elles filtraient `Course.source_url`, c'est-à-dire la sous-requête scalaire
corrélée du hybride — **évaluée une fois par ligne de `courses`**. Elles joignent
désormais la table, ce qui change deux choses : le plan de requête, et le sort de
la chaîne vide (voir `test_an_empty_url_matches_no_course`).

La sémantique du cache, elle, ne bouge pas : 10 min en cours, 30 j sinon. C'est
le **chemin** vers les courses qui change, pas la règle.
"""
from datetime import date, timedelta

import pytest

from app.core import sql_observability
from app.core.time import utcnow
from app.models.course import Course
from app.repositories import course_repository, course_source_repository

URL = "https://klikego.test/mesquer"
AUTRE = "https://breizhchrono.test/nozeen"


def _epreuve(db_session, nom: str, url: str = "", *, provider: str = "klikego") -> Course:
    course = course_repository.get_or_create(
        db_session,
        name=nom,
        event_date=date(2026, 5, 16),
        event_type=f"triathlon-{nom[0].lower()}",
        source_url=url,
        provider=provider if url else "",
    )
    db_session.flush()
    return course


@pytest.fixture
def compteur_sql(db_session):
    """Arme le bilan agrégé de `core/sql_observability` sur l'engine du test.

    `_stats_enabled` est un état de **module** : sans le `reset_for_tests` des
    deux côtés, un test armé contaminerait les suivants.
    """
    sql_observability.reset_for_tests()
    sql_observability.install(db_session.get_bind(), slow_query_ms=0, collect_stats=True)
    yield
    sql_observability.reset_for_tests()


def test_an_empty_url_matches_no_course(db_session):
    """La chaîne vide ne désigne aucune épreuve — et c'est un changement (#281).

    Le hybride replie la source absente sur `""` (contrat public : `CourseBrief`
    promet une chaîne, pas `null`). Conséquence non voulue : `Course.source_url ==
    ""` matchait **toutes** les épreuves sans source, donc les saisies manuelles.
    Aucun appelant ne passe aujourd'hui d'URL vide — `import_event` la reçoit
    validée, la sonde par heat la fabrique — mais une arête vive qu'on peut
    supprimer sans rien perdre ne se garde pas.

    En joignant `course_sources`, la question devient « quelle source porte cette
    URL ? » : la chaîne vide n'en désigne aucune, puisqu'une source sans URL
    n'existe pas (`CourseSource.url` est `NOT NULL`, et `get_or_create` ne crée
    de source que s'il a une URL).
    """
    _epreuve(db_session, "Manuelle")
    _epreuve(db_session, "Klikego", URL)

    assert course_repository.get_latest_by_source_url(db_session, "") is None
    assert course_repository.list_by_source_url(db_session, "") == []
    assert course_repository.list_by_source_urls(db_session, [""]) == []


def test_the_three_lookups_find_a_course_by_its_active_source(db_session):
    """AC1 — la fraîcheur reste jugeable, donc le court-circuit reste possible."""
    course = _epreuve(db_session, "Klikego", URL)

    assert course_repository.get_latest_by_source_url(db_session, URL) is course
    assert course_repository.list_by_source_url(db_session, URL) == [course]
    assert course_repository.list_by_source_urls(db_session, [URL]) == [course]


def test_a_passive_url_is_never_cached(db_session):
    """AC4 — une source passive n'alimente rien, donc elle ne cache rien.

    Le TTL protège du re-scraping inutile de ce qu'on **affiche** ; une passive
    n'est affichée nulle part et n'est jamais scrapée (#282). Son
    `last_scraped_at` n'entre donc pas dans le calcul de fraîcheur, et son URL ne
    doit rendre aucune épreuve : sinon coller la seconde publication d'une
    épreuve fraîche renverrait un résultat caché portant le classement de
    l'**autre** chronométreur.
    """
    course = _epreuve(db_session, "Klikego", URL)
    course_source_repository.add(
        db_session, course=course, url=AUTRE, provider="breizhchrono"
    )
    db_session.flush()

    assert course_repository.get_latest_by_source_url(db_session, AUTRE) is None
    assert course_repository.list_by_source_url(db_session, AUTRE) == []
    assert course_repository.list_by_source_urls(db_session, [AUTRE]) == []


def test_switching_the_active_source_moves_which_url_finds_the_course(db_session):
    """La bascule de #285 déplace le cache avec elle, sans code dédié."""
    course = _epreuve(db_session, "Klikego", URL)
    seconde = course_source_repository.add(
        db_session, course=course, url=AUTRE, provider="breizhchrono"
    )

    course_source_repository.set_active(db_session, seconde)
    db_session.flush()

    assert course_repository.get_latest_by_source_url(db_session, AUTRE) is course
    assert course_repository.get_latest_by_source_url(db_session, URL) is None


def test_list_by_source_url_renders_every_heat_of_the_url(db_session):
    """AC2 — le SSE `done` doit offrir **tous** les heats au sélecteur (#135).

    Une URL porte N épreuves : heats Klikego, catégories Wiclax, listes
    RaceResult, épreuves Chronoplace. Ordre `scraped_at` décroissant, le même que
    celui du repli `get_latest_by_source_url` — c'est la première course
    pré-sélectionnée du sélecteur qui en dépend.
    """
    ancien = _epreuve(db_session, "Sprint", URL)
    ancien.scraped_at = utcnow() - timedelta(hours=2)
    recent = _epreuve(db_session, "Medium", URL)
    recent.scraped_at = utcnow()
    db_session.flush()

    heats = course_repository.list_by_source_url(db_session, URL)

    assert heats == [recent, ancien]
    assert course_repository.get_latest_by_source_url(db_session, URL) is recent


def test_list_by_source_urls_never_duplicates_a_course(db_session):
    """La jointure ne peut pas doubler une ligne, et ce n'est pas un hasard.

    `UNIQUE(course_id, url)` plus l'index partiel `UNIQUE(course_id) WHERE
    is_active` : une épreuve a **au plus une** source active, donc au plus une
    ligne joignable, même quand le lot contient l'URL active *et* une passive de
    la même épreuve. Pas de `DISTINCT` à ajouter — il masquerait la garantie au
    lieu de s'appuyer sur elle.
    """
    course = _epreuve(db_session, "Klikego", URL)
    course_source_repository.add(
        db_session, course=course, url=AUTRE, provider="breizhchrono"
    )
    db_session.flush()

    assert course_repository.list_by_source_urls(db_session, [URL, AUTRE]) == [course]


def test_list_by_source_urls_costs_the_same_for_one_url_or_many(db_session, compteur_sql):
    """AC3 — le lot du fan-out reste à coût constant en k (#156).

    Deux requêtes, pas k : le `IN` sur les sources, puis le `selectinload` des
    sources des épreuves trouvées. C'est ce `selectinload` qui empêche le vrai
    N+1 — les appelants lisent `course.provider` sur chaque épreuve rendue.
    """
    urls = [f"https://klikego.test/heat-{indice}" for indice in range(3)]
    for indice, url in enumerate(urls):
        _epreuve(db_session, f"Heat{indice}", url)
    db_session.flush()

    with sql_observability.measure_queries("un seul heat caché") as une:
        assert len(course_repository.list_by_source_urls(db_session, urls[:1])) == 1
    with sql_observability.measure_queries("trois heats cachés") as trois:
        assert len(course_repository.list_by_source_urls(db_session, urls)) == 3

    assert une.count == 2
    assert trois.count == 2


def test_an_empty_batch_asks_nothing_of_the_database(db_session, compteur_sql):
    """Liste vide → aucune requête : le fan-out sans heat caché ne paie rien."""
    with sql_observability.measure_queries("lot vide") as stats:
        assert course_repository.list_by_source_urls(db_session, []) == []

    assert stats.count == 0
