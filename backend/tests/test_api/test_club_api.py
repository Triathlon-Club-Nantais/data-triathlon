from datetime import date, datetime

from app.core import season
from app.models.club_member import LINK_AUTO, LINK_UNLINKED, SOURCE_FFTRI, ClubMember
from app.repositories import athlete_repository, course_repository, participation_repository


def test_club_summary_club_vide(client, db_session):
    resp = client.get("/api/v1/club/summary")
    assert resp.status_code == 200
    assert resp.json() == {
        "roster": [],
        "podiums": {"scratch": [], "category": [], "gender": [], "all": []},
        "podiums_totals": {"scratch": 0, "category": 0, "gender": 0, "all": 0},
        "podiums_by_discipline": {},
        "composition": {"gender": {}, "category": {}},
        "licensees": None,
    }


def test_club_summary_forme_de_la_reponse(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    resp = client.get("/api/v1/club/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["roster"][0]["nom"] == "A"
    assert body["roster"][0]["count"] == 1
    assert len(body["podiums"]["scratch"]) == 1
    assert body["podiums"]["scratch"][0]["athlete_name"] == "Alice A"
    assert body["podiums_by_discipline"]["triathlon-m"]["overall"] == 1
    assert body["composition"]["gender"] == {"": 1}


def test_club_summary_nomme_les_equipiers_d_un_podium_de_relais(client, db_session):
    """#894 : un podium de relais reste une entrée, qui nomme toute l'équipe."""
    jean = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    paul = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Relais", event_date=date(2026, 6, 1), event_type="triathlon-s",
        is_relay=True,
    )
    relais = participation_repository.create(
        db_session, athlete_id=jean.id, course_id=course.id, bib_number="7",
        club="TCN", status="finisher", rank_overall=2, is_relay=True,
    )
    participation_repository.replace_teammates(db_session, relais, [jean.id, paul.id])
    individuel = participation_repository.create(
        db_session, athlete_id=paul.id, course_id=course_repository.get_or_create(
            db_session, name="Solo", event_date=date(2026, 5, 1), event_type="triathlon-m",
        ).id, bib_number="1", club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    entrees = {
        e["participation_id"]: e
        for e in client.get("/api/v1/club/summary").json()["podiums"]["scratch"]
    }

    assert len(entrees) == 2
    assert entrees[relais.id]["teammate_names"] == ["Jean DUPONT", "Paul MARTIN"]
    assert entrees[individuel.id]["teammate_names"] == []


def test_club_summary_accessible_sans_authentification(client, db_session):
    """FR-006 — pas de cookie de session requis, comme les autres routes de lecture."""
    resp = client.get("/api/v1/club/summary")
    assert resp.status_code == 200


def test_club_summary_federal_only(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="T", prenom="T", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Trail", event_date=date(2026, 5, 16), event_type="trail"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    resp = client.get("/api/v1/club/summary", params={"federal_only": "true"})
    assert resp.json()["roster"] == []


def test_club_roster_rank_renvoie_le_rang(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher",
    )
    db_session.commit()

    resp = client.get(f"/api/v1/club/roster/rank/{ath.id}")

    assert resp.status_code == 200
    assert resp.json() == {"rank": 1, "total": 1}


def test_club_roster_rank_restreint_aux_saisons(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher",
    )
    db_session.commit()

    hors = client.get(f"/api/v1/club/roster/rank/{ath.id}", params={"seasons": "2020"})
    dans = client.get(f"/api/v1/club/roster/rank/{ath.id}", params={"seasons": "2025"})

    assert hors.status_code == 404
    assert dans.json() == {"rank": 1, "total": 1}


def test_club_roster_rank_404_hors_roster(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    db_session.commit()

    resp = client.get(f"/api/v1/club/roster/rank/{ath.id}")

    assert resp.status_code == 404


def _huit_podiums_scratch(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    for jour in range(1, 9):
        course = course_repository.get_or_create(
            db_session, name=f"C{jour}", event_date=date(2026, 5, jour), event_type="triathlon-m"
        )
        participation_repository.create(
            db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
            club="TCN", status="finisher", rank_overall=1,
        )
    db_session.commit()


def test_club_summary_apercu_tronque_chaque_mode_et_garde_les_totaux(client, db_session):
    """#1354 : la page /club n'embarque que l'aperçu, la liste suit au dépliage."""
    _huit_podiums_scratch(db_session)

    body = client.get("/api/v1/club/summary", params={"podiums": "preview"}).json()

    assert len(body["podiums"]["scratch"]) == 6
    assert len(body["podiums"]["all"]) == 6
    assert body["podiums_totals"] == {"scratch": 8, "category": 0, "gender": 0, "all": 8}


def test_club_summary_sans_apercu_rend_tout_comme_avant(client, db_session):
    _huit_podiums_scratch(db_session)

    body = client.get("/api/v1/club/summary").json()

    assert len(body["podiums"]["scratch"]) == 8


def test_club_podiums_rend_la_liste_complete(client, db_session):
    _huit_podiums_scratch(db_session)

    resp = client.get("/api/v1/club/podiums")

    assert resp.status_code == 200
    assert len(resp.json()["scratch"]) == 8


def test_club_summary_counts_the_current_season_licensees_who_raced(client, db_session, monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))
    raced = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice")
    idle = athlete_repository.get_or_create(db_session, nom="B", prenom="Bea")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 10, 4), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=raced.id, course_id=course.id, bib_number="1", club="Triathlon Club Nantais",
    )
    db_session.add_all([
        ClubMember(season=2026, nom="A", prenom="Alice", licence_id="L1", athlete_id=raced.id,
                   link_status=LINK_AUTO, source=SOURCE_FFTRI),
        ClubMember(season=2026, nom="B", prenom="Bea", licence_id="L2", athlete_id=idle.id,
                   link_status=LINK_AUTO, source=SOURCE_FFTRI),
        ClubMember(season=2026, nom="X", prenom="Xavier", licence_id="L3", link_status=LINK_UNLINKED,
                   source=SOURCE_FFTRI),
        ClubMember(season=2025, nom="A", prenom="Alice", licence_id="L4", athlete_id=raced.id,
                   link_status=LINK_AUTO, source=SOURCE_FFTRI),
    ])
    db_session.commit()

    resp = client.get("/api/v1/club/summary")

    assert resp.json()["licensees"] == {"season": 2026, "total": 3, "raced": 1}


def _best_time_result(db_session, event_date):
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Alice", club="TCN")
    athlete.gender = "F"
    course = course_repository.get_or_create(
        db_session, name=f"M {event_date}", event_date=event_date, event_type="triathlon-m"
    )
    participation = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", total_time="02:05:30",
    )
    db_session.commit()
    return participation


def test_club_best_times_response_shape(client, db_session):
    participation = _best_time_result(db_session, date(2026, 5, 16))

    resp = client.get("/api/v1/club/best-times")

    assert resp.status_code == 200
    assert resp.json() == [{
        "participation_id": participation.id,
        "course_id": participation.course_id,
        "athlete_id": participation.athlete_id,
        "athlete_name": "Alice DUPONT",
        "event_name": "M 2026-05-16",
        "event_type": "triathlon-m",
        "event_date": "2026-05-16",
        "gender": "F",
        "total_time": "02:05:30",
    }]


def test_club_best_times_filters_by_season(client, db_session):
    _best_time_result(db_session, date(2026, 5, 16))

    assert len(client.get("/api/v1/club/best-times?season=2025").json()) == 1
    assert client.get("/api/v1/club/best-times?season=2026").json() == []


def test_club_best_times_rejects_an_absurd_season(client, db_session):
    assert client.get("/api/v1/club/best-times?season=1").status_code == 422


def test_last_outing_is_null_without_any_race(client, db_session, monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))

    resp = client.get("/api/v1/club/last-outing")

    assert resp.status_code == 200
    assert resp.json() is None


