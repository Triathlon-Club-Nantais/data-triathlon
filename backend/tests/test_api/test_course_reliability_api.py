"""`PATCH /admin/courses/{id}/reliability` — trancher la fiabilité à la main (#115).

Ce fichier vit sous `tests/test_api/`, donc sous la session de saisie du
`conftest` local. Les tests de **refus** y ouvrent leur propre session, plus
étroite, et écrasent le cookie posé par la fixture.
"""
import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.course import Course
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    course_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import session as session_service


@pytest.fixture
def epreuve_douteuse(db_session) -> Course:
    course = Course(
        name="Épreuve douteuse",
        event_type="triathlon-m",
        is_reliable_computed=False,
        quality_issues={"rank_gap": 3},
    )
    db_session.add(course)
    db_session.commit()
    return course


def _session_etroite(client, db_session, *codes):
    """Remplace la session large du conftest par une session à pouvoirs comptés."""
    organisation = db_session.query(Organisation).first()
    user = user_repository.create(db_session, email="etroit@exemple.fr")
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="etroit", name="Étroit")
        for code in codes:
            role.permissions.append(RolePermission(permission_code=str(code)))
        db_session.flush()
        user_role_repository.grant(
            db_session,
            user_id=user.id,
            role_id=role.id,
            organisation_id=organisation.id,
        )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


def test_declarer_une_epreuve_fiable_rend_les_trois_champs(client, epreuve_douteuse):
    """Les trois valeurs sont rendues **délibérément**.

    « La machine a relevé trois trous de classement et doute ; un humain a
    tranché que l'épreuve est fiable » : c'est ce qu'une interface de revue doit
    montrer, et ce qu'une valeur unique rendrait indicible.
    """
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True},
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["is_reliable"] is True
    assert corps["is_reliable_computed"] is False
    assert corps["reliability_override"] is True
    assert corps["quality_issues"] == {"rank_gap": 3}


def test_declarer_une_epreuve_douteuse(client, db_session):
    course = Course(name="Épreuve", event_type="triathlon-m", is_reliable_computed=True)
    db_session.add(course)
    db_session.commit()

    corps = client.patch(
        f"/api/v1/admin/courses/{course.id}/reliability",
        json={"reliability_override": False},
    ).json()

    assert (corps["is_reliable"], corps["is_reliable_computed"]) == (False, True)


def test_lever_l_avis_humain_rend_le_verdict_calcule(client, epreuve_douteuse):
    client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True},
    )

    corps = client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": None},
    ).json()

    assert corps["reliability_override"] is None
    assert corps["is_reliable"] is False


def test_une_epreuve_inconnue_rend_404(client):
    assert (
        client.patch(
            "/api/v1/admin/courses/9999/reliability",
            json={"reliability_override": True},
        ).status_code
        == 404
    )


def test_sans_session_la_ressource_rend_401(client, db_session, epreuve_douteuse):
    client.cookies.clear()

    assert (
        client.patch(
            f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
            json={"reliability_override": True},
        ).status_code
        == 401
    )


def test_sans_le_pouvoir_de_qualite_la_ressource_rend_403(
    client, db_session, epreuve_douteuse
):
    _session_etroite(client, db_session, P.ROLES_READ)

    assert (
        client.patch(
            f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
            json={"reliability_override": True},
        ).status_code
        == 403
    )


def test_deux_roles_ont_bien_deux_perimetres_differents(
    client, db_session, epreuve_douteuse
):
    """La démonstration produite par la feature : un validateur **valide**, et
    rien d'autre. Sans elle, « rôle » ne serait qu'un mot sur un écran."""
    _session_etroite(client, db_session, P.QUALITY_OVERRIDE)

    arbitrage = client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True},
    )
    utilisateurs = client.get("/api/v1/admin/users")
    signalement = client.delete("/api/v1/admin/pending-providers/1")

    assert arbitrage.status_code == 200
    assert utilisateurs.status_code == 403
    assert signalement.status_code == 403


def test_un_reimport_n_ecrase_pas_l_avis_humain(client, db_session, epreuve_douteuse):
    """FR-037 — et ce test **constate l'absence de garde**, il n'en éprouve aucune.

    Les deux chemins d'écriture ne se croisent pas : l'import écrit sa colonne,
    toujours et sans condition. C'est la forme du modèle qui le tient.
    """
    client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True},
    )

    course_repository.set_quality(
        db_session,
        epreuve_douteuse,
        is_reliable_computed=False,
        quality_issues={"rank_gap": 12},
    )
    db_session.commit()

    corps = client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True},
    ).json()
    assert corps["reliability_override"] is True
    assert corps["is_reliable"] is True
    assert corps["quality_issues"] == {"rank_gap": 12}, "l'import a bien réécrit le reste"


def test_le_contrat_public_expose_toujours_is_reliable_et_lui_seul(
    client, db_session, epreuve_douteuse
):
    """FR-038 — `CourseBrief` ne change pas d'une ligne.

    `from_attributes=True` lit une propriété comme une colonne ; les deux champs
    internes n'apparaissent **que** sur la ressource de revue.
    """
    client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True},
    )

    # `GET /courses/{id}` rend une page paginée dont l'épreuve est une clé (#163).
    detail = client.get(f"/api/v1/courses/{epreuve_douteuse.id}").json()["course"]
    liste = client.get("/api/v1/courses").json()

    assert detail["is_reliable"] is True, "l'avis humain traverse le contrat public"
    assert "is_reliable_computed" not in detail
    assert "reliability_override" not in detail
    ligne = next(c for c in liste if c["id"] == epreuve_douteuse.id)
    assert ligne["is_reliable"] is True
    assert "reliability_override" not in ligne
