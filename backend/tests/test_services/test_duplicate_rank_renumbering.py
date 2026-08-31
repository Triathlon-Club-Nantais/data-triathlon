"""Un rang non global côté source renumérote `rank_overall` par temps (#757, #785).

Mesuré sur RaceResult (3 façades) : certaines épreuves publient leur champ de
rang (`AUTORANK`) **par groupe d'affichage** — le genre, le plus souvent — et
non pour l'épreuve entière. Deux finishers de groupes différents peuvent donc
partager le même `rank_overall` sans qu'aucun ne soit réellement premier :
constaté en direct sur Embrunman, deux vainqueurs de rang 1, temps 09:17:39 et
10:28:19 (celui-ci pourtant classé derrière un homme parti dans un groupe
distinct). `services/quality.py::_rank_anomalies` le relève en
`duplicate_rank`.

Le fix renumérote `rank_overall` en 1..N par temps croissant, au même point
que la renumérotation solo/relais (#672) — mais sur un critère différent : le
rang source ne peut pas servir de tri (deux ordres indépendants y sont
mélangés), contrairement au rang combiné du cas #672 où l'ordre relatif reste
correct.
"""
from datetime import date

from app.core.config import Settings
from app.repositories import course_repository, participation_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service

URL = "https://my.raceresult.com/350635/results?contest=1"
NOM = "Embrunman - {EN:Embrunman|FR:Embruman}"
JOUR = date(2025, 8, 15)
TYPE = "triathlon-xl"


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(bib: str, rank_overall: int, total_time: str) -> ScrapedResult:
    return ScrapedResult(
        source_url=URL,
        provider="raceresult",
        athlete_name=f"NOM-{bib}",
        athlete_firstname="Jean",
        bib_number=bib,
        event_name=NOM,
        event_date=JOUR,
        event_type=TYPE,
        is_relay=False,
        rank_overall=rank_overall,
        total_time=total_time,
    )


def test_deux_groupes_avec_rang_1_partage_sont_renumerotes_par_temps(db_session, patch_scraper):
    """Carte exacte mesurée sur Embrunman : deux « rang 1 » (un par genre),
    temps 09:17:39 et 10:28:19 — le temps le plus rapide doit obtenir le
    rang 1 une fois fusionné, peu importe le rang porté par la source."""
    patch_scraper(
        [
            _result("104", 1, "09:17:39"),  # rang source 1 (groupe hommes)
            _result("7", 1, "10:28:19"),    # rang source 1 (groupe femmes)
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    assert course is not None
    ranks = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }
    assert ranks == {"104": 1, "7": 2}
    assert course.is_reliable is True
    assert course.quality_issues == {}


def test_quatre_lignes_deux_groupes_reordonnees_par_temps_croissant(db_session, patch_scraper):
    """Généralise à 2 groupes de 2 : le classement fusionné doit suivre le
    temps du plus rapide au plus lent, indépendamment du rang source."""
    patch_scraper(
        [
            _result("F1", 1, "10:00:00"),
            _result("F2", 2, "11:00:00"),
            _result("H1", 1, "09:00:00"),
            _result("H2", 2, "09:30:00"),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    ranks = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }
    assert ranks == {"H1": 1, "H2": 2, "F1": 3, "F2": 4}


def test_sans_doublon_le_rang_source_est_conserve(db_session, patch_scraper):
    """Garde-fou : un rang déjà unique dans ce lot n'est pas retouché — rien
    n'indique qu'il est scindé par groupe d'affichage, y toucher serait sans
    fondement et pourrait même désaccorder un rang authentiquement global
    d'un temps mal formé ou incomparable (chronométrage manuel, ex æquo
    officiel déjà tranché par la source)."""
    patch_scraper(
        [
            _result("1", 1, "09:00:00"),
            _result("2", 2, "10:00:00"),
            _result("3", 3, "08:00:00"),  # rang 3 alors que le temps est le plus rapide
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    ranks = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }
    # Rang source conservé tel quel : aucun doublon dans ce lot, rien à corriger.
    assert ranks == {"1": 1, "2": 2, "3": 3}
