"""Page de vérification des résultats par les bénévoles (#271).

La garde (`require_benevole_access`) est **distincte** de `require_permission`
(SSO/RBAC) : mot de passe partagé, cookie signé par HMAC, aucune table.
"""
from datetime import date

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_benevole_access
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.services import benevole_access

MOT_DE_PASSE = "secret-du-club"


@pytest.fixture(autouse=True)
def mot_de_passe_configure(monkeypatch):
    monkeypatch.setenv("BENEVOLE_SHARED_PASSWORD", MOT_DE_PASSE)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- Garde `require_benevole_access`, seule, sur une application jetable ----


@pytest.fixture
def application(db_session) -> FastAPI:
    api = FastAPI()
    register_exception_handlers(api)

    @api.get("/protege", dependencies=[Depends(require_benevole_access)])
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
    visiteur.cookies.set(benevole_access.BENEVOLE_SESSION_COOKIE, "n-importe-quoi")
    assert visiteur.get("/protege").status_code == 401


def test_refuse_meme_avec_un_cookie_signe_par_un_autre_mot_de_passe(visiteur):
    valeur = benevole_access.sign_session("autre-mot-de-passe")
    visiteur.cookies.set(benevole_access.BENEVOLE_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


def test_passe_avec_un_cookie_valide(visiteur):
    valeur = benevole_access.sign_session(MOT_DE_PASSE)
    visiteur.cookies.set(benevole_access.BENEVOLE_SESSION_COOKIE, valeur)
    reponse = visiteur.get("/protege")
    assert reponse.status_code == 200
    assert reponse.json() == {"ok": True}


def test_refuse_si_le_mot_de_passe_n_est_pas_configure(visiteur, monkeypatch):
    monkeypatch.setenv("BENEVOLE_SHARED_PASSWORD", "")
    get_settings.cache_clear()
    valeur = benevole_access.sign_session(MOT_DE_PASSE)
    visiteur.cookies.set(benevole_access.BENEVOLE_SESSION_COOKIE, valeur)
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
        db_session, email=benevole_access.SYSTEM_USER_EMAIL, display_name="Bénévoles (accès partagé)"
    )
    db_session.commit()
    return compte


# --- POST/DELETE /benevoles/session (US4, T013/T014) ------------------------


def test_connexion_refuse_un_mauvais_mot_de_passe(client):
    reponse = client.post("/api/v1/benevoles/session", json={"password": "faux"})
    assert reponse.status_code == 401


def test_connexion_refuse_si_non_configure(client, monkeypatch):
    monkeypatch.setenv("BENEVOLE_SHARED_PASSWORD", "")
    get_settings.cache_clear()
    reponse = client.post("/api/v1/benevoles/session", json={"password": MOT_DE_PASSE})
    assert reponse.status_code == 401


def test_connexion_pose_le_cookie_et_ouvre_la_file(client, compte_systeme):
    reponse = client.post("/api/v1/benevoles/session", json={"password": MOT_DE_PASSE})
    assert reponse.status_code == 204
    assert benevole_access.BENEVOLE_SESSION_COOKIE in reponse.cookies

    file_attente = client.get("/api/v1/benevoles/queue")
    assert file_attente.status_code == 200


def test_deconnexion_efface_le_cookie(benevole_connecte, compte_systeme):
    assert benevole_connecte.get("/api/v1/benevoles/queue").status_code == 200

    reponse = benevole_connecte.delete("/api/v1/benevoles/session")
    assert reponse.status_code == 204
    assert benevole_access.BENEVOLE_SESSION_COOKIE not in benevole_connecte.cookies

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
