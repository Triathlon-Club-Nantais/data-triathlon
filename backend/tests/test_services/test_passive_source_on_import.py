"""Une URL déjà connue s'enregistre en source passive au lieu d'être perdue (#283, D3).

C'est l'observation (b) de la discussion #210 : `get_or_create` apparie l'épreuve
par son identité et rend l'existante **sans jamais toucher ses sources**, donc la
seconde publication — l'autre chronométreur — disparaissait sans trace. Ses
participations, elles, étaient bien importées : seul le lien était perdu, ce qui
donnait une épreuve dont le classement venait d'une source que l'application ne
savait plus nommer.

Le sondage `docs/superpowers/specs/2026-08-12-sources-multiples-epreuve-sondage.md`
mesure ce cas sur Mesquer 2026 et le Duathlon Nozéen 2026 : Klikego et Breizh
Chrono y publient **la même identité champ par champ**, l'appariement a donc déjà
lieu. Attente de test qu'il pose explicitement : **une seule** `Course`, **deux**
sources.

La règle est une comparaison, pas une mémoire de ce qui vient d'arriver : l'URL
soumise qui n'est pas la source **active** de l'épreuve en devient une passive.
C'est ce qui rend l'appel idempotent sans avoir à savoir si l'épreuve vient d'être
créée ou d'être appariée.
"""
from datetime import date

from app.core.config import Settings
from app.models.course import Course
from app.repositories import course_repository, course_source_repository, participation_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service, mapping

#: Deux chronométreurs, une seule épreuve. Hosts réels : `_validate_url` refuse
#: une URL qu'aucun provider ne reconnaît, un `.test` ferait échouer les tests
#: pour une raison qui n'a rien à voir avec #283.
KLIKEGO = "https://www.klikego.com/resultats/mesquer-2026/1706667557931-4"
BREIZH = "https://resultats.breizhchrono.com/resultats-courses/mesquer-2026-1732665322557-2"


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(bib: str, *, source_url: str, provider: str, nom: str = "DUPONT") -> ScrapedResult:
    """Un résultat dont l'identité d'épreuve est **fixe** — seule la source varie.

    C'est le cas mesuré : les deux chronométreurs publient les mêmes `name`,
    `event_date`, `event_type` et `is_relay`, donc `get_or_create` apparie. Faire
    varier l'identité testerait #289 (le rapprochement de deux épreuves qui *ne*
    collident pas), pas #283.
    """
    return ScrapedResult(
        source_url=source_url,
        provider=provider,
        athlete_name=nom,
        athlete_firstname="Jean",
        bib_number=bib,
        event_name="Triathlon de Mesquer",
        event_date=date(2026, 5, 16),
        event_type="triathlon-s",
        total_time="01:59:00",
    )


def _importer(db, patch_scraper, url: str, provider: str, *, bibs=("1",), force=False) -> dict:
    """Importe l'épreuve sous cette URL et rend la phase `done`."""
    patch_scraper([_result(bib, source_url=url, provider=provider) for bib in bibs])
    phases = list(import_service.iter_import_event(db, url, _settings(), force=force))
    assert phases[-1]["phase"] == "done", phases[-1]
    return phases[-1]


def _sources(db, course_id: int) -> list:
    return course_source_repository.list_for_course(db, course_id)


# --------------------------------------------------------------------------- AC1


def test_a_second_url_on_a_known_course_becomes_a_passive_source(db_session, patch_scraper):
    """AC1 — une seule `Course`, deux sources, l'active inchangée."""
    _importer(db_session, patch_scraper, KLIKEGO, "klikego")
    course = course_repository.get_by_identity(
        db_session, "Triathlon de Mesquer", date(2026, 5, 16), "triathlon-s", False
    )
    assert course is not None

    _importer(db_session, patch_scraper, BREIZH, "breizhchrono")

    assert db_session.query(Course).all() == [course], "une seule épreuve, pas deux"
    urls = [source.url for source in _sources(db_session, course.id)]
    assert urls == [KLIKEGO, BREIZH], "l'active en tête, la seconde publication ensuite"
    assert course.source_url == KLIKEGO, "la première scrapée garde la main (D3)"
    assert course.provider == "klikego"


def test_the_second_publication_leaves_the_participations_alone(db_session, patch_scraper):
    """AC1, seconde moitié — enregistrer une source ne rejoue pas le classement.

    Le scrape a bien lieu (une URL neuve n'est jamais dans le cache TTL, qui est
    indexé sur la source **active**), donc la garde porte sur l'upsert : des
    valeurs identiques ne doivent produire ni ligne ni modification.
    """
    _importer(db_session, patch_scraper, KLIKEGO, "klikego")
    avant = participation_repository.list_participations(db_session, page_size=100)
    assert len(avant) == 1
    identifiants = {row.id for row in avant}

    done = _importer(db_session, patch_scraper, BREIZH, "breizhchrono")

    apres = participation_repository.list_participations(db_session, page_size=100)
    assert {row.id for row in apres} == identifiants
    assert (done["imported"], done["updated"]) == (0, 0)
    assert done["skipped"] == 1


