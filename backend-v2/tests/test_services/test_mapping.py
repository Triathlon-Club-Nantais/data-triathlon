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


def test_derive_status():
    assert mapping.derive_status(_scraped(total_time="01:59:00")) == "finisher"
    assert mapping.derive_status(_scraped()) == "DNF"


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
