"""API des retours utilisateurs (#267) — contracts/feedback-api.md."""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    feedback_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import session as session_service

_URL = "/api/v1/admin/feedback"


def _session_etroite(client, db_session, *codes):
    """Ce fichier vit sous `tests/test_api/` : la session de saisie du conftest
    local est superutilisateur. Un test de refus a besoin d'une session plus
    étroite pour l'écraser — même patron que `test_course_reliability_api.py`."""
    organisation = db_session.query(Organisation).first()
    user = user_repository.create(db_session, email="etroit@exemple.fr")
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="etroit-feedback", name="Étroit")
        for code in codes:
            role.permissions.append(RolePermission(permission_code=str(code)))
        db_session.flush()
        user_role_repository.grant(
            db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
        )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


def _payload(**overrides):
    defaults = {"type": "bug", "title": "Un titre", "body": "Une description."}
    return {**defaults, **overrides}


def test_soumission_publique_sans_session_repond_201(client):
    client.cookies.clear()

    reponse = client.post(_URL, json=_payload())

    assert reponse.status_code == 201
    assert reponse.json()["status"] == "nouveau"


def test_soumission_sans_session_ne_porte_aucune_identite(client, db_session):
    client.cookies.clear()

    reponse = client.post(_URL, json=_payload())

    entry = feedback_repository.get(db_session, reponse.json()["id"])
    assert entry.user_id is None


def test_soumission_connectee_associe_lauteur(client, db_session):
    # `session_de_saisie` (autouse) a déjà ouvert une session superutilisateur.
    reponse = client.post(_URL, json=_payload())

    entry = feedback_repository.get(db_session, reponse.json()["id"])
    assert entry.user_id is not None


def test_titre_vide_rend_422(client):
    assert client.post(_URL, json=_payload(title="")).status_code == 422


def test_titre_trop_long_rend_422(client):
    assert client.post(_URL, json=_payload(title="x" * 201)).status_code == 422


def test_corps_vide_rend_422(client):
    assert client.post(_URL, json=_payload(body="")).status_code == 422


def test_type_inconnu_rend_422(client):
    assert client.post(_URL, json=_payload(type="autre")).status_code == 422


def test_page_url_trop_longue_rend_422(client):
    assert client.post(_URL, json=_payload(page_url="x" * 2001)).status_code == 422


def test_user_agent_trop_long_rend_422(client):
    assert client.post(_URL, json=_payload(user_agent="x" * 501)).status_code == 422


def test_honeypot_rempli_repond_201_sans_persister(client, db_session):
    client.cookies.clear()

    reponse = client.post(_URL, json=_payload(honeypot="je-suis-un-bot"))

    assert reponse.status_code == 201
    assert feedback_repository.list_sorted(db_session) == []


def test_debit_depasse_rend_429(client, monkeypatch):
    client.cookies.clear()
    monkeypatch.setattr(get_settings(), "feedback_rate_limit_max_per_window", 2)

    client.post(_URL, json=_payload())
    client.post(_URL, json=_payload())
    reponse = client.post(_URL, json=_payload())

    assert reponse.status_code == 429
    assert "réessayez" in reponse.json()["detail"]


# --- Consultation de la liste (US2) ------------------------------------------


def test_lister_rend_les_signalements(client, db_session):
    feedback_repository.create(db_session, type="bug", title="Un bug", body="Détail")
    db_session.commit()

    reponse = client.get(_URL)

    assert reponse.status_code == 200
    titres = [ligne["title"] for ligne in reponse.json()]
    assert "Un bug" in titres


def test_lister_ne_rend_jamais_lip(client, db_session):
    feedback_repository.create(
        db_session, type="bug", title="Un bug", body="Détail", ip_address="203.0.113.1"
    )
    db_session.commit()

    ligne = client.get(_URL).json()[0]

    assert "ip_address" not in ligne


def test_lister_respecte_le_tri_demande(client, db_session):
    feedback_repository.create(db_session, type="feedback", title="F", body="x")
    feedback_repository.create(db_session, type="bug", title="B", body="x")
    db_session.commit()

    reponse = client.get(_URL, params={"sort": "type", "order": "asc"})

    assert [ligne["type"] for ligne in reponse.json()] == ["bug", "feedback"]


