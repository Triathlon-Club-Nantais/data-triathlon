"""Page de vérification des résultats par les bénévoles (#271).

La garde (`require_volunteer_access`) est **distincte** de `require_permission`
(SSO/RBAC) : mot de passe partagé, cookie signé par HMAC — la clé est
désormais `session_secret`, en base (`specs/20260815-173645-admin-mdp-
benevoles/`), plus le mot de passe en clair (#271, `research.md` §D2).
"""
from datetime import date

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_volunteer_access
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.models.user import SYSTEM_USER_EMAIL
from app.models.volunteer_access_config import VolunteerAccessConfig
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.services import shared_password, volunteer_access
from app.services.scrape_service import YouthResultError
from tests.test_api.test_admin_data_api import _session_etroite

MOT_DE_PASSE = "secret-du-club"


@pytest.fixture(autouse=True)
def benevole_sans_session_sso(session_de_saisie, client):
    """Retire la session superutilisateur que `tests/test_api/conftest.py` pose
    sur le client : depuis #1272 elle ouvrirait la page par le pouvoir, et ces
    tests éprouvent le bénévole, qui n'a que le mot de passe partagé. L'accès
    par pouvoir est éprouvé dans `tests/test_auth/test_volunteer_access_sso.py`."""
    from app.api.v1.auth import session_cookie_name
    from app.core.config import get_settings

    client.cookies.delete(session_cookie_name(get_settings()))


@pytest.fixture(autouse=True)
def mot_de_passe_configure(db_session, administrateur):
    volunteer_access.replace_password(
        db_session, password=MOT_DE_PASSE, admin_user_id=administrateur.id
    )
    db_session.commit()


@pytest.fixture
def sans_configuration(db_session):
    """Ramène à l'état « jamais configuré » (fail-closed, FR-007)."""

    def _vider() -> None:
        db_session.query(VolunteerAccessConfig).delete()
        db_session.commit()

    return _vider


# --- Garde `require_volunteer_access`, seule, sur une application jetable ----


@pytest.fixture
def application(db_session) -> FastAPI:
    api = FastAPI()
    register_exception_handlers(api)

    @api.get("/protege", dependencies=[Depends(require_volunteer_access)])
    def protege():
        return {"ok": True}

    def _get_db():
        yield db_session

    api.dependency_overrides[get_db] = _get_db
    return api


@pytest.fixture
def visiteur(application) -> TestClient:
    with TestClient(application) as client:
        yield client


def test_refuse_sans_cookie(visiteur):
    assert visiteur.get("/protege").status_code == 401


def test_refuse_avec_un_cookie_invalide(visiteur):
    visiteur.cookies.set(volunteer_access.VOLUNTEER_SESSION_COOKIE, "n-importe-quoi")
    assert visiteur.get("/protege").status_code == 401


