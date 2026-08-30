"""Accès données de VolunteerDeclaration (#751)."""
from app.repositories import user_repository, volunteer_declaration_repository


def _user(db_session, email="membre@exemple.fr"):
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    return user


def test_create_pour_soi_meme(db_session):
    membre = _user(db_session)

    declaration = volunteer_declaration_repository.create(
        db_session,
        title="Ravitaillement",
        description="Poste eau, 10km du Lac",
        beneficiary_user_id=membre.id,
        author_user_id=membre.id,
        status="en_attente",
    )

    assert declaration.id is not None
    assert declaration.beneficiary_user_id == membre.id
    assert declaration.author_user_id == membre.id
    assert declaration.status == "en_attente"


def test_create_pour_un_tiers(db_session):
    admin = _user(db_session, "admin@exemple.fr")
    beneficiaire = _user(db_session, "beneficiaire@exemple.fr")

    declaration = volunteer_declaration_repository.create(
        db_session,
        title="Signaleur",
        description="Carrefour dangereux",
        beneficiary_user_id=beneficiaire.id,
        author_user_id=admin.id,
        status="validee",
    )

    assert declaration.beneficiary_user_id == beneficiaire.id
    assert declaration.author_user_id == admin.id
    assert declaration.status == "validee"


def test_get_rend_none_si_absent(db_session):
    assert volunteer_declaration_repository.get(db_session, 999) is None


def test_get_rend_la_declaration(db_session):
    membre = _user(db_session)
    declaration = volunteer_declaration_repository.create(
        db_session,
        title="T",
        description="D",
        beneficiary_user_id=membre.id,
        author_user_id=membre.id,
        status="en_attente",
    )

    assert volunteer_declaration_repository.get(db_session, declaration.id).id == declaration.id


def test_list_for_beneficiary_trie_par_date_desc(db_session):
    membre = _user(db_session)
    premiere = volunteer_declaration_repository.create(
        db_session,
        title="Première",
        description="D",
        beneficiary_user_id=membre.id,
        author_user_id=membre.id,
        status="en_attente",
    )
    seconde = volunteer_declaration_repository.create(
        db_session,
        title="Seconde",
        description="D",
        beneficiary_user_id=membre.id,
        author_user_id=membre.id,
        status="en_attente",
    )
    premiere.created_at, seconde.created_at = seconde.created_at, premiere.created_at
    db_session.flush()

    resultats = volunteer_declaration_repository.list_for_beneficiary(db_session, membre.id)

    assert [r.id for r in resultats] == [premiere.id, seconde.id]


def test_list_for_beneficiary_ignore_un_autre_membre(db_session):
    membre = _user(db_session)
    autre = _user(db_session, "autre@exemple.fr")
    volunteer_declaration_repository.create(
        db_session,
        title="T",
        description="D",
        beneficiary_user_id=autre.id,
        author_user_id=autre.id,
        status="en_attente",
    )

    assert volunteer_declaration_repository.list_for_beneficiary(db_session, membre.id) == []


def test_list_all_rend_toutes_les_declarations(db_session):
    membre = _user(db_session)
    autre = _user(db_session, "autre@exemple.fr")
    volunteer_declaration_repository.create(
        db_session,
        title="T1",
        description="D",
        beneficiary_user_id=membre.id,
        author_user_id=membre.id,
        status="en_attente",
    )
    volunteer_declaration_repository.create(
        db_session,
        title="T2",
        description="D",
        beneficiary_user_id=autre.id,
        author_user_id=autre.id,
        status="validee",
    )

    assert len(volunteer_declaration_repository.list_all(db_session)) == 2


def test_delete_retire_la_declaration(db_session):
    membre = _user(db_session)
    declaration = volunteer_declaration_repository.create(
        db_session,
        title="T",
        description="D",
        beneficiary_user_id=membre.id,
        author_user_id=membre.id,
        status="en_attente",
    )

    volunteer_declaration_repository.delete(db_session, declaration.id)

    assert volunteer_declaration_repository.get(db_session, declaration.id) is None


def test_set_status_change_le_statut(db_session):
    membre = _user(db_session)
    declaration = volunteer_declaration_repository.create(
        db_session,
        title="T",
        description="D",
        beneficiary_user_id=membre.id,
        author_user_id=membre.id,
        status="en_attente",
    )

    mise_a_jour = volunteer_declaration_repository.set_status(db_session, declaration.id, "validee")

    assert mise_a_jour.status == "validee"
