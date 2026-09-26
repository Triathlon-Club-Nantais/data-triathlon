import logging

import pytest

from app.scrapers.base import ScrapedResult
from app.services import mapping


def _scraped(**kw) -> ScrapedResult:
    base = dict(source_url="http://x", provider="klikego")
    base.update(kw)
    return ScrapedResult(**base)


def test_build_splits_only_non_empty():
    s = _scraped(swim_time="00:20:00", bike_time="01:00:00", run_time="00:40:00")
    assert mapping.build_splits(s) == {
        "swim": "00:20:00",
        "bike": "01:00:00",
        "run": "00:40:00",
    }


def test_build_splits_empty():
    assert mapping.build_splits(_scraped()) == {}


def test_build_splits_duathlon_renames_keys():
    # Duathlon : les scrapers rangent course1 → swim_time, course2 → run_time.
    # build_splits doit ré-étiqueter selon le sport (course1/course2, pas swim/run).
    s = _scraped(
        event_type="duathlon-m",
        swim_time="00:15:00", bike_time="00:40:00", run_time="00:18:00",
    )
    assert mapping.build_splits(s) == {
        "course1": "00:15:00",
        "bike": "00:40:00",
        "course2": "00:18:00",
    }


def test_build_splits_bike_run_omits_swim():
    s = _scraped(event_type="bike-run", bike_time="00:20:00", run_time="00:10:00")
    assert mapping.build_splits(s) == {"bike": "00:20:00", "run": "00:10:00"}


def test_build_splits_bike_run_keeps_a_filled_first_slot():
    # Il n'y a pas de natation en bike & run : le slot 1 ne doit jamais sortir en
    # « swim ». Mais rempli, il ne doit pas non plus être jeté — runnerbreizh
    # publie 3 colonnes figées quelle que soit la discipline, et la première n'a
    # là-bas aucune discipline lisible, d'où une clé positionnelle.
    s = _scraped(
        event_type="bike-run",
        swim_time="00:10:00", bike_time="00:30:00", run_time="00:20:00",
    )
    assert mapping.build_splits(s) == {
        "segment1": "00:10:00",
        "bike": "00:30:00",
        "run": "00:20:00",
    }


def test_build_splits_swimrun_keeps_a_filled_middle_slot():
    # Même trou dans le gabarit swimrun : le slot vélo n'y a pas de sens, mais un
    # temps qui s'y trouve est une donnée, pas un parasite.
    s = _scraped(
        event_type="swimrun-l",
        swim_time="00:12:00", bike_time="00:25:00", run_time="00:40:00",
    )
    assert mapping.build_splits(s) == {
        "swim": "00:12:00",
        "segment2": "00:25:00",
        "run": "00:40:00",
    }


# #971 : un segment n'est gardé que s'il est une durée strictement positive,
# au plus égale au temps total.

@pytest.mark.parametrize(
    "bad", ["00:00:00", "0:00:00", "00:00", "-00:02:10", "00:-43:-18", "-1:-14:-32", "FRA"]
)
def test_build_splits_drops_a_slot_that_is_not_a_positive_duration(bad):
    s = _scraped(total_time="02:00:00", swim_time=bad, bike_time="01:00:00")
    assert mapping.build_splits(s) == {"bike": "01:00:00"}


@pytest.mark.parametrize("bad", ["00:00:00", "-00:02:10", "FRA"])
def test_build_splits_drops_a_segment_that_is_not_a_positive_duration(bad):
    s = _scraped(total_time="02:00:00", segments=[("Natation", bad), ("Vélo", "01:00:00")])
    assert mapping.build_splits(s) == {"Vélo": "01:00:00"}


def test_build_splits_drops_a_segment_longer_than_the_total():
    s = _scraped(total_time="00:19:38", swim_time="00:05:00", t1_time="00:30:48")
    assert mapping.build_splits(s) == {"swim": "00:05:00"}


def test_build_splits_keeps_segments_when_the_total_is_unreadable():
    s = _scraped(swim_time="00:05:00", run_time="00:30:48")
    assert mapping.build_splits(s) == {"swim": "00:05:00", "run": "00:30:48"}


def test_build_splits_drops_every_segment_when_all_equal_the_total():
    segs = [(f"T{i}", "00:50:12") for i in range(1, 6)]
    assert mapping.build_splits(_scraped(total_time="00:50:12", segments=segs)) == {}


def test_build_splits_keeps_a_single_segment_equal_to_the_total():
    s = _scraped(event_type="trail", total_time="01:45:00", run_time="01:45:00")
    assert mapping.build_splits(s) == {"run": "01:45:00"}


def test_build_splits_logs_each_rejected_segment(caplog):
    s = _scraped(provider="breizhchrono", total_time="02:00:00", swim_time="-00:02:10")
    with caplog.at_level(logging.INFO, logger="app.services.mapping"):
        mapping.build_splits(s)
    assert "breizhchrono" in caplog.text
    assert "swim" in caplog.text
    assert "-00:02:10" in caplog.text


