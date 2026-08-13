"""Rapprochement automatique de deux façades Breizh Chrono à l'import (#289).

Le sondage `docs/superpowers/specs/2026-08-12-sources-multiples-epreuve-sondage.md`
mesure que Klikego et Breizh Chrono « classique » (`resultats.`) collident déjà
sur l'identité actuelle (même back-office, même nom au caractère près) —
`test_passive_source_on_import.py` (#283) couvre ce cas. Le cas qui a réellement
besoin d'un rapprochement automatique est **l'inter-façade Breizh Chrono**,
`live.` contre `resultats.` : elles divergent sur `name` (événement+millésime
contre événement+heat) et sur `event_date` (jusqu'à 2 jours), mais partagent le
même identifiant de plateforme et le même slug de heat dans leur `source_url`.

Sans #289, ces deux scrapes produiraient deux `Course` sans lien — exactement
la régression qu'un rapprochement par nom seul (l'énoncé initial de l'epic
#275) ne peut pas réparer non plus (granularité de nommage différente).
"""
from dataclasses import replace
from datetime import date

import pytest

from app.core.config import Settings
from app.models.course import Course
from app.repositories import course_source_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service

#: Le couple mesuré par le sondage sur Dinard 2025 — noms et dates différents,
#: même identifiant de plateforme (`1488071608761-688`) et même heat.
RESULTATS = (
    "https://resultats.breizhchrono.com/resultats-courses/"
    "dinard-1488071608761-688/swimrun-court-duo"
)
LIVE = (
    "https://live.breizhchrono.com/external/live5/classements.jsp"
    "?version=new&reference=1488071608761-688&heat=swimrun-court-duo"
)


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _resultats_result(bib: str) -> ScrapedResult:
    return ScrapedResult(
        source_url=RESULTATS,
        provider="breizhchrono",
        athlete_name="DUPONT",
        athlete_firstname="Jean",
        bib_number=bib,
        event_name="Triathlon SwimRun Dinard Côte d'Emeraude 2025",
        event_date=date(2025, 9, 12),
        event_type="swimrun-m",
        is_relay=True,
        total_time="02:59:00",
    )


def _live_result(bib: str, *, heat_ref: str = "1488071608761-688:swimrun-court-duo") -> ScrapedResult:
    """Même paire (event_id, heat) que `_resultats_result` par défaut, nom et
    date **délibérément différents** — c'est ce que la règle R doit ignorer."""
    event_id, heat = heat_ref.split(":")
    return ScrapedResult(
        source_url=(
            "https://live.breizhchrono.com/external/live5/classements.jsp"
            f"?version=new&reference={event_id}&heat={heat}"
        ),
        provider="breizhchrono",
        athlete_name="DUPONT",
        athlete_firstname="Jean",
        bib_number=bib,
        event_name="Triathlon SwimRun Dinard Côte d'Emeraude - Swimrun Court Duo",
        event_date=date(2025, 9, 14),
        event_type="swimrun-m",
        is_relay=True,
        total_time="02:59:00",
    )


@pytest.fixture
def patch_scraper(monkeypatch):
    def _set(results):
        monkeypatch.setattr(
            import_service, "registry_scrape_event_all", lambda url, **kwargs: results
        )
    return _set


def _importer(db, patch_scraper, url: str, résultats: list[ScrapedResult], *, force=False) -> dict:
    patch_scraper(résultats)
    phases = list(import_service.iter_import_event(db, url, _settings(), force=force))
    assert phases[-1]["phase"] == "done", phases[-1]
    return phases[-1]


def test_deux_facades_du_meme_evenement_ne_font_quune_seule_course(db_session, patch_scraper):
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])
    cible = db_session.query(Course).one()

    _importer(db_session, patch_scraper, LIVE, [_live_result("1")])

    assert db_session.query(Course).all() == [cible], "une seule épreuve malgré des noms différents"
    urls = [s.url for s in course_source_repository.list_for_course(db_session, cible.id)]
    assert urls == [RESULTATS, LIVE]
    assert cible.source_url == RESULTATS, "la première scrapée garde la main (D3)"


def test_le_nom_et_la_date_de_la_cible_restent_ceux_de_la_source_active(db_session, patch_scraper):
    """La règle R dit « même épreuve », pas « quel nom garder » — c'est D2
    (source active fait foi) qui tranche, pas ce module."""
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])
    _importer(db_session, patch_scraper, LIVE, [_live_result("1")])

    cible = db_session.query(Course).one()
    assert cible.name == "Triathlon SwimRun Dinard Côte d'Emeraude 2025"
    assert cible.event_date == date(2025, 9, 12)


