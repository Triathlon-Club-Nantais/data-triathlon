"""La garde transverse du mot de passe site (#509) : tout, sauf trois
exceptions nommées, exige le cookie `tcn_site_session`.

Inventaire dérivé de l'application, comme `test_public_routes_still_open.py`
— jamais tenu à la main.
"""
import pytest

from app.api.deps import require_site_access
from app.main import app
from app.repositories import user_repository
from app.services import site_access

PREFIXE_AUTH = "/api/v1/auth/"

#: Les trois exceptions nommées (design, § Garde backend).
ROUTES_EXEMPTEES_PREFIXES = ("/api/v1/health", "/api/v1/version", "/api/v1/site-access/", "/api/v1/benevoles/")


def _toutes_les_routes() -> list[tuple[str, str]]:
    return [
        (methode.upper(), chemin)
        for chemin, operations in app.openapi()["paths"].items()
        for methode in operations
        if not chemin.startswith(PREFIXE_AUTH)
    ]


def _routes_gardees_par_le_site() -> list[tuple[str, str]]:
    return [
        (methode, chemin)
        for methode, chemin in _toutes_les_routes()
        if not chemin.startswith(ROUTES_EXEMPTEES_PREFIXES)
    ]


def _chemin_concret(chemin: str) -> str:
    return "/".join(
        "1" if morceau.startswith("{") and morceau.endswith("}") else morceau
        for morceau in chemin.split("/")
    )


@pytest.fixture(autouse=True)
def sans_neutralisation(client):
    """Ce fichier éprouve la vraie garde — retire la neutralisation que
    `conftest.py::client` pose par défaut. Dépend explicitement de `client`
    pour s'exécuter **après** elle : deux fixtures sans lien de dépendance
    n'ont aucun ordre garanti entre elles."""
    app.dependency_overrides.pop(require_site_access, None)
    yield


def test_l_inventaire_n_est_pas_vide():
    assert len(_routes_gardees_par_le_site()) >= 10


@pytest.mark.parametrize(
    ("methode", "chemin"),
    _routes_gardees_par_le_site(),
    ids=lambda v: v.replace("/", "_") if isinstance(v, str) else v,
)
def test_toute_route_gardee_refuse_l_anonyme(client, methode, chemin):
    reponse = client.request(methode, _chemin_concret(chemin), json={})
    assert reponse.status_code == 401, f"{methode} {chemin} répond sans le cookie site"


def test_health_repond_sans_cookie(client):
    assert client.get("/api/v1/health").status_code == 200


def test_version_repond_sans_cookie(client):
    assert client.get("/api/v1/version").status_code == 200


def test_benevoles_session_repond_sans_cookie_site(client):
    """La garde site ne ferme pas la page bénévoles : mauvais mot de passe,
    mais pas 401 « pas de cookie site »."""
    reponse = client.post("/api/v1/benevoles/session", json={"password": "n-importe-quoi"})
    assert reponse.status_code == 401  # refus du mot de passe bénévoles, pas de la garde site
    assert not reponse.cookies


def test_une_route_gardee_repond_normalement_avec_le_cookie(client, db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    config, _ = site_access.replace_password(db_session, password="secret-du-club", admin_user_id=admin.id)
    db_session.commit()

    client.cookies.set(site_access.SITE_SESSION_COOKIE, site_access.sign_session(config.session_secret))

    assert client.get("/api/v1/health").status_code == 200  # santé, jamais gardée
    assert client.get("/api/v1/courses").status_code != 401
