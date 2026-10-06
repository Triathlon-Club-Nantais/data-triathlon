"""Licenciés du club publiés par la FFTri sur T2Area (#1202).

La page club porte un bloc JSON-LD `SportsTeam` dont `member[]` liste les
licenciés de la saison en cours : `name` « NOM Prénom », `gender`
(`Female`/`Male`), `identifier` (numéro de licence). L'année de licence n'y
figure pas : elle se lit sur chaque carte, « Membre · 2027 ».

Ce n'est pas un fournisseur de résultats : le module n'est pas inscrit au
registre et n'expose pas `scrape_event_all`.
"""
import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from app.core import http
from app.core.gender import normalize_gender

from .utils import DEFAULT_HEADERS

CLUB_URL = "https://fftri.t2area.com/clubs/triathlon-club-nantais.html"

_LICENCE_YEAR = re.compile(r"Membre\s*·\s*(\d{4})")


@dataclass(frozen=True)
class RosterMember:
    nom: str
    prenom: str
    gender: str
    licence_id: str | None


@dataclass(frozen=True)
class ClubRoster:
    licence_year: int
    members: list[RosterMember]


class RosterUnreadableError(Exception):
    """La page ne se lit plus comme mesuré le 2026-10-06."""


def split_name(full: str) -> tuple[str, str]:
    """Le nom est la suite de mots en capitales qui ouvre le libellé, le prénom le reste.

    « BELBEOC H Victor » garde « BELBEOC H » : la clé d'identité ignore
    l'espace et rejoint « BELBEOC'H » des classements. Le dernier mot reste
    toujours au prénom, même en capitales (« DUPONT JEAN »).
    """
    words = full.split()
    cut = 0
    while cut < len(words) - 1 and words[cut].isupper():
        cut += 1
    if cut == 0:
        return " ".join(words), ""
    return " ".join(words[:cut]), " ".join(words[cut:])


def _team(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "SportsTeam":
            return data
    raise RosterUnreadableError("bloc JSON-LD SportsTeam introuvable")


def parse_club_roster(html: str) -> ClubRoster:
    soup = BeautifulSoup(html, "lxml")
    team = _team(soup)
    years = {int(year) for year in _LICENCE_YEAR.findall(soup.get_text(" "))}
    if len(years) != 1:
        raise RosterUnreadableError(f"année de licence illisible : {sorted(years)}")
    members = []
    for person in team.get("member") or []:
        nom, prenom = split_name(person.get("name") or "")
        if not nom:
            continue
        members.append(RosterMember(
            nom=nom,
            prenom=prenom,
            gender=normalize_gender(person.get("gender")),
            licence_id=(person.get("identifier") or "").strip() or None,
        ))
    # Une liste vide viderait la saison à la synchro : refusée comme illisible.
    if not members:
        raise RosterUnreadableError("aucun licencié lu")
    return ClubRoster(licence_year=years.pop(), members=members)


def fetch_club_roster(url: str) -> ClubRoster:
    with http.client(timeout=30, headers=DEFAULT_HEADERS) as client:
        response = client.get(url)
        response.raise_for_status()
    return parse_club_roster(response.text)