def test_limport_de_la_seconde_facade_alimente_bien_la_meme_course(db_session, patch_scraper):
    """Le rapprochement n'est pas qu'un lien de source : les participations
    scrapées par la seconde façade s'indexent sur la `Course` retrouvée."""
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])

    done = _importer(db_session, patch_scraper, LIVE, [_live_result("2")])

    cible = db_session.query(Course).one()
    assert {p.bib_number for p in cible.participations} == {"1", "2"}
    assert done["imported"] == 1


def test_un_heat_different_ne_rapproche_pas_et_cree_une_seconde_course(db_session, patch_scraper):
    """Mesquer : `swim-run-s-duo` et `swim-run-s-indiv` sont deux heats du même
    événement — la règle ne doit jamais les fondre en un seul."""
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])

    _importer(
        db_session, patch_scraper, LIVE,
        [_live_result("1", heat_ref="1488071608761-688:swimrun-court-solo")],
    )

    assert db_session.query(Course).count() == 2


def test_un_evenement_different_ne_rapproche_pas(db_session, patch_scraper):
    """Nozéen 2025 vs 2026 : l'édition change le suffixe de l'identifiant, la
    règle ne doit jamais confondre deux éditions successives."""
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])

    _importer(
        db_session, patch_scraper, LIVE,
        [_live_result("1", heat_ref="1488071608761-999:swimrun-court-duo")],
    )

    assert db_session.query(Course).count() == 2


def test_klikego_seul_ne_declenche_aucun_rapprochement_avec_un_id_partage(db_session, patch_scraper):
    """La règle exige les deux fournisseurs dans `{klikego, breizhchrono}` — un
    identifiant qui ressemble à un id de plateforme chez un autre fournisseur
    ne doit jamais être comparé."""
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])

    autre = ScrapedResult(
        source_url="https://timepulse.fr/live?id_event=1488071608761",
        provider="timepulse",
        athlete_name="DUPONT", athlete_firstname="Jean", bib_number="1",
        event_name="Autre épreuve", event_date=date(2025, 9, 14),
        event_type="swimrun-m", is_relay=True, total_time="02:59:00",
    )
    _importer(db_session, patch_scraper, "https://timepulse.fr/live?id_event=1488071608761", [autre])

    assert db_session.query(Course).count() == 2


def test_le_rescrape_de_la_source_active_rafraichit_la_classification(db_session, patch_scraper):
    """#294 sur le chemin de la règle R : le doublon avait disparu, pas le symptôme.

    Rapprochée par `(platform_event_id, heat_slug)`, la cible n'est plus jamais
    recréée — mais elle gardait le `event_type` de son **premier** scrape. Le
    classement de Mesquer restait donc affiché en swimrun alors que la source
    disait triathlon : un seul enregistrement, et faux.
    """
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])

    _importer(
        db_session, patch_scraper, RESULTATS,
        [replace(_resultats_result("1"), event_type="triathlon-m")],
        force=True,
    )

    cible = db_session.query(Course).one()
    assert cible.event_type == "triathlon-m"


def test_un_scrape_de_la_source_passive_ne_reclasse_pas_la_cible(db_session, patch_scraper):
    """D2, sur la classification comme sur le nom et la date : la source active
    fait foi. La façade `live.`, rattachée en passive, n'a pas voix au chapitre —
    sans quoi coller une seconde URL réécrirait le sport d'une épreuve dont le
    classement affiché vient d'ailleurs."""
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])

    _importer(
        db_session, patch_scraper, LIVE,
        [replace(_live_result("1"), event_type="triathlon-m")],
    )

    cible = db_session.query(Course).one()
    assert cible.event_type == "swimrun-m"
    assert cible.source_url == RESULTATS


def test_une_reclassification_en_collision_didentite_ne_reecrit_rien(db_session, patch_scraper):
    """`uq_course_identity` prime sur le scrape : reclasser vers l'identité d'une
    épreuve déjà en base ferait tomber le flush sur la contrainte, en plein
    import. La cible garde son type ; le doublon se règle par une fusion (#287)."""
    _importer(db_session, patch_scraper, RESULTATS, [_resultats_result("1")])
    cible_id = db_session.query(Course).one().id
    cible = db_session.get(Course, cible_id)
    db_session.add(
        Course(
            name=cible.name,
            event_date=cible.event_date,
            event_type="triathlon-m",
            is_relay=cible.is_relay,
        )
    )
    db_session.flush()

    _importer(
        db_session, patch_scraper, RESULTATS,
        [replace(_resultats_result("1"), event_type="triathlon-m")],
        force=True,
    )

    assert db_session.get(Course, cible_id).event_type == "swimrun-m"
    assert db_session.query(Course).count() == 2
