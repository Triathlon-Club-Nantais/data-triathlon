"""Poser, changer et lever l'avis humain sur la fiabilité (#115, FR-036, FR-039)."""
from app.models.course import Course
from app.repositories import course_repository
from app.services import course_review


def _epreuve(db_session, **colonnes) -> Course:
    course = Course(name="Épreuve", **colonnes)
    db_session.add(course)
    db_session.flush()
    return course


def test_poser_un_avis_humain(db_session):
    course = _epreuve(db_session, is_reliable_computed=False)

    course_review.set_override(db_session, course, verdict=True)

    assert course.reliability_override is True
    assert course.is_reliable is True
    assert course.is_reliable_computed is False, "le verdict machine survit"


def test_changer_d_avis(db_session):
    course = _epreuve(db_session, is_reliable_computed=True)
    course_review.set_override(db_session, course, verdict=True)

    course_review.set_override(db_session, course, verdict=False)

    assert course.reliability_override is False
    assert course.is_reliable is False


def test_lever_l_avis_fait_reprendre_le_dernier_verdict_calcule(db_session):
    """FR-039 — le **dernier**, pas celui qui valait au moment de la décision.

    Entre la décision humaine et sa levée, l'import a continué d'écrire sa
    colonne. Une implémentation qui aurait mémorisé « ce que la machine disait
    alors » restituerait un verdict périmé.
    """
    course = _epreuve(db_session, is_reliable_computed=False)
    course_review.set_override(db_session, course, verdict=True)

    course_repository.set_quality(
        db_session, course, is_reliable_computed=True, quality_issues={}
    )
    db_session.flush()
    course_review.set_override(db_session, course, verdict=None)

    assert course.reliability_override is None
    assert course.is_reliable is True


def test_lever_un_avis_absent_est_sans_effet(db_session):
    course = _epreuve(db_session, is_reliable_computed=True)

    course_review.set_override(db_session, course, verdict=None)

    assert course.reliability_override is None
    assert course.is_reliable is True


def test_le_service_ne_recalcule_rien(db_session):
    """Aucune branche, aucun recalcul — la propriété hybride fait le travail.

    C'est ce qui rend ce service tenable en trois lignes : l'intelligence est
    dans la forme du modèle, pas dans du code de synchronisation.
    """
    course = _epreuve(db_session, is_reliable_computed=None, quality_issues={"rank_gap": 3})

    course_review.set_override(db_session, course, verdict=True)

    assert course.quality_issues == {"rank_gap": 3}
    assert course.is_reliable_computed is None
