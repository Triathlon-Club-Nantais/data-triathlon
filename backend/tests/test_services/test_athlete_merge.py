"""Admin merge of two records of one person (#908, #907, epic #1146)."""
from datetime import date

import pytest

from app.core.exceptions import DomainError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.athlete_alias import AthleteAlias
from app.models.challenge import ChallengeResult
from app.models.club_member import LINK_AUTO, SOURCE_FFTRI, ClubMember
from app.models.participation import Participation
from app.models.season_validation import SeasonValidation
from app.models.volunteer_action import VolunteerAction
from app.repositories import (
    athlete_known_club_repository,
    challenge_repository,
    course_repository,
    ignored_athlete_pair_repository,
    participation_repository,
    season_validation_repository,
    user_repository,
    volunteer_action_repository,
)
from app.services import athlete_merge


def _course(db, name: str, *, is_relay: bool = False):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m", is_relay=is_relay
    )


def _result(db, athlete: Athlete, course, bib: str) -> Participation:
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=bib, status="finisher"
    )


def _athlete(db, nom: str, prenom: str, **fields) -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom, **fields)
    db.add(athlete)
    db.flush()
    return athlete


@pytest.fixture
def admin(db_session_fk):
    return user_repository.create(db_session_fk, email="admin@exemple.fr")


def test_a_merge_moves_every_reference_and_deletes_the_absorbed_record(db_session_fk, admin):
    db = db_session_fk
    kept, absorbed = _athlete(db, "DUPONT", "Jean"), _athlete(db, "DUPOMT", "Jean")
    result = _result(db, absorbed, _course(db, "Tri A"), "1")
    relay = _result(db, _athlete(db, "AUTRE", "Equipier"), _course(db, "Relais", is_relay=True), "9")
    participation_repository.replace_teammates(db, relay, [relay.athlete_id, absorbed.id])
    volunteer_action_repository.create_pending(
        db, athlete_id=absorbed.id, season=2026, declared_by_user_id=None, title="Ravito", description=""
    )
    season_validation_repository.create(db, athlete_id=absorbed.id, season=2025, validated_by_user_id=admin.id)
    member = user_repository.create(db, email="jean@exemple.fr")
    member.athlete_id = absorbed.id
    db.flush()

    athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert db.get(Athlete, absorbed.id) is None
    assert db.get(Participation, result.id).athlete_id == kept.id
    assert sorted(link.athlete_id for link in relay.teammate_links) == sorted([relay.athlete_id, kept.id])
    assert db.query(VolunteerAction).one().athlete_id == kept.id
    assert db.query(SeasonValidation).one().athlete_id == kept.id
    assert member.athlete_id == kept.id


def test_a_season_validated_on_both_records_keeps_one_validation(db_session_fk, admin):
    db = db_session_fk
    kept, absorbed = _athlete(db, "DUPONT", "Jean"), _athlete(db, "DUPOMT", "Jean")
    season_validation_repository.create(db, athlete_id=kept.id, season=2026, validated_by_user_id=admin.id)
    season_validation_repository.create(db, athlete_id=absorbed.id, season=2026, validated_by_user_id=admin.id)
    season_validation_repository.create(db, athlete_id=absorbed.id, season=2025, validated_by_user_id=admin.id)

    athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert sorted((v.athlete_id, v.season) for v in db.query(SeasonValidation)) == [
        (kept.id, 2025), (kept.id, 2026)
    ]


def test_the_kept_record_takes_what_it_lacks_from_the_absorbed_one(db_session_fk, admin):
    db = db_session_fk
    kept = _athlete(db, "DUPONT", "Jean", club="CLUB IMPORT")
    absorbed = _athlete(
        db, "DUPOMT", "Jean", club="Triathlon Club Nantais", club_locked=True, gender="M", birth_date=date(1990, 1, 1)
    )

    athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert (kept.club, kept.club_locked, kept.gender, kept.birth_date) == (
        "Triathlon Club Nantais", True, "M", date(1990, 1, 1)
    )


def test_a_merge_remembers_the_absorbed_spelling_as_a_variant(db_session_fk, admin):
    db = db_session_fk
    kept, absorbed = _athlete(db, "DUPONT", "Jean"), _athlete(db, "DUPOMT", "Jean")
    older = _athlete(db, "DUPONTT", "Jean")
    athlete_merge.merge_athletes(db, kept_id=absorbed.id, absorbed_id=older.id, user_id=admin.id)

    athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert sorted((a.last_name_key, a.athlete_id) for a in db.query(AthleteAlias)) == [
        ("dupomt", kept.id), ("dupontt", kept.id)
    ]


