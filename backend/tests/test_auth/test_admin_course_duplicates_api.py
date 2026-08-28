"""La liste des doublons suspects, côté HTTP (#288).

Le réglage de la détection est éprouvé dans
`tests/test_services/test_course_duplicates.py` ; ici on n'éprouve que la couche
HTTP : la garde, et la forme rendue à l'écran de #292.

Le fichier vit sous `test_auth/` et non `test_api/` : ce dernier ouvre d'office
une session superutilisateur (son `conftest.py`), ce qui rendrait le cas 403
intestable — même motif que `test_admin_batches_api.py`.
"""
from datetime import date

import pytest

from app.core.permissions import P
from app.repositories import course_repository

URL = "/api/v1/admin/courses/duplicates"

MESQUER = (
    "https://resultats.breizhchrono.com/resultats-courses/"
    "triathlon-et-swimrun-mesquer-quimiac-2026-1677015306084-12/triathlon-s-indiv"
)


@pytest.fixture
def mesquer(db_session):
    """Le cas « même URL », celui que #292 présente à part : deux types, une page."""
    for event_type in ("swimrun-s", "triathlon-s"):
        course_repository.get_or_create(
            db_session,
            name="Triathlon et SwimRun Mesquer-Quimiac 2026",
            event_date=date(2026, 6, 13),
            event_type=event_type,
            source_url=MESQUER,
            provider="breizhchrono",
        )
    db_session.commit()


def test_sans_session_la_liste_est_refusee(client):
    assert client.get(URL).status_code == 401


def test_un_autre_pouvoir_ne_donne_pas_acces_a_la_liste(client, ouvrir_session):
    """AC6 — `courses:write` ne suffit pas.

    Corriger le nom d'une épreuve et arbitrer entre deux publications
    concurrentes ne sont pas le même geste : la liste des doublons est la porte
    d'entrée de la fusion, dont l'issue est destructive.
    """
    ouvrir_session(P.COURSES_WRITE)

    assert client.get(URL).status_code == 403


def test_avec_le_pouvoir_la_liste_est_rendue(client, ouvrir_session, mesquer):
    """AC6, versant positif — `courses:sources` ouvre, et rien d'autre n'est requis."""
    ouvrir_session(P.COURSES_SOURCES)

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert len(reponse.json()["candidates"]) == 1


def test_chaque_paire_annonce_son_motif_en_francais(client, ouvrir_session, mesquer):
    """AC4 — le motif est ce qui rend la paire arbitrable sans aller voir ailleurs.

    Deux champs, et non un : `reason` est le code stable sur lequel l'écran
    branche son traitement (#292 réserve un sort particulier au cas « même
    URL »), `reason_label` est la phrase affichée — donc française, comme tout ce
    qui est visible.
    """
    ouvrir_session(P.COURSES_SOURCES)

    (candidat,) = client.get(URL).json()["candidates"]

    assert candidat["reason"] == "same_source_url"
    assert candidat["reason_label"] == "Même URL de source"


def test_une_paire_porte_les_huit_champs_de_chaque_epreuve(
    client, ouvrir_session, mesquer
):
    """La liste doit suffire à décider : rien de ce qui suit n'est un second appel."""
    ouvrir_session(P.COURSES_SOURCES)

    (candidat,) = client.get(URL).json()["candidates"]

    assert [
        {cle: valeur for cle, valeur in course.items() if cle != "id"}
        for course in candidat["courses"]
    ] == [
        {
            "name": "Triathlon et SwimRun Mesquer-Quimiac 2026",
            "event_date": "2026-06-13",
            "event_type": "swimrun-s",
            "is_relay": False,
            "provider": "breizhchrono",
            "source_url": MESQUER,
            "total": 0,
            "tcn_count": 0,
        },
        {
            "name": "Triathlon et SwimRun Mesquer-Quimiac 2026",
            "event_date": "2026-06-13",
            "event_type": "triathlon-s",
            "is_relay": False,
            "provider": "breizhchrono",
            "source_url": MESQUER,
            "total": 0,
            "tcn_count": 0,
        },
    ]


def test_une_base_sans_doublon_rend_une_liste_vide(client, ouvrir_session, db_session):
    """Aucun candidat n'est pas une erreur : c'est l'état souhaité de la base."""
    course_repository.get_or_create(
        db_session,
        name="Triathlon de Vertou - S-Open",
        event_date=date(2026, 5, 3),
        event_type="triathlon-s",
        source_url="https://www.chronosmetron.com/754-triathlon-de-vertou-2026",
        provider="wiclax",
    )
    db_session.commit()
    ouvrir_session(P.COURSES_SOURCES)

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == {"candidates": []}


# --- GET /admin/courses/duplicates/count ------------------------------------

COUNT_URL = "/api/v1/admin/courses/duplicates/count"


def test_sans_session_le_compte_est_refuse(client):
    assert client.get(COUNT_URL).status_code == 401


def test_un_autre_pouvoir_ne_donne_pas_acces_au_compte(client, ouvrir_session):
    ouvrir_session(P.COURSES_WRITE)

    assert client.get(COUNT_URL).status_code == 403


def test_avec_le_pouvoir_le_compte_est_rendu(client, ouvrir_session, mesquer):
    """Même garde et même donnée que la liste : le compte est sa taille."""
    ouvrir_session(P.COURSES_SOURCES)

    reponse = client.get(COUNT_URL)

    assert reponse.status_code == 200
    assert reponse.json() == {"total": 1}


def test_une_base_sans_doublon_rend_un_compte_a_zero(client, ouvrir_session, db_session):
    course_repository.get_or_create(
        db_session,
        name="Triathlon de Vertou - S-Open",
        event_date=date(2026, 5, 3),
        event_type="triathlon-s",
        source_url="https://www.chronosmetron.com/754-triathlon-de-vertou-2026",
        provider="wiclax",
    )
    db_session.commit()
    ouvrir_session(P.COURSES_SOURCES)

    reponse = client.get(COUNT_URL)

    assert reponse.status_code == 200
    assert reponse.json() == {"total": 0}