def test_build_splits_uses_segments_when_provided():
    # Chemin générique : si `segments` est renseigné, il prime sur les 5 slots
    # et les étiquettes libres sont conservées (ordre inclus).
    s = _scraped(
        event_type="triathlon-m",
        swim_time="00:20:00",  # ignoré car segments fourni
        segments=[("prologue", "00:05:00"), ("bike", "01:00:00"), ("epilogue", "00:30:00")],
    )
    assert mapping.build_splits(s) == {
        "prologue": "00:05:00",
        "bike": "01:00:00",
        "epilogue": "00:30:00",
    }


def test_build_splits_segments_skip_empty():
    s = _scraped(segments=[("a", "00:01:00"), ("b", ""), ("c", "00:03:00")])
    assert mapping.build_splits(s) == {"a": "00:01:00", "c": "00:03:00"}


def test_build_splits_segments_desambiguent_les_libelles_en_collision():
    # Deux colonnes réduites au même libellé (ex. deux « Course à pied » une fois
    # l'i18n retirée) ne doivent pas se collapser : le second est désambiguïsé,
    # aucun temps n'est perdu (promesse « pas de plafond » de l'AGENTS.md).
    s = _scraped(segments=[
        ("Course à pied", "00:20:00"),
        ("bike", "01:00:00"),
        ("Course à pied", "00:25:00"),
    ])
    assert mapping.build_splits(s) == {
        "Course à pied": "00:20:00",
        "bike": "01:00:00",
        "Course à pied (2)": "00:25:00",
    }


def test_build_splits_segments_uncapped():
    # Plus de 5 segments (ex. swimrun multi-legs) : aucun plafond sur le chemin générique.
    segs = [(f"leg{i}", f"00:0{i}:00") for i in range(1, 8)]
    assert len(mapping.build_splits(_scraped(segments=segs))) == 7


def test_derive_status_heuristic_finisher():
    # Pas de status explicite + temps total → finisher (heuristique).
    assert mapping.derive_status(_scraped(total_time="01:59:00")) == "finisher"


def test_derive_status_heuristic_dnf():
    # Pas de status explicite + pas de temps → DNF (heuristique).
    assert mapping.derive_status(_scraped()) == "DNF"


def test_derive_status_respects_explicit_status():
    # Un status posé par le scraper prime sur l'heuristique, même contre le temps.
    assert mapping.derive_status(_scraped(status="DSQ", total_time="01:59:00")) == "DSQ"
    assert mapping.derive_status(_scraped(status="DNS")) == "DNS"


@pytest.mark.parametrize("bad", ["Abandon", "Disqualifié", "-00:00:06", "00:12'15\"000x"])
def test_participation_fields_neither_stores_nor_ranks_finisher_an_unreadable_total(bad):
    # #969 : un libellé ou un format non lu n'est pas un temps d'arrivée.
    fields = mapping.participation_fields(
        _scraped(total_time=bad), athlete_id=1, course_id=2
    )
    assert fields["total_time"] is None
    assert fields["status"] == "DNF"


def test_unreadable_total_is_logged_as_a_warning(caplog):
    # Écarter un total fait d'un finisher un DNF : la perte doit se voir.
    with caplog.at_level(logging.WARNING, logger="app.services.mapping"):
        mapping.participation_fields(_scraped(total_time="Abandon"), athlete_id=1, course_id=2)
    assert any(
        rec.levelno == logging.WARNING and "Temps total écarté" in rec.message
        for rec in caplog.records
    )


def test_participation_fields():
    s = _scraped(
        bib_number="42", club="TCN", category="V1H",
        rank_overall=10, total_time="01:59:00", swim_time="00:20:00",
    )
    fields = mapping.participation_fields(s, athlete_id=1, course_id=2)
    assert fields["athlete_id"] == 1
    assert fields["course_id"] == 2
    assert fields["bib_number"] == "42"
    assert fields["status"] == "finisher"
    assert fields["splits"] == {"swim": "00:20:00"}


def test_participation_fields_import_nest_jamais_pendant():
    """FR-017 — un résultat importé ne porte jamais l'état de saisie manuelle."""
    fields = mapping.participation_fields(_scraped(), athlete_id=1, course_id=2)
    assert fields["is_pending_validation"] is False


def test_participation_fields_carries_is_relay():
    assert mapping.participation_fields(
        _scraped(is_relay=True), athlete_id=1, course_id=2
    )["is_relay"] is True
    assert mapping.participation_fields(
        _scraped(), athlete_id=1, course_id=2
    )["is_relay"] is False


def test_build_splits_trail_single_run():
    s = _scraped(event_type="trail", run_time="01:45:00")
    assert mapping.build_splits(s) == {"run": "01:45:00"}