def test_the_passive_source_keeps_the_provider_that_published_it(db_session, patch_scraper):
    """Le provider est un champ de la **source**, pas de l'épreuve (#279)."""
    _importer(db_session, patch_scraper, KLIKEGO, "klikego")
    _importer(db_session, patch_scraper, BREIZH, "breizhchrono")

    course = course_repository.get_by_identity(
        db_session, "Triathlon de Mesquer", date(2026, 5, 16), "triathlon-s", False
    )
    passive = [source for source in _sources(db_session, course.id) if not source.is_active]
    assert [(source.url, source.provider) for source in passive] == [(BREIZH, "breizhchrono")]


# --------------------------------------------------------------------------- AC2


def test_resubmitting_the_active_url_creates_no_duplicate_source(db_session, patch_scraper):
    """AC2 — `UNIQUE(course_id, url)` ne doit jamais remonter en exception.

    Le chemin nominal du re-scrape, celui que `rescrape-db` emprunte des dizaines
    de fois par exécution : rien à enregistrer, et surtout rien à faire lever.
    """
    _importer(db_session, patch_scraper, KLIKEGO, "klikego")
    course = course_repository.get_by_identity(
        db_session, "Triathlon de Mesquer", date(2026, 5, 16), "triathlon-s", False
    )

    done = _importer(db_session, patch_scraper, KLIKEGO, "klikego", force=True)

    assert [source.url for source in _sources(db_session, course.id)] == [KLIKEGO]
    assert done["passive_sources"] == []


def test_a_first_import_registers_no_passive_source(db_session, patch_scraper):
    """L'épreuve neuve : sa première source est **active**, il n'y a rien à signaler."""
    done = _importer(db_session, patch_scraper, KLIKEGO, "klikego")

    assert done["passive_sources"] == []
    course = course_repository.get_by_identity(
        db_session, "Triathlon de Mesquer", date(2026, 5, 16), "triathlon-s", False
    )
    assert [(s.url, s.is_active) for s in _sources(db_session, course.id)] == [(KLIKEGO, True)]


# --------------------------------------------------------------------------- AC3


def test_resubmitting_a_passive_url_creates_nothing_and_reports_it_again(
    db_session, patch_scraper
):
    """AC3 — ne crée rien, **rend le même message**.

    Le signalement n'est donc pas « je viens de l'enregistrer » mais « cette URL
    est une source passive de cette épreuve » : c'est un état, pas un événement.
    Sinon la deuxième personne à coller la même URL n'obtiendrait aucune
    explication et croirait avoir importé le classement qu'elle voit.
    """
    _importer(db_session, patch_scraper, KLIKEGO, "klikego")
    premier = _importer(db_session, patch_scraper, BREIZH, "breizhchrono")

    second = _importer(db_session, patch_scraper, BREIZH, "breizhchrono", force=True)

    course = course_repository.get_by_identity(
        db_session, "Triathlon de Mesquer", date(2026, 5, 16), "triathlon-s", False
    )
    assert len(_sources(db_session, course.id)) == 2, "aucune source de plus"
    assert second["passive_sources"] == premier["passive_sources"]


# --------------------------------------------------------------------------- AC4


def test_the_message_is_french_and_names_the_course(db_session, patch_scraper):
    """AC4 — nommer l'épreuve est ce qui rend le message actionnable.

    « Cette URL a été enregistrée » sans dire *où* laisse l'utilisateur devant un
    classement qu'il n'a pas demandé, sans moyen de savoir laquelle de ses
    épreuves l'a absorbé.
    """
    _importer(db_session, patch_scraper, KLIKEGO, "klikego")
    done = _importer(db_session, patch_scraper, BREIZH, "breizhchrono")

    assert len(done["passive_sources"]) == 1
    signalee = done["passive_sources"][0]
    assert signalee.url == BREIZH
    assert signalee.course_name == "Triathlon de Mesquer"
    assert "Triathlon de Mesquer" in signalee.message
    assert "administrateur" in signalee.message


def test_the_passive_source_is_reported_once_whatever_the_number_of_rows(
    db_session, patch_scraper
):
    """Le signalement compte des **sources**, pas des lignes scrapées.

    `_Persister.add` résout l'épreuve une fois par participant : sans dédup, un
    classement de 250 lignes rendrait 250 fois la même phrase, et le bilan de
    batch aurait compté 250 sources enregistrées pour une.
    """
    _importer(db_session, patch_scraper, KLIKEGO, "klikego", bibs=("1", "2", "3"))

    done = _importer(db_session, patch_scraper, BREIZH, "breizhchrono", bibs=("1", "2", "3"))

    assert [source.url for source in done["passive_sources"]] == [BREIZH]


