"""Édition de la portée des compteurs depuis le panel admin (#95).

La base de test est montée par `create_all`, donc **sans** les lignes que la
migration amorce : chaque test part de deux listes vides et déclare ce dont il a
besoin. C'est plus proche du vrai que d'un décor pré-rempli — une écriture
recharge le registre depuis la base, et le registre vaut donc exactement ce que
la base porte.
"""
import pytest

from app.api.v1.auth import session_cookie_name
from app.core import counter_scope
from app.core.config import get_settings
from app.models.admin_action_log import AdminActionLog
from app.models.counter_scope_entry import CLUB_LABEL, NON_FEDERAL_DISCIPLINE
from app.models.role_permission import RolePermission
from app.repositories import (
    counter_scope_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import session as session_service

BASE = "/api/v1/admin/counter-scope"


def _semer(db_session, kind: str, *valeurs: str) -> None:
    for valeur in valeurs:
        counter_scope_repository.create_entry(
            db_session, kind=kind, value=valeur, created_by_user_id=None
        )
    db_session.commit()


# --- GET ---------------------------------------------------------------------


def test_la_lecture_rend_les_deux_listes(client, db_session):
    _semer(db_session, CLUB_LABEL, "tcn")
    _semer(db_session, NON_FEDERAL_DISCIPLINE, "trail")

    corps = client.get(BASE).json()

    assert [e["value"] for e in corps["club_labels"]] == ["tcn"]
    assert [e["value"] for e in corps["disciplines"]] == ["trail"]


def test_la_lecture_trie_par_valeur(client, db_session):
    _semer(db_session, CLUB_LABEL, "tri club nantais", "tcn")

    corps = client.get(BASE).json()

    assert [e["value"] for e in corps["club_labels"]] == ["tcn", "tri club nantais"]


def test_la_lecture_rend_deux_listes_vides_sans_configuration(client):
    corps = client.get(BASE).json()

    assert corps == {"disciplines": [], "club_labels": []}


# --- POST --------------------------------------------------------------------


def test_l_ajout_normalise_la_valeur(client):
    reponse = client.post(f"{BASE}/club-labels", json={"value": "TRIATHLON  CLUB NANTAIS 44"})

    assert reponse.status_code == 201
    assert reponse.json()["value"] == "triathlon club nantais 44"


def test_l_ajout_nomme_son_auteur(client):
    corps = client.post(f"{BASE}/club-labels", json={"value": "tcn"}).json()

    assert corps["created_by"] is not None
    assert corps["created_at"] is not None


def test_l_ajout_refuse_une_valeur_vide(client):
    reponse = client.post(f"{BASE}/club-labels", json={"value": "   "})

    assert reponse.status_code == 400
    assert "vide" in reponse.json()["detail"]


def test_l_ajout_refuse_un_doublon(client, db_session):
    _semer(db_session, CLUB_LABEL, "tcn")

    reponse = client.post(f"{BASE}/club-labels", json={"value": "  TCN "})

    assert reponse.status_code == 409
    assert "figure déjà" in reponse.json()["detail"]


def test_une_nature_inconnue_est_refusee(client):
    reponse = client.post(f"{BASE}/pouet", json={"value": "tcn"})

    assert reponse.status_code == 422


# --- DELETE ------------------------------------------------------------------


def test_le_retrait_supprime_l_entree(client, db_session):
    _semer(db_session, CLUB_LABEL, "tcn", "tri club nantais")
    cible = counter_scope_repository.find_by_value(db_session, kind=CLUB_LABEL, value="tcn")

    reponse = client.delete(f"{BASE}/club-labels/{cible.id}")

    assert reponse.status_code == 204
    assert [e["value"] for e in client.get(BASE).json()["club_labels"]] == ["tri club nantais"]


def test_le_retrait_du_dernier_libelle_de_club_est_refuse(client, db_session):
    """Sans aucun libellé, plus rien n'est compté comme résultat du club — et
    ça ne se voit pas : les compteurs tombent à zéro sans erreur."""
    _semer(db_session, CLUB_LABEL, "tcn")
    cible = counter_scope_repository.find_by_value(db_session, kind=CLUB_LABEL, value="tcn")

    reponse = client.delete(f"{BASE}/club-labels/{cible.id}")

    assert reponse.status_code == 409
    assert "Au moins un libellé de club" in reponse.json()["detail"]


def test_vider_la_liste_des_disciplines_est_permis(client, db_session):
    """Tout devient fédéral : cohérent, visible et réversible."""
    _semer(db_session, NON_FEDERAL_DISCIPLINE, "trail")
    cible = counter_scope_repository.find_by_value(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail"
    )

    reponse = client.delete(f"{BASE}/disciplines/{cible.id}")

    assert reponse.status_code == 204


def test_un_identifiant_inconnu_est_introuvable(client):
    reponse = client.delete(f"{BASE}/club-labels/4242")

    assert reponse.status_code == 404


def test_un_identifiant_de_l_autre_nature_est_introuvable(client, db_session):
    """La nature fait partie de la question, elle n'est pas décorative."""
    _semer(db_session, NON_FEDERAL_DISCIPLINE, "trail")
    cible = counter_scope_repository.find_by_value(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail"
    )

    reponse = client.delete(f"{BASE}/club-labels/{cible.id}")

    assert reponse.status_code == 404


# --- L'écriture prend effet immédiatement (FR-008) ----------------------------


def test_l_ajout_recharge_le_registre(client):
    client.post(f"{BASE}/club-labels", json={"value": "tcn 44"})

    assert counter_scope.tcn_club_labels() == frozenset({"tcn 44"})


def test_le_retrait_recharge_le_registre(client, db_session):
    _semer(db_session, NON_FEDERAL_DISCIPLINE, "trail")
    cible = counter_scope_repository.find_by_value(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail"
    )

    client.delete(f"{BASE}/disciplines/{cible.id}")

    assert counter_scope.non_federal_disciplines() == frozenset()


# --- Le badge et le compteur bougent ensemble (FR-005) ------------------------


@pytest.fixture
def _un_resultat_au_club_inconnu(client, db_session):
    """Une participation portant un libellé de club encore non déclaré."""
    from tests.test_api.conftest import valider_toutes_les_participations

    course = client.post(
        "/api/v1/participations",
        json={
            "nom": "LEMÉE",
            "prenom": "Jean",
            "club": "TRIATHLON CLUB NANTAIS 44",
            "event_name": "Tri du test",
            "event_date": "2026-05-16",
            "event_type": "triathlon-m",
            "bib_number": "1",
            "total_time": "01:00:00",
        },
    )
    assert course.status_code in (200, 201), course.text
    valider_toutes_les_participations(db_session)


def test_le_badge_suit_la_configuration(client, _un_resultat_au_club_inconnu):
    def badge() -> bool:
        return client.get("/api/v1/participations").json()[0]["is_tcn"]

    assert badge() is False

    client.post(f"{BASE}/club-labels", json={"value": "TRIATHLON CLUB NANTAIS 44"})

    assert badge() is True


def test_le_compteur_suit_la_configuration(client, _un_resultat_au_club_inconnu):
    def compte() -> int:
        return len(client.get("/api/v1/participations", params={"scope": "club"}).json())

    assert compte() == 0

    client.post(f"{BASE}/club-labels", json={"value": "TRIATHLON CLUB NANTAIS 44"})

    assert compte() == 1


# --- Journal d'administration (FR-013) ----------------------------------------


def test_l_ajout_est_journalise(client, db_session):
    client.post(f"{BASE}/club-labels", json={"value": "tcn"})

    ligne = db_session.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first()
    assert ligne.action == "counter_scope.entry_add"
    assert ligne.entity_type == "counter_scope_entry"
    assert ligne.user_id is not None


def test_le_retrait_est_journalise(client, db_session):
    _semer(db_session, NON_FEDERAL_DISCIPLINE, "trail")
    cible = counter_scope_repository.find_by_value(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail"
    )

    client.delete(f"{BASE}/disciplines/{cible.id}")

    ligne = db_session.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first()
    assert ligne.action == "counter_scope.entry_remove"
    assert ligne.entity_id == cible.id


# --- La garde (FR-012) --------------------------------------------------------


def test_l_acces_anonyme_est_refuse(client):
    client.cookies.clear()

    assert client.get(BASE).status_code == 401


def test_un_compte_sans_le_pouvoir_est_refuse(client, db_session):
    """Connecté, mais sans `counter_scope:manage` : 403, pas 401."""
    from app.models.organisation import Organisation

    organisation = db_session.query(Organisation).filter_by(slug="tcn").one()
    role = role_repository.create(db_session, slug="sans-pouvoir", name="Sans pouvoir")
    role.permissions.append(RolePermission(permission_code="feedback:read"))
    db_session.flush()
    autre = user_repository.create(db_session, email="sans-pouvoir@exemple.fr")
    db_session.flush()
    user_role_repository.grant(
        db_session, user_id=autre.id, role_id=role.id, organisation_id=organisation.id
    )
    jeton = session_service.open_for(db_session, autre)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)

    assert client.get(BASE).status_code == 403


def test_un_rechargement_en_echec_ne_fait_pas_echouer_l_ecriture(client, db_session, monkeypatch):
    """L'écriture est déjà commitée quand le rechargement s'exécute.

    Rendre 500 dirait à l'administrateur que son geste a échoué alors qu'il a
    réussi, et il le referait — en récoltant cette fois un 409 de doublon.
    """
    from app.api.v1 import admin_counter_scope

    def _en_panne(_db):
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(admin_counter_scope.counter_scope, "load_from_db", _en_panne)

    reponse = client.post(f"{BASE}/club-labels", json={"value": "TCN 44"})

    assert reponse.status_code == 201
    assert reponse.json()["value"] == "tcn 44"
    # L'entrée est bien en base, malgré le registre resté périmé.
    assert any(e["value"] == "tcn 44" for e in client.get(BASE).json()["club_labels"])
