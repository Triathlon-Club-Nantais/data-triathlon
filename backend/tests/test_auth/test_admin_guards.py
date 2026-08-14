"""Les trois issues de chaque ressource fermée par #115 (SC-003, SC-004).

401 anonyme, 403 connecté sans le pouvoir, succès avec. Sur les **trois**
routes que la feature ferme encore aujourd'hui — `GET`/`DELETE
/admin/pending-providers` et `DELETE /participations/{id}`.

`POST /participations` a rejoint ce lot un temps (#115), puis en est ressortie
(#270) : la mise en quarantaine du résultat créé (`is_pending_validation`)
protège désormais l'intégrité des agrégats publics à la place d'une session —
voir `test_creer_un_resultat_reste_public` plus bas.
"""
import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.organisation import Organisation
from app.models.participation import Participation
from app.models.pending_provider import PendingProvider
from app.models.role_permission import RolePermission
from app.repositories import role_repository, user_repository, user_role_repository
from app.services.auth import session as session_service


@pytest.fixture
def organisation(db_session) -> Organisation:
    ligne = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db_session.add(ligne)
    db_session.flush()
    return ligne


def connecte(client, db_session, organisation, *codes, email="a@exemple.fr"):
    """Ouvre une session pour un utilisateur portant exactement ces pouvoirs."""
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="role-test", name="Rôle de test")
        for code in codes:
            role.permissions.append(RolePermission(permission_code=code))
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


@pytest.fixture
def signalement(db_session) -> PendingProvider:
    entree = PendingProvider(url="https://inconnu.example/x", provider_hint="inconnu")
    db_session.add(entree)
    db_session.commit()
    return entree


@pytest.fixture
def participation(db_session) -> Participation:
    course = Course(name="Épreuve", event_type="triathlon-m")
    athlete = Athlete(nom="NOM", prenom="Prénom")
    db_session.add_all([course, athlete])
    db_session.flush()
    ligne = Participation(course_id=course.id, athlete_id=athlete.id, bib_number="1")
    db_session.add(ligne)
    db_session.commit()
    return ligne


# --- GET /admin/pending-providers ------------------------------------------


def test_lister_les_signalements_sans_session_rend_401(client, signalement):
    assert client.get("/api/v1/admin/pending-providers").status_code == 401


def test_lister_les_signalements_sans_le_pouvoir_rend_403(
    client, db_session, organisation, signalement
):
    connecte(client, db_session, organisation)

    assert client.get("/api/v1/admin/pending-providers").status_code == 403


def test_lister_les_signalements_avec_le_pouvoir_rend_la_liste(
    client, db_session, organisation, signalement
):
    connecte(client, db_session, organisation, P.PENDING_PROVIDERS_READ.code)

    reponse = client.get("/api/v1/admin/pending-providers")

    assert reponse.status_code == 200
    assert [ligne["url"] for ligne in reponse.json()] == [signalement.url]


# --- DELETE /admin/pending-providers/{id} ----------------------------------


def test_instruire_un_signalement_sans_session_rend_401(client, signalement):
    reponse = client.delete(f"/api/v1/admin/pending-providers/{signalement.id}")

    assert reponse.status_code == 401


def test_instruire_un_signalement_sans_le_pouvoir_rend_403(
    client, db_session, organisation, signalement
):
    """Et **lire** ne suffit pas : les deux pouvoirs sont distincts.

    C'est pourquoi le rôle `moderator` semé porte les deux — l'oubli du second
    est le bug attendu d'une composition à la main.
    """
    connecte(client, db_session, organisation, P.PENDING_PROVIDERS_READ.code)

    reponse = client.delete(f"/api/v1/admin/pending-providers/{signalement.id}")

    assert reponse.status_code == 403


def test_instruire_un_signalement_avec_le_pouvoir_rend_204(
    client, db_session, organisation, signalement
):
    connecte(client, db_session, organisation, P.PENDING_PROVIDERS_HANDLE.code)

    reponse = client.delete(f"/api/v1/admin/pending-providers/{signalement.id}")

    assert reponse.status_code == 204


# --- POST /participations ---------------------------------------------------

CORPS_RESULTAT = {
    "source_url": "https://exemple.fr/epreuve",
    "provider": "manuel",
    "athlete_name": "NOM",
    "athlete_firstname": "Prénom",
    "event_name": "Épreuve manuelle",
    "event_date": "2026-05-01",
    "event_type": "triathlon-m",
    "bib_number": "42",
}


def test_creer_un_resultat_reste_public(client):
    """#270 — la route redevient publique : un membre sans compte peut saisir.

    Ce que #115 protégeait (l'injection anonyme d'un résultat) est désormais
    tenu par la mise en quarantaine du résultat créé, pas par une session :
    voir `is_pending_validation` et son exclusion des agrégats publics.
    """
    reponse = client.post("/api/v1/participations", json=CORPS_RESULTAT)

    assert reponse.status_code == 201
    assert reponse.json()["is_pending_validation"] is True
    assert not client.cookies, "le test doit passer sans le moindre cookie"


# --- DELETE /participations/{id} --------------------------------------------


def test_supprimer_un_resultat_sans_session_rend_401(client, participation):
    """`db.delete(row)` puis `db.commit()`, sans la moindre garde — jusqu'ici."""
    reponse = client.delete(f"/api/v1/participations/{participation.id}")

    assert reponse.status_code == 401


def test_supprimer_un_resultat_sans_le_pouvoir_rend_403(
    client, db_session, organisation, participation
):
    # Un pouvoir quelconque mais pas le bon : prouve que la garde est
    # spécifique à `participations:delete`, pas à « avoir une session ».
    connecte(client, db_session, organisation, P.PENDING_PROVIDERS_READ.code)

    reponse = client.delete(f"/api/v1/participations/{participation.id}")

    assert reponse.status_code == 403


def test_supprimer_un_resultat_avec_le_pouvoir_rend_204(
    client, db_session, organisation, participation
):
    connecte(client, db_session, organisation, P.PARTICIPATIONS_DELETE.code)

    reponse = client.delete(f"/api/v1/participations/{participation.id}")

    assert reponse.status_code == 204


def test_un_refus_precede_toute_ecriture(client, db_session, organisation, participation):
    """403 et la ligne est toujours là — la garde est une dépendance, pas un contrôle
    posé au milieu du endpoint."""
    connecte(client, db_session, organisation)

    client.delete(f"/api/v1/participations/{participation.id}")

    assert db_session.query(Participation).count() == 1


# --- Le signalement anonyme, qui ne bouge pas -------------------------------


def test_signaler_un_chronometreur_reste_ouvert_sans_le_moindre_cookie(client):
    """FR-022 — répété ici, à côté des routes fermées, pour que le contraste soit lu.

    Trois routes du même préfixe sont gardées ; celle-ci ne l'est pas, et c'est
    pourquoi aucune garde ne peut être posée sur le préfixe (FR-018).
    """
    assert not client.cookies

    reponse = client.post(
        "/api/v1/admin/pending-providers", json={"url": "https://inconnu.example/y"}
    )

    assert reponse.status_code == 201


def test_les_six_pages_publiques_ne_reclament_rien(client):
    """FR-024 — l'échantillon des routes que le site public appelle réellement."""
    for chemin in (
        "/api/v1/courses",
        "/api/v1/athletes",
        "/api/v1/participations",
        "/api/v1/stats/dashboard",
        "/api/v1/health",
        "/api/v1/version",
    ):
        assert client.get(chemin).status_code not in (401, 403), chemin