def test_merging_a_homonym_into_its_principal_keeps_rank_zero(db_session_fk, admin):
    db = db_session_fk
    principal = _athlete(db, "MARTIN", "Thomas")
    homonym = _athlete(db, "MARTIN", "Thomas", homonym_rank=1)

    athlete_merge.merge_athletes(db, kept_id=homonym.id, absorbed_id=principal.id, user_id=admin.id)

    assert homonym.homonym_rank == 0
    assert db.query(AthleteAlias).count() == 0


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("same", "same_athlete"),
        ("users", "distinct_users"),
        ("bibs", "same_course_bibs"),
        ("relay", "same_participation"),
        ("birth", "distinct_birth_dates"),
        ("team", "team_and_person"),
    ],
)
def test_a_refused_merge_writes_nothing(db_session_fk, admin, setup, reason):
    db = db_session_fk
    kept, absorbed = _athlete(db, "DUPONT", "Jean"), _athlete(db, "DUPOMT", "Jean")
    absorbed_id = kept.id if setup == "same" else absorbed.id
    if setup == "users":
        for athlete, email in [(kept, "a@x.fr"), (absorbed, "b@x.fr")]:
            user_repository.create(db, email=email).athlete_id = athlete.id
    if setup == "bibs":
        course = _course(db, "Tri A")
        _result(db, kept, course, "1")
        _result(db, absorbed, course, "2")
    if setup == "relay":
        relay = _result(db, kept, _course(db, "Relais", is_relay=True), "9")
        participation_repository.replace_teammates(db, relay, [kept.id, absorbed.id])
    if setup == "birth":
        kept.birth_date, absorbed.birth_date = date(1990, 1, 1), date(1991, 1, 1)
    if setup == "team":
        absorbed.nom, absorbed.prenom = "DUPONT", "& JEAN"
    db.flush()

    impact = athlete_merge.merge_impact(db, kept_id=kept.id, absorbed_id=absorbed_id)
    with pytest.raises(DomainError) as refused:
        athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=absorbed_id, user_id=admin.id)

    assert impact["blocking_reason"] == reason and impact["blocking_label"]
    assert (refused.value.status_code, refused.value.code) == (409, reason)
    assert db.get(Athlete, absorbed.id) is not None
    assert db.query(AdminActionLog).count() == 0


def test_a_person_never_merges_into_a_team_record(db_session_fk, admin):
    """#1192 : la reprise des doublons a versé « ARNAUD & VINCENT » dans ARNAUD Vincent."""
    team, person = _athlete(db_session_fk, "ARNAUD", "& VINCENT ."), _athlete(db_session_fk, "ARNAUD", "Vincent")

    with pytest.raises(DomainError) as refused:
        athlete_merge.merge_athletes(db_session_fk, kept_id=team.id, absorbed_id=person.id, user_id=admin.id)

    assert refused.value.code == "team_and_person"


def test_two_spellings_of_one_team_still_merge(db_session_fk, admin):
    kept = _athlete(db_session_fk, "ARNAUD", "& VINCENT .")
    absorbed = _athlete(db_session_fk, "ARNAUD /", "VINCENT", homonym_rank=1)

    assert athlete_merge.merge_impact(db_session_fk, kept_id=kept.id, absorbed_id=absorbed.id)["blocking_reason"] is None


def test_a_merge_with_an_unknown_record_is_a_404(db_session_fk, admin):
    kept = _athlete(db_session_fk, "DUPONT", "Jean")

    with pytest.raises(NotFoundError):
        athlete_merge.merge_athletes(db_session_fk, kept_id=kept.id, absorbed_id=999, user_id=admin.id)


def test_the_merge_is_logged_once_without_birth_date(db_session_fk, admin):
    db = db_session_fk
    kept = _athlete(db, "DUPONT", "Jean")
    absorbed = _athlete(db, "DUPOMT", "Jean", birth_date=date(1990, 1, 1), club="TCN")
    _result(db, absorbed, _course(db, "Tri A"), "1")

    athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    [entry] = db.query(AdminActionLog).all()
    assert (entry.action, entry.entity_type, entry.entity_id) == ("athlete.merge", "athlete", kept.id)
    assert entry.payload["absorbed"] == {"id": absorbed.id, "nom": "DUPOMT", "prenom": "Jean", "club": "TCN"}
    assert entry.payload["moved"]["participations"] == 1
    assert entry.payload["alias_added"] is True
    assert "birth_date" not in str(entry.payload)


