"""Liste des licenciés publiée par la FFTri sur T2Area (#1202)."""
from pathlib import Path

import httpx
import pytest

from app.scrapers import fftri_club_members
from app.scrapers.fftri_club_members import (
    CLUB_URL,
    RosterMember,
    RosterUnreadableError,
    parse_club_roster,
    split_name,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fftri_club_members.html"


def test_parse_reads_the_licence_year_and_every_member():
    roster = parse_club_roster(FIXTURE.read_text(encoding="utf-8"))

    assert roster.licence_year == 2027
    assert roster.members == [
        RosterMember("MARTIN", "Anne sophie", "F", "C00001"),
        RosterMember("KERBRAT H", "Victor", "M", "C00002"),
        RosterMember("DURAND VIALAR", "Albane", "F", "C00003"),
        RosterMember("LE GOFF", "Loan", "M", "C00004"),
    ]


@pytest.mark.parametrize(
    ("full", "expected"),
    [
        ("ABOT Anne sophie", ("ABOT", "Anne sophie")),
        ("BELBEOC H Victor", ("BELBEOC H", "Victor")),
        ("BOURGAIN  VIALAR Albane", ("BOURGAIN VIALAR", "Albane")),
        ("L AOT Sebastien", ("L AOT", "Sebastien")),
        ("DUPONT JEAN", ("DUPONT", "JEAN")),
        ("Inconnu", ("Inconnu", "")),
        ("", ("", "")),
    ],
)
def test_split_name_takes_the_leading_upper_case_run_as_last_name(full, expected):
    assert split_name(full) == expected


def test_a_page_without_the_json_ld_team_is_unreadable():
    with pytest.raises(RosterUnreadableError):
        parse_club_roster("<html><body>Membre · 2027</body></html>")


def test_a_page_without_licence_year_is_unreadable():
    html = FIXTURE.read_text(encoding="utf-8").replace("2027", "")
    with pytest.raises(RosterUnreadableError):
        parse_club_roster(html)


def test_a_page_with_two_licence_years_is_unreadable():
    html = FIXTURE.read_text(encoding="utf-8").replace("</body>", "<span>Membre · 2026</span></body>")
    with pytest.raises(RosterUnreadableError):
        parse_club_roster(html)


def test_an_empty_roster_is_unreadable_rather_than_an_empty_season():
    # La synchro ne doit jamais vider une saison.
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type": "SportsTeam", "member": []}</script></head>'
        "<body><span>Membre · 2027</span></body></html>"
    )
    with pytest.raises(RosterUnreadableError):
        parse_club_roster(html)


def test_fetch_reads_the_page_through_the_app_http_client(monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=html)

    monkeypatch.setattr(
        fftri_club_members.http, "client",
        lambda **_: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert fftri_club_members.fetch_club_roster(CLUB_URL).licence_year == 2027
    assert seen == [CLUB_URL]
