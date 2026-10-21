"""Une reclassification met à jour l'épreuve, elle n'en crée pas une seconde (#294).

`classify_event_type` ne rend pas toujours le même verdict d'un scrape à l'autre —
l'heuristique s'affine, le contexte de nom change. L'identité d'une `Course` étant
`(name, event_date, event_type, is_relay)`, l'épreuve ne se retrouvait alors plus :
une **seconde** ligne naissait, et la première gardait ses résultats sous un sport
devenu faux. Constaté sur Mesquer 2026 — 498 finishers affichés en `swimrun-s`
alors que l'épreuve est un `triathlon-s`, et rien à l'écran ne distinguait les deux
lignes.

**Le rattrapage est un geste de lot, et ces tests disent pourquoi.** Le signal qui
sépare une reclassification d'un second heat n'existe pas sur une ligne : une même
URL publie légitimement N épreuves du **même nom**, à la **même date**, que seuls
`event_type` et `is_relay` distinguent — les six heats TimePulse d'une URL
d'événement, mesurés par le sondage #277 et déjà gardés par
`services/course_duplicates._same_source_url`. Ligne à ligne, le second heat est
indistinguable d'un premier heat reclassé. Le lot, lui, tranche : un scrape qui ne
publie **qu'une** classification pour une clé n'a pas deux heats à confondre.

Le chemin de la règle R (#289, Klikego ↔ Breizh Chrono) a ses propres tests dans
`test_platform_event_reconciliation.py` : là, l'épreuve n'était plus dédoublée
depuis #289, mais elle gardait le verdict de son *premier* scrape.
"""
from datetime import date, datetime, timedelta

from app.core.config import Settings
from app.models.course import EVENT_TYPE_ORIGIN_MANUAL, Course
from app.repositories import user_repository
from app.scrapers.base import ScrapedResult
from app.services import admin_actions, import_service

#: Hosts réels : `validate_url` refuse une URL qu'aucun provider ne reconnaît, un
#: `.test` ferait échouer ces tests pour une raison étrangère à #294.
WICLAX = "https://www.chronosmetron.com/754-triathlon-de-mesquer-2026?parcours=s-open"
#: L'URL d'**événement** TimePulse du cas mesuré : six heats sous une seule adresse
#: et sous un seul nom (cf. `test_course_duplicates`, motif « même URL »).
TIMEPULSE = "https://www.timepulse.fr/epreuves/resultats/live/3232"

MESQUER = "Triathlon de Mesquer S"
JOUR = date(2026, 6, 14)


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(
    bib: str,
    *,
    url: str,
    provider: str,
    event_name: str,
    event_type: str,
    is_relay: bool = False,
) -> ScrapedResult:
    return ScrapedResult(
        source_url=url,
        provider=provider,
        athlete_name=f"NOM-{bib}",
        athlete_firstname="Jean",
        bib_number=bib,
        event_name=event_name,
        event_date=JOUR,
        event_type=event_type,
        is_relay=is_relay,
        total_time="01:59:00",
    )


def _mesquer(bib: str, event_type: str) -> ScrapedResult:
    return _result(
        bib, url=WICLAX, provider="wiclax", event_name=MESQUER, event_type=event_type
    )


def _importer(db, patch_scraper, url, resultats, *, force=False) -> dict:
    patch_scraper(resultats)
    phases = list(import_service.iter_import_event(db, url, _settings(), force=force))
    assert phases[-1]["phase"] == "done", phases[-1]
    return phases[-1]


def test_un_rescrape_reclasse_lepreuve_au_lieu_den_creer_une_seconde(db_session, patch_scraper):
    """Le cas de l'issue, chez un fournisseur que la règle R ne rapproche pas.

    Klikego et Breizh Chrono mis à part, aucun des 14 ne partage d'identifiant de
    plateforme : #289 ne les voit pas, et la reclassification y produisait deux
    `Course` — `['swimrun-s', 'triathlon-s']`. Le rattrapage vaut pour les
    quatorze, il ne demande rien au fournisseur.
    """
    _importer(db_session, patch_scraper, WICLAX, [_mesquer("1", "swimrun-s")])

    _importer(db_session, patch_scraper, WICLAX, [_mesquer("1", "triathlon-s")], force=True)

    epreuve = db_session.query(Course).one()
    assert epreuve.event_type == "triathlon-s"