# ------------------------------------------------- contrat de la phase `done`


def test_every_done_phase_carries_the_key(db_session, patch_scraper):
    """Le contrat de `done` : les mêmes clés sur **tous** les chemins.

    Trois chemins mènent à `done`, et le consommateur SSE / batch ne doit avoir
    aucun accès conditionnel à gérer. Le court-circuit du cache TTL et le chemin
    « aucun résultat » ne scrapent rien, ils ne peuvent donc rien enregistrer —
    mais ils doivent quand même porter la clé.
    """
    _importer(db_session, patch_scraper, KLIKEGO, "klikego")

    # Cache TTL frais : `done` seule, sans phase `scraping`.
    phases = list(import_service.iter_import_event(db_session, KLIKEGO, _settings()))
    assert [p["phase"] for p in phases] == ["done"]
    assert phases[-1]["cached"] is True
    assert phases[-1]["passive_sources"] == []

    # Aucun résultat scrapé.
    patch_scraper([])
    phases = list(
        import_service.iter_import_event(db_session, BREIZH, _settings(), force=True)
    )
    assert phases[-1]["phase"] == "done"
    assert phases[-1]["passive_sources"] == []


def test_the_blocking_import_carries_it_too(db_session, patch_scraper):
    """`POST /scrape/event` et le SSE ne doivent pas diverger sur le fond.

    Même parti pris que `reconciled` : le dict d'`import_event` porte le
    signalement, le schéma public `ImportResult` ne l'expose pas — le front
    consomme le SSE, et une route bloquante n'a pas à grossir pour un champ que
    personne n'y lit.
    """
    patch_scraper([_result("1", source_url=KLIKEGO, provider="klikego")])
    import_service.import_event(db_session, KLIKEGO, _settings())

    patch_scraper([_result("1", source_url=BREIZH, provider="breizhchrono")])
    out = import_service.import_event(db_session, BREIZH, _settings())

    assert [source.url for source in out["passive_sources"]] == [BREIZH]


# ------------------------------------- l'épreuve sans source active (saisie manuelle)


def test_a_course_without_any_active_source_takes_the_submitted_url_as_active(
    db_session, patch_scraper
):
    """La même règle que pour une épreuve neuve : la première scrapée prend la main.

    Une épreuve saisie à la main (`POST /participations` sans `source_url`) n'a
    **aucune** source. Y rattacher la première URL collée en *passive* produirait
    une source orpheline : jamais scrapée (#282), jamais affichée (#279), et
    inutilisable jusqu'à ce qu'un administrateur l'active à la main — pour une
    épreuve dont il n'y a rien d'autre à activer. D3 dit « la **première
    scrapée** garde la main » : ici, il n'y en a pas encore.
    """
    manuelle = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-s",
    )
    db_session.flush()
    assert _sources(db_session, manuelle.id) == []

    done = _importer(db_session, patch_scraper, KLIKEGO, "klikego")

    assert [(s.url, s.is_active) for s in _sources(db_session, manuelle.id)] == [(KLIKEGO, True)]
    assert done["passive_sources"] == [], "rien à signaler : l'URL a pris la main"


# ------------------------------------------------------- la primitive du repository


def test_attaching_a_url_twice_returns_the_same_source(db_session):
    """`attach` est idempotent sur `UNIQUE(course_id, url)`, et le dit par son retour.

    C'est cette idempotence qui permet à `mapping` d'appeler sans condition, une
    fois par ligne scrapée, plutôt que de tenir un registre de ce qu'il a déjà vu.
    """
    course = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-s", source_url=KLIKEGO, provider="klikego",
    )
    db_session.flush()

    premier = course_source_repository.attach(
        db_session, course=course, url=BREIZH, provider="breizhchrono"
    )
    second = course_source_repository.attach(
        db_session, course=course, url=BREIZH, provider="breizhchrono"
    )

    assert premier.id == second.id
    assert premier.is_active is False
    assert len(_sources(db_session, course.id)) == 2


def test_an_empty_url_attaches_nothing(db_session):
    """`POST /participations` sans `source_url` : il n'y a pas d'URL à rattacher.

    Une source sans URL serait une ligne qui ne désigne rien — `CourseSource.url`
    est `NOT NULL`, et l'épinglage de #279 (`test_a_provider_without_a_url_is_not
    _representable`) tient précisément à ce qu'aucun chemin n'en crée.
    """
    resolution = mapping.get_or_create_course(
        db_session,
        _result("1", source_url="", provider="manuel", nom="MARTIN"),
        "",
    )

    assert resolution.passive_source is None
    assert _sources(db_session, resolution.course.id) == []
    assert resolution.course.provider == ""