def test_last_outing_shape(client, db_session, monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 10, 11), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    resp = client.get("/api/v1/club/last-outing?federal_only=true")

    assert resp.status_code == 200
    assert resp.json() == {
        "end_date": "2026-10-11", "events": 1, "athletes": 1, "podiums": 1,
        "courses": [{"id": course.id, "name": "C", "event_type": "triathlon-m", "tcn": 1, "podiums": 1}],
    }


def _two_season_results(db_session):
    for nom, day, rank in (("OLD", date(2026, 5, 10), 1), ("NEW", date(2026, 10, 11), 2)):
        ath = athlete_repository.get_or_create(db_session, nom=nom, prenom="Jean", club="TCN")
        course = course_repository.get_or_create(
            db_session, name=f"C {nom}", event_date=day, event_type="triathlon-m"
        )
        participation_repository.create(
            db_session, athlete_id=ath.id, course_id=course.id, bib_number=nom,
            club="TCN", status="finisher", rank_overall=rank,
        )
    db_session.commit()


def test_club_summary_accepts_seasons(client, db_session):
    _two_season_results(db_session)

    assert len(client.get("/api/v1/club/summary").json()["roster"]) == 2
    only_2025 = client.get("/api/v1/club/summary?seasons=2025").json()
    assert [e["nom"] for e in only_2025["roster"]] == ["OLD"]
    assert len(client.get("/api/v1/club/podiums?seasons=2025").json()["scratch"]) == 1