def test_le_rattrapage_garde_les_resultats_sur_la_meme_epreuve(db_session, patch_scraper):
    """Ce que le doublon coûtait vraiment : un classement orphelin sous un faux sport.

    Créer la seconde `Course` ne perdait pas les résultats, il les **scindait** —
    la première gardait ceux d'avant, la neuve recevait ceux d'après.
    """
    _importer(
        db_session, patch_scraper, WICLAX,
        [_mesquer("1", "swimrun-s"), _mesquer("2", "swimrun-s")],
    )

    _importer(
        db_session, patch_scraper, WICLAX,
        [_mesquer("1", "triathlon-s"), _mesquer("2", "triathlon-s")],
        force=True,
    )

    epreuve = db_session.query(Course).one()
    assert {p.bib_number for p in epreuve.participations} == {"1", "2"}


def test_les_heats_dune_url_devenement_ne_sont_jamais_fondus(db_session, patch_scraper):
    """Le garde-fou, et c'est **lui** qui impose le rattrapage de lot.

    TimePulse publie ses six heats sous une seule URL d'événement et sous le même
    nom ; seuls `event_type` et `is_relay` les séparent. Un rattrapage ligne à
    ligne prendrait le deuxième heat pour une reclassification du premier et
    fondrait deux classements réels en un — une perte de données, là où #294
    n'est qu'un affichage faux.
    """
    lot = [
        _result("1", url=TIMEPULSE, provider="timepulse",
                event_name="LE NORTH MAY", event_type="triathlon-l"),
        _result("2", url=TIMEPULSE, provider="timepulse",
                event_name="LE NORTH MAY", event_type="triathlon-m"),
        _result("3", url=TIMEPULSE, provider="timepulse",
                event_name="LE NORTH MAY", event_type="triathlon-l", is_relay=True),
    ]

    _importer(db_session, patch_scraper, TIMEPULSE, lot)
    _importer(db_session, patch_scraper, TIMEPULSE, lot, force=True)

    epreuves = db_session.query(Course).all()
    assert {(c.event_type, c.is_relay) for c in epreuves} == {
        ("triathlon-l", False),
        ("triathlon-m", False),
        ("triathlon-l", True),
    }


def test_une_collision_didentite_laisse_lepreuve_intacte(db_session, patch_scraper):
    """`uq_course_identity` prime sur le scrape : reclasser vers l'identité d'une
    épreuve déjà en base ferait tomber le flush sur la contrainte, en plein import.

    La ligne garde son type, et les deux épreuves restent deux — le doublon se
    règle par une fusion (#287), pas par une écriture forcée.
    """
    _importer(db_session, patch_scraper, WICLAX, [_mesquer("1", "swimrun-s")])
    reclassee_id = db_session.query(Course).one().id
    db_session.add(
        Course(name=MESQUER, event_date=JOUR, event_type="triathlon-s", is_relay=False)
    )
    db_session.flush()

    _importer(db_session, patch_scraper, WICLAX, [_mesquer("1", "triathlon-s")], force=True)

    assert db_session.get(Course, reclassee_id).event_type == "swimrun-s"
    assert db_session.query(Course).count() == 2


def test_a_manually_corrected_event_type_survives_a_reimport(db_session, patch_scraper):
    """#1745 : l'import rattache le scrape à l'épreuve corrigée, il ne la reclasse pas."""
    _importer(db_session, patch_scraper, WICLAX, [_mesquer("1", "swimrun-s")])
    epreuve = db_session.query(Course).one()
    epreuve.event_type = "duathlon-s"
    epreuve.event_type_origin = EVENT_TYPE_ORIGIN_MANUAL
    db_session.flush()

    _importer(db_session, patch_scraper, WICLAX, [_mesquer("1", "triathlon-s")], force=True)
    _importer(db_session, patch_scraper, WICLAX, [_mesquer("2", "triathlon-s")], force=True)

    epreuve = db_session.query(Course).one()
    assert epreuve.event_type == "duathlon-s"
    assert {p.bib_number for p in epreuve.participations} == {"1", "2"}


