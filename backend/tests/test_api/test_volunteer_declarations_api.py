"""API self-service des déclarations de bénévolat (#751) —
contracts/volunteer-declaration-api.md.

`session_de_saisie` (autouse, `tests/test_api/conftest.py`) ouvre déjà une
session sur `client` — le membre standard de ces tests, aucune permission
particulière n'étant vérifiée par ce router self-service.
"""
from app.repositories import volunteer_declaration_repository

_URL = "/api/v1/volunteer-declarations"


def test_creer_pour_soi_meme(client):
    reponse = client.post(_URL, json={"title": "Ravitaillement", "description": "Poste eau"})

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["status"] == "en_attente"
    assert corps["beneficiary_user_id"] == corps["author_user_id"]


def test_titre_vide_rend_422_et_ne_persiste_rien(client, db_session):
    reponse = client.post(_URL, json={"title": "", "description": "Une description"})

    assert reponse.status_code == 422
    assert volunteer_declaration_repository.list_all(db_session) == []


def test_description_vide_rend_422_et_ne_persiste_rien(client, db_session):
    reponse = client.post(_URL, json={"title": "Un titre", "description": ""})

    assert reponse.status_code == 422
    assert volunteer_declaration_repository.list_all(db_session) == []


def test_lister_ne_retourne_que_les_declarations_du_membre_connecte(client, db_session):
    client.post(_URL, json={"title": "La mienne", "description": "D"})
    # Une déclaration d'un autre membre, créée directement via le repository
    # (le router self-service ne permet pas de déclarer pour un tiers — cf.
    # test_beneficiary_user_id_surnumeraire_est_ignore).
    from app.repositories import user_repository

    autre = user_repository.create(db_session, email="autre@exemple.fr")
    db_session.flush()
    volunteer_declaration_repository.create(
        db_session,
        title="Pas la mienne",
        description="D",
        beneficiary_user_id=autre.id,
        author_user_id=autre.id,
        status="en_attente",
    )
    db_session.commit()

    reponse = client.get(_URL)

    titres = [ligne["title"] for ligne in reponse.json()]
    assert titres == ["La mienne"]


def test_lister_trie_de_la_plus_recente_a_la_plus_ancienne(client):
    client.post(_URL, json={"title": "Première", "description": "D"})
    client.post(_URL, json={"title": "Seconde", "description": "D"})

    titres = [ligne["title"] for ligne in client.get(_URL).json()]

    assert titres == ["Seconde", "Première"]


def test_creer_sans_session_rend_401(client):
    client.cookies.clear()

    reponse = client.post(_URL, json={"title": "T", "description": "D"})

    assert reponse.status_code == 401


def test_lister_sans_session_rend_401(client):
    client.cookies.clear()

    assert client.get(_URL).status_code == 401


def test_beneficiary_user_id_surnumeraire_est_ignore(client, db_session):
    """FR-003 : le schéma self-service n'expose aucun champ bénéficiaire — un
    champ surnuméraire ne doit jamais remonter jusqu'à la déclaration créée."""
    from app.repositories import user_repository

    tiers = user_repository.create(db_session, email="tiers@exemple.fr")
    db_session.flush()
    db_session.commit()

    reponse = client.post(
        _URL,
        json={"title": "T", "description": "D", "beneficiary_user_id": tiers.id},
    )

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["beneficiary_user_id"] != tiers.id
    assert corps["beneficiary_user_id"] == corps["author_user_id"]
