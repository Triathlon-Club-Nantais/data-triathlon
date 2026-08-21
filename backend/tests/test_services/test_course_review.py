"""Poser, changer et lever l'avis humain sur la fiabilité (#115, FR-036, FR-039)."""
from app.models.course import Course
from app.repositories import admin_action_log_repository, course_repository, user_repository
from app.services import course_review


def _epreuve(db_session, **colonnes) -> Course:
    course = Course(name="Épreuve", **colonnes)
    db_session.add(course)
    db_session.flush()
    return course


def _auteur(db_session) -> int:
    user = user_repository.create(db_session, email="validateur@exemple.fr")
    db_session.flush()
    return user.id


def test_poser_un_avis_humain(db_session):
    course = _epreuve(db_session, is_reliable_computed=False)
    auteur = _auteur(db_session)

    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    assert course.reliability_override is True
    assert course.is_reliable is True
    assert course.is_reliable_computed is False, "le verdict machine survit"


def test_changer_d_avis(db_session):
    course = _epreuve(db_session, is_reliable_computed=True)
    auteur = _auteur(db_session)
    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    course_review.set_override(db_session, course, verdict=False, user_id=auteur)

    assert course.reliability_override is False
    assert course.is_reliable is False


def test_lever_l_avis_fait_reprendre_le_dernier_verdict_calcule(db_session):
    """FR-039 — le **dernier**, pas celui qui valait au moment de la décision.

    Entre la décision humaine et sa levée, l'import a continué d'écrire sa
    colonne. Une implémentation qui aurait mémorisé « ce que la machine disait
    alors » restituerait un verdict périmé.
    """
    course = _epreuve(db_session, is_reliable_computed=False)
    auteur = _auteur(db_session)
    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    course_repository.set_quality(
        db_session, course, is_reliable_computed=True, quality_issues={}
    )
    db_session.flush()
    course_review.set_override(db_session, course, verdict=None, user_id=auteur)

    assert course.reliability_override is None
    assert course.is_reliable is True


def test_lever_un_avis_absent_est_sans_effet(db_session):
    course = _epreuve(db_session, is_reliable_computed=True)
    auteur = _auteur(db_session)

    course_review.set_override(db_session, course, verdict=None, user_id=auteur)

    assert course.reliability_override is None
    assert course.is_reliable is True


def test_le_service_ne_recalcule_rien(db_session):
    """Aucune branche, aucun recalcul — la propriété hybride fait le travail.

    C'est ce qui rend ce service tenable en trois lignes : l'intelligence est
    dans la forme du modèle, pas dans du code de synchronisation.
    """
    course = _epreuve(db_session, is_reliable_computed=None, quality_issues={"rank_gap": 3})
    auteur = _auteur(db_session)

    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    assert course.quality_issues == {"rank_gap": 3}
    assert course.is_reliable_computed is None


def test_le_verdict_est_journalise_avec_ses_notes(db_session):
    """AC3 — la décision est tracée, avec le motif que le validateur a saisi."""
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=False, quality_issues={"rank_gap": 3})

    course_review.set_override(
        db_session,
        course,
        verdict=True,
        user_id=auteur,
        notes="Trous vérifiés à la source : classement correct.",
    )

    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert len(traces) == 1
    assert traces[0].action == "course.reliability"
    assert traces[0].user_id == auteur
    assert traces[0].payload == {
        "before": None,
        "after": True,
        "computed": False,
        "notes": "Trous vérifiés à la source : classement correct.",
    }


def test_un_verdict_deja_en_place_n_ecrit_aucune_trace(db_session):
    """Une demande sans effet n'est pas un geste : un journal rempli de
    non-événements est un journal qu'on cesse de lire."""
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=False)
    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert len(traces) == 1, "le second appel ne change rien, donc ne trace rien"


def test_lever_l_avis_est_un_geste_et_se_trace(db_session):
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=False)
    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    course_review.set_override(db_session, course, verdict=None, user_id=auteur)

    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert len(traces) == 2
    assert traces[0].payload["before"] is True
    assert traces[0].payload["after"] is None


def test_lever_un_avis_absent_ne_trace_rien(db_session):
    """Rien à lever, donc rien qui change, donc rien à consigner."""
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=True)

    course_review.set_override(db_session, course, verdict=None, user_id=auteur)

    assert (
        admin_action_log_repository.list_for_entity(
            db_session, entity_type="course", entity_id=course.id
        )
        == []
    )


def test_les_notes_sont_facultatives(db_session):
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=False)

    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert traces[0].payload["notes"] is None
