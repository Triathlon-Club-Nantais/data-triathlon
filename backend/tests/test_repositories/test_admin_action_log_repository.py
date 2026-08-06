"""Le journal des altérations manuelles (#117, FR-012 à FR-015).

**Une entrée survit à ce qu'elle décrit**, et c'est l'invariant qui commande la
forme : `entity_id` ne porte aucune clé étrangère. Une FK vers `courses.id`
interdirait précisément d'enregistrer une suppression d'épreuve — l'usage
principal du journal.
"""
from app.models.course import Course
from app.repositories import admin_action_log_repository, course_repository, user_repository


def _auteur(db_session, email="admin@exemple.fr"):
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    return user


def test_create_consigne_les_cinq_champs_du_contrat(db_session):
    """AC4 : auteur, action, type et identifiant d'entité, horodatage."""
    auteur = _auteur(db_session)

    entree = admin_action_log_repository.create(
        db_session,
        user_id=auteur.id,
        action="course.delete",
        entity_type="course",
        entity_id=12,
        payload={"name": "Triathlon de Nantes", "participations_deleted": 412},
    )
    db_session.flush()

    assert entree.user_id == auteur.id
    assert entree.action == "course.delete"
    assert entree.entity_type == "course"
    assert entree.entity_id == 12
    assert entree.payload["participations_deleted"] == 412
    assert entree.created_at is not None


def test_create_accepte_un_payload_absent(db_session):
    auteur = _auteur(db_session)

    entree = admin_action_log_repository.create(
        db_session,
        user_id=auteur.id,
        action="athlete.update",
        entity_type="athlete",
        entity_id=3,
    )
    db_session.flush()

    assert entree.payload is None


def test_list_for_entity_rend_la_plus_recente_d_abord(db_session):
    auteur = _auteur(db_session)
    for indice in range(3):
        admin_action_log_repository.create(
            db_session,
            user_id=auteur.id,
            action="athlete.update",
            entity_type="athlete",
            entity_id=7,
            payload={"rang": indice},
        )
    admin_action_log_repository.create(
        db_session,
        user_id=auteur.id,
        action="athlete.update",
        entity_type="athlete",
        entity_id=99,
    )
    db_session.flush()

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="athlete", entity_id=7
    )

    assert [e.payload["rang"] for e in entrees] == [2, 1, 0]


def test_list_for_entity_ne_melange_pas_deux_types(db_session):
    """Le couple (type, id) est la clé : l'épreuve 5 n'est pas le coureur 5."""
    auteur = _auteur(db_session)
    admin_action_log_repository.create(
        db_session, user_id=auteur.id, action="course.delete", entity_type="course", entity_id=5
    )
    admin_action_log_repository.create(
        db_session, user_id=auteur.id, action="athlete.update", entity_type="athlete", entity_id=5
    )
    db_session.flush()

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=5
    )

    assert [e.action for e in entrees] == ["course.delete"]


def test_une_entree_survit_a_la_disparition_de_son_entite(db_session):
    """FR-014 — sans quoi le journal ne pourrait pas tracer une suppression.

    C'est l'absence de FK sur `entity_id` qui le permet. Ce test est la seule
    chose qui empêche quelqu'un d'en ajouter une « pour bien faire ».
    """
    auteur = _auteur(db_session)
    course = Course(name="Épreuve éphémère", event_type="triathlon-m")
    db_session.add(course)
    db_session.flush()
    course_id = course.id

    admin_action_log_repository.create(
        db_session,
        user_id=auteur.id,
        action="course.delete",
        entity_type="course",
        entity_id=course_id,
        payload={"name": "Épreuve éphémère"},
    )
    db_session.delete(course)
    db_session.flush()

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course_id
    )

    assert course_repository.get(db_session, course_id) is None
    assert [e.payload["name"] for e in entrees] == ["Épreuve éphémère"]
