"""La scission solo/relais par `is_relay` renumérote `rank_overall` (#672).

Quand une épreuve source ne fait qu'un « heat » mêlant solo et relais/duo,
`is_relay` faisant partie de l'identité `Course`
(`course_repository.get_by_identity` : `name, event_date, event_type,
is_relay`), le scrape se retrouve scindé en deux `Course`. Le `rank_overall`
scrapé porte alors le rang dans le **champ combiné** de la source (ex. 597
pour 3 relayeurs) — conservé tel quel, il casse l'hypothèse de
`services/quality.py::_rank_anomalies` (classement local 1..N sans trou) et
classe l'épreuve « à revalider » (#119) alors que rien n'est faux. Constaté
sur deux fournisseurs indépendants (ProLiveSport, Chronoplace) : la cause
commune est l'identité `Course`, pas un scraper.

Le fix renumérote `rank_overall` en 1..N au moment précis où le scrape scinde
l'épreuve par `is_relay` (`import_service`, avant l'écriture) — pas dans les
scrapers.
"""
from datetime import date

from app.core.config import Settings
from app.repositories import course_repository, participation_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service

URL = "https://www.prolivesport.fr/resultats/event/1082"
NOM = "Audencia La Baule 2025"
JOUR = date(2025, 9, 14)
TYPE = "triathlon-m"


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(bib: str, rank_overall: int, *, is_relay: bool) -> ScrapedResult:
    return ScrapedResult(
        source_url=URL,
        provider="prolivesport",
        athlete_name=f"NOM-{bib}",
        athlete_firstname="Jean",
        bib_number=bib,
        event_name=NOM,
        event_date=JOUR,
        event_type=TYPE,
        is_relay=is_relay,
        rank_overall=rank_overall,
        total_time="01:59:00",
    )


def test_la_scission_solo_relais_renumerote_le_rang_du_petit_lot(db_session, patch_scraper):
    """3 relayeurs hérités des rangs 597-599 du champ combiné → renumérotés 1-3."""
    patch_scraper(
        [
            _result("1", 1, is_relay=False),
            _result("2", 2, is_relay=False),
            _result("3", 3, is_relay=False),
            _result("R1", 597, is_relay=True),
            _result("R2", 598, is_relay=True),
            _result("R3", 599, is_relay=True),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    solo = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    relais = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, True)
    assert solo is not None and relais is not None
    assert solo.id != relais.id

    ranks_relais = sorted(
        p.rank_overall
        for p in participation_repository.list_for_course(db_session, relais.id)
    )
    assert ranks_relais == [1, 2, 3]

    # Le classement solo, déjà 1..N localement, ne bouge pas.
    ranks_solo = sorted(
        p.rank_overall
        for p in participation_repository.list_for_course(db_session, solo.id)
    )
    assert ranks_solo == [1, 2, 3]

    assert relais.is_reliable is True
    assert relais.quality_issues == {}
    assert solo.is_reliable is True
    assert solo.quality_issues == {}


def test_ordre_relatif_du_rang_source_preserve_apres_renumerotation(db_session, patch_scraper):
    """Le tri de renumérotation respecte l'ordre du rang combiné d'origine,
    même si les lignes n'arrivent pas déjà triées dans le scrape."""
    patch_scraper(
        [
            _result("1", 1, is_relay=False),
            _result("R2", 598, is_relay=True),  # arrive en 1er, rang combiné 598
            _result("R1", 597, is_relay=True),  # arrive en 2nd, rang combiné 597 (< 598)
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    relais = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, True)
    rows = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, relais.id)
    }
    # R1 (597, le plus petit rang source) devient 1, R2 (598) devient 2 —
    # l'ordre du rang combiné d'origine prime sur l'ordre d'arrivée du scrape.
    assert rows["R1"] == 1
    assert rows["R2"] == 2


def test_sans_scission_dans_le_lot_le_rang_source_est_conserve(db_session, patch_scraper):
    """Garde-fou : un lot qui ne publie qu'une seule valeur `is_relay` pour
    l'épreuve n'est pas touché — rien n'indique une scission par champ
    combiné dans **ce** lot (ex. re-scrape d'un seul heat relais). Renuméroter
    quand même corromprait un classement qui n'a peut-être aucun rapport avec
    un champ combiné."""
    patch_scraper(
        [
            _result("R1", 597, is_relay=True),
            _result("R2", 598, is_relay=True),
            _result("R3", 599, is_relay=True),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    relais = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, True)
    ranks = sorted(
        p.rank_overall
        for p in participation_repository.list_for_course(db_session, relais.id)
    )
    assert ranks == [597, 598, 599]


def test_lot_partiel_ne_renumerote_pas_le_sous_groupe_incomplet(db_session, patch_scraper):
    """#764 : une source instable (ProLiveSport, cf. docs/scrapers/prolivesport.md)
    peut omettre une ligne d'un essai à l'autre — renuméroter le sous-groupe
    restant écraserait un classement complet et correct par un classement
    partiel et faux, sans jamais converger."""
    patch_scraper(
        [
            _result("1", 1, is_relay=False),
            _result("2", 2, is_relay=False),
            _result("3", 3, is_relay=False),
            _result("R1", 597, is_relay=True),
            _result("R2", 598, is_relay=True),
            _result("R3", 599, is_relay=True),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    relais = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, True)
    assert relais.participation_count == 3

    # Rescrape : R1 a disparu du jeu de lignes rendu par la source cette
    # fois-ci — le lot ne couvre plus que 2 des 3 lignes déjà persistées.
    patch_scraper(
        [
            _result("1", 1, is_relay=False),
            _result("2", 2, is_relay=False),
            _result("3", 3, is_relay=False),
            _result("R2", 598, is_relay=True),
            _result("R3", 599, is_relay=True),
        ]
    )
    import_service.import_event(db_session, URL, _settings(), force=True)

    ranks_relais = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, relais.id)
    }
    # R2/R3 gardent leur rang local déjà correct (2, 3) — ni écrasés par le
    # rang combiné brut de la source (598, 599), ni renumérotés en 1..2 sur un
    # sous-groupe incomplet. R1, absent de ce lot, reste inchangé (1).
    assert ranks_relais == {"R1": 1, "R2": 2, "R3": 3}


def test_lot_deja_scinde_et_numerote_localement_reste_inchange(db_session, patch_scraper):
    """Sécurité : quand chaque sous-groupe `is_relay` du lot est déjà classé
    localement en 1..N (ex. deux heats de la source, déjà distincts), la
    renumérotation ne change rien — tri stable sur un rang déjà 1..N."""
    patch_scraper(
        [
            _result("1", 1, is_relay=False),
            _result("2", 2, is_relay=False),
            _result("R1", 1, is_relay=True),
            _result("R2", 2, is_relay=True),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    solo = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    relais = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, True)

    ranks_solo = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, solo.id)
    }
    ranks_relais = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, relais.id)
    }
    assert ranks_solo == {"1": 1, "2": 2}
    assert ranks_relais == {"R1": 1, "R2": 2}