def test_refuse_meme_avec_un_cookie_signe_par_un_autre_secret(visiteur):
    valeur = shared_password.sign_cookie("autre-secret-de-session")
    visiteur.cookies.set(volunteer_access.VOLUNTEER_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


def test_passe_avec_un_cookie_valide(visiteur, db_session):
    config = db_session.query(VolunteerAccessConfig).one()
    valeur = shared_password.sign_cookie(config.session_secret)
    visiteur.cookies.set(volunteer_access.VOLUNTEER_SESSION_COOKIE, valeur)
    reponse = visiteur.get("/protege")
    assert reponse.status_code == 200
    assert reponse.json() == {"ok": True}


def _cookie_signe_il_y_a(monkeypatch, secret: str, secondes: int) -> str:
    """Cookie bien signé mais émis il y a `secondes` (#1534)."""
    import time

    maintenant = time.time()
    monkeypatch.setattr(shared_password.time, "time", lambda: maintenant - secondes)
    valeur = shared_password.sign_cookie(secret)
    monkeypatch.setattr(shared_password.time, "time", lambda: maintenant)
    return valeur


def test_refuse_un_cookie_plus_vieux_que_la_duree_serveur(visiteur, db_session, monkeypatch):
    """Le navigateur peut restaurer un cookie de session sans fin : seule
    l'horloge serveur borne sa durée (#1534)."""
    config = db_session.query(VolunteerAccessConfig).one()
    valeur = _cookie_signe_il_y_a(
        monkeypatch, config.session_secret, volunteer_access.VOLUNTEER_SESSION_TTL_SECONDS + 1
    )
    visiteur.cookies.set(volunteer_access.VOLUNTEER_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


def test_passe_avec_un_cookie_encore_dans_la_duree_serveur(visiteur, db_session, monkeypatch):
    config = db_session.query(VolunteerAccessConfig).one()
    valeur = _cookie_signe_il_y_a(
        monkeypatch, config.session_secret, volunteer_access.VOLUNTEER_SESSION_TTL_SECONDS - 60
    )
    visiteur.cookies.set(volunteer_access.VOLUNTEER_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 200


def test_refuse_un_cookie_emis_avant_le_remplacement_du_mot_de_passe(
    visiteur, db_session, administrateur
):
    config = db_session.query(VolunteerAccessConfig).one()
    valeur = shared_password.sign_cookie(config.session_secret)
    volunteer_access.replace_password(db_session, password="autre-secret", admin_user_id=administrateur.id)
    db_session.commit()
    visiteur.cookies.set(volunteer_access.VOLUNTEER_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


def test_refuse_si_le_mot_de_passe_n_est_pas_configure(visiteur, sans_configuration, db_session):
    config = db_session.query(VolunteerAccessConfig).one()
    valeur = shared_password.sign_cookie(config.session_secret)
    sans_configuration()
    visiteur.cookies.set(volunteer_access.VOLUNTEER_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


# --- Routes réelles de l'application (client + base réelle) -----------------


@pytest.fixture
def benevole_connecte(client):
    """Ouvre une session bénévole sur le client partagé, par la route réelle —
    c'est aussi ce qui garantit que le cookie porte les mêmes attributs
    (chemin, drapeaux) que ceux que la déconnexion devra effacer."""
    reponse = client.post("/api/v1/benevoles/session", json={"password": MOT_DE_PASSE})
    assert reponse.status_code == 204
    return client


@pytest.fixture
def resultat_pendant(db_session):
    """Une épreuve, un athlète, un résultat en attente de validation."""
    course = course_repository.get_or_create(
        db_session, name="Tri Bénévoles", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    ligne = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, total_time="01:00:00",
    )
    db_session.commit()
    return course, athlete, ligne


@pytest.fixture
def compte_systeme(db_session):
    compte = user_repository.create(
        db_session, email=SYSTEM_USER_EMAIL, display_name="Bénévoles (accès partagé)"
    )
    db_session.commit()
    return compte


# --- POST/DELETE /benevoles/session (US4, T013/T014) ------------------------


def test_connexion_refuse_un_mauvais_mot_de_passe(client):
    reponse = client.post("/api/v1/benevoles/session", json={"password": "faux"})
    assert reponse.status_code == 401


def test_connexion_refuse_si_non_configure(client, sans_configuration):
    sans_configuration()
    reponse = client.post("/api/v1/benevoles/session", json={"password": MOT_DE_PASSE})
    assert reponse.status_code == 401


def test_connexion_pose_le_cookie_et_ouvre_la_file(client, compte_systeme):
    reponse = client.post("/api/v1/benevoles/session", json={"password": MOT_DE_PASSE})
    assert reponse.status_code == 204
    assert volunteer_access.VOLUNTEER_SESSION_COOKIE in reponse.cookies

    file_attente = client.get("/api/v1/benevoles/queue")
    assert file_attente.status_code == 200


def test_deconnexion_efface_le_cookie(benevole_connecte, compte_systeme):
    assert benevole_connecte.get("/api/v1/benevoles/queue").status_code == 200

    reponse = benevole_connecte.delete("/api/v1/benevoles/session")
    assert reponse.status_code == 204
    assert volunteer_access.VOLUNTEER_SESSION_COOKIE not in benevole_connecte.cookies

    assert benevole_connecte.get("/api/v1/benevoles/queue").status_code == 401


# --- GET /benevoles/queue (US1, T020) ----------------------------------------


def test_queue_refuse_sans_cookie(client):
    assert client.get("/api/v1/benevoles/queue").status_code == 401


def test_queue_rend_les_resultats_en_attente_avec_leurs_champs(benevole_connecte, resultat_pendant):
    course, athlete, ligne = resultat_pendant
    reponse = benevole_connecte.get("/api/v1/benevoles/queue")
    assert reponse.status_code == 200
    charge = reponse.json()
    assert len(charge) == 1
    assert charge[0]["id"] == ligne.id
    assert charge[0]["athlete"]["nom"] == "DUPONT"
    assert charge[0]["course"]["name"] == "Tri Bénévoles"
    assert charge[0]["total_time"] == "01:00:00"


def test_queue_vide_sans_erreur_si_rien_en_attente(benevole_connecte):
    reponse = benevole_connecte.get("/api/v1/benevoles/queue")
    assert reponse.status_code == 200
    assert reponse.json() == []


# --- GET /benevoles/queue/history (US13, #466) -------------------------------


def test_queue_history_refuse_sans_cookie(client):
    assert client.get("/api/v1/benevoles/queue/history").status_code == 401


def test_queue_history_vide_sans_resolution(benevole_connecte):
    reponse = benevole_connecte.get("/api/v1/benevoles/queue/history")
    assert reponse.status_code == 200
    assert reponse.json() == {"backlog_by_day": [], "average_resolution_seconds": None}


def test_queue_history_compte_une_entree_encore_en_attente(benevole_connecte, resultat_pendant):
    reponse = benevole_connecte.get("/api/v1/benevoles/queue/history")
    assert reponse.status_code == 200
    charge = reponse.json()
    assert len(charge["backlog_by_day"]) >= 1
    assert charge["backlog_by_day"][-1]["pending_count"] >= 1


# --- POST /benevoles/participations/{id}/validate (US1, T022) ---------------


def test_validate_fait_disparaitre_le_resultat_de_la_file(
    benevole_connecte, resultat_pendant, compte_systeme
):
    course, athlete, ligne = resultat_pendant

    reponse = benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/validate")
    assert reponse.status_code == 200
    assert reponse.json()["is_pending_validation"] is False

    assert benevole_connecte.get("/api/v1/benevoles/queue").json() == []


def test_validate_sur_resultat_inconnu_est_un_404(benevole_connecte, compte_systeme):
    reponse = benevole_connecte.post("/api/v1/benevoles/participations/4242/validate")
    assert reponse.status_code == 404


def test_validate_refuse_sans_cookie(client, resultat_pendant):
    course, athlete, ligne = resultat_pendant
    reponse = client.post(f"/api/v1/benevoles/participations/{ligne.id}/validate")
    assert reponse.status_code == 401


# --- PATCH /benevoles/courses/{id} (US2, T029) -------------------------------


def test_rename_course_sans_collision(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/courses/{course.id}", json={"name": "Triathlon de Nantes"}
    )
    assert reponse.status_code == 200
    assert reponse.json()["name"] == "Triathlon de Nantes"


def test_rename_course_consigne_sous_le_compte_systeme(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    course, athlete, ligne = resultat_pendant

    benevole_connecte.patch(f"/api/v1/benevoles/courses/{course.id}", json={"name": "Renommée"})

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert len(entrees) == 1
    assert entrees[0].user_id == compte_systeme.id


def test_rename_course_signale_une_collision(benevole_connecte, resultat_pendant, compte_systeme, db_session):
    course, athlete, ligne = resultat_pendant
    # Même date et même type que `course` : seul le nom la distinguerait encore.
    course_repository.get_or_create(
        db_session, name="Déjà prise", event_date=course.event_date, event_type=course.event_type
    )
    db_session.commit()

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/courses/{course.id}", json={"name": "Déjà prise"}
    )
    assert reponse.status_code == 409


def test_rename_course_refuse_sans_cookie(client, resultat_pendant):
    course, athlete, ligne = resultat_pendant
    reponse = client.patch(f"/api/v1/benevoles/courses/{course.id}", json={"name": "X"})
    assert reponse.status_code == 401


def test_rename_course_refuse_si_aucun_resultat_en_attente(benevole_connecte, resultat_pendant, compte_systeme):
    """Revue de code : le mot de passe partagé ne doit pas ouvrir n'importe
    quelle épreuve à la réécriture, seulement celles qui ont un résultat à
    valider."""
    course, athlete, ligne = resultat_pendant
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/validate")

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/courses/{course.id}", json={"name": "Renommée"}
    )
    assert reponse.status_code == 404


# --- POST /benevoles/participations/{id}/reassign (US3, T034) ---------------


def test_reassign_vers_un_athlete_existant(benevole_connecte, resultat_pendant, compte_systeme, db_session):
    course, athlete, ligne = resultat_pendant
    cible = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    db_session.commit()

    reponse = benevole_connecte.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": cible.id}
    )
    assert reponse.status_code == 200
    assert reponse.json()["athlete"]["nom"] == "MARTIN"


def test_reassign_d_un_relais_attribue_vide_ses_equipiers(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    """#894 — la route bénévoles partage `reassign_participation` avec l'admin."""
    course, athlete, ligne = resultat_pendant
    ligne.is_relay = True
    equipier = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Marie")
    db_session.flush()
    participation_repository.replace_teammates(db_session, ligne, [athlete.id, equipier.id])
    cible = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    db_session.commit()

    reponse = benevole_connecte.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": cible.id}
    )

    assert reponse.status_code == 200
    assert reponse.json()["teammates"] == []


def test_reassign_consigne_sous_le_compte_systeme(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    course, athlete, ligne = resultat_pendant
    cible = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    db_session.commit()

    benevole_connecte.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": cible.id}
    )

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="participation", entity_id=ligne.id
    )
    assert len(entrees) == 1
    assert entrees[0].user_id == compte_systeme.id


def test_reassign_signale_un_conflit(benevole_connecte, resultat_pendant, compte_systeme, db_session):
    course, athlete, ligne = resultat_pendant
    cible = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    participation_repository.create(
        db_session, athlete_id=cible.id, course_id=course.id, bib_number="2"
    )
    db_session.commit()

    reponse = benevole_connecte.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": cible.id}
    )
    assert reponse.status_code == 409


def test_reassign_vers_un_athlete_inconnu_est_un_404(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    reponse = benevole_connecte.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": 4242}
    )
    assert reponse.status_code == 404


def test_reassign_refuse_sans_cookie(client, resultat_pendant):
    course, athlete, ligne = resultat_pendant
    reponse = client.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": athlete.id}
    )
    assert reponse.status_code == 401


