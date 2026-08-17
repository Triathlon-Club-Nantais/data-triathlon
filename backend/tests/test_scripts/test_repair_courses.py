"""Passe A de `scripts/repair_courses.py` — exclusion de la façade live (#432).

Le filtre cherchait `"live.breizhchrono.com"` **dans l'URL entière** : toute URL
portant le jeton ailleurs que comme host (préfixe d'un domaine tiers, query)
était exclue de la réparation sans l'être du scraping. Comparaison stricte
d'hôte désormais ; ces deux tests bornent les deux côtés de la frontière.
"""
from datetime import date

from app.models.course import Course
from app.models.course_source import CourseSource
from scripts import repair_courses

LIVE_URL = "https://live.breizhchrono.com/external/live5/index.jsp?reference=42-7"
USURPATEUR_URL = "https://live.breizhchrono.com.evil.tld/resultats-courses/x-42-7/heat"


def _course(db_session, url: str) -> Course:
    course = Course(
        name="Ancien nom", event_date=date(2025, 1, 1),
        event_type="triathlon-s", is_relay=False,
    )
    db_session.add(course)
    db_session.flush()
    db_session.add(
        CourseSource(course_id=course.id, url=url, provider="breizhchrono", is_active=True)
    )
    db_session.flush()
    return course


def test_la_vraie_facade_live_reste_exclue(db_session, monkeypatch):
    monkeypatch.setattr(
        repair_courses, "_name_from_page",
        lambda url: (_ for _ in ()).throw(AssertionError(f"page requêtée : {url}")),
    )
    _course(db_session, LIVE_URL)

    assert repair_courses.repair_names(db_session, dry_run=True) == 0


def test_un_host_prefixe_par_le_live_n_est_pas_exclu(db_session, monkeypatch):
    monkeypatch.setattr(repair_courses, "_name_from_page", lambda url: "Nom de la page")
    _course(db_session, USURPATEUR_URL)

    assert repair_courses.repair_names(db_session, dry_run=True) == 1