def test_last_outing_accepts_seasons(client, db_session, monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))
    _two_season_results(db_session)

    assert client.get("/api/v1/club/last-outing").json()["end_date"] == "2026-10-11"
    assert client.get("/api/v1/club/last-outing?seasons=2025").json()["end_date"] == "2026-05-10"


def _total(swim, bike="00:30:00", run="00:20:00"):
    from app.services.mapping import parse_duration

    seconds = sum(parse_duration(value) for value in (swim, bike, run))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _split_row(db_session, course, index, *, club="TCN", swim="00:10:00", bike="00:30:00", run="00:20:00",
               total=None, splits=True):
    athlete = athlete_repository.get_or_create(db_session, nom=f"N{course.id}{index}{club}", prenom="P", club=club)
    return participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=f"{course.id}-{index}-{club}",
        club=club, status="finisher", total_time=total or _total(swim, bike, run),
        splits={"swim": swim, "t1": "00:00:00", "bike": bike, "t2": "00:00:00", "run": run} if splits else None,
    )


def _split_course(db_session, *, provider="klikego", day=16, event_type="triathlon-s"):
    return course_repository.get_or_create(
        db_session, name=f"S{provider}{day}", event_date=date(2026, 5, day), event_type=event_type,
        provider=provider, source_url=f"https://{provider}.example/{day}",
    )


def test_club_split_medians_median_and_sample(client, db_session):
    course = _split_course(db_session)
    for index, swim in enumerate(("00:10:00", "00:12:00", "00:20:00")):
        _split_row(db_session, course, index, swim=swim)
    db_session.commit()

    body = client.get("/api/v1/club/split-medians?event_type=triathlon-s").json()

    assert body == {"event_type": "triathlon-s", "sample": 3, "swim": "00:12:00", "bike": "00:30:00", "run": "00:20:00"}


def test_club_split_medians_ignore_non_club_unreliable_and_incomplete_rows(client, db_session):
    good = _split_course(db_session)
    _split_row(db_session, good, 0)
    _split_row(db_session, good, 1, club="AUTRE", swim="00:30:00")
    _split_row(db_session, good, 2, splits=False)
    unreliable = _split_course(db_session, provider="breizhchrono", day=17)
    _split_row(db_session, unreliable, 0, swim="00:40:00")
    db_session.commit()

    body = client.get("/api/v1/club/split-medians?event_type=triathlon-s").json()

    assert body["sample"] == 1
    assert body["swim"] == "00:10:00"


def test_club_split_medians_exclude_outliers(client, db_session):
    course = _split_course(db_session)
    for index in range(11):
        _split_row(db_session, course, index)
    # Les inters ne couvrent qu'une fraction du total : écart aberrant face à l'épreuve.
    _split_row(db_session, course, 99, swim="00:50:00", bike="00:01:00", run="00:01:00", total="03:00:00")
    db_session.commit()

    body = client.get("/api/v1/club/split-medians?event_type=triathlon-s").json()

    assert body["sample"] == 11
    assert body["swim"] == "00:10:00"


def test_club_split_medians_filter_by_seasons(client, db_session):
    _split_row(db_session, _split_course(db_session), 0)
    db_session.commit()

    assert client.get("/api/v1/club/split-medians?event_type=triathlon-s&seasons=2025").json()["sample"] == 1
    assert client.get("/api/v1/club/split-medians?event_type=triathlon-s&seasons=2026").json()["sample"] == 0


def test_club_split_medians_empty_gives_nulls(client, db_session):
    body = client.get("/api/v1/club/split-medians?event_type=triathlon-s").json()

    assert body == {"event_type": "triathlon-s", "sample": 0, "swim": None, "bike": None, "run": None}


def test_club_split_medians_reference_gap_median_covers_the_whole_course(client, db_session):
    course = _split_course(db_session)
    _split_row(db_session, course, 0)
    _split_row(db_session, course, 1)
    # Ligne cassée du club : les inters dépassent le total (écart négatif).
    _split_row(db_session, course, 2, swim="00:50:00", total="01:00:00")
    for index in range(10, 20):
        _split_row(db_session, course, index, club="AUTRE")
    db_session.commit()

    body = client.get("/api/v1/club/split-medians?event_type=triathlon-s").json()

    assert body["sample"] == 2
    assert body["swim"] == "00:10:00"


def test_course_brief_exposes_whether_splits_are_reliable(db_session):
    from app.schemas.course import CourseBrief

    good = _split_course(db_session)
    unreliable = _split_course(db_session, provider="breizhchrono", day=17)

    assert CourseBrief.model_validate(good).has_reliable_splits is True
    assert CourseBrief.model_validate(unreliable).has_reliable_splits is False
