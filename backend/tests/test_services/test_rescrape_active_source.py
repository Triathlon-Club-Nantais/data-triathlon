"""Le rescrape en masse ne travaille que sur des sources **actives** (#282).

Une épreuve fusionnée porte N sources dont une seule active. Le batch ne doit
toucher qu'à celle-là — c'est la fin des doublons qu'un `rescrape-db` fabriquait
en re-scrapant les deux publications d'une même épreuve. Conséquence assumée :
une source passive vieillit indéfiniment, elle ne sert qu'à documenter l'autre
publication et à permettre la bascule (#285).

Le ciblage explicite (`--url`, `--urls-from`) est l'autre moitié du sujet : une
URL passive qu'on lui passe doit être **signalée en nommant l'épreuve et son
active**, jamais scrapée « à côté ». C'est la CLI qui en tire la substitution
(`test_cli/test_commands.py`) ; ce fichier-ci ne juge que la détection.
"""
from datetime import date

from app.core.config import Settings
from app.repositories import course_repository, course_source_repository
from app.services import import_service, rescrape_service

ACTIVE = "https://klikego.test/nozeen"
PASSIVE = "https://breizhchrono.test/nozeen"


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _epreuve(db, nom: str, url: str = "", *, provider: str = "klikego", jour: int = 1):
    course = course_repository.get_or_create(
        db, name=nom, event_date=date(2026, 1, jour),
        event_type=f"triathlon-{nom[0].lower()}",
        source_url=url, provider=provider if url else "",
    )
    db.flush()
    return course


def _fusionnee(db, nom: str = "Nozeen", *, jour: int = 1):
    """Une épreuve à deux sources : `ACTIVE` active, `PASSIVE` passive (D3)."""
    course = _epreuve(db, nom, ACTIVE, jour=jour)
    course_source_repository.add(
        db, course=course, url=PASSIVE, provider="breizhchrono"
    )
    db.flush()
    return course


# --- AC1 / AC3 : la sélection en base -----------------------------------------


def test_the_batch_scrapes_the_active_source_and_not_the_passive_one(db_session, monkeypatch):
    """AC1 — une épreuve fusionnée vaut **une** épreuve à scraper, pas deux.

    C'est le gain de l'epic mesuré ici : avant la table des sources, les deux
    publications étaient deux lignes `Course` sans lien, donc deux scrapes, donc
    deux classements concurrents pour la même course réelle.
    """
    _fusionnee(db_session)
    vus: list[str] = []

    def _iter(db, url, settings, force=False, persist=True, **kwargs):
        vus.append(url)
        yield {"phase": "done", "imported": 1, "skipped": 0, "reconciled": 0,
               "reassignments": [], "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    outcome = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)

    assert outcome.total == 1
    assert vus == [ACTIVE]


def test_a_course_whose_only_source_is_passive_is_never_scraped(db_session, monkeypatch):
    """Une épreuve sans source active n'a rien de scrapable, et le batch le voit.

    L'état est représentable : `course_source_repository.add` naît passif, donc
    rattacher une URL à une épreuve saisie à la main (#283) produit exactement
    ça. Le batch doit passer outre en silence — pas en erreur : rien n'a échoué.
    """
    manuelle = _epreuve(db_session, "Manuelle")
    course_source_repository.add(
        db_session, course=manuelle, url=PASSIVE, provider="breizhchrono"
    )
    db_session.flush()

    def _iter(db, url, settings, force=False, persist=True, **kwargs):
        raise AssertionError(f"rien ne doit être scrapé, or {url} l'a été")

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    outcome = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)

    assert outcome.total == 0
    assert outcome.errors == 0


def test_the_provider_filter_reads_the_active_source(db_session, monkeypatch):
    """AC3 — `--provider breizhchrono` ne rattrape pas une passive breizhchrono.

    Le filtre nomme le chronométreur **qu'on va interroger**. Retenir une épreuve
    parce qu'elle porte une passive du bon provider ferait scraper une URL
    klikego sous `--provider breizhchrono` : le contraire de ce qui a été demandé.
    """
    _fusionnee(db_session)
    vus: list[str] = []

    def _iter(db, url, settings, force=False, persist=True, **kwargs):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "reconciled": 0,
               "reassignments": [], "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    passif = rescrape_service.run_rescrape_db(
        db_session, _settings(), provider="breizhchrono", delay=0.0
    )
    actif = rescrape_service.run_rescrape_db(
        db_session, _settings(), provider="klikego", delay=0.0
    )

    assert passif.total == 0
    assert actif.total == 1
    assert vus == [ACTIVE]


# --- AC2 : le ciblage explicite d'une URL passive ------------------------------


