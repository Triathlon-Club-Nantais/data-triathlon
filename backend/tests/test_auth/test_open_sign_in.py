"""Open sign-in (#1322): landing page, `is_member` on `/auth/me`, no power without a role."""
import pytest

from app.core.config import get_settings
from app.core.season import season_of
from app.core.time import utcnow
from app.models.member_email import MemberEmail
from app.models.role import Role
from app.repositories import allowed_email_repository
from app.services.auth import state
from app.services.auth.idp.base import ExternalIdentity

from .conftest import ADRESSE_AUTORISEE


def _sign_in(client, email=ADRESSE_AUTORISEE, doublure=None):
    if doublure is not None:
        doublure.identite = ExternalIdentity(
            provider=doublure.slug, subject=email, email=email, email_verified=True
        )
    client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    from app.api.v1.auth import state_cookie_name

    charge = state.read(client.cookies[state_cookie_name(get_settings())])
    return client.get(
        f"/api/v1/auth/doublure/callback?code=c&state={charge.state}", follow_redirects=False
    )


def test_an_account_without_role_lands_on_the_public_site(client, doublure):
    reponse = _sign_in(client)

    assert reponse.headers["location"] == f"{get_settings().auth_redirect_base_url}/"


def test_an_administrator_lands_on_the_back_office(client, doublure, db_session, organisation):
    role = Role(slug="admin-test", name="Admin", is_superuser=True, organisation_id=organisation.id)
    db_session.add(role)
    db_session.flush()
    entree = allowed_email_repository.get_by_email(db_session, ADRESSE_AUTORISEE)
    allowed_email_repository.set_initial_role(db_session, entree, role_id=role.id)
    db_session.commit()

    reponse = _sign_in(client)

    assert reponse.headers["location"] == f"{get_settings().auth_redirect_base_url}/admin"


def test_me_exposes_the_member_status(client, doublure, db_session):
    db_session.add(MemberEmail(email="adherent@exemple.fr", season=season_of(utcnow().date()), source="import"))
    db_session.commit()

    _sign_in(client, "adherent@exemple.fr", doublure)
    assert client.get("/api/v1/auth/me").json()["is_member"] is True


def test_me_reports_a_non_member(client, doublure):
    _sign_in(client, "visiteur@exemple.fr", doublure)
    corps = client.get("/api/v1/auth/me").json()

    assert corps["is_member"] is False
    assert corps["can_administer"] is False


@pytest.mark.parametrize(
    "chemin",
    ["/api/v1/admin/roles", "/api/v1/admin/allowed-emails", "/api/v1/admin/member-emails"],
)
def test_an_account_without_role_gets_403_on_guarded_routes(client, doublure, chemin):
    """FR-015: signing in grants nothing; every power-guarded route refuses."""
    _sign_in(client, "visiteur@exemple.fr", doublure)

    assert client.get(chemin).status_code == 403
