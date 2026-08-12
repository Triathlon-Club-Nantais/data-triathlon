"""Contrat de `GET /courses/{id}/sources` — la liste publique des sources (#284).

Elle sert la décision **D4** : les sources d'une épreuve sont visibles de tous.
Deux propriétés portent tout le fichier.

**L'ordre est un contrat, pas un hasard.** L'active en tête, puis les passives
par âge : c'est ce que rend `course_source_repository.list_for_course`, et c'est
ce qui empêche la source affichée de sauter d'un rechargement à l'autre.

**La réponse ne nomme jamais qui a soumis l'URL.** `created_by_user_id` et
`created_by` sont des données internes ; une route publique n'a aucune raison de
les publier. C'est le genre de champ qu'un `from_attributes` ramènerait sans
qu'on le demande, d'où un test qui fige l'ensemble **exact** des clés.

**Sur la session.** Le conftest de ce dossier ouvre une session comme raccourci
de peuplement, et son en-tête interdit de s'en servir pour établir qu'une route
est ouverte. Le test d'ouverture ci-dessous ne s'y appuie donc pas : il **vide
les cookies** avant d'appeler. Il complète — sans le remplacer — le filet
d'inventaire de `tests/test_auth/test_public_routes_still_open.py`, qui classe
automatiquement toute route nouvelle hors `/admin/` mais n'exige d'elle qu'un
statut hors 401/403, là où D4 promet ici un 200.
"""
from datetime import date, datetime

import pytest

from app.models.course_source import CourseSource
from app.repositories import course_repository

ACTIVE_URL = "https://www.klikego.com/resultats/mesquer-2026"
OLDEST_PASSIVE_URL = "https://www.breizhchrono.com/resultats/mesquer-2026"
NEWEST_PASSIVE_URL = "https://www.protiming.fr/resultats/mesquer-2026"


@pytest.fixture
def epreuve_a_trois_sources(db_session):
    """Trois sources dont une active, et l'active est la **plus récente**.

    L'âge et l'activité sont mis en opposition volontairement : un tri par
    `created_at` seul rendrait l'active en dernier, et le test ne verrait pas la
    différence si les deux critères pointaient dans le même sens.
    """
    course = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-m",
    )
    db_session.add_all(
        [
            CourseSource(
                course_id=course.id,
                url=NEWEST_PASSIVE_URL,
                provider="prolivesport",
                is_active=False,
                created_at=datetime(2026, 1, 3, 12, 0),
            ),
            CourseSource(
                course_id=course.id,
                url=ACTIVE_URL,
                provider="klikego",
                is_active=True,
                created_at=datetime(2026, 1, 5, 12, 0),
                last_scraped_at=datetime(2026, 5, 17, 8, 30),
            ),
            CourseSource(
                course_id=course.id,
                url=OLDEST_PASSIVE_URL,
                provider="breizhchrono",
                is_active=False,
                created_at=datetime(2026, 1, 2, 12, 0),
            ),
        ]
    )
    db_session.commit()
    return course


def test_the_active_source_leads_then_the_passive_ones_by_age(
    client, epreuve_a_trois_sources
):
    """AC1 — l'ordre publié est celui de `list_for_course`, pas celui de l'insertion."""
    body = client.get(f"/api/v1/courses/{epreuve_a_trois_sources.id}/sources").json()

    assert [source["url"] for source in body] == [
        ACTIVE_URL,
        OLDEST_PASSIVE_URL,
        NEWEST_PASSIVE_URL,
    ]
    assert [source["is_active"] for source in body] == [True, False, False]
    assert body[0]["provider"] == "klikego"
    assert body[0]["last_scraped_at"] == "2026-05-17T08:30:00"
    # Une passive n'a jamais été scrapée : le champ existe et vaut `null`.
    assert body[1]["last_scraped_at"] is None


def test_the_list_is_served_without_a_session(client, epreuve_a_trois_sources):
    """AC1 — D4 : la liste est visible de tous, y compris d'un visiteur anonyme."""
    client.cookies.clear()

    reponse = client.get(f"/api/v1/courses/{epreuve_a_trois_sources.id}/sources")

    assert not client.cookies, "le test doit passer sans le moindre cookie"
    assert reponse.status_code == 200
    assert len(reponse.json()) == 3


def test_an_unknown_course_is_a_not_found(client):
    """AC2 — même patron que `/courses/{id}` et `/courses/{id}/summary`."""
    reponse = client.get("/api/v1/courses/999999/sources")

    assert reponse.status_code == 404
    assert reponse.json() == {"detail": "Course introuvable"}


def test_a_course_without_any_source_answers_with_an_empty_list(client, db_session):
    """AC3 — une épreuve saisie à la main n'a aucune source, ce n'est pas une erreur."""
    course = course_repository.get_or_create(
        db_session, name="Triathlon manuel", event_date=date(2026, 6, 1),
        event_type="triathlon-s",
    )
    db_session.commit()

    reponse = client.get(f"/api/v1/courses/{course.id}/sources")

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_the_response_never_names_who_submitted_the_url(
    client, db_session, epreuve_a_trois_sources
):
    """AC4 — l'ensemble des clés est figé, pas seulement l'absence de `created_by`.

    Le champ est **peuplé en base** avant l'appel : une assertion d'absence sur
    une colonne nulle passerait pour la mauvaise raison.
    """
    source = db_session.query(CourseSource).filter_by(url=ACTIVE_URL).one()
    source.created_by_user_id = 1  # l'utilisateur du conftest de ce dossier
    db_session.commit()

    body = client.get(f"/api/v1/courses/{epreuve_a_trois_sources.id}/sources").json()

    for source in body:
        assert set(source) == {"id", "url", "provider", "is_active", "last_scraped_at"}