def test_build_splits_course_a_pied_named_size():
    # _sport_base doit gérer la base multi-mots "course-a-pied" (pas "course").
    s = _scraped(event_type="course-a-pied-10k", run_time="00:38:00")
    assert mapping.build_splits(s) == {"run": "00:38:00"}


def test_build_splits_cyclisme_single_bike():
    s = _scraped(event_type="cyclisme-route", bike_time="03:10:00")
    assert mapping.build_splits(s) == {"bike": "03:10:00"}


# --- Nouvelles disciplines de la saisie manuelle (#270) ---


def test_sport_base_reconnait_les_bases_multi_mots_nouvelles():
    # Piège central : _sport_base coupe au premier tiret. Sans déclaration dans
    # _MULTI_WORD_BASES, "swim-bike-m" donnerait la base "swim".
    assert mapping._sport_base("swim-bike-m") == "swim-bike"
    assert mapping._sport_base("swim-bike") == "swim-bike"
    assert mapping._sport_base("cross-triathlon") == "cross-triathlon"
    assert mapping._sport_base("raid-multisport") == "raid-multisport"


def test_build_splits_swim_bike_omet_la_course_a_pied():
    s = _scraped(
        event_type="swim-bike-m",
        swim_time="00:20:00", t1_time="00:02:00", bike_time="01:00:00",
        run_time="00:30:00",  # sans objet sur cette discipline : doit être ignoré
    )
    assert mapping.build_splits(s) == {
        "swim": "00:20:00", "t1": "00:02:00", "bike": "01:00:00",
    }


def test_build_splits_cross_triathlon_retombe_sur_le_gabarit_par_defaut():
    s = _scraped(
        event_type="cross-triathlon",
        swim_time="00:20:00", bike_time="01:00:00", run_time="00:40:00",
    )
    assert mapping.build_splits(s) == {
        "swim": "00:20:00", "bike": "01:00:00", "run": "00:40:00",
    }


def test_get_or_create_course_extracts_distance_km(db_session):
    s = _scraped(event_name="Trail des Forts 23 km", event_type="trail")
    course = mapping.get_or_create_course(db_session, s, event_url="http://x").course
    assert course.distance_km == 23.0


def test_get_or_create_course_falls_back_to_the_event_url_as_source(db_session):
    """A scraper that leaves `source_url` empty still attaches its course (#1108)."""
    s = _scraped(source_url="", event_name="Tri de Vertou", event_type="triathlon-s")

    course = mapping.get_or_create_course(
        db_session, s, event_url="https://www.klikego.com/resultats/vertou/1"
    ).course

    assert [source.url for source in course.sources] == ["https://www.klikego.com/resultats/vertou/1"]
    assert course.source_url == "https://www.klikego.com/resultats/vertou/1"


def test_get_or_create_course_explicit_distance_km_wins(db_session):
    s = _scraped(event_name="Trail sans km dans le nom", event_type="trail",
                 distance_km=30.0)
    course = mapping.get_or_create_course(db_session, s, event_url="http://x").course
    assert course.distance_km == 30.0


def test_get_or_create_course_solo_and_relay_are_distinct(db_session):
    solo = _scraped(
        event_name="Triathlon de Nantes",
        event_type="triathlon-m",
        is_relay=False,
    )
    relais = _scraped(
        event_name="Triathlon de Nantes",
        event_type="triathlon-m",
        is_relay=True,
    )
    c_solo = mapping.get_or_create_course(db_session, solo, event_url="http://x").course
    c_relais = mapping.get_or_create_course(db_session, relais, event_url="http://x").course
    assert c_solo.id != c_relais.id
    assert c_solo.is_relay is False
    assert c_relais.is_relay is True


def test_get_or_create_course_aquathlons_meme_jour_restent_distincts(db_session):
    """Régression : les 4 aquathlons de Carnac partagent date et `event_type`.

    `uq_course_identity` = (name, event_date, event_type, is_relay) : seul le nom
    de course, présent dans le nom composé « Événement - Course », les sépare.
    Nommer les courses d'après le seul événement les fusionnerait en une Course.
    """
    from datetime import date

    courses = [
        mapping.get_or_create_course(
            db_session,
            _scraped(
                event_name=f"Triathlon de Carnac 2025 - Aquathlon {categorie}",
                event_type="aquathlon",
                event_date=date(2025, 10, 4),
            ),
            event_url="http://x",
        ).course
        for categorie in ("Pupilles", "Benjamins", "Minimes", "Poussins et Mini-Poussins")
    ]
    assert len({c.id for c in courses}) == 4


def test_resolve_athlete_reporte_le_drapeau_de_creation(db_session):
    scraped = ScrapedResult(
        source_url="http://d", provider="klikego",
        athlete_name="LE BERRE", athlete_firstname="Audrey",
        event_name="Tri", event_type="triathlon-m",
    )
    _, cree = mapping.resolve_athlete(db_session, scraped)
    assert cree is True
    _, cree2 = mapping.resolve_athlete(db_session, scraped)
    assert cree2 is False