def test_reassign_refuse_si_le_resultat_n_est_plus_en_attente(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    """Revue de code : une fois validé, un résultat sort du périmètre bénévole."""
    course, athlete, ligne = resultat_pendant
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/validate")
    cible = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    db_session.commit()

    reponse = benevole_connecte.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": cible.id}
    )
    assert reponse.status_code == 404


# --- Le rejet bloque validate/reassign tant qu'il n'est pas levé (#437) -----


def test_validate_refuse_un_resultat_rejete(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")

    reponse = benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/validate")
    assert reponse.status_code == 404


def test_reassign_refuse_un_resultat_rejete(benevole_connecte, resultat_pendant, compte_systeme, db_session):
    course, athlete, ligne = resultat_pendant
    cible = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    db_session.commit()
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")

    reponse = benevole_connecte.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": cible.id}
    )
    assert reponse.status_code == 404


# --- POST .../reject, POST .../unreject, GET /benevoles/rejected (#437) -----


def test_reject_fait_sortir_le_resultat_de_la_file(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant

    reponse = benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")
    assert reponse.status_code == 200
    assert reponse.json()["is_rejected"] is True
    assert reponse.json()["is_pending_validation"] is True

    assert benevole_connecte.get("/api/v1/benevoles/queue").json() == []
    rejetees = benevole_connecte.get("/api/v1/benevoles/rejected").json()
    assert [r["id"] for r in rejetees] == [ligne.id]


def test_reject_sur_resultat_inconnu_est_un_404(benevole_connecte, compte_systeme):
    reponse = benevole_connecte.post("/api/v1/benevoles/participations/4242/reject")
    assert reponse.status_code == 404


def test_reject_refuse_sans_cookie(client, resultat_pendant):
    course, athlete, ligne = resultat_pendant
    reponse = client.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")
    assert reponse.status_code == 401


def test_unreject_fait_revenir_le_resultat_dans_la_file(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")

    reponse = benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/unreject")
    assert reponse.status_code == 200
    assert reponse.json()["is_rejected"] is False

    assert [p["id"] for p in benevole_connecte.get("/api/v1/benevoles/queue").json()] == [ligne.id]
    assert benevole_connecte.get("/api/v1/benevoles/rejected").json() == []


def test_rejected_vide_sans_erreur_si_rien_de_rejete(benevole_connecte):
    reponse = benevole_connecte.get("/api/v1/benevoles/rejected")
    assert reponse.status_code == 200
    assert reponse.json() == []


# --- PATCH /benevoles/participations/{id} (#437) -----------------------------


def test_update_fields_ecrit_les_champs_fournis(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/participations/{ligne.id}",
        json={"bib_number": "42", "club": "TCN"},
    )
    assert reponse.status_code == 200
    assert reponse.json()["bib_number"] == "42"
    assert reponse.json()["club"] == "TCN"


def test_update_fields_signale_un_conflit_de_dossard(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    course, athlete, ligne = resultat_pendant
    autre = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    participation_repository.create(db_session, athlete_id=autre.id, course_id=course.id, bib_number="9")
    db_session.commit()

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/participations/{ligne.id}", json={"bib_number": "9"}
    )
    assert reponse.status_code == 409


def test_update_fields_refuse_un_corps_vide(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    reponse = benevole_connecte.patch(f"/api/v1/benevoles/participations/{ligne.id}", json={})
    assert reponse.status_code == 422


def test_update_fields_refuse_sur_resultat_rejete(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/participations/{ligne.id}", json={"club": "TCN"}
    )
    assert reponse.status_code == 404


def test_update_fields_refuse_sans_cookie(client, resultat_pendant):
    course, athlete, ligne = resultat_pendant
    reponse = client.patch(f"/api/v1/benevoles/participations/{ligne.id}", json={"club": "TCN"})
    assert reponse.status_code == 401


# --- Effet de bout en bout de la validation (quickstart.md, scénario 1) -----


def test_valider_rend_le_resultat_visible_sur_la_fiche_et_dans_les_agregats(
    benevole_connecte, resultat_pendant, compte_systeme
):
    """FR-008/FR-009 : ce que #270 excluait, la validation le restitue."""
    course, athlete, ligne = resultat_pendant

    fiche = benevole_connecte.get(f"/api/v1/athletes/{athlete.id}").json()
    assert [p["id"] for p in fiche["participations"]] == [ligne.id]
    assert fiche["participations"][0]["is_pending_validation"] is True

    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/validate")

    apres = benevole_connecte.get(f"/api/v1/athletes/{athlete.id}").json()
    assert apres["participations"][0]["is_pending_validation"] is False

    stats = benevole_connecte.get("/api/v1/stats").json()
    assert stats["total"] >= 1


# --- La pastille « Validation » du rail admin (#1232, #1385) -----------------


def test_the_volunteer_cookie_opens_the_validation_badge(benevole_connecte, resultat_pendant, db_session):
    _session_etroite(benevole_connecte, db_session)

    assert benevole_connecte.get("/api/v1/admin/badge-counts").json() == {"validation": 1}


# --- PATCH /benevoles/participations/{id} : règle jeunes (#1280) ------------


@pytest.mark.parametrize(
    ("avant", "correction"),
    [
        ({"club": "TCN", "category": "MIH"}, {"club": "ASPTT"}),
        ({"club": "ASPTT", "category": "S1H"}, {"category": "MIH"}),
    ],
)
def test_a_correction_that_makes_a_non_tcn_youth_row_is_refused(
    benevole_connecte, resultat_pendant, compte_systeme, db_session, avant, correction
):
    """#1280 : la correction ne contourne pas le refus de la saisie manuelle."""
    _, _, ligne = resultat_pendant
    participation_repository.update(db_session, ligne, **avant)
    db_session.commit()

    reponse = benevole_connecte.patch(f"/api/v1/benevoles/participations/{ligne.id}", json=correction)

    assert reponse.status_code == 422
    assert "jeune" in reponse.json()["detail"]
    db_session.expire_all()
    rechargee = participation_repository.get(db_session, ligne.id)
    assert (rechargee.club, rechargee.category) == (avant["club"], avant["category"])


def test_a_neutral_correction_stays_accepted(benevole_connecte, resultat_pendant, compte_systeme, db_session):
    _, _, ligne = resultat_pendant
    participation_repository.update(db_session, ligne, club="ASPTT", category="S1H")
    db_session.commit()

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/participations/{ligne.id}", json={"category": "V1H"}
    )

    assert reponse.status_code == 200


# --- PATCH /benevoles/courses/{id} : règle jeunes (#1287) --------------------


def _rename(client, course, name):
    return client.patch(f"/api/v1/benevoles/courses/{course.id}", json={"name": name})


def test_a_rename_that_makes_a_non_tcn_row_youth_is_refused(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    """#1287 : le renommage ne contourne pas la règle de la saisie manuelle."""
    course, _, ligne = resultat_pendant
    participation_repository.update(db_session, ligne, club="ASPTT", category="S1H")
    db_session.commit()

    reponse = _rename(benevole_connecte, course, "Triathlon Jeunes")

    assert reponse.status_code == 422
    assert reponse.json()["detail"] == YouthResultError.message
    db_session.expire_all()
    assert course_repository.get(db_session, course.id).name == "Tri Bénévoles"


@pytest.mark.parametrize(
    "statut", [{"is_pending_validation": False}, {"is_rejected": True}], ids=["validated", "rejected"]
)
def test_a_non_tcn_row_out_of_the_queue_still_blocks_a_youth_rename(
    benevole_connecte, resultat_pendant, compte_systeme, db_session, statut
):
    course, _, ligne = resultat_pendant
    participation_repository.update(db_session, ligne, club="TCN", category="S1H")
    autre = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    participation_repository.create(
        db_session, athlete_id=autre.id, course_id=course.id, bib_number="2",
        club="ASPTT", category="S1H", total_time="01:01:00", **statut,
    )
    db_session.commit()

    reponse = _rename(benevole_connecte, course, "Triathlon Jeunes")

    assert reponse.status_code == 422
    assert reponse.json()["detail"] == YouthResultError.message


def test_a_youth_rename_with_only_tcn_rows_stays_accepted(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    course, _, ligne = resultat_pendant
    participation_repository.update(db_session, ligne, club="TCN", category="MIH")
    db_session.commit()

    assert _rename(benevole_connecte, course, "Triathlon Jeunes").status_code == 200


def test_a_neutral_rename_keeps_a_non_tcn_youth_row_kept_by_its_heat(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    """#1221 garde tout un heat portant un jeune TCN : ses lignes non TCN déjà
    jeunes par leur catégorie ne bloquent pas une simple correction de nom."""
    course, _, ligne = resultat_pendant
    participation_repository.update(db_session, ligne, club="ASPTT", category="MIH")
    db_session.commit()

    assert _rename(benevole_connecte, course, "Tri des Bénévoles").status_code == 200


def test_renaming_an_already_youth_course_stays_accepted(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    course, _, ligne = resultat_pendant
    course.name = "Triathlon Jeunes"
    participation_repository.update(db_session, ligne, club="ASPTT", category="S1H")
    db_session.commit()

    assert _rename(benevole_connecte, course, "Triathlon Jeunes de Nantes").status_code == 200
