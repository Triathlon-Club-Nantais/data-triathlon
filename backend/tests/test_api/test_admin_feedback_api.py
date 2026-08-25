"""API des retours utilisateurs (#267) — contracts/feedback-api.md."""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.models.user_feedback import FEEDBACK_STATUSES
from app.repositories import (
    feedback_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.schemas.feedback import FeedbackCounts
from app.services.auth import session as session_service

_URL = "/api/v1/admin/feedback"

#: La soumission publique, seule route de la ressource à ne pas vivre sous
#: `/admin` — les tests qui la couvrent sont dans `test_feedback_api.py`. Elle
#: sert ici à fabriquer un signalement **portant l'identité de son auteur**,
#: ce que `feedback_repository.create` ne fait pas.
_URL_PUBLIQUE = "/api/v1/feedback"


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


# --- File de traitement : filtre et comptage par statut (#500) ----------------


def _cree(db_session, statut=None, **kwargs):
    defaults = {"type": "bug", "title": "Titre", "body": "x"}
    entry = feedback_repository.create(db_session, **{**defaults, **kwargs})
    if statut:
        feedback_repository.update_status(db_session, entry.id, statut)
    db_session.commit()
    return entry


def test_lister_filtre_par_statut(client, db_session):
    _cree(db_session, title="À traiter")
    _cree(db_session, "ignore", title="Écarté")

    reponse = client.get(_URL, params={"status": "nouveau"})

    assert [ligne["title"] for ligne in reponse.json()] == ["À traiter"]


def test_lister_sans_statut_rend_tout(client, db_session):
    """Le paramètre est facultatif : la forme publiée de v1 ne change pas."""
    _cree(db_session, title="À traiter")
    _cree(db_session, "ignore", title="Écarté")

    assert len(client.get(_URL).json()) == 2


def test_lister_avec_un_statut_inconnu_rend_422(client):
    assert client.get(_URL, params={"status": "archive"}).status_code == 422


def test_comptage_par_statut(client, db_session):
    _cree(db_session)
    _cree(db_session)
    _cree(db_session, "traite")

    comptes = client.get(f"{_URL}/counts").json()

    assert comptes == {"nouveau": 2, "en_cours": 0, "traite": 1, "ignore": 0, "total": 3}


def test_comptage_dune_base_vide_rend_des_zeros(client):
    """Chaque statut est toujours une clé : le front affiche ses quatre filtres
    même quand aucun signalement n'existe encore."""
    comptes = client.get(f"{_URL}/counts").json()

    assert comptes == {"nouveau": 0, "en_cours": 0, "traite": 0, "ignore": 0, "total": 0}


def test_comptage_sans_le_pouvoir_rend_403(client, db_session):
    _session_etroite(client, db_session)

    assert client.get(f"{_URL}/counts").status_code == 403


def test_le_comptage_porte_exactement_les_statuts_de_la_nomenclature():
    """Le filtre de `GET /admin/feedback` **dérive** de `FEEDBACK_STATUSES`,
    `FeedbackCounts` **énumère** ses champs : sans ce test, un cinquième statut
    ajouté à la nomenclature ferait passer un kwarg de trop à un modèle
    Pydantic qui l'ignore en silence (`extra="ignore"` par défaut). La clé
    disparaîtrait de la réponse — donc un filtre du front —, pendant que
    `total` continuerait de compter ses lignes."""
    assert set(FeedbackCounts.model_fields) == {*FEEDBACK_STATUSES, "total"}


def test_comptage_ne_se_lit_pas_comme_un_identifiant(client, db_session):
    """`/counts` est déclaré avant `/{feedback_id}` — dans l'autre ordre, FastAPI
    tenterait d'y lire un entier et rendrait 422."""
    _cree(db_session)

    assert client.get(f"{_URL}/counts").status_code == 200


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
    id_signalement = client.post(
        _URL_PUBLIQUE, json={"type": "bug", "title": "Un titre", "body": "Une description."}
    ).json()["id"]

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