def test_a_passive_url_is_reported_naming_the_course_and_its_active_source(db_session):
    """AC2 — la matière du signalement : l'épreuve, et l'URL réellement scrapée.

    Sans le nom de l'épreuve, la substitution est indéboguable : l'opérateur ne
    sait qu'une chose, c'est qu'il a collé une URL qui existe. Avec l'URL active,
    le message porte sa propre correction — celle du fichier d'URLs.
    """
    course = _fusionnee(db_session)

    cibles = rescrape_service.find_passive_targets(db_session, [PASSIVE])

    assert [cible.url for cible in cibles] == [PASSIVE]
    assert cibles[0].course_name == course.name
    assert cibles[0].active_url == ACTIVE


def test_an_unknown_url_is_not_a_passive_target(db_session):
    """Le cas **nominal** du rejeu d'un échec d'import reste intact.

    Une épreuve qui a échoué à l'import n'a rien persisté : son URL est absente
    de `course_sources`. La détourner fermerait la boucle
    `import-sheet --json | … --urls-from -`, qui est la raison d'être du mode
    ciblé.
    """
    _fusionnee(db_session)

    assert rescrape_service.find_passive_targets(db_session, ["https://k/inconnue"]) == []


def test_a_url_active_somewhere_is_never_a_passive_target(db_session):
    """Passive ici, active là : elle reste scrapable, et pour l'épreuve où elle l'est.

    Une URL porte légitimement N épreuves (heats Klikego, catégories Wiclax) :
    rien n'interdit qu'elle soit l'active de l'une et la passive d'une autre. La
    détection porte sur l'URL, pas sur le couple — elle ne peut donc se
    déclencher que si **aucune** épreuve ne la tient pour active.
    """
    _epreuve(db_session, "Active", PASSIVE, provider="breizhchrono", jour=2)
    _fusionnee(db_session, jour=1)

    assert rescrape_service.find_passive_targets(db_session, [PASSIVE]) == []


def test_a_trailing_slash_does_not_hide_a_passive_url(db_session):
    """Le cas se juge sur l'URL normalisée, comme toute comparaison d'URL ici.

    Un slash final ou une casse d'hôte différente vient d'un copier-coller, pas
    d'une intention. Comparer les formes brutes ferait passer la passive au
    travers du garde-fou — et la ferait scraper telle quelle, ce qu'il existe
    pour empêcher.
    """
    _fusionnee(db_session)

    cibles = rescrape_service.find_passive_targets(db_session, [PASSIVE + "/"])

    assert [cible.url for cible in cibles] == [PASSIVE + "/"]
    assert cibles[0].active_url == ACTIVE


def test_a_course_without_any_active_source_names_no_replacement(db_session):
    """Signalée quand même, mais sans promettre une URL de repli qui n'existe pas.

    Épreuve saisie à la main + une URL rattachée (donc passive) : il n'y a rien à
    proposer. `active_url` vide est ce qui dit à la CLI de scraper la passive
    telle quelle, plutôt que de nommer une chaîne vide comme si c'était une URL.
    """
    manuelle = _epreuve(db_session, "Manuelle")
    course_source_repository.add(
        db_session, course=manuelle, url=PASSIVE, provider="breizhchrono"
    )
    db_session.flush()

    cibles = rescrape_service.find_passive_targets(db_session, [PASSIVE])

    assert [cible.course_name for cible in cibles] == ["Manuelle"]
    assert cibles[0].active_url == ""


def test_every_passive_url_of_the_batch_is_reported_at_once(db_session):
    """Un opérateur qui pipe 40 URLs veut la liste des fautives, pas la première.

    Ordre d'entrée conservé : c'est celui de son fichier, donc celui qu'il
    corrige.
    """
    _fusionnee(db_session, "Nozeen", jour=1)
    autre = _epreuve(db_session, "Mesquer", "https://klikego.test/mesquer", jour=2)
    seconde_passive = "https://timepulse.test/mesquer"
    course_source_repository.add(
        db_session, course=autre, url=seconde_passive, provider="timepulse"
    )
    db_session.flush()

    cibles = rescrape_service.find_passive_targets(
        db_session, [seconde_passive, "https://k/inconnue", PASSIVE]
    )

    assert [cible.url for cible in cibles] == [seconde_passive, PASSIVE]
    assert [cible.course_name for cible in cibles] == ["Mesquer", "Nozeen"]


def test_no_targeting_asks_nothing_of_the_sources_table(db_session):
    """Mode base : il n'y a pas d'URL saisie, donc rien à rediriger."""
    _fusionnee(db_session)

    assert rescrape_service.find_passive_targets(db_session, []) == []