def test_lister_sans_le_pouvoir_rend_403(client, db_session):
    _session_etroite(client, db_session)

    assert client.get(_URL).status_code == 403


def test_lister_avec_le_pouvoir_rend_200(client, db_session):
    _session_etroite(client, db_session, P.FEEDBACK_READ)

    assert client.get(_URL).status_code == 200


# --- Vue détail et changement de statut (US3) --------------------------------


def test_detail_dun_signalement_absent_rend_404(client):
    assert client.get(f"{_URL}/999999").status_code == 404


def test_detail_dun_signalement_anonyme_ne_porte_pas_demail(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()

    assert client.get(f"{_URL}/{entry.id}").json()["email"] is None


def test_detail_dun_signalement_connecte_porte_lemail(client, db_session):
    # `session_de_saisie` (autouse) est déjà ouverte : la soumission porte donc
    # l'identité de son auteur, avant que la lecture ne s'en serve.
    id_signalement = client.post(_URL, json=_payload()).json()["id"]

    ligne = client.get(f"{_URL}/{id_signalement}").json()
    entry = feedback_repository.get(db_session, id_signalement)

    assert ligne["email"] is not None
    assert entry.user is not None
    assert ligne["email"] == entry.user.email


def test_detail_sans_le_pouvoir_rend_403(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()
    _session_etroite(client, db_session)

    assert client.get(f"{_URL}/{entry.id}").status_code == 403


def test_changer_le_statut(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()

    reponse = client.patch(f"{_URL}/{entry.id}", json={"status": "traite"})

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "traite"


def test_changer_le_statut_autorise_le_retour_en_arriere(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()
    client.patch(f"{_URL}/{entry.id}", json={"status": "traite"})

    reponse = client.patch(f"{_URL}/{entry.id}", json={"status": "nouveau"})

    assert reponse.json()["status"] == "nouveau"


def test_changer_le_statut_avec_une_valeur_inconnue_rend_422(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()

    assert client.patch(f"{_URL}/{entry.id}", json={"status": "archive"}).status_code == 422


def test_changer_le_statut_dun_signalement_absent_rend_404(client):
    assert client.patch(f"{_URL}/999999", json={"status": "traite"}).status_code == 404


def test_les_champs_non_envoyes_restent_inchanges(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    feedback_repository.set_github_url(
        db_session, entry.id, "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/1"
    )
    db_session.commit()

    reponse = client.patch(f"{_URL}/{entry.id}", json={"status": "traite"})

    assert (
        reponse.json()["github_url"]
        == "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/1"
    )


def test_changer_le_statut_sans_le_pouvoir_rend_403(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()
    _session_etroite(client, db_session, P.FEEDBACK_READ)

    reponse = client.patch(f"{_URL}/{entry.id}", json={"status": "traite"})

    assert reponse.status_code == 403
    assert feedback_repository.get(db_session, entry.id).status == "nouveau"


# --- Pont vers GitHub (US4) ---------------------------------------------------

_ISSUE = "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/321"


def test_enregistrer_lurl_de_lissue(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()

    reponse = client.patch(f"{_URL}/{entry.id}", json={"github_url": _ISSUE})

    assert reponse.status_code == 200
    assert reponse.json()["github_url"] == _ISSUE
    assert feedback_repository.get(db_session, entry.id).github_url == _ISSUE


def test_une_url_invalide_rend_422(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()

    reponse = client.patch(f"{_URL}/{entry.id}", json={"github_url": "pas-une-url"})

    assert reponse.status_code == 422
    assert feedback_repository.get(db_session, entry.id).github_url is None


def test_enregistrer_lurl_sans_le_pouvoir_rend_403(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()
    _session_etroite(client, db_session, P.FEEDBACK_READ)

    reponse = client.patch(f"{_URL}/{entry.id}", json={"github_url": _ISSUE})

    assert reponse.status_code == 403
    assert feedback_repository.get(db_session, entry.id).github_url is None


def test_statut_et_url_peuvent_etre_envoyes_ensemble(client, db_session):
    entry = feedback_repository.create(db_session, type="bug", title="T", body="x")
    db_session.commit()

    reponse = client.patch(
        f"{_URL}/{entry.id}", json={"status": "traite", "github_url": _ISSUE}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert (corps["status"], corps["github_url"]) == ("traite", _ISSUE)