def test_a_sibling_heat_keeps_its_own_course_next_to_a_manually_corrected_one(
    db_session, patch_scraper
):
    """#1745 : un scrape qui ne publie que le heat frère ne le rattache pas à l'épreuve corrigée."""
    def heat(bib, event_type):
        return _result(
            bib, url=TIMEPULSE, provider="timepulse", event_name="Triathlon de Vertou",
            event_type=event_type,
        )

    _importer(
        db_session, patch_scraper, TIMEPULSE,
        [heat("1", "triathlon-s"), heat("2", "duathlon-s")],
    )
    corrected = db_session.query(Course).filter_by(event_type="triathlon-s").one()
    sibling = db_session.query(Course).filter_by(event_type="duathlon-s").one()
    admin = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    admin_actions.update_course(
        db_session, course_id=corrected.id, fields={"event_type": "aquathlon-s"}, user_id=admin.id
    )
    corrected.scraped_at = datetime(2030, 1, 1)
    sibling.scraped_at = datetime(2030, 1, 1) - timedelta(days=1)
    db_session.flush()

    _importer(db_session, patch_scraper, TIMEPULSE, [heat("2", "duathlon-s")], force=True)

    assert {p.bib_number for p in corrected.participations} == {"1"}
    assert {p.bib_number for p in sibling.participations} == {"2"}


def _neutral(bib, event_type="triathlon-s", *, name="La Chaussaire - Solo", **extra):
    return ScrapedResult(
        source_url=WICLAX, provider="wiclax", athlete_name=f"NOM-{bib}",
        athlete_firstname="Jean", bib_number=bib, event_name=name, event_date=JOUR,
        event_type=event_type, total_time="01:59:00", **extra,
    )


def test_import_flags_a_course_typed_by_the_fallback(db_session, patch_scraper):
    _importer(db_session, patch_scraper, WICLAX, [_neutral("1")])

    assert db_session.query(Course).one().event_type_origin == "fallback"


def test_import_does_not_flag_a_fallback_corroborated_by_splits(db_session, patch_scraper):
    _importer(
        db_session, patch_scraper, WICLAX,
        [_neutral("1", swim_time="00:20:00", bike_time="01:00:00")],
    )

    assert db_session.query(Course).one().event_type_origin == "classified"


def test_import_does_not_flag_a_named_triathlon(db_session, patch_scraper):
    _importer(
        db_session, patch_scraper, WICLAX,
        [_neutral("1", "triathlon-m", name="Triathlon M de Vertou")],
    )

    assert db_session.query(Course).one().event_type_origin == "classified"


def test_reimport_clears_the_flag_once_the_type_is_recognised(db_session, patch_scraper):
    _importer(db_session, patch_scraper, WICLAX, [_neutral("1")])

    _importer(db_session, patch_scraper, WICLAX, [_neutral("1", "duathlon-s")], force=True)

    course = db_session.query(Course).one()
    assert (course.event_type, course.event_type_origin) == ("duathlon-s", "classified")


def test_import_never_flags_a_manual_course(db_session, patch_scraper):
    _importer(db_session, patch_scraper, WICLAX, [_neutral("1")])
    admin = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    admin_actions.update_course(
        db_session, course_id=db_session.query(Course).one().id,
        fields={"event_type": "duathlon-s"}, user_id=admin.id,
    )

    _importer(db_session, patch_scraper, WICLAX, [_neutral("1")], force=True)

    course = db_session.query(Course).one()
    assert (course.event_type, course.event_type_origin) == ("duathlon-s", "manual")


def test_relay_twin_is_flagged_on_its_own(db_session, patch_scraper):
    _importer(
        db_session, patch_scraper, WICLAX,
        [_neutral("1"), _neutral("2", is_relay=True)],
    )

    courses = db_session.query(Course).all()
    assert len(courses) == 2
    assert {c.event_type_origin for c in courses} == {"fallback"}


def test_placeholder_splits_do_not_corroborate_a_fallback(db_session, patch_scraper):
    _importer(
        db_session, patch_scraper, WICLAX,
        [_neutral("1", swim_time="00:00:00", bike_time="00:00:00")],
    )

    assert db_session.query(Course).one().event_type_origin == "fallback"
