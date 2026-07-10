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


def test_get_or_create_course_extracts_distance_km(db_session):
    s = _scraped(event_name="Trail des Forts 23 km", event_type="trail")
    course = mapping.get_or_create_course(db_session, s, event_url="http://x")
    assert course.distance_km == 23.0


def test_get_or_create_course_explicit_distance_km_wins(db_session):
    s = _scraped(event_name="Trail sans km dans le nom", event_type="trail",
                 distance_km=30.0)
    course = mapping.get_or_create_course(db_session, s, event_url="http://x")
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
    c_solo = mapping.get_or_create_course(db_session, solo, event_url="http://x")
    c_relais = mapping.get_or_create_course(db_session, relais, event_url="http://x")
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
        )
        for categorie in ("Pupilles", "Benjamins", "Minimes", "Poussins et Mini-Poussins")
    ]
    assert len({c.id for c in courses}) == 4