def test_the_impact_announces_what_the_merge_does(db_session_fk, admin):
    db = db_session_fk
    kept, absorbed = _athlete(db, "DUPONT", "Jean"), _athlete(db, "DUPOMT", "Jean")
    _result(db, absorbed, _course(db, "Tri A"), "1")
    season_validation_repository.create(db, athlete_id=absorbed.id, season=2025, validated_by_user_id=admin.id)

    impact = athlete_merge.merge_impact(db, kept_id=kept.id, absorbed_id=absorbed.id)

    assert impact["moves"] == {
        "participations": 1, "teammates": 0, "volunteer_actions": 0, "season_validations": 1, "users": 0
    }
    assert (impact["alias_added"], impact["blocking_reason"]) == (True, None)
    assert db.get(Athlete, absorbed.id) is not None


def test_a_homonym_spelling_is_never_recorded_as_a_variant(db_session_fk, admin):
    """Un homonyme distingué n'est jamais visé par l'import : sa clé, portée par une
    autre personne, ne doit pas devenir une variante de la fiche conservée."""
    db = db_session_fk
    kept = _athlete(db, "DURAND", "Paul")
    _athlete(db, "MARTIN", "Luc")
    homonym = _athlete(db, "MARTIN", "Luc", homonym_rank=1)

    athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=homonym.id, user_id=admin.id)

    assert db.query(AthleteAlias).count() == 0


def test_a_record_without_identity_merges_into_a_homonym_without_error(db_session_fk, admin):
    db = db_session_fk
    _athlete(db, "DUPONT", "Jean")
    homonym = _athlete(db, "DUPONT", "Jean", homonym_rank=1)
    nameless = _athlete(db, "?", "")

    athlete_merge.merge_athletes(db, kept_id=homonym.id, absorbed_id=nameless.id, user_id=admin.id)

    assert homonym.homonym_rank == 1
    assert db.query(AthleteAlias).count() == 0


def test_a_pair_set_aside_follows_the_absorbed_record(db_session_fk, admin):
    """Un admin a jugé l'absorbée distincte d'une autre fiche : la fiche conservée hérite
    de ce jugement, sans quoi la revue et la reprise rouvriraient la paire."""
    kept = _athlete(db_session_fk, "DUPONT", "Jean")
    absorbed = _athlete(db_session_fk, "DUPONT", "Jéan", homonym_rank=1)
    other = _athlete(db_session_fk, "JEAN", "Dupont")
    already = _athlete(db_session_fk, "DUPOND", "Jean")
    for first, second in [(absorbed, other), (absorbed, kept), (absorbed, already), (kept, already)]:
        ignored_athlete_pair_repository.create(
            db_session_fk, athlete_id_a=first.id, athlete_id_b=second.id, user_id=admin.id
        )
    db_session_fk.flush()

    athlete_merge.merge_athletes(db_session_fk, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert ignored_athlete_pair_repository.all_pairs(db_session_fk) == {
        ignored_athlete_pair_repository.normalized(kept.id, other.id),
        ignored_athlete_pair_repository.normalized(kept.id, already.id),
    }


def test_a_merge_moves_challenge_rows_to_the_kept_record(db_session_fk, admin):
    db = db_session_fk
    kept = _athlete(db, "DUPONT", "Jean")
    absorbed = _athlete(db, "DUPOND", "Jean")
    challenge = challenge_repository.upsert(db, name="C", event_date=date(2026, 5, 16), source_url="u")
    challenge_repository.upsert_result(
        db, challenge, athlete_id=absorbed.id, bib_number="1", rank_overall=1, rank_gender=None,
        rank_category=None, total_time="06:50:33", status="finisher", raw_data={},
    )

    athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert db.query(ChallengeResult).one().athlete_id == kept.id


def test_a_merge_keeps_the_licence_link(db_session_fk):
    db = db_session_fk
    kept, absorbed = _athlete(db, "DUPONT", "Jean"), _athlete(db, "DUPOMT", "Jean")
    member = ClubMember(
        season=2026, licence_id="C1", nom="DUPOMT", prenom="Jean", athlete_id=absorbed.id,
        link_status=LINK_AUTO, source=SOURCE_FFTRI,
    )
    db.add(member)
    db.flush()
    admin = user_repository.create(db, email="admin2@exemple.fr")

    athlete_merge.merge_athletes(db, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    db.refresh(member)
    assert member.athlete_id == kept.id


def test_a_merge_carries_the_confirmed_clubs(db_session_fk, admin):
    kept = _athlete(db_session_fk, "MARTIN", "Thomas")
    absorbed = _athlete(db_session_fk, "MARTIN", "Tom")
    athlete_known_club_repository.add(db_session_fk, athlete_id=absorbed.id, club_key="asptt", user_id=None)

    athlete_merge.merge_athletes(db_session_fk, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert athlete_known_club_repository.keys_by_athlete(db_session_fk) == {kept.id: {"asptt"}}
